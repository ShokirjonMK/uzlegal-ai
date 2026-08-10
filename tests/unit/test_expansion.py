"""So'rov kengaytmasi testlari.

Kengaytma retrieval baholashida aniqlangan real muammoni hal qiladi:
foydalanuvchi «maosh» deydi, qonunda «ish haqi» yozilgan.
"""

from __future__ import annotations

import pytest

from uzlegal.retrieval.expansion import QueryExpander, load_thesaurus, simplify

THESAURUS = {
    "maosh": ["ish haqi", "mehnatga haq toʻlash"],
    "dam olish": ["taʼtil", "mehnat taʼtili"],
    "ajrashish": ["nikohni bekor qilish"],
}


@pytest.fixture
def expander() -> QueryExpander:
    return QueryExpander(thesaurus=THESAURUS)


# --------------------------------------------------------------------------- #
# Morfologik soddalashtirish
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("word", "stem"),
    [
        ("shartnomasini", "shartnoma"),
        ("shartnomaning", "shartnoma"),
        ("moddalar", "modda"),
        ("moddalarning", "modda"),
        ("mulkka", "mulkka"),  # qo'shimcha emas
        ("uy", "uy"),  # juda qisqa — tegilmaydi
        ("yer", "yer"),
    ],
)
def test_qoshimcha_olib_tashlanadi(word: str, stem: str) -> None:
    assert simplify(word) == stem


def test_qisqa_ozak_kesilmaydi() -> None:
    """«ishga» → «ish» bo'lsa 3 harf qoladi — ma'no yo'qoladi."""
    assert simplify("ishga") == "ishga"


# --------------------------------------------------------------------------- #
# Tezaurus
# --------------------------------------------------------------------------- #


def test_sozlashuv_atamaga_boglanadi(expander: QueryExpander) -> None:
    _, added = expander.expand("Maoshni toʻlash tartibi")
    assert "ish haqi" in added


def test_ibora_kengaytmasi(expander: QueryExpander) -> None:
    _, added = expander.expand("Xodimga yiliga necha kun dam olish beriladi")
    assert "taʼtil" in added


def test_asl_sorov_saqlanadi(expander: QueryExpander) -> None:
    """Kengaytma qo'shimcha — asl so'zlar ham qonunda uchrashi mumkin."""
    query = "Maoshni toʻlash tartibi"
    expanded, _ = expander.expand(query)
    assert expanded.startswith(query)


def test_apostrof_variantlari_mos_keladi(expander: QueryExpander) -> None:
    """Foydalanuvchi ASCII apostrof yozadi, tezaurusda esa ʻ turibdi."""
    _, added = expander.expand("Ajrashish uchun nima kerak")
    assert "nikohni bekor qilish" in added


def test_allaqachon_bor_atama_qoshilmaydi(expander: QueryExpander) -> None:
    _, added = expander.expand("ish haqi va maosh")
    assert "ish haqi" not in added


def test_mos_kelmasa_sorov_ozgarmaydi(expander: QueryExpander) -> None:
    query = "Kosmik huquq"
    expanded, added = expander.expand(query)
    assert expanded == query
    assert added == []


def test_bosh_tezaurus_xato_bermaydi() -> None:
    expanded, added = QueryExpander(thesaurus={}).expand("shartnomasini bekor qilish")
    # Tezaurus bo'sh, lekin morfologik soddalashtirish baribir ishlaydi
    assert "shartnoma" in added
    assert expanded.startswith("shartnomasini")


def test_takror_atama_qoshilmaydi(expander: QueryExpander) -> None:
    _, added = expander.expand("maosh maosh maosh")
    assert added.count("ish haqi") == 1


# --------------------------------------------------------------------------- #
# Haqiqiy tezaurus fayli
# --------------------------------------------------------------------------- #


def test_loyiha_tezaurusi_oqiladi() -> None:
    thesaurus = load_thesaurus()
    assert thesaurus, "configs/retrieval/thesaurus.yaml topilishi kerak"
    assert "maosh" in thesaurus


def test_tezaurus_qiymatlari_royxat() -> None:
    for key, values in load_thesaurus().items():
        assert isinstance(values, list), f"{key}: qiymat ro'yxat bo'lishi kerak"
        assert values, f"{key}: bo'sh ro'yxat"


def test_yoq_fayl_bosh_lugat(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert load_thesaurus(tmp_path / "yoq.yaml") == {}
