"""Modda versiyalarini qurish — docs/03 § 3.4.

## Nima uchun bu modul bor

`docs/00` da «bekor qilingan norma 0%» kafolati bor. Bu kafolat
`retrieval/hybrid.py: version_filter()` da amalga oshiriladi, lekin filtr
`valid_from` / `valid_to` / `status` maydonlariga tayanadi. Ular to'ldirilmasa
filtr **bo'sh ishlaydi** — hech narsa chiqarilmaydi va kafolat isbotlanmaydi.

Bu modul o'sha maydonlarni to'ldiradi.

## Signal qayerdan keladi

lex.uz konsolidatsiyalangan matnni beradi va har bir tahrirni qavs ichidagi
izoh bilan belgilaydi. O'zbek nashrlarida format juda barqaror:

    (148-moddaning birinchi qismi Oʻzbekiston Respublikasining 2017-yil
     6-sentabrdagi OʻRQ-442-sonli Qonuni tahririda - OʻR QHT, 2017-y.,
     36-son, 943-modda)

    (Oʻzbekiston Respublikasining 2025-yil 7-fevraldagi OʻRQ-1025-sonli
     Qonuniga asosan 63-moddaning oʻz kuchini yoʻqotish sanasi -
     2025-yil 8-may - Qonunchilik maʼlumotlari milliy bazasi, …)

Bu izohlarning **katta qismi modda tanasi ichida** keladi (ACT_TEXT bloki),
faqat kichik qismi alohida blok sifatida. 20 kodeksda o'lchangan: parser
`AmendmentNote` sifatida ~250 tasini ajratadi, tana ichida esa ~6400 ta bor.
Shuning uchun bu modul ikkala manbani ham o'qiydi.

## Uchta tuzoq

1. **Nashr havolasi modda emas.** Izoh oxiridagi «OʻR QHT, 2014-y., 20-son,
   222-modda» — byulleten moddasi, kodeks moddasi emas. Shuning uchun izoh
   avval «bosh» va «nashr quyrug'i» ga bo'linadi.

2. **Bekor qilish izohi qo'shni moddada turadi.** 63-modda bekor qilinsa,
   u matndan olib tashlanadi va izoh 62-modda tanasida qoladi. Demak nishon
   izoh matnidan olinadi, o'ralgan moddadan emas.

3. **Kelajakdagi sana.** «Kuchga kirish sanasi — 2027-yil 1-yanvar» bo'lsa,
   matndagi versiya hali **eski** versiya. Bunday sanani `valid_from` ga
   yozsak, `version_filter` bugungi so'rovda amaldagi moddani chiqarib
   yuboradi. Shuning uchun `valid_from` faqat **o'tgan** sanalardan olinadi,
   kelajakdagilari ogohlantirish sifatida qayd etiladi.

Sana umuman topilmasa — `None` qoladi va ogohlantirish yoziladi. **Taxmin
qilinmaydi**: noto'g'ri sana yo'q sanadan xavfliroq.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import expand_article_run, extract_date, fold
from uzlegal.ingest.types import ParsedDocument

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Izohni bosh va nashr quyrug'iga bo'lish
# --------------------------------------------------------------------------- #

# Nashr manbalari — shulardan keyin keladigan raqamlar hujjatga tegishli emas.
# Barcha shablonlar `fold()` qilingan matnga qo'llaniladi (apostrof bir xil,
# kirill lotinda, hammasi kichik harfda).
_PUBLICATION = re.compile(
    r"(o'r qht|"
    r"oliy majlis\w*\s+axborotnoma|palatalarining\s+axborotnoma|"
    r"qonun\w*\s+hujjatlari\s+ma'lumotlari\s+milliy\s+bazasi|"
    r"qonunchilik\s+ma'lumotlari\s+milliy\s+bazasi|"
    r"qonun\s+hujjatlari\s+to'plami|"
    r"ведомости|собрание\s+законодательства)"
)


def split_citation(folded: str) -> tuple[str, str]:
    """Izohni `(bosh, nashr quyrug'i)` ga bo'ladi.

    Bosh qismda nishon modda va tahrir turi bor; quyruqda faqat nashr
    havolasi. Quyruqdagi «222-modda» ni nishon deb olish — eng oson va eng
    zararli xato, shuning uchun bo'lish har doim birinchi qadam.
    """
    m = _PUBLICATION.search(folded)
    if not m:
        return folded, ""
    return folded[: m.start()], folded[m.start() :]


# --------------------------------------------------------------------------- #
# Nishon modda(lar)
# --------------------------------------------------------------------------- #

# «148-moddaning», «65 va 66-moddalar», «173-1 - 173-7-moddalar», «2 — 7-moddalari»
_TARGET_RUN = re.compile(
    r"((?:\d+(?:-\d+)?\s*(?:,|\bva\b|\bhamda\b|—|–|(?<=\s)-(?=\s))\s*)*\d+(?:-\d+)?)-modda"
)
_RU_TARGET = re.compile(r"стать[юяие]\s+(\d+(?:-\d+)?)")

# Bob / bo'lim darajasidagi izoh — «(42-bob … oʻz kuchini yoʻqotgan)».
# Bunday izohda modda raqami yo'q va uni o'ralgan moddaga bog'lash
# **amaldagi moddani bekor qilingan deb belgilaydi** (o'lchangan xato:
# 20 kodeksda 14 ta yolg'on «repealed»). Shuning uchun bunday izohlar
# butunlay o'tkazib yuboriladi — bob bekor qilinganda uning moddalari
# konsolidatsiyalangan matndan allaqachon olib tashlangan.
_STRUCTURE_ONLY = re.compile(r"(?:\d+|[ivxl]+)\s*-?\s*(?:bob|bo'lim)\b|paragraf|\bглав[аы]\b")


def note_targets(head: str) -> list[str]:
    """Izoh boshidan nishon modda raqamlarini ajratadi (kanonik: `234`, `173-1`)."""
    out: list[str] = []
    for m in _TARGET_RUN.finditer(head):
        for number in expand_article_run(m.group(1)):
            if number not in out:
                out.append(number)
    for m in _RU_TARGET.finditer(head):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


# --------------------------------------------------------------------------- #
# Tahrir turi va qamrovi
# --------------------------------------------------------------------------- #

_REPEAL = re.compile(r"kuchini\s+yo'qot|утратил\w*\s+силу")
_REMOVED = re.compile(r"chiqarib\s+tashlangan|исключен")
_ADDED = re.compile(r"\bkiritilgan\b|\bдополнен")
_AMENDED_WORDS = re.compile(r"o'zgart(ish|irish)\w*\s+kiritilgan|внесены\s+изменения")

# Modda ichidagi qism/band — bunday izoh moddani bekor qilmaydi, faqat tahrirlaydi
_SUBSCOPE = re.compile(
    r"\bqism|\bband|\bxatboshi|dispozitsiya|sanksiya|\bnomi\b|\bmatni\b|\bizoh|"
    r"\bчаст|\bпункт|\bабзац"
)

Kind = str  # "edition" | "added" | "removed" | "repealed"


class VersionSignal(BaseModel):
    """Bitta izohdan chiqarilgan versiya signali."""

    articles: list[str]
    kind: Kind
    scope: str = "article"  # "article" — butun modda · "part" — ichki bo'lak
    effective_date: str | None = None
    amending_doc: str | None = None
    raw: str = Field(repr=False)


# «OʻRQ-683-sonli», «ЗРУ-683», eski shakl «535-II-son»
_AMENDING_DOC = re.compile(r"\b(o'rq|zru|зру|ўрқ)[-\s]?(\d+)|\b(\d+)-(i{1,3}|iv|v)-son")


def amending_doc_id(folded: str) -> str | None:
    """O'zgartiruvchi qonun raqami: `OʻRQ-683` yoki `535-II`."""
    m = _AMENDING_DOC.search(folded)
    if not m:
        return None
    if m.group(2):
        return f"OʻRQ-{m.group(2)}"
    return f"{m.group(3)}-{m.group(4).upper()}"


# --------------------------------------------------------------------------- #
# Sana
# --------------------------------------------------------------------------- #

# Diqqat: sana ichida tire bor («2025-yil 8-may»), shuning uchun oynani
# tire bilan chegaralab bo'lmaydi — qavsgacha olinadi va sana ichidan
# `extract_date()` bilan qidiriladi.
_FORCE_DATE = re.compile(r"kuchga\s+kirish\s+sanasi\s*[-–—:]?\s*([^)]{6,45})")
_FORCE_FROM = re.compile(
    r"((?:\d{4}[-\s]?yil\s+)?\d{1,2}[-\s]?\w+|\d{1,2}\.\d{2}\.\d{4})dan\s+kuchga\s+kirad"
)
_REPEAL_DATE = re.compile(r"kuchini\s+yo'qotish\s+sanasi\s*[-–—:]?\s*([^)]{6,45})")
# «2017-yil 6-sentabrdagi … Qonuni» — o'zgartiruvchi qonunning qabul sanasi
_LAW_DATE = re.compile(r"(\d{4}-yil\s+\d{1,2}-\w+)dagi")


def effective_date(folded: str, kind: Kind) -> str | None:
    """Kuchga kirish sanasi. Topilmasa `None` — taxmin qilinmaydi.

    Ustuvorlik tartibi muhim: bir izohda uchtagacha sana bo'lishi mumkin —
    qonunning qabul sanasi, nashr sanasi va **kuchga kirish** sanasi. Bizga
    normaning amal qilish sanasi kerak, shuning uchun eng aniq ko'rsatilgani
    birinchi o'rinda turadi.
    """
    if (
        kind == "repealed"
        and (m := _REPEAL_DATE.search(folded))
        and (found := extract_date(m.group(1)))
    ):
        return found

    for pattern in (_FORCE_DATE, _FORCE_FROM):
        if (m := pattern.search(folded)) and (found := extract_date(m.group(1))):
            return found

    if (m := _LAW_DATE.search(folded)) and (found := extract_date(m.group(1))):
        return found

    # Oxirgi imkoniyat: nashr sanasi («21.04.2021-y.»)
    return extract_date(folded)


# --------------------------------------------------------------------------- #
# Izohni tahlil qilish
# --------------------------------------------------------------------------- #

_NOTE_LINE = re.compile(r"^\(.*\)$", re.DOTALL)
_HAS_SIGNAL = re.compile(
    r"tahririda|kuchini\s+yo'qot|chiqarib\s+tashlangan|to'ldirilgan|kiritilgan|"
    r"утратил|исключен|дополнен|внесены\s+изменения"
)


def parse_note(text: str, fallback_article: str | None = None) -> VersionSignal | None:
    """Bitta izohdan versiya signalini quradi. Izoh emas bo'lsa — `None`."""
    folded = fold(text)
    if not _HAS_SIGNAL.search(folded):
        return None

    head, _tail = split_citation(folded)
    targets = note_targets(head)

    if _REPEAL.search(head):
        kind = "repealed"
    elif _REMOVED.search(head):
        kind = "removed"
    elif _ADDED.search(head) and not _AMENDED_WORDS.search(head):
        kind = "added"
    else:
        kind = "edition"

    if not targets:
        # Nishon aniq ko'rsatilmagan. Ikki holatda taxmin qilish xavfli:
        # bob/bo'lim izohi va bekor qilish izohi — ikkalasi ham o'ralgan
        # moddani noto'g'ri belgilaydi. Qolgan holatda izoh o'zi turgan
        # modda haqida (o'lchangan: shakl juda barqaror).
        if kind == "repealed" or _STRUCTURE_ONLY.search(head) or not fallback_article:
            return None
        targets = [fallback_article]

    # Nishondan keyingi matn qamrovni ko'rsatadi: «…-moddaning ikkinchi qismi»
    after = head[m.end() :] if (m := _TARGET_RUN.search(head)) else head
    scope = "part" if _SUBSCOPE.search(after[:80]) else "article"

    return VersionSignal(
        articles=targets,
        kind=kind,
        scope=scope,
        effective_date=effective_date(folded, kind),
        amending_doc=amending_doc_id(folded),
        raw=text[:300],
    )


def collect_notes(doc: ParsedDocument) -> list[tuple[str | None, str]]:
    """Hujjatdagi barcha tahrir izohlarini `(o'ralgan modda, matn)` ko'rinishida.

    Uchta manba: parser ajratgan hujjat darajasidagi eslatmalar, modda
    darajasidagi eslatmalar va **modda tanasi ichidagi** qavsli qatorlar.
    Uchinchisi eng katta manba — o'lchov modul docstringida.
    """
    out: list[tuple[str | None, str]] = []
    seen: set[str] = set()

    for note in doc.amendments:
        if note.raw_text not in seen:
            seen.add(note.raw_text)
            out.append((note.target_article, note.raw_text))

    for element in doc.articles:
        for note in element.amendments:
            if note.raw_text not in seen:
                seen.add(note.raw_text)
                out.append((element.article_number, note.raw_text))
        for line in element.body.split("\n"):
            line = line.strip()
            if _NOTE_LINE.match(line) and line not in seen:
                seen.add(line)
                out.append((element.article_number, line))

    return out


# --------------------------------------------------------------------------- #
# Modda versiyasi
# --------------------------------------------------------------------------- #


class ArticleVersion(BaseModel):
    """Bitta moddaning versiya holati."""

    article: str
    valid_from: str | None = None
    valid_to: str | None = None
    status: str = "in_force"
    amended_by: list[str] = Field(default_factory=list)
    note_count: int = 0
    pending_from: str | None = Field(default=None, description="Hali kuchga kirmagan tahrir sanasi")


class VersionReport(BaseModel):
    """Hujjat bo'yicha versiyalash natijasi."""

    doc_id: str
    versions: dict[str, ArticleVersion] = Field(default_factory=dict)
    repealed_absent: list[str] = Field(
        default_factory=list, description="Bekor qilingan va matnda yo'q moddalar"
    )
    notes_seen: int = 0
    notes_parsed: int = 0
    warnings: list[str] = Field(default_factory=list)

    @property
    def dated(self) -> int:
        return sum(1 for v in self.versions.values() if v.valid_from or v.valid_to)


def build_versions(doc: ParsedDocument, *, today: date | None = None) -> VersionReport:
    """Hujjatdagi izohlardan modda versiyalarini quradi (elementlarga tegmaydi)."""
    now = (today or date.today()).isoformat()
    report = VersionReport(doc_id=doc.doc_id)
    present = {a.article_number for a in doc.articles if a.article_number}

    for fallback, text in collect_notes(doc):
        report.notes_seen += 1
        signal = parse_note(text, fallback)
        if signal is None:
            continue
        report.notes_parsed += 1

        if signal.effective_date is None:
            report.warnings.append(f"Sana topilmadi: {signal.raw[:90]}")

        for number in signal.articles:
            version = report.versions.setdefault(number, ArticleVersion(article=number))
            version.note_count += 1
            if signal.amending_doc and signal.amending_doc not in version.amended_by:
                version.amended_by.append(signal.amending_doc)

            if signal.kind == "repealed" and signal.scope == "article":
                _apply_repeal(version, signal.effective_date, now)
            else:
                _apply_edition(version, signal.effective_date, now)

    report.repealed_absent = sorted(
        n for n, v in report.versions.items() if v.valid_to and n not in present
    )
    return report


def _apply_repeal(version: ArticleVersion, when: str | None, now: str) -> None:
    """Bekor qilish: `valid_to` eng **erta** sana bo'ladi.

    Bir moddaga bir necha bekor qilish izohi kelsa, norma birinchisida
    to'xtaydi — keyingilari uni «tiriltirmaydi».
    """
    if when is None:
        # Sana yo'q, lekin bekor qilingani aniq: hozirdan boshlab amalda emas.
        # Bu yerda taxmin qilinmaydi — `valid_to` bo'sh qoladi, faqat holat
        # o'zgaradi va tekshiruv buni ogohlantirish sifatida ko'radi.
        version.status = "repealed"
        return
    if version.valid_to is None or when < version.valid_to:
        version.valid_to = when
    if version.valid_to <= now:
        version.status = "repealed"


def _apply_edition(version: ArticleVersion, when: str | None, now: str) -> None:
    """Tahrir: `valid_from` eng **oxirgi** kuchga kirgan sana bo'ladi.

    Kelajakdagi sana `pending_from` ga yoziladi — matndagi versiya hali
    eskisi, shuning uchun uni `valid_from` ga qo'yish moddani bugungi
    qidiruvdan chiqarib yuborardi (modul docstringidagi 3-tuzoq).
    """
    if when is None:
        return
    if when > now:
        if version.pending_from is None or when < version.pending_from:
            version.pending_from = when
        return
    if version.valid_from is None or when > version.valid_from:
        version.valid_from = when


# --------------------------------------------------------------------------- #
# Qo'llash
# --------------------------------------------------------------------------- #


def apply_versions(doc: ParsedDocument, *, today: date | None = None) -> ParsedDocument:
    """Versiya maydonlarini hujjat elementlariga yozadi.

    Hujjat **joyida** o'zgartiriladi va o'zi qaytariladi (7000 modda uchun
    nusxa olish ortiqcha). Chunker bu maydonlarni `Chunk` ga ko'chiradi.
    """
    report = build_versions(doc, today=today)

    for element in doc.articles:
        version = report.versions.get(element.article_number or "")
        if version is None:
            continue
        element.valid_from = version.valid_from
        element.valid_to = version.valid_to
        element.status = "repealed" if version.status == "repealed" else "in_force"
        element.amended_by = list(version.amended_by)

    if report.repealed_absent:
        doc.warnings.append(
            f"{len(report.repealed_absent)} ta bekor qilingan modda matnda yo'q "
            f"(masalan {report.repealed_absent[:3]})"
        )
    undated = len(report.warnings)
    if undated:
        doc.warnings.append(f"{undated} ta tahrir izohida sana topilmadi")

    log.debug("%s: %d izoh → %d modda versiyalandi", doc.doc_id, report.notes_seen, report.dated)
    return doc
