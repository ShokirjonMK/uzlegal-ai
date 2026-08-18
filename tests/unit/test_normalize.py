"""O'zbek matnini normallashtirish testlari.

Bu qatlam butun quvurning poydevori: apostrof noto'g'ri normallashtirilsa
BM25 qidiruvi ishlamaydi va iqtiboslar mos kelmaydi.
"""

from __future__ import annotations

import pytest

from uzlegal.ingest.normalize import (
    canonical,
    cyrillic_ratio,
    extract_article_number,
    extract_date,
    fold,
    has_cyrillic,
    looks_russian,
    to_latin,
)

# --------------------------------------------------------------------------- #
# Apostroflar — asosiy muammo
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "variant",
    ["o'zgartirish", "oʻzgartirish", "o‘zgartirish", "o’zgartirish", "o`zgartirish"],
)
def test_apostrof_variantlari_bir_xil_foldga_tushadi(variant: str) -> None:
    """Beshta yozuv varianti qidiruvda bitta kalitga tushishi shart."""
    assert fold(variant) == "o'zgartirish"


def test_canonical_rasmiy_apostrofni_qoyadi() -> None:
    assert canonical("o'zgartirish") == "oʻzgartirish"
    assert canonical("g'alaba") == "gʻalaba"


def test_tutuq_belgisi_alohida() -> None:
    """oʻ/gʻ dan boshqa joyda tutuq belgisi (ʼ) ishlatiladi."""
    out = canonical("ma'no")
    assert out == "maʼno"
    assert "ʻ" not in out


def test_fold_katta_kichik_harfni_tenglaydi() -> None:
    assert fold("Oʻzbekiston") == fold("o'zbekiston")


# --------------------------------------------------------------------------- #
# Kirill → lotin
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("cyrillic", "latin"),
    [
        ("модда", "modda"),
        ("ҳуқуқ", "huquq"),
        ("ўзгартириш", "oʻzgartirish"),
        ("ғалаба", "gʻalaba"),
        ("шартнома", "shartnoma"),
        ("қонун", "qonun"),
        ("чегара", "chegara"),
        ("жавобгарлик", "javobgarlik"),
    ],
)
def test_transliteratsiya(cyrillic: str, latin: str) -> None:
    assert to_latin(cyrillic) == latin


def test_kirill_aniqlash() -> None:
    assert has_cyrillic("модда")
    assert not has_cyrillic("modda")
    assert cyrillic_ratio("модда") == 1.0
    assert cyrillic_ratio("abc") == 0.0


def test_canonical_transliteratsiya_bilan() -> None:
    assert canonical("ўзгартириш киритилди", transliterate=True) == "oʻzgartirish kiritildi"


def test_transliteratsiyasiz_kirill_saqlanadi() -> None:
    assert canonical("модда") == "модда"


# --------------------------------------------------------------------------- #
# Rus tilini ajratish — transliteratsiya qilmaslik uchun
# --------------------------------------------------------------------------- #


def test_rus_tili_aniqlanadi() -> None:
    ru = (
        "Гражданское законодательство определяет правовое положение участников, "
        "если это предусмотрено настоящим Кодексом, в соответствии со статьей 5."
    )
    assert looks_russian(ru)


def test_ozbek_kirill_rus_deb_belgilanmaydi() -> None:
    uz = "Фуқаролик қонунчилиги мулкдорларнинг ҳуқуқларини белгилайди ва ҳимоя қилади."
    assert not looks_russian(uz)


def test_lotin_matn_rus_emas() -> None:
    assert not looks_russian("Mehnat shartnomasi bekor qilinadi")


def test_rus_matni_transliteratsiya_qilinmaydi() -> None:
    """Rus matnini o'zbek qoidalari bilan o'girish ma'nosiz natija beradi."""
    ru = "Гражданское законодательство, если это предусмотрено настоящим Кодексом, статья 5"
    assert canonical(ru, transliterate=True) == canonical(ru)


# --------------------------------------------------------------------------- #
# Modda raqamlari
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("234-modda", "234"),
        ("234 modda", "234"),
        ("234-модда", "234"),
        ("Статья 234", "234"),
        ("Статья 234. Основные начала", "234"),
        ("статьи 53 внесены", "53"),
        ("234-1-modda", "234-1"),
        ("Umumiy qoidalar", None),
        # Prim moddada tire OLDIDAN bo'sh joy bo'lishi mumkin. Ilgari
        # bunday sarlavhadan butun raqam emas, oxirgi bo'lagi ajralardi
        # va 244-3-modda «3-modda» deb iqtibos qilinardi (docs/23 § 2.2.2).
        ("244 -3 -modda. Diniy mazmundagi materiallar", "244-3"),
        ("56 -2-modda. Giyohvandlik vositalari", "56-2"),
        ("24 -5 -modda. Qishloq xo'jaligi yeri", "24-5"),
        # Ikki tomonida ham bo'sh joy bo'lgan tire — diapazon
        # ajratuvchisi, prim qo'shimchasi emas. Bu farq saqlanishi shart,
        # aks holda «24 — 35-moddalari» dan «24-35» degan mavjud bo'lmagan
        # modda chiqardi.
        ("24 — 35-moddalari", "35"),
        ("173-1 - 173-7-moddalar", "173-7"),
        ("65 va 66-moddalar", "66"),
    ],
)
def test_modda_raqami(text: str, expected: str | None) -> None:
    assert extract_article_number(text) == expected


# --------------------------------------------------------------------------- #
# Sanalar
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("15.03.2024", "2024-03-15"),
        ("2024-03-15", "2024-03-15"),
        ("2024-yil 15-mart", "2024-03-15"),
        ("1995 йил 21 декабр", "1995-12-21"),
        # lex.uz o'zgartirish eslatmalaridagi rus qaratqich kelishigi
        ("Законом от 25 декабря 2025 года № ЗРУ-110", "2025-12-25"),
        ("от 3 марта 2021 г.", "2021-03-03"),
        ("sanasiz matn", None),
    ],
)
def test_sana_ajratish(text: str, expected: str | None) -> None:
    assert extract_date(text) == expected


# --------------------------------------------------------------------------- #
# Bo'sh joy va tire
# --------------------------------------------------------------------------- #


def test_bosh_joylar_tartibga_solinadi() -> None:
    assert canonical("bir   ikki\t\tuch") == "bir ikki uch"


def test_nonbreaking_space() -> None:
    assert canonical("bir ikki") == "bir ikki"


def test_tirelar_birlashtiriladi() -> None:
    assert canonical("2020—2024") == "2020-2024"


def test_qatorlar_tozalanadi() -> None:
    assert canonical("bir\n\n\n\nikki") == "bir\n\nikki"


def test_bosh_matn() -> None:
    assert canonical("") == ""
    assert fold("") == ""
