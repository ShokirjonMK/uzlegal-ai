"""Hujjat ziddiyati — da'vo bir kodeksni nomlaydi, iqtibos boshqasidan (docs/28).

## Nima uchun kerak

`has_invented_article()` da'vodagi **modda raqamini** iqtibos bilan
solishtiradi. Lekin da'vo modda raqamisiz ham noto'g'ri manbaga ishora
qilishi mumkin:

    «Fuqarolik kodeksiga ko'ra mol-mulk teng bo'linadi [C1]»
     C1 = Oila kodeksi, 23-modda

Havola ishlaydi, modda raqami umuman aytilmagan, lekin da'vo
**boshqa kodeksni** nomlaydi. Foydalanuvchi «Fuqarolik kodeksi» deb
o'qiydi va o'sha kodeksdan izlaydi.

## Nima uchun bu tekshiruv ishonchli

`has_invented_article()` va `quantity.contradicts()` bilan bir xil
tamoyil: **aniq**, taxminiy emas. Kodeks nomi yo mos keladi, yo
kelmaydi.

## Nima uchun faqat NOM AYTILGANDA

Da'vo hech qanday hujjat nomlamasa — tekshirib bo'lmaydi va u
tegilmaydi. Bu loyihaning umumiy qoidasi: tekshirib bo'lmaydigan
narsani jazolash to'g'ri javoblarni ham o'chiradi.

Amalda bu tekshiruv **tor** ishlaydi va shunday bo'lishi kerak:
modelning ko'p javobida kodeks nomi umuman aytilmaydi.
"""

from __future__ import annotations

import re

from uzlegal.ingest.normalize import fold
from uzlegal.types import Citation

# «Fuqarolik kodeksi», «Mehnat kodeksiga», «Oila kodeksining» —
# nomdan oldingi uchtagacha so'z olinadi.
_DOCUMENT_RE = re.compile(
    r"([\w'ʻʼ‘’-]+(?:\s+[\w'ʻʼ‘’-]+){0,2})\s+kodeks\w*",
    re.IGNORECASE | re.UNICODE,
)

# Nomning bir qismi bo'la olmaydigan so'zlar. `graph._DOC_STOPWORDS` bilan
# bir xil ro'yxat: u yerda savol tahlil qilinadi, bu yerda javob.
_STOPWORDS = frozenset(
    {
        "yangi",
        "eski",
        "amaldagi",
        "joriy",
        "shu",
        "bu",
        "ushbu",
        "haqidagi",
        "mazkur",
        "o'sha",
        "ayni",
    }
)

# Bu so'zlar kodeks NOMI emas, unga ishora: «ushbu kodeksning»,
# «mazkur kodeks». Ular tekshiruvni ishga tushirmaydi.
_SELF_REFERENCE = frozenset({"", "ushbu", "mazkur", "shu", "o'sha", "ayni"})


def _names(text: str) -> set[str]:
    found: set[str] = set()
    for match in _DOCUMENT_RE.finditer(text):
        words = [w for w in match.group(1).split() if w.casefold() not in _STOPWORDS]
        name = " ".join(words).strip()
        if name and name.casefold() not in _SELF_REFERENCE:
            found.add(fold(name))
    return found


def contradicts(claim: str, citations: list[Citation]) -> tuple[str, str] | None:
    """Da'vodagi kodeks nomi iqtibosdagiga zidmi.

    Qaytadi: `(da'vodagi nom, iqtibosdagi hujjat)` yoki `None`.

    Tekshiruv **faqat** quyidagi hamma shart bajarilganda ishlaydi:

    * da'vo kodeks nomini aytadi (`ushbu kodeks` kabi ishoralar emas);
    * iqtibosda hujjat sarlavhasi bor;
    * nomlangan kodeks iqtibos qilingan **hech bir** hujjatda uchramaydi.

    Oxirgi shart muhim: da'vo bir necha iqtibosga tayanishi mumkin va
    ulardan **bittasi** mos kelsa yetarli.
    """
    claimed = _names(claim)
    if not claimed:
        return None

    titles = [fold(c.doc_title) for c in citations if c.doc_title]
    if not titles:
        return None

    for name in sorted(claimed):
        if not any(name in title for title in titles):
            first = next((c.doc_title for c in citations if c.doc_title), "")
            return name, first or ""
    return None
