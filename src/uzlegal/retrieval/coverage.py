"""Qamrov darvozasi — tizim o'z chegarasini biladi (docs/27).

## Nima uchun kerak

Korpus O'zbekiston qonunchiligining bir qismini qoplaydi. Qamrovdan
tashqaridagi savolga tizim **yaqin narsani** topib berardi: GDPR
so'ralganda O'zbekiston shaxsiy ma'lumotlar qonunini, AQSh
Konstitutsiyasi so'ralganda O'zbekiston Konstitutsiyasini.

Bu yo'qotish emas, **noto'g'ri javob**: foydalanuvchi savoliga emas,
boshqa savolga javob oladi — va u ishonarli ko'rinadi, chunki iqtibos
haqiqiy.

## Nima uchun qaror MODELGA berilmaydi

Ikki sabab:

1. Model «bilmayman» deyishga tabiatan qarshi. U har doim yaqin narsa
   topadi va uni ishonch bilan taqdim etadi.
2. Deterministik qaror **modelsiz testlanadi** va takrorlanadi.

## Nima uchun ball chegarasi EMAS

Birinchi urinishda qamrov qidiruv balli bo'yicha aniqlanmoqchi edi.
O'lchandi (2026-08-20, gold-36 va qamrov tuzoqlari):

    gold savollar     min 0.2000   median 0.3626
    qamrov tuzoqlari      0.2000 … 0.2030

Ya'ni **ajratmaydi**: RRF balli o'rinni normallashtiradi, mosligini
emas — birinchi natija har doim bir xil hissa oladi, u qanchalik
yaroqsiz bo'lishidan qat'i nazar.

Ikkinchi urinish — so'rovdagi atamalar korpus lug'atida bormi.
U ham ajratmadi va hatto **teskari** ishladi: gold savollarning
5 tasida korpusda umuman yo'q so'z bor edi (`mulkimni`, `majburmi` —
morfologik shakllar), tuzoqlarda esa deyarli yo'q edi.

## Ishlaydigan signal

Beshala tuzoqning umumiy tuzilishi bitta: **savol huquqiy manbani
nomlaydi va o'sha manba korpusda yo'q.**

    «AQSh Konstitutsiyasi»          → boshqa yurisdiksiya
    «Yevropa Ittifoqi GDPR»         → boshqa yurisdiksiya
    «Oliy sud Plenumining qarori»   → korpusda 4 ta hujjat
    «hokimning qarori»              → korpusda yo'q
    «xalqaro dengiz huquqi»         → korpusda yo'q

Shuning uchun darvoza **nomlangan manbani** qidiradi va uni korpus
haqiqati bilan solishtiradi. Bu ball ham, o'xshashlik ham emas —
bu ha yoki yo'q.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

GapKind = Literal["yurisdiksiya", "manba-turi"]


@dataclass(frozen=True)
class CoverageGap:
    """Qamrovdagi teshik — nima so'ralgani va nima uchun javob yo'qligi."""

    kind: GapKind
    subject: str
    detail: str


# --------------------------------------------------------------------------- #
# 1. Boshqa yurisdiksiya
# --------------------------------------------------------------------------- #

# Korpus **faqat** O'zbekiston qonunchiligidan iborat. Boshqa davlat yoki
# tashkilotning huquqi haqidagi savolga javob yo'q va bo'lishi ham mumkin
# emas — bu korpusni kengaytirish bilan hal bo'lmaydi, bu boshqa mahsulot.
#: Uchinchi element: nom o'zi huquqiy hujjatmi. `True` bo'lsa yonida
#: qo'shimcha manba so'zi talab qilinmaydi — «GDPR jarimasi qancha»
#: savolida «qonun» so'zi yo'q, lekin GDPR ning o'zi qonun.
_JURISDICTIONS: tuple[tuple[str, str, bool], ...] = (
    (r"aqsh|amerika qo'shma shtatlari", "AQSh", False),
    (r"rossiya", "Rossiya", False),
    (r"qozog'iston|qozogiston", "Qozog'iston", False),
    (r"qirg'iziston|qirgiziston", "Qirg'iziston", False),
    (r"tojikiston", "Tojikiston", False),
    (r"turkmaniston", "Turkmaniston", False),
    (r"\bturkiya\b", "Turkiya", False),
    (r"\bxitoy\b", "Xitoy", False),
    (r"germaniya", "Germaniya", False),
    (r"fransiya", "Fransiya", False),
    (r"buyuk britaniya", "Buyuk Britaniya", False),
    (r"ukraina", "Ukraina", False),
    (r"\bbelarus", "Belarus", False),
    (r"yevropa ittifoqi|\byei\b", "Yevropa Ittifoqi", False),
    (r"\bgdpr\b", "Yevropa Ittifoqi (GDPR)", True),
    (r"yevropa kengashi", "Yevropa Kengashi", False),
)

# Yurisdiksiya nomining o'zi yetarli emas: «chet el fuqarosi» yoki
# «Rossiyaga eksport» — bular O'ZBEKISTON huquqi savollari. Rad etish
# uchun yonida huquqiy manba so'zi ham turishi kerak.
_LEGAL_SOURCE = re.compile(
    r"konstitutsiya|qonun|kodeks|direktiva|reglament|qaror|tuzatish|"
    r"huquqi\b|normas|akt\b|nizom",
    re.IGNORECASE,
)


def _foreign_jurisdiction(question: str) -> CoverageGap | None:
    low = question.casefold()
    has_source = bool(_LEGAL_SOURCE.search(question))
    for pattern, name, self_evident in _JURISDICTIONS:
        if not (has_source or self_evident):
            continue
        if re.search(pattern, low):
            return CoverageGap(
                kind="yurisdiksiya",
                subject=name,
                detail=(
                    f"Bilim bazasi faqat O'zbekiston Respublikasi qonunchiligidan "
                    f"iborat. {name} huquqi bo'yicha manba yo'q."
                ),
            )
    return None


# --------------------------------------------------------------------------- #
# 2. Korpusda yo'q manba turi
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceClass:
    """Savolda nomlanishi mumkin bo'lgan hujjat sinfi va uning korpusdagi izi."""

    key: str
    label: str
    #: Savolda shu sinf nomlanganini bildiruvchi naqsh.
    asked: str
    #: Korpusda shu sinf borligini tekshiruvchi naqsh (`doc_title` bo'yicha).
    #: `doc_types` berilgan bo'lsa u ustun turadi.
    title_probe: str = ""
    doc_types: tuple[str, ...] = ()
    #: Shu sondan kam hujjat bo'lsa sinf «qoplanmagan» hisoblanadi.
    #: Nol emas: bitta-ikkita tasodifiy hujjat savolga javob bermaydi,
    #: lekin qidiruvni «topdim» deb aldashi mumkin.
    min_docs: int = 10


_SOURCE_CLASSES: tuple[SourceClass, ...] = (
    SourceClass(
        key="plenum",
        label="Oliy sud Plenumi qarorlari",
        asked=r"plenum",
        doc_types=("plenum",),
    ),
    SourceClass(
        key="hokim",
        label="hokim qarorlari",
        # «sud hokimiyati» tasodifan tushmasin — shuning uchun hokim
        # so'zidan keyin hujjat turi kelishi talab qilinadi.
        asked=r"hokim\w*\s+(?:\d{4}[-\s]?yil.{0,40}?)?(?:qaror|farmoyish|buyru)",
        title_probe=r"hokim(?:ning|i)\s+qarori",
    ),
    SourceClass(
        key="xalqaro",
        label="xalqaro shartnoma va konvensiyalar",
        asked=r"xalqaro\s+(?:\w+\s+){0,2}?(?:shartnoma|konvensiya|huquq|majburiyat)|konvensiya",
        title_probe=r"konvensiya|xalqaro shartnoma",
    ),
    SourceClass(
        key="vazirlik",
        label="vazirlik buyruqlari",
        asked=r"vazirli(?:gi|k)ning\s+buyru",
        title_probe=r"vazirligining buyru",
    ),
)


def _corpus_has(index: Any, source: SourceClass) -> int:
    """Korpusda shu sinfdan nechta hujjat bor."""
    try:
        chunks = getattr(index, "_chunks", None)
        if not chunks:
            index.read_chunks()
            chunks = index._chunks
    except Exception:  # pragma: no cover — indeks o'qilmasa tekshirmaymiz
        return -1

    seen: set[str] = set()
    probe = re.compile(source.title_probe, re.IGNORECASE) if source.title_probe else None
    for chunk in chunks.values():
        if chunk.doc_id in seen:
            continue
        if source.doc_types:
            if chunk.doc_type in source.doc_types:
                seen.add(chunk.doc_id)
        elif probe is not None and probe.search(chunk.doc_title or ""):
            seen.add(chunk.doc_id)
    return len(seen)


def _absent_source(question: str, index: Any) -> CoverageGap | None:
    for source in _SOURCE_CLASSES:
        if not re.search(source.asked, question, re.IGNORECASE):
            continue
        count = _corpus_has(index, source)
        if count < 0 or count >= source.min_docs:
            continue
        holat = "umuman yo'q" if count == 0 else f"atigi {count} ta hujjat bor"
        return CoverageGap(
            kind="manba-turi",
            subject=source.label,
            detail=(
                f"Bilim bazasida {source.label} {holat}. Shu sababli bu savolga "
                f"ishonchli javob bera olmayman — topilgan normalar so'ralgan "
                f"manbadan emas."
            ),
        )
    return None


# --------------------------------------------------------------------------- #
# Darvoza
# --------------------------------------------------------------------------- #


def check_coverage(question: str, index: Any = None) -> CoverageGap | None:
    """Savol korpus qamrovidan tashqarimi.

    Tartib ataylab: yurisdiksiya birinchi, chunki u korpusga umuman
    bog'liq emas va eng aniq signal. Manba turi ikkinchi — u korpus
    holatiga qarab **o'zgaradi**: korpus kengaysa, tekshiruv o'zi
    yumshaydi va qo'lda hech narsa o'zgartirilmaydi.

    `None` qaytsa — darvoza to'smaydi. Bu «javob to'g'ri» degani
    emas: qolgan tekshiruvlar (`missing_document`, iqtibos darvozasi)
    o'z ishini bajaradi.
    """
    if not question or not question.strip():
        return None

    gap = _foreign_jurisdiction(question)
    if gap is not None:
        return gap

    if index is not None:
        return _absent_source(question, index)
    return None
