"""So'rov kengaytmasi — so'zlashuv tilini yuridik atamaga bog'lash.

## Muammo (baholashda o'lchangan)

`retrieval-gold-v1` da nosozliklarning katta qismi bitta sababdan:
foydalanuvchi kundalik so'z ishlatadi, qonun esa rasmiy atama.

    savol:  "Maoshni toʻlash tartibi va muddatlari"
    qonun:  "333-modda. Xodimga ish haqi toʻlashni …"

«Maosh» so'zi Mehnat kodeksida umuman uchramaydi — BM25 uchun bu so'z
mavjud emas, vektor qidiruvi esa faqat qisman qutqaradi.

## Yechim

Ikki qatlamli kengaytma:

1. **Tezaurus** (`configs/retrieval/thesaurus.yaml`) — qo'lda tuzilgan
   so'zlashuv ↔ atama juftliklari. Deterministik, tez, tushunarli.
2. **Morfologik soddalashtirish** — o'zbek tili agglyutinativ, so'z
   oxiridagi qo'shimchalar BM25 mosligini buzadi:
   `shartnomasini` / `shartnomaning` / `shartnomalar` → `shartnoma`

Kengaytma **qo'shimcha**: asl so'rov saqlanadi, atamalar unga qo'shiladi.
Bu muhim — asl so'zlar ham qonun matnida uchrashi mumkin.

## Nima uchun LLM bilan emas

HyDE (gipotetik javob generatsiyasi) yaxshiroq natija berishi mumkin, lekin
u har so'rovga model chaqiruvi qo'shadi — `simple` rejimda kechikish 5 s dan
oshib ketadi. Tezaurus bepul va takrorlanadigan. LLM kengaytmasi keyingi
bosqichda, o'lchov bilan taqqoslab qo'shiladi.
"""

from __future__ import annotations

import functools
import logging
import re
from pathlib import Path

import yaml

from uzlegal.ingest.normalize import fold

log = logging.getLogger(__name__)

DEFAULT_THESAURUS = Path("configs/retrieval/thesaurus.yaml")

# O'zbek tilidagi eng keng tarqalgan otlashuvchi qo'shimchalar.
# Tartib muhim: uzunroq qo'shimcha avval olib tashlanadi.
_SUFFIXES = [
    "larining", "lariga", "larida", "laridan", "larini", "larning",
    "sining", "siga", "sida", "sidan", "sini",
    "ning", "lar", "ga", "da", "dan", "ni", "si", "i",
]

_MIN_STEM = 4  # bundan qisqa o'zakni kesmaymiz — ma'no yo'qoladi


def simplify(word: str) -> str:
    """So'z oxiridagi kelishik qo'shimchasini olib tashlaydi.

    Bu to'liq morfologik tahlil emas — o'zbek tili uchun to'liq lemmatizator
    yo'q. Amalda BM25 mosligini sezilarli yaxshilaydigan yengil evristika.

        shartnomasini → shartnoma
        moddalarning  → modda
        uy            → uy   (o'zgarmaydi, juda qisqa)
    """
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= _MIN_STEM:
            return word[: -len(suffix)]
    return word


@functools.lru_cache(maxsize=4)
def load_thesaurus(path: Path = DEFAULT_THESAURUS) -> dict[str, list[str]]:
    """Tezaurusni yuklaydi. Fayl yo'q bo'lsa bo'sh lug'at — kengaytma o'chadi."""
    if not path.exists():
        log.debug("Tezaurus topilmadi: %s", path)
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {fold(k): list(v) for k, v in (data.get("synonyms") or {}).items()}


class QueryExpander:
    def __init__(self, thesaurus: dict[str, list[str]] | None = None) -> None:
        self.thesaurus = thesaurus if thesaurus is not None else load_thesaurus()

    def expand(self, query: str) -> tuple[str, list[str]]:
        """So'rovni kengaytiradi.

        `(kengaytirilgan_sorov, qoshilgan_atamalar)` qaytaradi.
        Hech narsa qo'shilmasa asl so'rov o'zgarishsiz qaytadi.
        """
        folded = fold(query)
        added: list[str] = []

        # 1. Tezaurus — uzunroq iboralar avval tekshiriladi
        for phrase in sorted(self.thesaurus, key=len, reverse=True):
            if phrase in folded:
                for term in self.thesaurus[phrase]:
                    if fold(term) not in folded and term not in added:
                        added.append(term)

        # 2. Morfologik o'zaklar — faqat asl shakldan farq qilsa
        for word in re.findall(r"[a-zʻʼ']{5,}", folded):
            stem = simplify(word)
            if stem != word and stem not in folded.split() and stem not in added:
                added.append(stem)

        if not added:
            return query, []
        return f"{query} {' '.join(added)}", added
