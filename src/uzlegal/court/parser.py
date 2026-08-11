"""Sud qarorini strukturaga ajratish.

## Nima uchun regex, model emas

Sud qarori — **qat'iy shakldagi** hujjat. Uning tuzilishi protsessual
kodekslarda belgilangan: kirish qismi, tavsiflovchi qism (ANIQLADI),
asoslovchi qism va rezolyutiv qism (HUKM QILDI / QAROR QILDI). Bu
tuzilma o'zgarmaydi va uni ajratish uchun model kerak emas.

Model ishlatish bu yerda ikki marta yutqazadi: u sekin va u **o'ylab
topishi mumkin**. Sud qarorida sudya ismini yoki ish raqamini xato
ajratish — tahlilning butun natijasini yaroqsiz qiladi. Regex esa
topolmasa `None` qaytaradi va bu holat ochiq ko'rinadi.

## Nima ajratilmaydi

Matn ma'nosi bo'yicha hech narsa xulosa qilinmaydi: «dalil yetarlimi»,
«jazo adolatlimi» degan savollarga bu modul javob bermaydi. U faqat
**nima yozilganini** ajratadi; baho `analyzer.py` da beriladi va u ham
deterministik qoidalarga tayanadi.

## Topilmagan maydon

Har bir maydon `None` yoki bo'sh bo'lishi mumkin va bu **xato emas** —
qarorlarning shakli turlicha. Topilmagan majburiy element `warnings` ga
yoziladi va `analyzer` uni protsessual buzilish sifatida ko'radi.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import canonical, expand_article_run, extract_date, fold
from uzlegal.types import Citation


class DecisionKind(StrEnum):
    HUKM = "hukm"  # jinoyat ishi bo'yicha
    QAROR = "qaror"  # fuqarolik / iqtisodiy ish
    AJRIM = "ajrim"  # oraliq protsessual hujjat
    NOMALUM = "nomalum"


class PenaltyKind(StrEnum):
    OZODLIKDAN_MAHRUM = "ozodlikdan_mahrum"
    OZODLIKNI_CHEKLASH = "ozodlikni_cheklash"
    AXLOQ_TUZATISH = "axloq_tuzatish"
    JARIMA = "jarima"
    JAMOAT_ISHLARI = "jamoat_ishlari"
    UNDIRUV = "undiruv"  # fuqarolik ishida pul undirish
    NOMALUM = "nomalum"


class Party(BaseModel):
    role: str
    name: str


class Penalty(BaseModel):
    kind: PenaltyKind = PenaltyKind.NOMALUM
    amount: float | None = None
    unit: str | None = None
    suspended: bool = False
    raw: str = ""


class CourtDecision(BaseModel):
    kind: DecisionKind = DecisionKind.NOMALUM
    case_number: str | None = None
    court: str | None = None
    judge: str | None = None
    decided_at: str | None = None
    hearing_at: str | None = None

    parties: list[Party] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    law_references: list[Citation] = Field(default_factory=list)

    circumstances: str = ""
    reasoning: str = ""
    conclusion: str = ""
    penalty: Penalty | None = None

    sections: dict[str, str] = Field(default_factory=dict)
    appeal_note: str = ""
    warnings: list[str] = Field(default_factory=list)
    raw: str = ""

    def party(self, role: str) -> Party | None:
        return next((p for p in self.parties if p.role == role), None)

    def has_role(self, *roles: str) -> bool:
        present = {p.role for p in self.parties}
        return any(r in present for r in roles)

    def cites(self, code_fragment: str) -> bool:
        needle = fold(code_fragment)
        return any(needle in fold(c.doc_title or c.doc_id) for c in self.law_references)

    @property
    def is_criminal(self) -> bool:
        return self.kind is DecisionKind.HUKM or self.cites("jinoyat kodeksi")


# --------------------------------------------------------------------------- #
# Bo'limlar
# --------------------------------------------------------------------------- #

# Rezolyutiv qism sarlavhalari protsessual kodekslarda belgilangan va
# amalda deyarli o'zgarmaydi. Kirill variantlari ham qo'shilgan: eski
# qarorlar hamon kirill yozuvida keladi.
_SECTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "circumstances": ("aniqladi", "topdi", "установил", "aniqlandi"),
    "reasoning": ("asoslar", "sud xulosalari", "мотивировочная", "sud fikricha"),
    "conclusion": (
        "hukm qildi",
        "qaror qildi",
        "ajrim qildi",
        "hal qildi",
        "приговорил",
        "решил",
        "определил",
    ),
}

_HEADING_RE = re.compile(r"(?m)^\s*([A-ZЎҚҒҲА-Я][A-ZЎҚҒҲА-Я'ʻʼ\s]{3,40}?)\s*:?\s*$")


def split_sections(text: str) -> dict[str, str]:
    lines = text.splitlines()
    marks: list[tuple[int, str]] = []

    for i, line in enumerate(lines):
        if not _HEADING_RE.match(line):
            continue
        folded = fold(line).strip().rstrip(":").strip()
        for name, variants in _SECTION_HEADINGS.items():
            if any(folded == fold(v) or folded.startswith(fold(v)) for v in variants):
                marks.append((i, name))
                break

    if not marks:
        return {}

    sections: dict[str, str] = {}
    # Sarlavhadan oldingi matn — kirish qismi (sud, sudya, tomonlar).
    sections["intro"] = "\n".join(lines[: marks[0][0]]).strip()
    for pos, (start, name) in enumerate(marks):
        end = marks[pos + 1][0] if pos + 1 < len(marks) else len(lines)
        sections[name] = "\n".join(lines[start + 1 : end]).strip()
    return sections


# --------------------------------------------------------------------------- #
# Kirish qismi maydonlari
# --------------------------------------------------------------------------- #

_CASE_NUMBER = re.compile(
    r"(?:ish\w*\s*(?:raqami|№|N)|№|дело\s*№)\s*[:\-]?\s*([0-9][0-9A-Za-z\-/№.]{2,30})",
    re.IGNORECASE,
)

_COURT = re.compile(
    r"([A-ZЎҚҒҲA-Za-zʻʼ'\-\s]{4,60}?(?:tumanlararo|tuman|shahar|viloyat|respublika)"
    r"[A-Za-zʻʼ'\-\s]{0,40}?sudi)",
    re.IGNORECASE,
)

# Ism-sharif: «Karimov A.B.» yoki «Karimov Alisher Baxtiyorovich».
#
# Ikki nozik joy:
#   * bo'shliq `[^\S\n]` — ism satr chegarasidan **oshmasligi** kerak,
#     aks holda keyingi qatordagi rol nomi ismga yopishib qoladi;
#   * bosh harf talabi qat'iy va shuning uchun `re.IGNORECASE`
#     ishlatilmaydi — u bo'lsa «guvoh koʻrsatuvlari» ham ism sifatida
#     tushunilardi. Rol nomi esa `(?i:…)` bilan alohida yumshatiladi.
_SP = r"[^\S\n]"
_NAME = (
    rf"[A-ZЎҚҒҲ][a-zʻʼ']+"
    rf"(?:{_SP}+[A-ZЎҚҒҲ]\.{_SP}*[A-ZЎҚҒҲ]\.|{_SP}+[A-ZЎҚҒҲ][a-zʻʼ']+){{0,2}}"
)

_JUDGE = re.compile(
    rf"(?i:sudya\w*|raislik{_SP}+qiluvchi|раислик|судья){_SP}*[:\-]?{_SP}*({_NAME})"
)

_ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("sudlanuvchi", r"sudlanuvchi"),
    ("ayblanuvchi", r"ayblanuvchi"),
    ("jabrlanuvchi", r"jabrlanuvchi"),
    ("davogar", r"da[ʼ'`]?vogar|истец"),
    ("javobgar", r"javobgar|ответчик"),
    ("prokuror", r"prokuror|прокурор"),
    ("himoyachi", r"himoyachi|advokat|защитник"),
    ("tarjimon", r"tarjimon|переводчик"),
    ("guvoh", r"guvoh"),
)


def extract_parties(text: str) -> list[Party]:
    out: list[Party] = []
    seen: set[tuple[str, str]] = set()

    for role, pattern in _ROLE_PATTERNS:
        for match in re.finditer(rf"(?i:{pattern}){_SP}*[:\-—]?{_SP}*({_NAME})", text):
            name = match.group(1).strip()
            key = (role, fold(name))
            if key not in seen:
                seen.add(key)
                out.append(Party(role=role, name=name))
    return out


# --------------------------------------------------------------------------- #
# Qonun havolalari
# --------------------------------------------------------------------------- #

_CODE_NAMES: tuple[str, ...] = (
    "jinoyat-protsessual kodeksi",
    "fuqarolik protsessual kodeksi",
    "iqtisodiy protsessual kodeksi",
    "jinoyat-ijroiya kodeksi",
    "jinoyat kodeksi",
    "fuqarolik kodeksi",
    "mehnat kodeksi",
    "oila kodeksi",
    "soliq kodeksi",
    "yer kodeksi",
    "uy-joy kodeksi",
    "bojxona kodeksi",
    "budjet kodeksi",
    "maʼmuriy javobgarlik toʻgʻrisidagi kodeks",
)

# «Jinoyat kodeksining 169-moddasi 2-qismi» · «JK 169-modda» ·
# «ushbu Kodeksning 45 va 46-moddalari»
_LAW_REF = re.compile(
    r"([A-Za-zʻʼ'\-\s]{3,60}?kodeks\w*|\bJK\b|\bFK\b|\bJPK\b|\bFPK\b|\bMK\b|\bMJTK\b)"
    r"[a-zʻʼ'\s]{0,12}?"
    r"((?:\d{1,4}(?:\s*[-–]\s*\d{1,3})?[\s,va]{0,6}){1,8})\s*[-–]\s*moddas?\w*"
    r"(?:\s*(\d{1,2})\s*[-–]\s*qism\w*)?",
    re.IGNORECASE,
)

_ABBREVIATIONS: dict[str, str] = {
    "jk": "jinoyat kodeksi",
    "fk": "fuqarolik kodeksi",
    "jpk": "jinoyat-protsessual kodeksi",
    "fpk": "fuqarolik protsessual kodeksi",
    "mk": "mehnat kodeksi",
    "mjtk": "maʼmuriy javobgarlik toʻgʻrisidagi kodeks",
}


def _resolve_code(raw: str) -> str | None:
    folded = fold(raw).strip()
    if folded in _ABBREVIATIONS:
        return _ABBREVIATIONS[folded]
    # Eng uzun moslik oldin: «jinoyat-protsessual kodeksi» «jinoyat
    # kodeksi» dan oldin tekshirilishi kerak, aks holda u noto'g'ri
    # kodeksga bog'lanadi.
    for name in sorted(_CODE_NAMES, key=len, reverse=True):
        if fold(name) in folded:
            return name
    return None


def extract_law_references(text: str) -> list[Citation]:
    out: list[Citation] = []
    seen: set[tuple[str, str, str]] = set()

    for match in _LAW_REF.finditer(text):
        code = _resolve_code(match.group(1))
        if code is None:
            continue
        part = match.group(3)
        for article in expand_article_run(match.group(2)):
            key = (code, article, part or "")
            if key in seen:
                continue
            seen.add(key)
            out.append(
                Citation(
                    tag=f"L{len(out) + 1}",
                    doc_id=fold(code).replace(" ", "-"),
                    doc_title=code,
                    doc_type="kodeks",
                    article=article,
                    part=part,
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Dalillar
# --------------------------------------------------------------------------- #

_EVIDENCE_MARKERS = re.compile(
    r"\b(guvoh\w*\s+ko[ʻ']?rsatuv\w*|ko[ʻ']?rsatuv\w*|ekspert\w*\s+xulosa\w*|xulosa\w*|"
    r"protokol\w*|hujjat\w*|dalil\w*|ashyoviy\s+dalil\w*|videoyozuv\w*|audioyozuv\w*|"
    r"tekshiruv\s+bayonnoma\w*|surishtiruv\s+materiallar\w*)\b",
    re.IGNORECASE,
)


def extract_evidence(text: str) -> list[str]:
    out: list[str] = []
    for raw_line in re.split(r"[\n;]|(?<=[.!?])\s+", text):
        line = raw_line.strip(" -–—•\t")
        if len(line) < 15 or not _EVIDENCE_MARKERS.search(line):
            continue
        if line not in out:
            out.append(line)
    return out


# --------------------------------------------------------------------------- #
# Jazo
# --------------------------------------------------------------------------- #

_PENALTY_PATTERNS: tuple[tuple[PenaltyKind, str], ...] = (
    (PenaltyKind.OZODLIKDAN_MAHRUM, r"ozodlikdan\s+mahrum\s+qil\w*"),
    (PenaltyKind.OZODLIKNI_CHEKLASH, r"ozodlikni\s+cheklash"),
    (PenaltyKind.AXLOQ_TUZATISH, r"axloq\s+tuzatish\s+ishlar\w*"),
    (PenaltyKind.JAMOAT_ISHLARI, r"majburiy\s+jamoat\s+ishlar\w*"),
    (PenaltyKind.JARIMA, r"jarima"),
    (PenaltyKind.UNDIRUV, r"undiril\w*|undirib\s+beril\w*"),
)

_TERM = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(yil|oy|kun|foiz|%|baravar|barobar|BHM|bazaviy\s+hisoblash\s+miqdor\w*|so[ʻ']?m)",
    re.IGNORECASE,
)

_SUSPENDED = re.compile(
    r"shartli\s+ravishda|shartli\s+hukm|jazoni\s+o[ʻ']?tashdan\s+ozod", re.IGNORECASE
)


def extract_penalty(text: str) -> Penalty | None:
    if not text.strip():
        return None

    kind = PenaltyKind.NOMALUM
    for candidate, pattern in _PENALTY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            kind = candidate
            break
    if kind is PenaltyKind.NOMALUM:
        return None

    amount: float | None = None
    unit: str | None = None
    term = _TERM.search(text)
    if term:
        amount = float(term.group(1).replace(",", "."))
        unit = fold(term.group(2))

    return Penalty(
        kind=kind,
        amount=amount,
        unit=unit,
        suspended=bool(_SUSPENDED.search(text)),
        raw=text.strip()[:300],
    )


# --------------------------------------------------------------------------- #
# Asosiy kirish nuqtasi
# --------------------------------------------------------------------------- #

_KIND_MARKERS: tuple[tuple[DecisionKind, str], ...] = (
    (DecisionKind.HUKM, r"\bhukm\b|приговор"),
    (DecisionKind.QAROR, r"\bqaror\b|решение"),
    (DecisionKind.AJRIM, r"\bajrim\b|определение"),
)

_APPEAL_NOTE = re.compile(
    r"[^.\n]{0,160}(?:apellyatsiya|kassatsiya|shikoyat)[^.\n]{0,160}\.", re.IGNORECASE
)

# Kirish qismida ikkinchi sana odatda sud majlisi sanasi bo'ladi.
_HEARING_HINT = re.compile(
    r"[^.\n]{0,120}(?:majlis\w*|yig[ʻ']?ilish\w*)[^.\n]{0,120}", re.IGNORECASE
)

_REQUIRED = ("case_number", "court", "judge", "conclusion")


def parse(text: str) -> CourtDecision:
    normalized = canonical(text)
    sections = split_sections(normalized)
    intro = sections.get("intro") or normalized[:1500]
    conclusion = sections.get("conclusion", "")

    kind = DecisionKind.NOMALUM
    head = fold(normalized[:400])
    for candidate, pattern in _KIND_MARKERS:
        if re.search(pattern, head, re.IGNORECASE):
            kind = candidate
            break

    case_number = _CASE_NUMBER.search(normalized)
    court = _COURT.search(intro)
    judge = _JUDGE.search(intro)
    hearing = _HEARING_HINT.search(intro)

    decision = CourtDecision(
        kind=kind,
        case_number=case_number.group(1).strip() if case_number else None,
        court=re.sub(r"\s+", " ", court.group(1)).strip() if court else None,
        judge=judge.group(1).strip() if judge else None,
        decided_at=extract_date(intro),
        hearing_at=extract_date(hearing.group(0)) if hearing else None,
        parties=extract_parties(intro + "\n" + sections.get("circumstances", "")),
        evidence=extract_evidence(
            sections.get("circumstances", "") + "\n" + sections.get("reasoning", "")
        ),
        law_references=extract_law_references(normalized),
        circumstances=sections.get("circumstances", ""),
        reasoning=sections.get("reasoning", ""),
        conclusion=conclusion,
        penalty=extract_penalty(conclusion),
        sections=sections,
        raw=normalized,
    )

    appeal = _APPEAL_NOTE.search(conclusion or normalized)
    decision.appeal_note = appeal.group(0).strip() if appeal else ""

    decision.warnings = [
        f"«{field}» ajratilmadi" for field in _REQUIRED if not getattr(decision, field)
    ]
    if not sections:
        decision.warnings.append("hujjat bo'limlarga ajralmadi — shakl notanish")

    return decision
