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
        self.batch_size = batch_size
        self._device = device
        self._model: Any = None

    @property
    def device(self) -> str:
        if self._device is None:
            import torch

            self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        return self._device

    def load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        log.info("Embedding modeli yuklanmoqda: %s (%s)", self.model_id, self.device)
        self._model = SentenceTransformer(self.model_id, device=self.device)
        self._model.max_seq_length = MAX_LENGTH

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
        """
        self.load()
        return self._model.encode(  # type: ignore[no-any-return]
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,  # kosinus = skalyar ko'paytma
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )

    def encode_one(self, text: str, *, is_query: bool = False) -> NDArray[Any]:
        return self.encode([text], is_query=is_query)[0]

    def unload(self) -> None:
        self._model = None
