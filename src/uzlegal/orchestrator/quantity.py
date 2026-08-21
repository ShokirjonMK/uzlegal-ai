"""Miqdor ziddiyati — iqtibosga zid son (docs/28).

## Nima uchun kerak

`gate.support_score()` da'voni iqtibos bilan **so'z ustma-ustligi**
bo'yicha solishtiradi. Bu son ziddiyatini printsipial ravishda ko'ra
olmaydi. O'lchandi (2026-08-21, haqiqiy chaqiruv):

    SAVOL   Vindikatsiya da'vosi muddati necha yil
    JAVOB   «…qonuniy muddat … 10 yil bo'lib…»  [C1]
    [C1]    Fuqarolik kodeksi, 150-modda:
            «Umumiy da'vo muddati — uch yil.»

Ikki jumla ko'p so'zni bo'lishadi — `da'vo`, `muddat`, `umumiy`,
`yil`. Qoplama yuqori, demak da'vo «asoslangan» hisoblanadi. Lekin
farq aynan o'sha so'zlarda emas, **sonda**.

Foydalanuvchi uchun bu eng yomon xato turi: havola ishlaydi, modda
to'g'ri, matn esa boshqa raqamni aytadi.

## Nima uchun bu tekshiruv ishonchli

`has_invented_article()` bilan bir xil tamoyil: **aniq**, taxminiy
emas. Son yo mos keladi, yo kelmaydi. Shuning uchun natija belgilash
emas, **o'chirish**.

Lekin ehtiyot chorasi ham xuddi shunday: iqtibosda o'sha birlikda
son umuman bo'lmasa — tekshirib bo'lmaydi va da'vo tegilmaydi.
Tekshirib bo'lmaydigan narsani jazolash to'g'ri javoblarni ham
o'chirardi.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------- #
# O'zbekcha son so'zlari
# --------------------------------------------------------------------------- #

# Yuridik matnda son ko'pincha SO'Z bilan yoziladi: «uch yil», «o'n kun».
# Raqamli shakl ham uchraydi, shuning uchun ikkalasi ham tanilishi kerak.
_ONES: dict[str, int] = {
    "bir": 1,
    "ikki": 2,
    "uch": 3,
    "to'rt": 4,
    "tort": 4,
    "besh": 5,
    "olti": 6,
    "yetti": 7,
    "sakkiz": 8,
    "to'qqiz": 9,
    "toqqiz": 9,
}

_TENS: dict[str, int] = {
    "o'n": 10,
    "on": 10,
    "yigirma": 20,
    "o'ttiz": 30,
    "ottiz": 30,
    "qirq": 40,
    "ellik": 50,
    "oltmish": 60,
    "yetmish": 70,
    "sakson": 80,
    "to'qson": 90,
    "yuz": 100,
    "ming": 1000,
}

_WORDS = {**_ONES, **_TENS}

# Miqdor **birligi**. Faqat yuridik matnda ma'no tashiydiganlari:
# «uch yil» muhim, «uch tomon» esa miqdor emas, tavsif.
_UNITS: dict[str, str] = {
    "yil": "yil",
    "yilgacha": "yil",
    "yildan": "yil",
    "oy": "oy",
    "oygacha": "oy",
    "oydan": "oy",
    "kun": "kun",
    "kungacha": "kun",
    "kundan": "kun",
    "hafta": "hafta",
    "soat": "soat",
    "foiz": "foiz",
    "foizdan": "foiz",
    "barobar": "barobar",
    "baravar": "barobar",
    "marta": "marta",
    "yosh": "yosh",
    "yoshdan": "yosh",
    "yoshga": "yosh",
}

_UNIT_RE = "|".join(sorted(_UNITS, key=len, reverse=True))
_WORD_RE = "|".join(sorted((re.escape(w) for w in _WORDS), key=len, reverse=True))

# «10 yil», «3 oy» — lekin «150-modda» EMAS: raqamdan keyin defis kelsa,
# bu tartib raqami (modda, band, qism) va miqdor emas.
_DIGIT_QTY = re.compile(rf"\b(\d{{1,4}})\s+({_UNIT_RE})\b", re.IGNORECASE)

# «uch yil», «o'n besh kun» — ikkita so'zgacha ruxsat (o'n besh, yigirma besh).
_WORD_QTY = re.compile(rf"\b({_WORD_RE})(?:\s+({_WORD_RE}))?\s+({_UNIT_RE})\b", re.IGNORECASE)


def _combine(first: str, second: str | None) -> int | None:
    """«o'n besh» → 15, «uch» → 3. Mos kelmasa `None`."""
    a = _WORDS.get(first.casefold())
    if a is None:
        return None
    if second is None:
        return a
    b = _WORDS.get(second.casefold())
    if b is None:
        return None
    # Faqat «o'nliklar + birliklar» birikmasi mantiqiy: «o'n besh» = 15.
    # «besh o'n» kabi teskari tartib o'zbek tilida miqdor emas.
    if a in _TENS.values() and b in _ONES.values():
        return a + b
    return None


def quantities(text: str) -> set[tuple[int, str]]:
    """Matndagi `(qiymat, birlik)` juftliklari.

    Tartib raqamlari (`150-modda`) miqdor **emas** va bu yerga tushmaydi:
    ular defis bilan yoziladi, naqsh esa bo'sh joy talab qiladi.
    """
    found: set[tuple[int, str]] = set()

    for match in _DIGIT_QTY.finditer(text):
        unit = _UNITS[match.group(2).casefold()]
        found.add((int(match.group(1)), unit))

    for match in _WORD_QTY.finditer(text):
        value = _combine(match.group(1), match.group(2))
        if value is None:
            # Birinchi so'zning o'zi son bo'lishi mumkin: «uch [oy]» dagi
            # ikkinchi guruh boshqa narsani ushlagan bo'lsa.
            value = _WORDS.get(match.group(1).casefold())
        if value is not None:
            found.add((value, _UNITS[match.group(3).casefold()]))

    return found


def contradicts(claim: str, sources: list[str]) -> tuple[int, int, str] | None:
    """Da'vodagi miqdor manbadagiga zidmi.

    Qaytadi: `(da'vodagi, manbadagi, birlik)` yoki `None`.

    Qoida ataylab tor — faqat **ayni birlik** solishtiriladi:

    * da'voda miqdor yo'q → tekshirib bo'lmaydi;
    * manbada o'sha birlikda miqdor yo'q → tekshirib bo'lmaydi;
    * da'vodagi qiymat manbadagilar orasida bor → ziddiyat yo'q
      (manbada bir necha muddat bo'lishi normal: «uch yil … o'n yil»);
    * faqat qiymat butunlay boshqa bo'lsa → ziddiyat.

    Oxirgi qoida muhim: modda ko'pincha bir nechta muddat sanaydi va
    javob ulardan **birini** keltirishi mumkin. Shuning uchun da'vo
    manbadagi har qanday qiymatga mos kelsa — u to'g'ri hisoblanadi.
    """
    claim_q = quantities(claim)
    if not claim_q:
        return None

    source_q: set[tuple[int, str]] = set()
    for source in sources:
        if source:
            source_q |= quantities(source)
    if not source_q:
        return None

    for value, unit in sorted(claim_q):
        same_unit = {v for v, u in source_q if u == unit}
        if same_unit and value not in same_unit:
            return value, min(same_unit), unit
    return None
