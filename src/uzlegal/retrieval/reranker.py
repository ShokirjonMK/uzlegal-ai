"""Cross-encoder reranker — retrieval sifatining oxirgi bosqichi.

## Nima uchun kerak

Vektor qidiruvi so'rov va hujjatni **alohida** kodlaydi (bi-encoder). Bu tez
— hujjat vektorlari oldindan hisoblanadi — lekin so'rov bilan hujjat
o'rtasidagi nozik bog'liqlikni ko'rmaydi.

Cross-encoder ikkalasini **birga** o'qiydi va ancha aniqroq ball beradi.
Buning narxi: har juftlik uchun alohida hisob, ya'ni butun korpusni
rerank qilib bo'lmaydi.

Shuning uchun ikki bosqich:

    50 nomzod  →  gibrid qidiruv (tez, taxminiy)
     8 natija  →  cross-encoder (sekin, aniq)

## Yuridik matnda nima uchun ayniqsa muhim

Bi-encoder «mehnat shartnomasini bekor qilish» va «mehnat shartnomasini
tuzish» ni juda o'xshash deb topadi — ikkalasi ham mehnat shartnomasi
haqida. Cross-encoder esa **bekor qilish** va **tuzish** qarama-qarshi
ekanini payqaydi.

Yuridik savolda bu farq hal qiluvchi.

## Xarajat

Reranker ixtiyoriy (`enabled=False` bilan o'chiriladi). M4 da 8 juftlik
uchun ~1–2 s qo'shadi. Kechikish muhim bo'lgan `simple` rejimda
o'tkazib yuborilishi mumkin.
"""

from __future__ import annotations

import logging
from typing import Any

from uzlegal.index.store import ScoredChunk

log = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"


class Reranker:
    """Cross-encoder qayta tartiblash.

    Model birinchi ishlatilganda yuklanadi — indekslash va boshqa
    buyruqlar uni kutmasligi uchun.
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
        from sentence_transformers import CrossEncoder

        log.info("Reranker yuklanmoqda: %s (%s)", self.model_id, self.device)
        self._model = CrossEncoder(self.model_id, device=self.device, max_length=1024)

    def rerank(
        self, query: str, results: list[ScoredChunk], top_k: int | None = None
    ) -> list[ScoredChunk]:
        """Natijalarni cross-encoder ballari bo'yicha qayta tartiblaydi.

        Chunk **matni sarlavha bilan birga** beriladi: modda raqami va
        hujjat nomi ham relevantlikka ta'sir qiladi.
        """
        if not results:
            return []

        self.load()
        pairs = [(query, item.chunk.indexed_text) for item in results]
        scores = self._model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)

        reranked = [
            ScoredChunk(chunk=item.chunk, score=float(score), source="rerank")
            for item, score in zip(results, scores, strict=True)
        ]
        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked[:top_k] if top_k else reranked

    def unload(self) -> None:
        self._model = None
