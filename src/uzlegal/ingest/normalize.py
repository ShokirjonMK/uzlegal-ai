"""O'zbek yuridik matnini normallashtirish.

Bu modul butun ma'lumot quvurining poydevori. Agar normalizatsiya noto'g'ri
bo'lsa, BM25 qidiruvi ishlamaydi va iqtiboslar mos kelmaydi.

## Nima uchun bu jiddiy muammo

O'zbek lotin yozuvida apostrof to'rt xil belgi bilan yoziladi:

    o'zgartirish   (U+0027 ASCII apostrophe)
    oʻzgartirish   (U+02BB modifier letter turned comma)  ← rasmiy
    o‘zgartirish   (U+2018 left single quote)
    o’zgartirish   (U+2019 right single quote)            ← Word avtomatik qo'yadi

Bular kompyuter uchun **to'rt xil so'z**. Normalizatsiyasiz `oʻzgartirish`
so'rovi `o'zgartirish` matnini topmaydi.

Bunga qo'shimcha, lex.uz hujjatlari kirill va lotin yozuvida aralash keladi.

## Ikki shakl

`canonical()` — saqlash uchun: rasmiy imlo (oʻ, gʻ, ʼ)
`fold()`      — qidiruv/taqqoslash uchun: hamma narsa sodda ASCII ga
"""

from __future__ import annotations

import re
import unicodedata

# --------------------------------------------------------------------------- #
# Apostroflar
# --------------------------------------------------------------------------- #

# Rasmiy: oʻ/gʻ da U+02BB, tutuq belgisi uchun U+02BC
TURNED_COMMA = "ʻ"  # ʻ — oʻ, gʻ
MODIFIER_APOS = "ʼ"  # ʼ — tutuq belgisi (maʼno)

_APOSTROPHE_VARIANTS = "'‘’ʻʼ`´′"
_APOS_CLASS = f"[{re.escape(_APOSTROPHE_VARIANTS)}]"

# --------------------------------------------------------------------------- #
# Kirill → lotin (o'zbek alifbosi)
# --------------------------------------------------------------------------- #

_CYR_MULTI: list[tuple[str, str]] = [
    ("ьо", "yo"),
    ("Ў", "O" + TURNED_COMMA), ("ў", "o" + TURNED_COMMA),
    ("Ғ", "G" + TURNED_COMMA), ("ғ", "g" + TURNED_COMMA),
    ("Щ", "Shch"), ("щ", "shch"),
    ("Ч", "Ch"), ("ч", "ch"),
    ("Ш", "Sh"), ("ш", "sh"),
    ("Ё", "Yo"), ("ё", "yo"),
    ("Ю", "Yu"), ("ю", "yu"),
    ("Я", "Ya"), ("я", "ya"),
    ("Ц", "Ts"), ("ц", "ts"),
]

_CYR_SINGLE: dict[str, str] = {
    "А": "A", "а": "a", "Б": "B", "б": "b", "В": "V", "в": "v",
    "Г": "G", "г": "g", "Д": "D", "д": "d", "Е": "E", "е": "e",
    "Ж": "J", "ж": "j", "З": "Z", "з": "z", "И": "I", "и": "i",
    "Й": "Y", "й": "y", "К": "K", "к": "k", "Қ": "Q", "қ": "q",
    "Л": "L", "л": "l", "М": "M", "м": "m", "Н": "N", "н": "n",
    "О": "O", "о": "o", "П": "P", "п": "p", "Р": "R", "р": "r",
    "С": "S", "с": "s", "Т": "T", "т": "t", "У": "U", "у": "u",
    "Ф": "F", "ф": "f", "Х": "X", "х": "x", "Ҳ": "H", "ҳ": "h",
    "Ъ": MODIFIER_APOS, "ъ": MODIFIER_APOS,
    "Ь": "", "ь": "",
    "Э": "E", "э": "e",
    "Ы": "I", "ы": "i",
}

CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def has_cyrillic(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text))


def cyrillic_ratio(text: str) -> float:
    if not text:
        return 0.0
    return len(CYRILLIC_RE.findall(text)) / len(text)


def to_latin(text: str) -> str:
    """O'zbek kirill yozuvini lotin yozuviga o'giradi.

    Diqqat: bu **o'zbek** transliteratsiyasi, rus tili uchun emas. Rus tilidagi
    matnda ishlatilsa natija ma'nosiz bo'ladi — shuning uchun chaqirishdan
    oldin til aniqlanishi kerak (`looks_russian()`).
    """
    for src, dst in _CYR_MULTI:
        text = text.replace(src, dst)
    return "".join(_CYR_SINGLE.get(ch, ch) for ch in text)


# Rus tiliga xos, o'zbek kirillida uchramaydigan belgilar va so'zlar
_RUSSIAN_ONLY_CHARS = set("ЫЬЭыьэ")
_RUSSIAN_WORDS = re.compile(
    r"\b(что|это|который|которая|также|если|быть|может|должен|должна|"
    r"настоящего|соответствии|является|статья|статьи|закон|кодекс|"
    r"договор|лицо|лица|случае|порядке|течение)\b",
    re.IGNORECASE,
)


def looks_russian(text: str) -> bool:
    """Matn rus tilidami (o'zbek kirilli emas).

    lex.uz hujjatlari ikki tilda keladi va ularni ajratish kerak:
    o'zbek kirilli lotin yozuviga o'giriladi, rus matni esa `body_ru` ga
    alohida saqlanadi.
    """
    if not has_cyrillic(text):
        return False
    sample = text[:4000]
    if len(_RUSSIAN_WORDS.findall(sample)) >= 3:
        return True
    ru_chars = sum(1 for ch in sample if ch in _RUSSIAN_ONLY_CHARS)
    return ru_chars / max(len(sample), 1) > 0.015


# --------------------------------------------------------------------------- #
# Asosiy normalizatsiya
# --------------------------------------------------------------------------- #

_WS_RE = re.compile(r"[ \t  -​﻿]+")
_NL_RE = re.compile(r"\n{3,}")
_DASH_RE = re.compile(r"[‐-―−]")


def canonical(text: str, *, transliterate: bool = False) -> str:
    """Saqlash uchun kanonik shakl.

    - Unicode NFC
    - Apostroflar rasmiy shaklga (oʻ, gʻ, tutuq belgisi ʼ)
    - Tire va bo'sh joylar tartibga solinadi
    - `transliterate=True` bo'lsa o'zbek kirilli lotinga o'giriladi
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if transliterate and has_cyrillic(text) and not looks_russian(text):
        text = to_latin(text)

    # o/g dan keyingi apostrof → oʻ, gʻ (alifbo harflari).
    # Qolgan barcha holatlar → tutuq belgisi (maʼno).
    #
    # Lookbehind ikkinchi almashtirishda ham kerak: usiz u birinchi
    # almashtirish natijasini (ʻ) qayta o'zgartirib yuboradi.
    text = re.sub(rf"(?<=[oOgG]){_APOS_CLASS}", TURNED_COMMA, text)
    text = re.sub(rf"(?<![oOgG]){_APOS_CLASS}", MODIFIER_APOS, text)

    text = _DASH_RE.sub("-", text)
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def fold(text: str) -> str:
    """Qidiruv va taqqoslash uchun soddalashtirilgan shakl.

    Barcha apostroflar ASCII `'` ga, kirill lotinga, hammasi kichik harfga.
    Indekslashda ham, so'rovda ham shu funksiya qo'llaniladi — shunda
    `oʻzgartirish` va `o'zgartirish` bir xil kalitga tushadi.
    """
    text = unicodedata.normalize("NFC", text)
    if has_cyrillic(text) and not looks_russian(text):
        text = to_latin(text)
    text = re.sub(_APOS_CLASS, "'", text)
    text = _WS_RE.sub(" ", text)
    return text.strip().lower()


# --------------------------------------------------------------------------- #
# Yuridik atamalar
# --------------------------------------------------------------------------- #

# "234-modda", "234 modda", "Статья 234", "234-м." → "234"
_ARTICLE_PATTERNS = [
    re.compile(r"(\d+(?:[-–]\d+)?)\s*[-–]?\s*modda", re.IGNORECASE),
    re.compile(r"(\d+(?:[-–]\d+)?)\s*[-–]?\s*модда", re.IGNORECASE),
    re.compile(r"стать[яи]\s+(\d+(?:[-–.]\d+)?)", re.IGNORECASE),
    re.compile(r"^\s*(\d+(?:[-–]\d+)?)\s*[-–.]", re.IGNORECASE),
]


def extract_article_number(text: str) -> str | None:
    """Sarlavhadan modda raqamini ajratadi. Kanonik shakl: `234` yoki `234-1`."""
    for pattern in _ARTICLE_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1).replace("–", "-")
    return None


_DATE_PATTERNS = [
    (re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"), (3, 2, 1)),
    (re.compile(r"\b(\d{4})-yil\s+(\d{1,2})-\w+"), None),  # maxsus ishlov
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), (1, 2, 3)),
]

# Oy nomlari — o'zbek (lotin/kirill) va rus tilida.
# Kalitlar prefiks sifatida ishlatiladi, chunki rus tilida qaratqich kelishigi
# oy nomini o'zgartiradi: "декабрь" → "декабря", "март" → "марта".
_MONTH_PREFIXES: list[tuple[str, int]] = [
    ("yanvar", 1), ("fevral", 2), ("mart", 3), ("aprel", 4), ("may", 5), ("iyun", 6),
    ("iyul", 7), ("avgust", 8), ("sentabr", 9), ("oktabr", 10), ("noyabr", 11), ("dekabr", 12),
    ("январ", 1), ("феврал", 2), ("март", 3), ("апрел", 4), ("май", 5), ("июн", 6),
    ("июл", 7), ("август", 8), ("сентябр", 9), ("октябр", 10), ("ноябр", 11), ("декабр", 12),
    ("янв", 1), ("фев", 2), ("мар", 3), ("апр", 4), ("сен", 9), ("окт", 10), ("ноя", 11), ("дек", 12),
]


def _month_number(word: str) -> int | None:
    word = word.lower()
    for prefix, number in _MONTH_PREFIXES:
        if word.startswith(prefix):
            return number
    return None


def extract_date(text: str) -> str | None:
    """Sanani ISO 8601 (`YYYY-MM-DD`) shaklida qaytaradi.

    Qo'llab-quvvatlanadigan shakllar:

        15.03.2024
        2024-03-15
        2024-yil 15-mart
        1995 йил 21 декабр
        25 декабря 2025 года     ← lex.uz o'zgartirish eslatmalarida
    """
    # "2024-yil 15-mart" / "1995 йил 21 декабр"
    m = re.search(r"\b(\d{4})[-\s]*(?:yil|йил)\s+(\d{1,2})[-\s]*(\w+)", text, re.IGNORECASE)
    if m and (month := _month_number(m.group(3))):
        return f"{m.group(1)}-{month:02d}-{int(m.group(2)):02d}"

    # "25 декабря 2025 года" / "15 mart 2024"
    m = re.search(r"\b(\d{1,2})\s+([А-Яа-яA-Za-zЁёЎўҚқҒғҲҳ]{3,12})\s+(\d{4})\b", text)
    if m and (month := _month_number(m.group(2))):
        return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"

    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if m:
        return m.group(0)

    return None
