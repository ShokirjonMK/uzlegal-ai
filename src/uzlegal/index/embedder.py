"""BGE-M3 embedding — ko'p tilli semantik vektorlar.

## Nima uchun BGE-M3

O'zbek tili past-resursli, shuning uchun embedding modeli tanlovi cheklangan:

| Nomzod | O'zbek | Maks. uzunlik | Verdikt |
|--------|--------|---------------|---------|
| **BGE-M3** | Yaxshi | 8192 | **Tanlangan** |
| multilingual-e5-large | O'rtacha | 512 | Yuridik modda sig'maydi |
| LaBSE | Zaif retrieval | 256 | Bitext uchun mo'ljallangan |

8192 token muhim: yuridik modda 1300 tokengacha yetadi, 512 limitli model
uni kesib tashlaydi va ma'noning bir qismini yo'qotadi.

## Normallashtirish

Matn embeddingdan **oldin** `fold()` dan o'tkazilmaydi — semantik model
tabiiy matn bilan yaxshiroq ishlaydi. `fold()` faqat BM25 uchun.
Lekin apostrof kanonizatsiyasi (`canonical`) parsing bosqichida qilingan,
shuning uchun matn izchil.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from numpy.typing import NDArray

log = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
MAX_LENGTH = 8192

# Belgidan tokenga taxminiy nisbat (o'zbek + rus yuridik matni uchun
# `estimate_tokens` bilan bir xil). Aniq bo'lishi shart emas — bu faqat
# xotira byudjetini hisoblash uchun.
CHARS_PER_TOKEN = 3

# Attention matritsasi byudjeti: `batch × seq²` shu sondan oshmasin.
#
# NEGA `seq²`, `seq` EMAS. BGE-M3 (XLM-RoBERTa) oddiy attention
# ishlatadi — xotira uzunlikning KVADRATIGA proporsional. 5 500 tokenli
# bo'lak bitta o'zi ~2 GB attention buferi talab qiladi, 1 100 tokenli
# esa 25 barobar kam. Shuning uchun «16 ta bo'lak» degan chegara ma'nosiz:
# u qisqa bo'laklar uchun juda ehtiyotkor, uzunlari uchun esa halokatli.
#
# Qiymat o'lchovdan olingan (RTX 4060, 8 GB): haqiqiy korpus bo'laklarida
# `batch=4` (4 × 5504² ≈ 121 mln) 33 700 belgi/s bergan, `batch=16`
# (485 mln) esa 2 292 belgi/s — 15 BAROBAR sekin, chunki VRAM to'lib
# PCIe orqali tizim xotirasiga to'kilgan. Chegara ikkalasining orasida.
ATTENTION_BUDGET_PER_GB = 30_000_000


class Embedder:
    """BGE-M3 o'ramchisi.

    Model birinchi ishlatilganda yuklanadi (lazy) — CLI ning boshqa
    buyruqlari 2.2 GB modelni kutib turmasligi uchun.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL,
        device: str | None = None,
        batch_size: int = 8,
    ) -> None:
        self.model_id = model_id
        # `batch_size` — YUQORI CHEGARA, aniq qiymat emas. Haqiqiy hajm
        # har chaqiruvda matn uzunligiga qarab hisoblanadi (`_batch_for`).
        # Sabab: foydalanuvchi bergan son uzun bo'laklar uchun 15 barobar
        # sekinlashtirishi mumkin, va buni oldindan bilish imkonsiz.
        self.batch_size = batch_size
        self._device = device
        self._model: Any = None
        self._budget: float | None = None

    @property
    def device(self) -> str:
        """Hisoblash qurilmasi: `mps` · `cpu` · `cuda`.

        `UZLEGAL_EMBED_DEVICE` bilan majburlash mumkin. Bu zaxira yo'l
        emas, amaliy ehtiyoj: Metal kontekstini boshqa jarayon band
        qilib qo'yganda (masalan bir vaqtda ikkita indeks qurilsa) MPS
        cheksiz kutib qoladi va jarayon qotadi. Bunday holatda CPU ga
        o'tish indeksni qayta qurish imkonini beradi.
        """
        if self._device is None:
            import os

            forced = os.getenv("UZLEGAL_EMBED_DEVICE")
            if forced:
                self._device = forced
            else:
                self._device = best_device()
        return self._device

    def load(self) -> None:
        """Modelni yuklaydi. GPU da yarim aniqlikda (fp16).

        ## Nima uchun fp16

        O'lchangan (RTX 4060, haqiqiy korpus bo'laklari):

        | Aniqlik | Tezlik | Cho'qqi xotira |
        |---------|--------|----------------|
        | fp32 | 36 224 belgi/s | 3.00 GB |
        | **fp16** | **123 819 belgi/s** | **1.53 GB** |

        3.4 barobar tez va xotira ikki barobar kam. Sifat esa amalda
        o'zgarmaydi: fp32 va fp16 vektorlari orasidagi eng past kosinus
        o'xshashlik **0.99975**. Reyting uchun bu farq sezilmaydi —
        qo'shni natijalar orasidagi tafovut undan yuz barobar katta.

        Xotiraning kamayishi bu mashinada alohida muhim: 8 GB VRAM
        `ollama` bilan bo'lishiladi va fp32 da ikkalasi bir vaqtda
        sig'maydi.

        CPU da fp16 QO'LLANMAYDI — u yerda yarim aniqlik apparatda
        tezlashtirilmaydi va aksincha sekinlashtiradi.
        """
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        kwargs: dict[str, Any] = {}
        if self.device == "cuda":
            import torch

            kwargs["model_kwargs"] = {"torch_dtype": torch.float16}

        log.info(
            "Embedding modeli yuklanmoqda: %s (%s, %s)",
            self.model_id,
            self.device,
            "fp16" if kwargs else "fp32",
        )
        self._model = SentenceTransformer(self.model_id, device=self.device, **kwargs)
        self._model.max_seq_length = MAX_LENGTH

    def _memory_budget(self) -> float:
        """Attention uchun ajratilgan byudjet (`batch × seq²` birligida).

        GPU da bo'sh VRAM o'lchanadi — model yuklangandan KEYIN, chunki
        modelning o'zi 2.3 GB oladi va uni byudjetga kiritish xato
        bo'lardi. CPU da chegara xotira emas, vaqt: u yerda baribir
        sekin, katta batch foyda bermaydi.
        """
        if self._budget is not None:
            return self._budget

        free_gb = 4.0  # cpu/mps uchun ehtiyotkor taxmin
        headroom = 1.0
        if self.device == "cuda":
            try:
                import torch

                free_bytes, _ = torch.cuda.mem_get_info()
                # 20% zaxira: fragmentatsiya va boshqa jarayonlar uchun.
                free_gb = (free_bytes / 1024**3) * 0.8
                # fp16 da har element ikki barobar kam joy egallaydi,
                # demak shu xotiraga ikki barobar ko'p sig'adi.
                headroom = 2.0
            except Exception as exc:  # pragma: no cover — apparatga bog'liq
                log.debug("VRAM o'lchanmadi (%s) — ehtiyotkor byudjet", exc)

        self._budget = max(1.0, free_gb) * ATTENTION_BUDGET_PER_GB * headroom
        return self._budget

    def _batch_for(self, texts: list[str]) -> int:
        """Shu matnlar uchun xavfsiz batch hajmi.

        `sentence-transformers` matnlarni uzunligi bo'yicha saralaydi,
        shuning uchun eng og'ir batch — eng uzun matnlarniki. Hisob aynan
        o'shanga qarab yuritiladi: qolganlari avtomatik sig'adi.
        """
        if not texts:
            return self.batch_size

        longest_tokens = max(len(t) for t in texts) / CHARS_PER_TOKEN
        if longest_tokens < 1:
            return self.batch_size

        fits = int(self._memory_budget() / (longest_tokens**2))
        return max(1, min(self.batch_size, fits))

    def encode(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
        show_progress: bool = False,
    ) -> NDArray[Any]:
        """Matnlarni vektorga o'giradi.

        `is_query` — BGE-M3 uchun so'rov va hujjat bir xil kodlanadi
        (prefiks talab qilinmaydi), lekin parametr saqlanadi: boshqa
        embedding modeliga o'tilsa u yerda prefiks kerak bo'lishi mumkin.

        ## Nima uchun batch bitta emas

        Bitta `batch_size` butun korpusga yaramaydi. Korpusda uzunlik
        farqi 40 barobar (median 1 100 belgi, eng uzuni 15 000), xotira
        esa uzunlikning kvadratiga o'sadi — ya'ni farq 1 600 barobar.
        Eng uzuniga qarab tanlangan batch qisqalarini behuda sekin
        kodlaydi, o'rtachaga qarab tanlangani esa uzunlarida VRAM ni
        to'ldirib, ishni PCIe ga tushiradi va 15 barobar sekinlashtiradi.

        Yechim: matnlar uzunligi bo'yicha saralanadi va har bir guruh
        O'Z batch hajmi bilan kodlanadi. Natija asl tartibda qaytariladi.
        """
        self.load()
        if not texts:
            import numpy as np

            return np.zeros((0, EMBEDDING_DIM), dtype="float32")

        import numpy as np

        # Uzundan qisqaga: og'ir guruhlar oldin: xotira yetishmasa
        # bu haqda ishning oxirida emas, boshida bilgan yaxshi.
        order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
        vectors = np.zeros((len(texts), EMBEDDING_DIM), dtype="float32")

        bar = None
        if show_progress:
            try:
                from tqdm import tqdm

                # Hisob BO'LAKLARDA emas, BELGILARDA yuritiladi.
                #
                # Bo'laklar uzundan qisqaga saralangani uchun bo'laklar
                # soni bo'yicha qolgan vaqt qo'pol yolg'on chiqaradi:
                # amalda birinchi daqiqada «12 soat» deb ko'rsatgan,
                # aslida butun ish 15 daqiqa olgan. Belgilar bo'yicha
                # baho ancha halol, chunki vaqt matn hajmiga bog'liq.
                bar = tqdm(
                    total=sum(len(t) for t in texts),
                    unit="belgi",
                    unit_scale=True,
                    desc="Vektorlar",
                )
            except ImportError:  # pragma: no cover
                bar = None

        try:
            pos = 0
            while pos < len(order):
                # Guruhdagi eng uzuni — saralangani uchun birinchisi.
                batch = self._batch_for([texts[order[pos]]])
                part = order[pos : pos + batch]
                encoded = self._model.encode(
                    [texts[i] for i in part],
                    batch_size=batch,
                    normalize_embeddings=True,  # kosinus = skalyar ko'paytma
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                vectors[part] = encoded
                pos += len(part)
                if bar is not None:
                    bar.update(sum(len(texts[i]) for i in part))
        finally:
            if bar is not None:
                bar.close()

        return vectors

    def encode_one(self, text: str, *, is_query: bool = False) -> NDArray[Any]:
        vector: NDArray[Any] = self.encode([text], is_query=is_query)[0]
        return vector

    def unload(self) -> None:
        self._model = None


def best_device() -> str:
    """Mavjud eng tez qurilma: `cuda` → `mps` → `cpu`.

    NEGA `cuda` BIRINCHI. Ilgari faqat `mps` tekshirilardi va NVIDIA
    kartali mashinada embedder jimgina `cpu` da ishlardi — 8 000 bo'lakni
    kodlash o'nlab daqiqa olardi, holbuki GPU bir necha daqiqada bajaradi.
    Izohda uchala qurilma sanalgan edi, lekin `cuda` hech qachon
    tanlanmasdi.

    `torch` o'rnatilmagan bo'lsa `cpu` qaytariladi: bu funksiya hech
    qachon yiqilmasligi kerak — u faqat maslahat beradi.
    """
    try:
        import torch
    except ImportError:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
