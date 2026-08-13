"""Batch hajmini avtomatik tanlash testlari.

Bu testlar bitta aniq nosozlikni qo'riqlaydi: haqiqiy korpusda
`--batch-size 16` indeks qurishni **15 barobar** sekinlashtirgan
(2 292 belgi/s, `batch=4` da esa 33 703). Sabab — uzun bo'laklarning
attention buferi 8 GB VRAM ga sig'may, PCIe orqali tizim xotirasiga
to'kilgan.

Muhimi: bu sekinlik **xato bermaydi**. Jarayon ishlayotgandek
ko'rinadi, GPU 100% band, lekin natija soatlab kutiladi. Shuning uchun
uni testda ushlash kerak — ishlatishda sezilmaydi.
"""

from __future__ import annotations

from typing import Any

import pytest

from uzlegal.index.embedder import ATTENTION_BUDGET_PER_GB, CHARS_PER_TOKEN, Embedder


def _embedder(*, batch_size: int = 8, free_gb: float = 5.5) -> Embedder:
    """Apparatsiz embedder: byudjet qo'lda o'rnatiladi."""
    embedder = Embedder(batch_size=batch_size, device="cpu")
    embedder._budget = free_gb * ATTENTION_BUDGET_PER_GB
    return embedder


def _text(tokens: int) -> str:
    return "x" * (tokens * CHARS_PER_TOKEN)


# --------------------------------------------------------------------------- #
# Asosiy xatti-harakat
# --------------------------------------------------------------------------- #


def test_qisqa_boklaklar_uchun_chegara_saqlanadi() -> None:
    """Oddiy uzunlikda foydalanuvchi bergan qiymat o'zgarmaydi."""
    assert _embedder(batch_size=8)._batch_for([_text(370)] * 100) == 8


def test_uzun_boklaklar_batchni_kamaytiradi() -> None:
    """15 000 belgili bo'lak — indeksni qotirgan aynan shu holat."""
    batch = _embedder(batch_size=16)._batch_for([_text(5010)] * 100)
    assert batch < 16
    assert batch >= 2  # butunlay 1 ga tushib ketmasin — bu ham sekin


def test_bitta_uzun_boklak_hammasini_sekinlashtirmaydi() -> None:
    """Korpusda bitta ulkan bo'lak bo'lsa ham batch 1 ga tushmasin.

    `sentence-transformers` matnlarni uzunligi bo'yicha saralaydi, lekin
    batch hajmi bitta — shuning uchun hisob eng uzuniga qarab yuritiladi.
    Chegara qat'iy: aks holda 48 000 qisqa bo'lak bitta-bittalab
    kodlanardi.
    """
    corpus = [_text(370)] * 1000 + [_text(5010)]
    assert _embedder(batch_size=8)._batch_for(corpus) >= 4


def test_juda_uzun_boklak_ham_kodlanadi() -> None:
    """Modelning to'liq oynasi (8192 token) — batch 1 bo'lsa ham ishlasin."""
    assert _embedder(batch_size=8)._batch_for([_text(8192)]) >= 1


def test_batch_hech_qachon_nolga_tushmaydi() -> None:
    """Byudjet juda kichik bo'lsa ham `encode` yiqilmasligi kerak."""
    embedder = _embedder(batch_size=8, free_gb=0.01)
    assert embedder._batch_for([_text(8192)]) == 1


# --------------------------------------------------------------------------- #
# Chegaraviy holatlar
# --------------------------------------------------------------------------- #


def test_bosh_royxat_yiqilmaydi() -> None:
    assert _embedder()._batch_for([]) == 8


def test_bosh_matn_yiqilmaydi() -> None:
    """Nolga bo'lish xavfi: uzunlik 0 bo'lsa `seq²` ham 0."""
    assert _embedder()._batch_for(["", ""]) == 8


def test_kop_vram_kop_batch_beradi() -> None:
    """Kattaroq karta — kattaroq batch. Aks holda hisob ma'nosiz."""
    texts = [_text(5010)] * 10
    kichik = _embedder(batch_size=64, free_gb=5.5)._batch_for(texts)
    katta = _embedder(batch_size=64, free_gb=40.0)._batch_for(texts)
    assert katta > kichik


@pytest.mark.parametrize("tokens", [100, 500, 1000, 2000, 4000, 8192])
def test_batch_uzunlik_bilan_kamayadi(tokens: int) -> None:
    """Monotonlik: uzunroq matn hech qachon KATTAROQ batch olmasin."""
    embedder = _embedder(batch_size=64)
    kichik = embedder._batch_for([_text(tokens)])
    katta = embedder._batch_for([_text(tokens * 2)])
    assert katta <= kichik


# --------------------------------------------------------------------------- #
# Tartib — guruhlashning eng jiddiy xavfi
# --------------------------------------------------------------------------- #


class _FakeModel:
    """Har matnni uning uzunligidan kelib chiqqan vektorga o'giradi.

    Shu tufayli qaytgan vektorga qarab qaysi matn kodlanganini aniq
    bilish mumkin — tartib buzilsa test darhol ko'radi.
    """

    def __init__(self) -> None:
        self.batches: list[int] = []

    def encode(self, texts: list[str], *, batch_size: int, **_: object) -> Any:
        import numpy as np

        self.batches.append(batch_size)
        out = np.zeros((len(texts), 1024), dtype="float32")
        for row, text in enumerate(texts):
            out[row, 0] = float(len(text))
        return out


def _with_fake(embedder: Embedder) -> _FakeModel:
    model = _FakeModel()
    embedder._model = model
    return model


def test_natija_asl_tartibda_qaytadi() -> None:
    """Guruhlash matnlarni saralaydi — natija qayta tiklanishi SHART.

    Aks holda har bo'lak boshqa hujjatning vektorini olardi va butun
    qidiruv jimgina noto'g'ri ishlardi. Bu eng xavfli nosozlik turi:
    xato bermaydi, shunchaki noto'g'ri javob beradi.
    """
    embedder = _embedder(batch_size=4)
    _with_fake(embedder)

    texts = [_text(t) for t in (100, 5000, 300, 8000, 50, 1200, 2500)]
    vectors = embedder.encode(texts)

    assert len(vectors) == len(texts)
    for index, text in enumerate(texts):
        assert vectors[index][0] == pytest.approx(len(text)), f"{index}-o'rin adashdi"


def test_takrorlangan_matnlar_ham_togri_joylashadi() -> None:
    """Bir xil uzunlikdagi matnlar saralashda o'rin almashmasin."""
    embedder = _embedder(batch_size=3)
    _with_fake(embedder)

    texts = [_text(500)] * 10 + [_text(4000)] * 5
    vectors = embedder.encode(texts)
    assert all(v[0] == pytest.approx(1500.0) for v in vectors[:10])
    assert all(v[0] == pytest.approx(12000.0) for v in vectors[10:])


def test_uzun_va_qisqa_har_xil_batch_oladi() -> None:
    """Guruhlashning butun maqsadi shu — bitta batch hammaga emas."""
    embedder = _embedder(batch_size=32)
    model = _with_fake(embedder)

    embedder.encode([_text(6000)] * 4 + [_text(200)] * 200)

    assert min(model.batches) < max(model.batches), "guruhlash ishlamadi"


def test_bosh_royxat_bosh_natija_beradi() -> None:
    embedder = _embedder()
    _with_fake(embedder)
    assert embedder.encode([]).shape == (0, 1024)
