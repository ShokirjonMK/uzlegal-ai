"""Miqdor ziddiyati — docs/28.

Ikki talab teng darajada muhim:

* iqtibosga **zid** son ushlansin;
* to'g'ri son **tegilmasin**.

Ikkinchisi xavfliroq. Haddan tashqari qattiq tekshiruv to'g'ri
javoblarni ham o'chiradi va buni sezish qiyin — o'chirilgan da'vo
xatoga o'xshamaydi, u shunchaki yo'q bo'ladi.
"""

from __future__ import annotations

import pytest

from uzlegal.orchestrator.gate import DropReason, groundedness_gate
from uzlegal.orchestrator.quantity import contradicts, quantities
from uzlegal.types import Citation

# --------------------------------------------------------------------------- #
# Miqdor ajratish
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("matn", "kutilgan"),
    [
        ("muddat 10 yil bo'lib", {(10, "yil")}),
        ("Umumiy da'vo muddati - uch yil.", {(3, "yil")}),
        ("o'n besh kun ichida", {(15, "kun")}),
        ("yigirma besh foiz", {(25, "foiz")}),
        ("sinov muddati uch oydan ortiq bo'lmaydi", {(3, "oy")}),
        ("o'n sakkiz yoshga to'lgan", {(18, "yosh")}),
        ("uch yil va olti oy", {(3, "yil"), (6, "oy")}),
    ],
)
def test_miqdor_ajratiladi(matn: str, kutilgan: set[tuple[int, str]]) -> None:
    assert quantities(matn) == kutilgan


@pytest.mark.parametrize(
    "matn",
    [
        # Tartib raqami — miqdor emas. Bu eng muhim istisno: modda
        # raqamlari matnda son bo'lib ko'rinadi.
        "150-modda va 163-moddalari",
        "2-qism, 3-band",
        "Kodeksning 228-moddasiga ko'ra",
        # Birligi yo'q son.
        "jami 15 ta hujjat",
        "matn hech qanday miqdorsiz",
    ],
)
def test_miqdor_emas(matn: str) -> None:
    assert quantities(matn) == set()


def test_teskari_tartib_miqdor_emas() -> None:
    """«besh o'n» — o'zbek tilida miqdor emas, tasodifiy yonma-yonlik."""
    assert (50, "kun") not in quantities("besh o'n kun")


# --------------------------------------------------------------------------- #
# Ziddiyat
# --------------------------------------------------------------------------- #


def test_haqiqiy_xato_ushlanadi() -> None:
    """2026-08-21 da o'lchangan haqiqiy holat.

    Model «10 yil» dedi, iqtibos qilingan modda esa «uch yil» deydi.
    Leksik qoplama buni ko'rmagan edi.
    """
    natija = contradicts(
        "Vindikatsiya da'vosi uchun qonuniy muddat umumiy qoidalarga mos ravishda 10 yil",
        ["Umumiy da'vo muddati - uch yil."],
    )
    assert natija == (10, 3, "yil")


def test_togri_son_tegilmaydi() -> None:
    assert contradicts("Da'vo muddati uch yil", ["Umumiy da'vo muddati - uch yil."]) is None


def test_boshqa_birlik_toqnashmaydi() -> None:
    """«uch oy» va «uch yil» boshqa-boshqa narsa."""
    assert contradicts("Sinov muddati uch oy", ["Umumiy da'vo muddati - uch yil."]) is None


def test_manbada_bir_necha_qiymat_bolsa() -> None:
    """Modda ko'pincha bir necha muddat sanaydi — javob birini keltiradi."""
    manba = ["Muddat uch yil, ayrim hollarda o'n yil bo'lishi mumkin."]
    assert contradicts("Muddat o'n yil", manba) is None
    assert contradicts("Muddat uch yil", manba) is None


def test_davoda_miqdor_yoq() -> None:
    assert contradicts("Bu 150-moddada belgilangan", ["Umumiy da'vo muddati - uch yil."]) is None


def test_manbada_miqdor_yoq_tekshirilmaydi() -> None:
    """Tekshirib bo'lmaydigan narsa jazolanmaydi — loyihaning umumiy qoidasi."""
    assert contradicts("Muddat 10 yil", ["Mulkdor talab qilishga haqli."]) is None


def test_bosh_manba_yiqilmaydi() -> None:
    assert contradicts("Muddat 10 yil", []) is None
    assert contradicts("Muddat 10 yil", ["", ""]) is None


# --------------------------------------------------------------------------- #
# Darvoza bilan birga
# --------------------------------------------------------------------------- #


def _citation(excerpt: str, article: str = "150") -> Citation:
    return Citation(
        tag="C1",
        doc_id="-111189",
        doc_title="Fuqarolik kodeksi",
        article=article,
        excerpt=excerpt,
    )


def test_darvoza_zid_miqdorni_ochiradi() -> None:
    javob = "Umumiy da'vo muddati 10 yil deb belgilangan [C1]."
    hisobot = groundedness_gate(javob, [_citation("Umumiy da'vo muddati - uch yil.")])

    assert hisobot.dropped == 1
    assert hisobot.checks[0].reason is DropReason.WRONG_QUANTITY
    assert "10 yil" not in hisobot.answer


def test_darvoza_togri_miqdorni_saqlaydi() -> None:
    javob = "Umumiy da'vo muddati uch yil deb belgilangan [C1]."
    hisobot = groundedness_gate(javob, [_citation("Umumiy da'vo muddati - uch yil.")])

    assert hisobot.dropped == 0
    assert "uch yil" in hisobot.answer


def test_miqdor_tekshiruvi_modda_tekshiruvidan_oldin() -> None:
    """Ikkalasi ham aniq tekshiruv, lekin sabab to'g'ri yozilishi kerak.

    Da'voda ham zid miqdor, ham o'ylab topilgan modda bo'lsa — miqdor
    birinchi ko'rinadi, chunki u foydalanuvchi uchun aniqroq signal.
    """
    javob = "Kodeksning 999-moddasiga ko'ra muddat 10 yil [C1]."
    hisobot = groundedness_gate(javob, [_citation("Umumiy da'vo muddati - uch yil.")])
    assert hisobot.checks[0].reason is DropReason.WRONG_QUANTITY
