"""Sud qarorini tekshirish — yettita deterministik nazorat.

## Nima tekshiriladi va nima tekshirilmaydi

Bu modul **shakl va izchillikni** tekshiradi, mazmuniy adolatni emas.
U «sudya noto'g'ri qaror chiqargan» demaydi va deya olmaydi — buni
faqat yuqori instansiya sudi aytadi. U aytadigan narsa boshqacha:
qarorda protsessual kodeks talab qiladigan element yo'q, yoki qaror
o'z ichida ziddiyatli.

Farq muhim. «Jazo adolatsiz» — baho. «Jazo tayinlangan, lekin biror
qonun moddasiga havola yo'q» — **faktik kamchilik** va uni matnning
o'zidan ko'rsatish mumkin.

## Nima uchun model chaqirilmaydi

Har bir topilma qarorning aynan qaysi joyidan kelib chiqqanini
ko'rsatishi kerak. Model «menimcha dalillar yetarli emas» desa, buni
tekshirib bo'lmaydi va sudda ishlatib ham bo'lmaydi. Qoida esa
takrorlanadi: bir xil matn → bir xil topilma.

## Jiddiylik darajalari

| Daraja | Ma'nosi |
|--------|---------|
| `critical` | Qarorni bekor qilish uchun asos bo'lishi mumkin |
| `major` | O'zgartirish yoki qo'shimcha asoslash talab qiladi |
| `minor` | Rasmiylashtirish kamchiligi |
| `info` | Diqqat qaratish uchun, kamchilik emas |

Daraja **qat'iy emas**: u yurist e'tiborini yo'naltirish uchun, uning
o'rniga qaror qabul qilish uchun emas.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from uzlegal.court.parser import CourtDecision, PenaltyKind
from uzlegal.ingest.normalize import fold
from uzlegal.types import Citation


class Severity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.MINOR: 1,
    Severity.MAJOR: 2,
    Severity.CRITICAL: 3,
}


class Finding(BaseModel):
    code: str
    check: str
    severity: Severity
    description: str
    recommendation: str
    citation: Citation | None = None
    excerpt: str = ""

    @property
    def weight(self) -> int:
        return SEVERITY_ORDER[self.severity]


def _norm(code: str, article: str, part: str | None = None) -> Citation:
    return Citation(
        tag=code.upper(),
        doc_id=fold(code).replace(" ", "-"),
        doc_title=code,
        doc_type="kodeks",
        article=article,
        part=part,
    )


# Tez-tez ishlatiladigan protsessual normalar. Raqamlar amaldagi
# kodekslardan olingan; korpus yangilanganda ular tekshirilishi kerak.
JPK_HIMOYA = _norm("Jinoyat-protsessual kodeksi", "49")
JPK_DALIL = _norm("Jinoyat-protsessual kodeksi", "95")
JPK_HUKM = _norm("Jinoyat-protsessual kodeksi", "455")
JPK_TARJIMON = _norm("Jinoyat-protsessual kodeksi", "20")
JK_JAZO = _norm("Jinoyat kodeksi", "54")
FPK_QAROR = _norm("Fuqarolik protsessual kodeksi", "285")


# --------------------------------------------------------------------------- #
# 1 — Protsessual buzilish
# --------------------------------------------------------------------------- #


def check_procedural(decision: CourtDecision) -> list[Finding]:
    out: list[Finding] = []
    basis = JPK_HUKM if decision.is_criminal else FPK_QAROR

    required = (
        ("case_number", "ish raqami"),
        ("court", "sud nomi"),
        ("judge", "sudya"),
        ("decided_at", "qaror sanasi"),
    )
    for field, label in required:
        if not getattr(decision, field):
            out.append(
                Finding(
                    code="PROC-001",
                    check="protsessual",
                    severity=Severity.MAJOR,
                    description=f"Qarorda {label} ko'rsatilmagan.",
                    recommendation=f"Kirish qismiga {label}ni qo'shing.",
                    citation=basis,
                )
            )

    if not decision.conclusion.strip():
        out.append(
            Finding(
                code="PROC-002",
                check="protsessual",
                severity=Severity.CRITICAL,
                description="Rezolyutiv qism (HUKM QILDI / QAROR QILDI) topilmadi.",
                recommendation=(
                    "Rezolyutiv qismsiz hujjat ijro etilmaydi — uni "
                    "rasmiylashtirish talab qilinadi."
                ),
                citation=basis,
            )
        )

    if not decision.parties:
        out.append(
            Finding(
                code="PROC-003",
                check="protsessual",
                severity=Severity.MAJOR,
                description="Ish ishtirokchilari ko'rsatilmagan.",
                recommendation="Tomonlar va ularning protsessual maqomini ko'rsating.",
                citation=basis,
            )
        )

    if decision.is_criminal and not decision.has_role("prokuror"):
        out.append(
            Finding(
                code="PROC-004",
                check="protsessual",
                severity=Severity.MINOR,
                description="Jinoyat ishida davlat ayblovchisi ko'rsatilmagan.",
                recommendation="Prokurorning ishtiroki qayd etilsin.",
                citation=basis,
            )
        )

    return out


# --------------------------------------------------------------------------- #
# 2 — Dalillar to'liq tekshirilganmi
# --------------------------------------------------------------------------- #

# Ayblov xulosasini bildiruvchi iboralar — dalil talabi shulardan kelib chiqadi.
_GUILT = re.compile(r"aybdor\s+deb\s+top|aybi\s+isbotlan|jinoyat\s+sodir\s+etgan", re.IGNORECASE)


def check_evidence(decision: CourtDecision) -> list[Finding]:
    out: list[Finding] = []
    # Ayblov xulosasi rezolyutiv qismda ham, tavsiflovchi qismda ham
    # yozilishi mumkin — uchalasi ham skanerlanadi, aks holda dalil
    # talabi shakl tasodifiga bog'lanib qolardi.
    convicting = bool(
        _GUILT.search(
            fold(" ".join((decision.conclusion, decision.reasoning, decision.circumstances)))
        )
    )

    if not decision.evidence:
        out.append(
            Finding(
                code="EVID-001",
                check="dalillar",
                severity=Severity.CRITICAL if convicting else Severity.MAJOR,
                description="Qarorda tekshirilgan dalillar keltirilmagan.",
                recommendation=(
                    "Har bir dalil va uning baholanishi asoslovchi qismda ko'rsatilishi kerak."
                ),
                citation=JPK_DALIL,
            )
        )
        return out

    if convicting and len(decision.evidence) == 1:
        out.append(
            Finding(
                code="EVID-002",
                check="dalillar",
                severity=Severity.MAJOR,
                description=(
                    "Ayblov xulosasi bitta dalilga tayanadi — dalillar majmuasi ko'rsatilmagan."
                ),
                recommendation=(
                    "Ayblov bitta dalil bilan asoslanmaydi; boshqa dalillar "
                    "bilan tasdiqlanishi kerak."
                ),
                citation=JPK_DALIL,
                excerpt=decision.evidence[0][:200],
            )
        )

    # Dalil sanab o'tilgan, lekin asoslovchi qismda umuman tahlil yo'q.
    if decision.evidence and not decision.reasoning.strip():
        out.append(
            Finding(
                code="EVID-003",
                check="dalillar",
                severity=Severity.MAJOR,
                description="Dalillar keltirilgan, lekin ularning bahosi yozilmagan.",
                recommendation="Har bir dalil nima uchun qabul yoki rad etilganini yozing.",
                citation=JPK_DALIL,
            )
        )

    return out


# --------------------------------------------------------------------------- #
# 3 — Qonun to'g'ri qo'llanganmi
# --------------------------------------------------------------------------- #

_PROCEDURAL_CODES = ("protsessual", "ijroiya")


def check_law_application(decision: CourtDecision) -> list[Finding]:
    out: list[Finding] = []

    if not decision.law_references:
        out.append(
            Finding(
                code="LAW-001",
                check="qonun",
                severity=Severity.CRITICAL,
                description="Qarorda birorta qonun moddasiga havola yo'q.",
                recommendation="Xulosa asoslangan normalarni aniq ko'rsating.",
            )
        )
        return out

    # Jazo tayinlangan, lekin faqat protsessual kodeksga havola bor:
    # javobgarlik moddiy normadan kelib chiqadi, protsessualdan emas.
    material = [
        c
        for c in decision.law_references
        if not any(p in fold(c.doc_title or "") for p in _PROCEDURAL_CODES)
    ]
    if decision.penalty is not None and not material:
        out.append(
            Finding(
                code="LAW-002",
                check="qonun",
                severity=Severity.CRITICAL,
                description=(
                    "Jazo tayinlangan, lekin moddiy huquq normasiga havola yo'q — "
                    "faqat protsessual kodeks keltirilgan."
                ),
                recommendation="Javobgarlik asosini moddiy kodeks moddasi bilan ko'rsating.",
                citation=decision.law_references[0],
            )
        )

    if decision.is_criminal and not decision.cites("jinoyat kodeksi"):
        out.append(
            Finding(
                code="LAW-003",
                check="qonun",
                severity=Severity.CRITICAL,
                description="Jinoyat ishi, lekin Jinoyat kodeksiga havola yo'q.",
                recommendation="Qilmish kvalifikatsiya qilingan moddani ko'rsating.",
            )
        )

    # Modda raqami mavjud oraliqdan tashqarida — terish xatosi belgisi.
    for citation in decision.law_references:
        head = citation.article.split("-")[0]
        if head.isdigit() and int(head) > 1600:
            out.append(
                Finding(
                    code="LAW-004",
                    check="qonun",
                    severity=Severity.MAJOR,
                    description=(
                        f"«{citation.doc_title} {citation.article}-modda» — "
                        f"bunday raqamli modda mavjud emasga o'xshaydi."
                    ),
                    recommendation="Modda raqamini manba bo'yicha tekshiring.",
                    citation=citation,
                )
            )

    return out


# --------------------------------------------------------------------------- #
# 4 — Jazo mutanosibmi
# --------------------------------------------------------------------------- #

_MITIGATING = re.compile(
    r"yengillashtiruvchi|birinchi\s+marta|voyaga\s+yetmagan|zararni\s+qopla\w*|"
    r"chin\s+ko[ʻ']?ngildan\s+pushaymon|homilador|nogiron",
    re.IGNORECASE,
)
_AGGRAVATING = re.compile(
    r"og[ʻ']?irlashtiruvchi|takroran|bir\s+necha\s+marta|uyushgan\s+guruh|"
    r"sudlanganlik\s+holati|retsidiv",
    re.IGNORECASE,
)

# Ozodlikdan mahrum qilish uchun yuqori chegara — JK umumiy qismi.
MAX_IMPRISONMENT_YEARS = 25


def check_proportionality(decision: CourtDecision) -> list[Finding]:
    out: list[Finding] = []
    penalty = decision.penalty
    if penalty is None:
        return out

    body = fold(decision.reasoning + " " + decision.circumstances)
    mitigating = bool(_MITIGATING.search(body))
    aggravating = bool(_AGGRAVATING.search(body))

    if (
        penalty.kind is PenaltyKind.OZODLIKDAN_MAHRUM
        and penalty.unit == "yil"
        and penalty.amount is not None
        and penalty.amount > MAX_IMPRISONMENT_YEARS
    ):
        out.append(
            Finding(
                code="PROP-001",
                check="mutanosiblik",
                severity=Severity.CRITICAL,
                description=(
                    f"Tayinlangan muddat ({penalty.amount:.0f} yil) umumiy qism "
                    f"chegarasidan ({MAX_IMPRISONMENT_YEARS} yil) oshadi."
                ),
                recommendation="Muddatni kodeks umumiy qismi chegarasiga keltiring.",
                citation=JK_JAZO,
                excerpt=penalty.raw[:200],
            )
        )

    if penalty.kind is PenaltyKind.OZODLIKDAN_MAHRUM and mitigating and not aggravating:
        out.append(
            Finding(
                code="PROP-002",
                check="mutanosiblik",
                severity=Severity.MAJOR,
                description=(
                    "Yengillashtiruvchi holatlar qayd etilgan, og'irlashtiruvchi "
                    "holatlar esa yo'q, lekin ozodlikdan mahrum qilish tayinlangan."
                ),
                recommendation=(
                    "Yengilroq jazo qo'llanmagani nima uchun ekanini asoslang "
                    "yoki jazoni qayta ko'ring."
                ),
                citation=JK_JAZO,
            )
        )

    if not decision.reasoning.strip():
        out.append(
            Finding(
                code="PROP-003",
                check="mutanosiblik",
                severity=Severity.MAJOR,
                description="Jazo tayinlangan, lekin uning asoslari yozilmagan.",
                recommendation="Jazo turi va miqdori tanlangan sabablarni ko'rsating.",
                citation=JK_JAZO,
            )
        )

    return out


# --------------------------------------------------------------------------- #
# 5 — Huquqlar himoya qilinganmi
# --------------------------------------------------------------------------- #

_LAST_WORD = re.compile(r"oxirgi\s+so[ʻ']?z", re.IGNORECASE)
_INTERPRETER_NEED = re.compile(
    r"tilini\s+bilmay\w*|tarjima\s+qilin\w*|rus\s+tilida\s+so[ʻ']?ragan", re.IGNORECASE
)


def check_rights(decision: CourtDecision) -> list[Finding]:
    out: list[Finding] = []
    body = fold(decision.raw)

    if decision.is_criminal and not decision.has_role("himoyachi"):
        out.append(
            Finding(
                code="RIGHT-001",
                check="huquqlar",
                severity=Severity.CRITICAL,
                description="Jinoyat ishida himoyachi ishtiroki qayd etilmagan.",
                recommendation=(
                    "Himoyachidan voz kechish yozma rasmiylashtirilgan bo'lishi "
                    "yoki himoyachi ta'minlanishi kerak."
                ),
                citation=JPK_HIMOYA,
            )
        )

    if decision.is_criminal and not _LAST_WORD.search(body):
        out.append(
            Finding(
                code="RIGHT-002",
                check="huquqlar",
                severity=Severity.MAJOR,
                description="Sudlanuvchiga oxirgi so'z berilgani qayd etilmagan.",
                recommendation="Oxirgi so'z berilgani bayonnomada aks etsin.",
                citation=JPK_HUKM,
            )
        )

    if _INTERPRETER_NEED.search(body) and not decision.has_role("tarjimon"):
        out.append(
            Finding(
                code="RIGHT-003",
                check="huquqlar",
                severity=Severity.CRITICAL,
                description=(
                    "Til bilmaslik holati ko'rsatilgan, lekin tarjimon ishtiroki qayd etilmagan."
                ),
                recommendation="Tarjimon ta'minlanishi va bu qarorda aks etishi kerak.",
                citation=JPK_TARJIMON,
            )
        )

    if not decision.appeal_note:
        out.append(
            Finding(
                code="RIGHT-004",
                check="huquqlar",
                severity=Severity.MINOR,
                description="Shikoyat qilish tartibi va muddati tushuntirilmagan.",
                recommendation="Rezolyutiv qismda shikoyat muddatini ko'rsating.",
            )
        )

    return out


# --------------------------------------------------------------------------- #
# 6 — Muddat buzilganmi
# --------------------------------------------------------------------------- #

# Apellyatsiya muddati — protsessual kodekslarda 10 va 20 kun oralig'ida.
APPEAL_DAYS = (10, 20)
MAX_DELIBERATION_DAYS = 30


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def check_deadlines(decision: CourtDecision) -> list[Finding]:
    out: list[Finding] = []
    decided = _as_date(decision.decided_at)
    heard = _as_date(decision.hearing_at)

    if decided and heard:
        if decided < heard:
            out.append(
                Finding(
                    code="TIME-001",
                    check="muddat",
                    severity=Severity.CRITICAL,
                    description=(
                        f"Qaror sanasi ({decision.decided_at}) sud majlisi sanasidan "
                        f"({decision.hearing_at}) oldin."
                    ),
                    recommendation="Sanalarni tekshiring — hujjatda ziddiyat bor.",
                )
            )
        elif (decided - heard).days > MAX_DELIBERATION_DAYS:
            out.append(
                Finding(
                    code="TIME-002",
                    check="muddat",
                    severity=Severity.MINOR,
                    description=(
                        f"Majlis va qaror orasida {(decided - heard).days} kun — "
                        f"qaror kechiktirilgan."
                    ),
                    recommendation="Kechikish sababini ko'rsating.",
                )
            )

    if decision.appeal_note:
        days = re.search(r"(\d{1,3})\s*kun", decision.appeal_note, re.IGNORECASE)
        if days and not (APPEAL_DAYS[0] <= int(days.group(1)) <= APPEAL_DAYS[1]):
            out.append(
                Finding(
                    code="TIME-003",
                    check="muddat",
                    severity=Severity.MAJOR,
                    description=(
                        f"Ko'rsatilgan shikoyat muddati ({days.group(1)} kun) "
                        f"odatdagi {APPEAL_DAYS[0]}–{APPEAL_DAYS[1]} kun oralig'idan tashqarida."
                    ),
                    recommendation="Shikoyat muddatini protsessual kodeks bo'yicha tekshiring.",
                    excerpt=decision.appeal_note[:200],
                )
            )

    if decided is None:
        out.append(
            Finding(
                code="TIME-004",
                check="muddat",
                severity=Severity.MINOR,
                description="Qaror sanasi aniqlanmadi — muddatlarni tekshirib bo'lmadi.",
                recommendation="Sanani aniq shaklda yozing.",
            )
        )

    return out


# --------------------------------------------------------------------------- #
# 7 — Oldingi qarorlar hisobga olinganmi
# --------------------------------------------------------------------------- #

_PRECEDENT = re.compile(
    r"plenum|oliy\s+sud|sud\s+amaliyot\w*|yuqori\s+turuvchi\s+sud|"
    r"umumlashtir\w*\s+amaliyot",
    re.IGNORECASE,
)
_PRIOR_CONVICTION = re.compile(
    r"sudlanganlik|ilgari\s+sudlangan|oldingi\s+hukm|takroran\s+sodir", re.IGNORECASE
)
# Sudlanganlik «hisobga olingan» deb hisoblanadigan shakllar. Uni
# og'irlashtiruvchi holat sifatida qayd etish ham baholashdir —
# sud uni ko'rgan va jazoga ta'sirini aytgan.
_PRIOR_ADDRESSED = re.compile(
    r"sudlanganlik\w*\s+(?:olib\s+tashlan|bekor\s+qilin|hisobga\s+olin)|"
    r"retsidiv\s+deb\s+top|og[ʻ']?irlashtiruvchi\s+holat",
    re.IGNORECASE,
)


def check_precedent(decision: CourtDecision) -> list[Finding]:
    out: list[Finding] = []
    body = fold(decision.raw)

    if _PRIOR_CONVICTION.search(body) and not _PRIOR_ADDRESSED.search(body):
        out.append(
            Finding(
                code="PREC-001",
                check="amaliyot",
                severity=Severity.MAJOR,
                description=(
                    "Oldingi sudlanganlik tilga olingan, lekin uning huquqiy "
                    "oqibati (retsidiv, jazo tayinlashga ta'siri) baholanmagan."
                ),
                recommendation=(
                    "Sudlanganlik holati saqlanganmi va u jazoga qanday ta'sir "
                    "qilganini ko'rsating."
                ),
                citation=JK_JAZO,
            )
        )

    if not _PRECEDENT.search(body) and decision.reasoning.strip():
        out.append(
            Finding(
                code="PREC-002",
                check="amaliyot",
                severity=Severity.INFO,
                description="Qarorda yuqori sud amaliyotiga havola yo'q.",
                recommendation=(
                    "Nizoli huquqiy masalada Plenum qarori yoki sud amaliyotiga "
                    "havola qaror asosini kuchaytiradi."
                ),
            )
        )

    return out


# --------------------------------------------------------------------------- #
# Barcha tekshiruvlar
# --------------------------------------------------------------------------- #

CHECKS: tuple[tuple[str, Callable[[CourtDecision], list[Finding]]], ...] = (
    ("protsessual", check_procedural),
    ("dalillar", check_evidence),
    ("qonun", check_law_application),
    ("mutanosiblik", check_proportionality),
    ("huquqlar", check_rights),
    ("muddat", check_deadlines),
    ("amaliyot", check_precedent),
)


class AnalysisResult(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    checks_run: list[str] = Field(default_factory=list)
    checks_failed: dict[str, str] = Field(default_factory=dict)

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity is severity]

    @property
    def worst(self) -> Severity | None:
        return max(
            (f.severity for f in self.findings), key=lambda s: SEVERITY_ORDER[s], default=None
        )


def analyze(decision: CourtDecision) -> AnalysisResult:
    result = AnalysisResult()

    for name, check in CHECKS:
        # Bitta tekshiruv yiqilsa qolganlari baribir bajariladi: yarim
        # tahlil hech qanday tahlildan foydaliroq va nosozlik ochiq
        # ko'rsatiladi.
        try:
            result.findings.extend(check(decision))
        except Exception as exc:
            result.checks_failed[name] = str(exc)
            continue
        result.checks_run.append(name)

    result.findings.sort(key=lambda f: (-f.weight, f.code))
    return result
