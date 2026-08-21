"""Groundedness gate — javobning oxirgi to'sig'i (docs/01 § 6).

## Nima uchun bu model emas

Gate — **deterministik tekshiruv**. Agar u model bo'lganida, hallucination ni
tekshirish uchun hallucination qila oladigan narsadan foydalangan bo'lardik.
Shu sababli bu yerda faqat qoidalar: belgi bormi, belgi haqiqiy chunkka
bog'lanadimi, iqtibos matni da'vo bilan umumiy leksikaga egami.

## Nima uchun gate faqat olib tashlaydi

Gate javobni **hech qachon qayta yozmaydi va yangi matn generatsiya
qilmaydi**. Sabab oddiy: qayta yozgan zahoti u o'zi hallucination manbaiga
aylanadi va uni tekshiradigan hech kim qolmaydi. Shuning uchun ruxsat etilgan
yagona harakat — segmentni chiqarib tashlash.

Ikkita istisno bor va ikkalasi ham **doimiy shablon**, generatsiya emas:

* qo'llab-quvvatlanmagan da'voga `⚠ noaniq` belgisi qo'yiladi (docs/01 § 6
  dagi `FLAG` tugmasi)
* barcha huquqiy da'vo o'chirilsa — rad javobi va topilgan manbalar ro'yxati
  (docs/06 § 8 dagi oxirgi qator)

## Nima uchun umumiy da'vo qoladi

"Bu masalada qo'shimcha hujjat kerak" degan gapga iqtibos talab qilish
javobni o'qib bo'lmaydigan holga keltiradi. Iqtibos **huquqiy da'vo** uchun
majburiy: norma mazmuni, huquq, majburiyat, muddat, javobgarlik haqidagi
bayonlar. Mantiqiy bog'lovchi va protsessual maslahat — qolaveradi.
"""

from __future__ import annotations

import logging
import re
from enum import StrEnum

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import fold
from uzlegal.ingest.types import unit_label
from uzlegal.orchestrator import document, quantity
from uzlegal.orchestrator.text import content_words
from uzlegal.types import Citation

log = logging.getLogger(__name__)

# Iqtibos matni da'voni qo'llab-quvvatlaydimi — leksik qoplama chegarasi.
# Past qo'yilgan (0.2): bu bosqichning vazifasi mutlaqo boshqa mavzudagi
# iqtibosni tutish, semantik nozikliklarni emas. Yuqori chegara to'g'ri
# iqtiboslarni ham "noaniq" deb belgilab, javobni ishonchsiz ko'rsatardi.
SUPPORT_THRESHOLD = 0.2
MIN_SUPPORT_WORDS = 3

REFUSAL = "Ishonchli javob shakllantirilmadi."
REFUSAL_NOTE = (
    "Javobdagi huquqiy da'volarning hech biri berilgan manbalarga bog'lanmadi, "
    "shuning uchun ular chiqarib tashlandi."
)
UNCERTAIN_MARK = "⚠ noaniq"

_TAG_RE = re.compile(r"\[\s*(C\d{1,3})\s*\]", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*(?:[-*•–—]\s+|\d{1,2}[.)]\s+)")
_HEADING_RE = re.compile(r"^[A-ZЎҚҒҲ'‘’ʻʼ \-]{3,40}:?$")
# Gap chegarasi. Raqamdan keyingi nuqta ("0.84", "1.") bo'linmaydi —
# yuridik matnda raqam va sana ko'p.
_SENTENCE_SPLIT = re.compile(r"(?<![0-9])(?<=[.!?…])\s+")

# Huquqiy da'vo alomatlari. Ro'yxat ataylab **tor**: noto'g'ri "huquqiy" deb
# belgilash foydali gapni o'chiradi, noto'g'ri "umumiy" deb belgilash esa
# iqtibossiz gapni qoldiradi. Ikkinchisi kamroq zarar — chunki bunday gapda
# norma haqida hech narsa aytilmagan.
_LEGAL_MARKERS = re.compile(
    r"\b("
    r"modda\w*|kodeks\w*|qonun\w*|farmon\w*|nizom\w*|plenum\w*|band\w*|qism\w*|"
    r"norma\w*|qaror\w*|hujjat\w*|"
    r"huquq\w*|majburiyat\w*|javobgar\w*|jarima\w*|sanksiya\w*|sanktsiya\w*|"
    r"da'vo\w*|sud\w*|shartnoma\w*|mulk\w*|meros\w*|nafaqa\w*|soliq\w*|"
    r"muddat\w*|ariza\w*|shikoyat\w*|apellyatsiya\w*|kassatsiya\w*|"
    r"belgilan\w*|nazarda\s+tutil\w*|taqiqlan\w*|ruxsat\s+etil\w*|"
    r"majbur\w*|haqli\w*|bekor\s+qilin\w*|amal\s+qilad\w*"
    r")\b"
)


class ClaimKind(StrEnum):
    LEGAL = "legal"
    GENERAL = "general"


class ClaimStatus(StrEnum):
    KEPT = "kept"
    FLAGGED = "flagged"
    DROPPED = "dropped"


class DropReason(StrEnum):
    NO_CITATION = "iqtibossiz huquqiy da'vo"
    UNKNOWN_CITATION = "iqtibos indeksda topilmadi"
    UNSUPPORTED = "iqtibos matni da'voni qo'llab-quvvatlamaydi"
    WRONG_ARTICLE = "da'vodagi modda raqami iqtibosga mos kelmaydi"
    WRONG_QUANTITY = "da'vodagi miqdor iqtibos matniga zid"
    WRONG_DOCUMENT = "da'voda boshqa hujjat nomlangan"


class ClaimCheck(BaseModel):
    """Bitta da'vo va u haqidagi qaror — trace ga to'liq yoziladi."""

    text: str
    kind: ClaimKind
    status: ClaimStatus
    tags: list[str] = Field(default_factory=list)
    reason: DropReason | None = None

    @property
    def is_legal(self) -> bool:
        return self.kind is ClaimKind.LEGAL


class GateReport(BaseModel):
    """Gate natijasi.

    `answer` — foydalanuvchiga ketadigan matn. Boshqa hamma narsa audit
    uchun: yuridik tizimda "nima uchun bu gap yo'q?" savoliga javob berish
    kerak bo'ladi.
    """

    answer: str
    refused: bool = False
    checks: list[ClaimCheck] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    @property
    def claims(self) -> int:
        return len(self.checks)

    @property
    def kept(self) -> int:
        return sum(1 for c in self.checks if c.status is not ClaimStatus.DROPPED)

    @property
    def dropped(self) -> int:
        return sum(1 for c in self.checks if c.status is ClaimStatus.DROPPED)

    @property
    def flagged(self) -> int:
        return sum(1 for c in self.checks if c.status is ClaimStatus.FLAGGED)

    @property
    def kept_legal(self) -> int:
        return sum(1 for c in self.checks if c.is_legal and c.status is not ClaimStatus.DROPPED)

    @property
    def drop_reasons(self) -> list[str]:
        seen: list[str] = []
        for check in self.checks:
            if check.reason and check.reason.value not in seen:
                seen.append(check.reason.value)
        return seen

    def summary(self) -> dict[str, int]:
        return {"claims": self.claims, "kept": self.kept, "dropped": self.dropped}


# --------------------------------------------------------------------------- #
# Da'volarga ajratish
# --------------------------------------------------------------------------- #


class Segment(BaseModel):
    """Javobning bitta bo'lagi.

    Sarlavha va bo'sh satr ham segment: ularsiz javobni asl tuzilishida
    qayta yig'ib bo'lmaydi, gate esa tuzilishni o'zgartirmasligi kerak.
    """

    text: str
    is_claim: bool
    is_heading: bool = False
    prefix: str = ""


def split_claims(answer: str) -> list[Segment]:
    """Javobni tekshiriladigan da'volarga ajratadi.

    Ikki darajali: avval satr (ro'yxat elementi = bitta da'vo), keyin gap.
    Yuridik javobda ro'yxat ustun shakl, shuning uchun satr chegarasi gap
    chegarasidan ishonchliroq.
    """
    segments: list[Segment] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            segments.append(Segment(text="", is_claim=False))
            continue
        if _HEADING_RE.match(line):
            segments.append(Segment(text=line, is_claim=False, is_heading=True))
            continue

        bullet = _BULLET_RE.match(line)
        if bullet:
            prefix = bullet.group(0)
            body = line[bullet.end() :].strip()
            segments.append(Segment(text=body, is_claim=bool(body), prefix=prefix))
            continue

        for sentence in _SENTENCE_SPLIT.split(line):
            sentence = sentence.strip()
            if sentence:
                segments.append(Segment(text=sentence, is_claim=True))
    return segments


def is_legal_claim(text: str) -> bool:
    """Da'vo huquqiymi — iqtibos majburiyati shunga bog'liq.

    Iqtibos belgisining o'zi ham alomat: model normaga havola qilgan bo'lsa,
    u huquqiy da'vo qilmoqda.
    """
    if _TAG_RE.search(text):
        return True
    return bool(_LEGAL_MARKERS.search(fold(text)))


def claim_tags(text: str) -> list[str]:
    out: list[str] = []
    for m in _TAG_RE.finditer(text):
        tag = m.group(1).upper()
        if tag not in out:
            out.append(tag)
    return out


# --------------------------------------------------------------------------- #
# Iqtibos da'voni qo'llab-quvvatlaydimi
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Modda raqami mosligi
# --------------------------------------------------------------------------- #

# "106-modda", "106-moddasiga", "130-131-modda", "Статья 106", "st. 106"
_ARTICLE_RE = re.compile(
    r"(\d+(?:\s*[-–]\s*\d+)?)\s*[-–]\s*modda\w*"
    r"|(\d+(?:\s*[-–]\s*\d+)?)\s*[-–]\s*модда\w*"
    r"|(?:статья|ст\.)\s*(\d+)",
    re.IGNORECASE,
)


def article_numbers(text: str) -> set[str]:
    """Matnda tilga olingan modda raqamlari.

    Diapazon («130-131-modda») ikkala chekka raqam sifatida qaytadi —
    iqtibosda diapazon, da'voda esa bitta raqam bo'lishi normal holat.
    """
    out: set[str] = set()
    for match in _ARTICLE_RE.finditer(text):
        raw = next((g for g in match.groups() if g), None)
        if raw:
            out.update(part.strip() for part in re.split(r"[-–]", raw) if part.strip())
    return out


def cited_article_numbers(citation: Citation) -> set[str]:
    """Iqtibos qamrab oladigan modda raqamlari.

    `article` maydonidan tashqari **parcha matni** ham qaraladi: yuridik
    normalar bir-biriga havola qiladi («228-moddada nazarda tutilgan
    tartibda…»), va bunday havolani da'voda takrorlash to'g'ri. Faqat
    manbada umuman uchramaydigan raqam o'ylab topilgan hisoblanadi.
    """
    # `article` maydonida «modda» so'zi bo'lmaydi — u sof raqam yoki
    # diapazon («130-131»). Shuning uchun undagi barcha raqamlar
    # to'g'ridan-to'g'ri olinadi, `article_numbers()` orqali emas.
    numbers = set(re.findall(r"\d+", citation.article or ""))
    if citation.excerpt:
        numbers |= article_numbers(citation.excerpt)
    return {n.strip() for n in numbers if n.strip().isdigit()}


def has_invented_article(claim: str, citations: list[Citation]) -> bool:
    """Da'voda manbada umuman yo'q modda raqami bormi.

    ## Nima uchun bu tekshiruv alohida kerak

    `support_score()` leksik qoplama bo'yicha ishlaydi va u modda
    RAQAMIGA sezgir emas: «Mehnat kodeksining 106-moddasiga ko'ra sinov
    muddati uch oydan ortiq bo'lmasligi kerak [C1]» degan javobda
    so'zlarning katta qismi manbaga mos keladi, shuning uchun qoplama
    yuqori chiqadi — holbuki C1 aslida **130-131-modda** va 106 raqami
    o'ylab topilgan.

    Amalda kuzatildi (gemma3-12b, 2026-08-12): javob to'g'ri normani
    keltirdi, lekin uni NOTO'G'RI modda raqamiga bog'ladi. Foydalanuvchi
    uchun bu eng yomon xato turi — javob ishonchli ko'rinadi, havola bor,
    lekin havola boshqa moddaga olib boradi.

    Leksik qoplamadan farqli o'laroq bu tekshiruv **aniq**: raqam yo bor,
    yo yo'q. Shuning uchun natija «belgilash» emas, **o'chirish** —
    xuddi iqtibossiz da'vo kabi.
    """
    claimed = article_numbers(claim)
    if not claimed:
        return False
    available: set[str] = set()
    for citation in citations:
        available |= cited_article_numbers(citation)
    if not available:
        # Iqtibosda modda raqami umuman yo'q — tekshirib bo'lmaydi.
        # Tekshirib bo'lmaydigan narsani jazolash to'g'ri javoblarni
        # ham o'chirardi (`support_score()` dagi bilan bir xil mantiq).
        return False
    return not (claimed & available)


def support_score(claim: str, citation: Citation) -> float | None:
    """Da'vo va iqtibos matni o'rtasidagi leksik qoplama (0…1).

    Manba matni yo'q bo'lsa `None` — bu "qo'llab-quvvatlamaydi" degani emas,
    "tekshirib bo'lmaydi" degani. Tekshirib bo'lmaydigan narsani jazolash
    to'g'ri javoblarni ham o'chirardi.
    """
    source = " ".join(filter(None, [citation.excerpt, citation.doc_title, citation.article]))
    if not source.strip():
        return None
    claim_words = content_words(claim)
    if len(claim_words) < MIN_SUPPORT_WORDS:
        return None
    return len(claim_words & content_words(source)) / len(claim_words)


# --------------------------------------------------------------------------- #
# Gate
# --------------------------------------------------------------------------- #


def groundedness_gate(
    answer: str,
    citations: list[Citation],
    *,
    verify_support: bool = True,
    support_threshold: float = SUPPORT_THRESHOLD,
) -> GateReport:
    """Javobni tekshiradi va **faqat olib tashlash** yo'li bilan tozalaydi.

    Qadamlar docs/01 § 6 diagrammasi bilan bir xil tartibda:
    da'volarga ajratish → iqtibos bormi → iqtibos haqiqiymi → matn
    qo'llab-quvvatlaydimi → qayta yig'ish → huquqiy da'vo qoldimi.
    """
    known = {c.tag.upper(): c for c in citations}
    segments = split_claims(answer)
    checks: list[ClaimCheck] = []
    used: list[str] = []
    kept_texts: list[str | None] = []

    for segment in segments:
        if not segment.is_claim:
            kept_texts.append(None if segment.is_heading or not segment.text else segment.text)
            continue

        check = _check_claim(
            segment.text,
            known,
            verify_support=verify_support,
            support_threshold=support_threshold,
        )
        checks.append(check)

        if check.status is ClaimStatus.DROPPED:
            kept_texts.append(None)
            continue

        used.extend(t for t in check.tags if t in known and t not in used)
        text = segment.text
        if check.status is ClaimStatus.FLAGGED:
            text = f"{text} [{UNCERTAIN_MARK}]"
        kept_texts.append(segment.prefix + text)

    report = GateReport(
        answer="",
        checks=checks,
        citations=[known[t] for t in used],
    )

    if report.kept_legal == 0:
        report.refused = True
        report.answer = _refusal_text(citations)
        report.citations = list(citations)
        return report

    report.answer = _reassemble(segments, kept_texts)
    return report


def _check_claim(
    text: str,
    known: dict[str, Citation],
    *,
    verify_support: bool,
    support_threshold: float,
) -> ClaimCheck:
    tags = claim_tags(text)
    kind = ClaimKind.LEGAL if is_legal_claim(text) else ClaimKind.GENERAL

    if not tags:
        # Umumiy/mantiqiy da'vo iqtibossiz qoladi — docs/01 § 6 dagi KEEP1.
        if kind is ClaimKind.GENERAL:
            return ClaimCheck(text=text, kind=kind, status=ClaimStatus.KEPT)
        return ClaimCheck(
            text=text, kind=kind, status=ClaimStatus.DROPPED, reason=DropReason.NO_CITATION
        )

    resolved = [known[t] for t in tags if t in known]
    if not resolved:
        # Yolg'on iqtibos: model belgini o'ylab topgan. Bu eng xavfli holat —
        # javob **ishonchliroq** ko'rinadi, lekin manba yo'q.
        return ClaimCheck(
            text=text,
            kind=kind,
            status=ClaimStatus.DROPPED,
            tags=tags,
            reason=DropReason.UNKNOWN_CITATION,
        )

    if kind is ClaimKind.LEGAL:
        # Miqdor ziddiyati — modda raqami bilan bir xil darajadagi aniq
        # tekshiruv (docs/28). Leksik qoplamadan OLDIN turadi, chunki
        # «10 yil» va «uch yil» jumlalari ko'p so'zni bo'lishadi va
        # qoplama yuqori chiqadi — farq esa aynan sonda.
        clash = quantity.contradicts(text, [c.excerpt or "" for c in resolved])
        if clash is not None:
            log.debug(
                "miqdor ziddiyati: da'vo %s %s, manba %s %s", clash[0], clash[2], clash[1], clash[2]
            )
            return ClaimCheck(
                text=text,
                kind=kind,
                status=ClaimStatus.DROPPED,
                tags=tags,
                reason=DropReason.WRONG_QUANTITY,
            )

    if kind is ClaimKind.LEGAL:
        clash_doc = document.contradicts(text, resolved)
        if clash_doc is not None:
            log.debug("hujjat ziddiyati: da'vo %s, iqtibos %s", clash_doc[0], clash_doc[1])
            return ClaimCheck(
                text=text,
                kind=kind,
                status=ClaimStatus.DROPPED,
                tags=tags,
                reason=DropReason.WRONG_DOCUMENT,
            )

    if kind is ClaimKind.LEGAL and has_invented_article(text, resolved):
        # Leksik qoplamadan OLDIN: bu tekshiruv aniq, u esa taxminiy.
        # Modda raqami o'ylab topilgan bo'lsa qoplama yuqori bo'lishining
        # ahamiyati yo'q — havola baribir boshqa normaga olib boradi.
        return ClaimCheck(
            text=text,
            kind=kind,
            status=ClaimStatus.DROPPED,
            tags=tags,
            reason=DropReason.WRONG_ARTICLE,
        )

    if verify_support and kind is ClaimKind.LEGAL:
        scores = [s for s in (support_score(text, c) for c in resolved) if s is not None]
        if scores and max(scores) < support_threshold:
            return ClaimCheck(
                text=text,
                kind=kind,
                status=ClaimStatus.FLAGGED,
                tags=tags,
                reason=DropReason.UNSUPPORTED,
            )

    return ClaimCheck(text=text, kind=kind, status=ClaimStatus.KEPT, tags=tags)


def _reassemble(segments: list[Segment], kept: list[str | None]) -> str:
    """Qolgan segmentlardan javobni asl tartibda yig'adi.

    Bo'shab qolgan sarlavha ham olib tashlanadi: "ASOSLAR" sarlavhasi ostida
    hech narsa qolmasa, u foydalanuvchini chalg'itadi.
    """
    lines: list[str] = []
    for i, segment in enumerate(segments):
        if segment.is_heading:
            if _has_content_after(segments, kept, i):
                lines.append(segment.text)
            continue
        if not segment.is_claim:
            if segment.text:
                lines.append(segment.text)
            elif lines and lines[-1] != "":
                lines.append("")
            continue
        if kept[i] is not None:
            lines.append(kept[i] or "")

    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def _has_content_after(segments: list[Segment], kept: list[str | None], start: int) -> bool:
    for i in range(start + 1, len(segments)):
        if segments[i].is_heading:
            return False
        if segments[i].is_claim and kept[i] is not None:
            return True
    return False


def _refusal_text(citations: list[Citation]) -> str:
    """Rad javobi — doimiy shablon va topilgan manbalar ro'yxati.

    Bu yerda ham generatsiya yo'q: manba nomlari indeksdan kelgan, matn esa
    o'zgarmas. Foydalanuvchi javob olmaydi, lekin qayerga qarashni biladi.
    """
    lines = [REFUSAL, "", REFUSAL_NOTE]
    if citations:
        lines += ["", "Topilgan manbalar:"]
        lines += [
            f"- [{c.tag}] {c.doc_title or c.doc_id}"
            + (f", {c.article}-{unit_label(c.doc_type)}" if c.article else "")
            + (f" — {c.url}" if c.url else "")
            for c in citations
        ]
    return "\n".join(lines)
