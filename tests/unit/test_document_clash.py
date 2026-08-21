"""Hujjat ziddiyati — docs/28.

Tekshiruv **ataylab tor**: u faqat da'vo kodeks nomini AYTGANDA
ishlaydi. Modelning ko'p javobida nom umuman aytilmaydi va u holda
tekshirib bo'lmaydi.

Shuning uchun testlarning yarmi «tegilmasin» talabini qo'riqlaydi.
"""

from __future__ import annotations

import pytest

from uzlegal.orchestrator.document import contradicts
from uzlegal.orchestrator.gate import DropReason, groundedness_gate
from uzlegal.types import Citation


def _cit(doc_title: str, tag: str = "C1", article: str = "23") -> Citation:
    return Citation(
        tag=tag,
        doc_id="d-1",
        doc_title=doc_title,
        article=article,
        excerpt="Er va xotinning nikoh davomida orttirgan mol-mulklari.",
    )


OILA = "OʻZBEKISTON RESPUBLIKASINING OILA KODEKSI"
FUQARO = "OʻZBEKISTON RESPUBLIKASINING FUQAROLIK KODEKSI"


# --------------------------------------------------------------------------- #
# Ziddiyat aniqlanadi
# --------------------------------------------------------------------------- #


def test_boshqa_kodeks_nomlanganda() -> None:
    """2026-08-21 da o'lchangan xato turi.

    Model ajrashish savoliga Fuqarolik kodeksini ko'rsatgan edi.
    """
    natija = contradicts("Fuqarolik kodeksiga ko'ra mol-mulk teng bo'linadi", [_cit(OILA)])
    assert natija is not None
    assert "fuqarolik" in natija[0]


def test_darvoza_ochiradi() -> None:
    javob = "Fuqarolik kodeksiga ko'ra mol-mulk teng bo'linadi [C1]."
    hisobot = groundedness_gate(javob, [_cit(OILA)])
    assert hisobot.dropped == 1
    assert hisobot.checks[0].reason is DropReason.WRONG_DOCUMENT


# --------------------------------------------------------------------------- #
# Tegilmasligi kerak — xavfliroq tomon
# --------------------------------------------------------------------------- #


def test_togri_kodeks_tegilmaydi() -> None:
    assert contradicts("Oila kodeksiga ko'ra mol-mulk teng bo'linadi", [_cit(OILA)]) is None


def test_nom_aytilmasa_tekshirilmaydi() -> None:
    """Modelning ko'p javobida kodeks nomi umuman aytilmaydi."""
    assert contradicts("Mol-mulk teng qismlarga bo'linadi", [_cit(OILA)]) is None


@pytest.mark.parametrize(
    "matn",
    [
        "ushbu kodeksning 23-moddasiga ko'ra",
        "mazkur kodeks talablari bo'yicha",
        "shu kodeksda belgilangan tartibda",
    ],
)
def test_ishora_nom_emas(matn: str) -> None:
    """«ushbu kodeks» — nom emas, ishora. U tekshiruvni ishga tushirmaydi."""
    assert contradicts(matn, [_cit(OILA)]) is None


def test_bir_nechta_iqtibosdan_bittasi_mos_kelsa_yetarli() -> None:
    """Da'vo bir necha manbaga tayanishi mumkin."""
    natija = contradicts(
        "Fuqarolik kodeksiga ko'ra bu majburiyat hisoblanadi",
        [_cit(OILA), _cit(FUQARO, tag="C2", article="225")],
    )
    assert natija is None


def test_sarlavhasiz_iqtibos_tekshirilmaydi() -> None:
    citation = Citation(tag="C1", doc_id="d-1", article="23", excerpt="matn")
    assert contradicts("Oila kodeksiga ko'ra", [citation]) is None


def test_yordamchi_sozlar_nomga_kirmaydi() -> None:
    """«amaldagi Mehnat kodeksi» → «mehnat», «amaldagi» emas."""
    natija = contradicts("amaldagi Mehnat kodeksiga ko'ra", [_cit("Mehnat kodeksi")])
    assert natija is None


def test_kirill_lotin_farqi_toqnashuv_yasamaydi() -> None:
    """`fold()` apostrof va yozuv farqini yo'q qiladi."""
    assert contradicts("Oila kodeksiga koʻra", [_cit(OILA)]) is None
