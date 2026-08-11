"""Leksik taqqoslash — gate va debate uchun umumiy.

Ikkala joyda ham bir xil savol turadi: ikki matn bir narsa haqidami? Gate
uni "iqtibos da'voni qo'llab-quvvatlaydimi" shaklida, debate esa "ikki
pozitsiya bir xil xulosaga keldimi" shaklida so'raydi.

Javob embedding bilan ham berilishi mumkin edi, lekin bu qadam har so'rovda
ishlaydi va 1.2 GB modelni ikkita jumla uchun yuklash narxga arzimaydi.
Leksik qoplama bu vazifa uchun yetarli: ikkalasi ham **shovqinni tutish**
uchun ishlatiladi, nozik semantik farqni o'lchash uchun emas.
"""

from __future__ import annotations

import re

from uzlegal.ingest.normalize import fold

_WORD_RE = re.compile(r"[a-z0-9']+")

# Mazmun tashimaydigan so'zlar. Ularsiz "va", "bu", "uchun" har qanday ikki
# matnni "o'xshash" ko'rsatardi.
STOPWORDS = frozenset(
    (
        "va",
        "yoki",
        "ham",
        "bu",
        "shu",
        "bir",
        "uchun",
        "bilan",
        "lekin",
        "ammo",
        "agar",
        "chunki",
        "hamda",
        "ya'ni",
        "kabi",
        "qilib",
        "qilish",
        "bo'lgan",
        "bo'ladi",
        "bo'lsa",
        "emas",
        "ega",
        "har",
        "hech",
        "faqat",
        "ushbu",
        "mazkur",
        "o'z",
        "ular",
        "biz",
        "siz",
        "men",
        "keyin",
        "oldin",
        "ko'ra",
        "asosan",
        "holda",
        "tomonidan",
    )
)

# Qisqa so'zlar ham tashlanadi: o'zbekchada ular deyarli har doim yordamchi.
MIN_WORD_LENGTH = 4


def content_words(text: str) -> set[str]:
    """Matnning mazmunli so'zlari — o'zaklashtirilgan shaklda.

    `fold()` shart: apostrof variantlari va kirill yozuvi bir shaklga
    keltirilmasa, «oʻzgartirish» va «o'zgartirish» turli so'z bo'lib qoladi.

    O'zaklashtirish ham shart va sababi o'lchangan. O'zbek agglyutinativ
    til; da'vo normani **qayta ifodalaydi**, nusxa ko'chirmaydi:

        daʼvo:  "…uch yillik muddat ichida qoʻzgʻatilishi kerak"
        norma:  "Umumiy daʼvo muddati uch yil qilib belgilanadi"

    `muddat`/`muddati` va `yil`/`yillik` bir xil ma'no, lekin harfma-harf
    boshqa. O'zaklashtirmasdan bu daʼvo «qo'llab-quvvatlanmagan» deb
    belgilanardi, holbuki u aynan shu normadan kelib chiqadi.

    `simplify()` BM25 uchun yozilgan va `retrieval-gold-v1` da o'lchangan —
    shu yerda qayta ishlatiladi, ikkinchi amalga oshirish yozilmaydi.
    """
    from uzlegal.retrieval.expansion import simplify

    return {
        simplify(w)
        for w in _WORD_RE.findall(fold(text))
        if len(w) >= MIN_WORD_LENGTH and w not in STOPWORDS
    }


def jaccard(a: set[str], b: set[str]) -> float:
    """Ikki to'plamning kesishuv nisbati. Ikkalasi bo'sh bo'lsa 1.0."""
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0
