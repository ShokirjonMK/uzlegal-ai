"""Sud qarorida pora belgilarini aniqlash — asosiy dvigatel.

Har tekshiruv funksiyasi bitta qarorni oladi va RedFlag roʻyxatini
qaytaradi. Tekshiruvlar mustaqil — biri yiqilsa qolganlari ishlaydi.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

from uzlegal.court.parser import CourtDecision, PenaltyKind, parse
from uzlegal.ingest.normalize import fold
from uzlegal.integrity.patterns import (
    FlagCategory,
    IntegrityProfile,
    RedFlag,
    Severity,
    risk_label,
)

# ------------------------------------------------------------------ #
# 1 — Jazoning nomutanosiblegi
# ------------------------------------------------------------------ #

# Jinoyat ishida odatiy jazo oraligi (yil). Bu jadval toʻliq emas va
# faqat oʻrtacha koʻrsatkich sifatida ishlatiladi — har ish yakka.
_TYPICAL_RANGE: dict[str, tuple[float, float]] = {
    "oʻgʻirlik": (1, 5),
    "talonchilik": (3, 10),
    "firibgarlik": (2, 7),
    "oʻldirish": (8, 20),
    "bosqinchilik": (5, 15),
    "giyohvand": (3, 10),
    "pora": (3, 10),
    "zorlash": (5, 15),
    "oʻzlashtirish": (3, 10),
}

_LENIENCY_THRESHOLD = 0.4
_HARSHNESS_THRESHOLD = 1.5


def check_sentencing(decision: CourtDecision) -> list[RedFlag]:
    out: list[RedFlag] = []
    penalty = decision.penalty
    if penalty is None or penalty.amount is None or penalty.unit != "yil":
        return out
    if penalty.kind is not PenaltyKind.OZODLIKDAN_MAHRUM:
        return out

    subject = fold(decision.circumstances + " " + decision.conclusion)
    for crime, (low, high) in _TYPICAL_RANGE.items():
        if fold(crime) not in subject:
            continue

        ratio_low = penalty.amount / low if low > 0 else 1.0
        ratio_high = penalty.amount / high if high > 0 else 1.0

        if ratio_low < _LENIENCY_THRESHOLD:
            out.append(RedFlag(
                code="SENT-001",
                category=FlagCategory.DISPROPORTIONATE,
                severity=Severity.HIGH,
                title="Jazo oʻrtachadan sezilarli yengil",
                description=(
                    f"«{crime}» uchun odatiy jazo {low}–{high} yil, "
                    f"tayinlangan: {penalty.amount:.0f} yil "
                    f"({ratio_low:.0%} past chegaradan)."
                ),
                evidence=penalty.raw[:200],
                weight=0.35,
            ))
        elif ratio_high > _HARSHNESS_THRESHOLD:
            out.append(RedFlag(
                code="SENT-002",
                category=FlagCategory.DISPROPORTIONATE,
                severity=Severity.MEDIUM,
                title="Jazo oʻrtachadan sezilarli ogʻir",
                description=(
                    f"«{crime}» uchun odatiy jazo {low}–{high} yil, "
                    f"tayinlangan: {penalty.amount:.0f} yil "
                    f"({ratio_high:.0%} yuqori chegaradan)."
                ),
                evidence=penalty.raw[:200],
                weight=0.20,
            ))
        break

    if penalty.suspended:
        out.append(RedFlag(
            code="SENT-003",
            category=FlagCategory.DISPROPORTIONATE,
            severity=Severity.MEDIUM,
            title="Shartli hukm",
            description=(
                "Ozodlikdan mahrum qilish tayinlangan, lekin shartli ravishda "
                "bajarilmaydi — bu oʻz-oʻzida belgi emas, lekin boshqa "
                "belgilar bilan birga diqqatga loyiq."
            ),
            evidence=penalty.raw[:200],
            weight=0.10,
        ))

    return out


# ------------------------------------------------------------------ #
# 2 — Protsessual qisqartmalar
# ------------------------------------------------------------------ #

_FAST_TRIAL = re.compile(
    r"qisqartirilgan\s+tartib|maxsus\s+tartib|kelishuv\s+shartnoma\w*|"
    r"soddalashtirilgan",
    re.IGNORECASE,
)
_PLEA_DEAL = re.compile(
    r"aybni\s+tan\s+ol\w*|kelishuv|yarashuv", re.IGNORECASE
)


def check_procedural(decision: CourtDecision) -> list[RedFlag]:
    out: list[RedFlag] = []
    body = fold(decision.raw)

    if _FAST_TRIAL.search(body) and decision.is_criminal:
        out.append(RedFlag(
            code="PROC-001",
            category=FlagCategory.PROCEDURAL,
            severity=Severity.LOW,
            title="Qisqartirilgan tartibda koʻrilgan",
            description=(
                "Ish qisqartirilgan tartibda koʻrilgan — bu qonuniy, lekin "
                "boshqa belgilar bilan birga diqqatga loyiq."
            ),
            weight=0.05,
        ))

    if not decision.has_role("himoyachi") and decision.is_criminal:
        out.append(RedFlag(
            code="PROC-002",
            category=FlagCategory.PROCEDURAL,
            severity=Severity.HIGH,
            title="Himoyachisiz sud",
            description=(
                "Jinoyat ishida himoyachi ishtiroki qayd etilmagan — "
                "mudofaa huquqi buzilgan boʻlishi mumkin."
            ),
            weight=0.30,
        ))

    if _PLEA_DEAL.search(body) and decision.penalty and decision.penalty.suspended:
        out.append(RedFlag(
            code="PROC-003",
            category=FlagCategory.PROCEDURAL,
            severity=Severity.MEDIUM,
            title="Kelishuv + shartli jazo",
            description=(
                "Aybni tan olish yoki yarashuv asosida shartli jazo — "
                "kombinatsiya boshqa belgilar bilan birga diqqatga loyiq."
            ),
            weight=0.15,
        ))

    return out


# ------------------------------------------------------------------ #
# 3 — Dalillar bilan muammo
# ------------------------------------------------------------------ #

_RECANTED = re.compile(
    r"koʻrsatma\w*\s+(?:oʻzgart|rad\s+et|bekor\s+qil|qaytarib\s+ol)",
    re.IGNORECASE,
)


def check_evidence_handling(decision: CourtDecision) -> list[RedFlag]:
    out: list[RedFlag] = []
    body = fold(decision.raw)

    inadmissible_count = sum(
        1 for e in decision.evidence
        if "qabul qilinmaydigan" in fold(e) or "noqonuniy" in fold(e)
    )
    if inadmissible_count > 0 and "aybdor" in fold(decision.conclusion):
        out.append(RedFlag(
            code="EVID-001",
            category=FlagCategory.EVIDENCE,
            severity=Severity.HIGH,
            title="Qabul qilinmaydigan dalil asosida ayblov",
            description=(
                f"{inadmissible_count} ta dalil qabul qilinmaydigan deb "
                "belgilangan, lekin ayblov xulosasi chiqarilgan."
            ),
            weight=0.30,
        ))

    if _RECANTED.search(body):
        out.append(RedFlag(
            code="EVID-002",
            category=FlagCategory.EVIDENCE,
            severity=Severity.MEDIUM,
            title="Oʻzgartirilgan koʻrsatma",
            description=(
                "Guvoh koʻrsatmasini oʻzgartirgan yoki rad etgan — "
                "dalillar bazasining ishonchliligi tekshirilishi kerak."
            ),
            weight=0.15,
        ))

    if len(decision.evidence) <= 1 and "aybdor" in fold(decision.conclusion):
        out.append(RedFlag(
            code="EVID-003",
            category=FlagCategory.EVIDENCE,
            severity=Severity.HIGH,
            title="Yagona dalil asosida ayblov",
            description=(
                "Ayblov xulosasi bitta yoki nol dalilga tayanadi — "
                "dalillar majmuasi koʻrsatilmagan."
            ),
            weight=0.25,
        ))

    return out


# ------------------------------------------------------------------ #
# 4 — Vaqt anomaliyalari
# ------------------------------------------------------------------ #


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


_VERY_FAST_DAYS = 3
_SUSPICIOUS_FAST_DAYS = 7


def check_timing(decision: CourtDecision) -> list[RedFlag]:
    out: list[RedFlag] = []
    decided = _as_date(decision.decided_at)
    heard = _as_date(decision.hearing_at)

    if decided and heard and decided >= heard:
        delta = (decided - heard).days
        if delta <= _VERY_FAST_DAYS and decision.is_criminal:
            out.append(RedFlag(
                code="TIME-001",
                category=FlagCategory.TIMING,
                severity=Severity.MEDIUM,
                title="Juda tez qaror",
                description=(
                    f"Majlisdan qaror chiqarishgacha {delta} kun — "
                    "murakkab ish uchun gʻayrioddiy tez."
                ),
                weight=0.15,
            ))
        elif delta <= _SUSPICIOUS_FAST_DAYS and decision.is_criminal:
            out.append(RedFlag(
                code="TIME-002",
                category=FlagCategory.TIMING,
                severity=Severity.LOW,
                title="Tez qaror",
                description=(
                    f"Majlisdan qaror chiqarishgacha {delta} kun."
                ),
                weight=0.05,
            ))

    return out


# ------------------------------------------------------------------ #
# 5 — Tuzilmaviy anomaliyalar
# ------------------------------------------------------------------ #

_MISSING_REASONING = re.compile(r"^\s*$")


def check_structural(decision: CourtDecision) -> list[RedFlag]:
    out: list[RedFlag] = []

    if not decision.reasoning.strip():
        out.append(RedFlag(
            code="STRUC-001",
            category=FlagCategory.STRUCTURAL,
            severity=Severity.HIGH,
            title="Asoslovchi qism yoʻq",
            description=(
                "Qarorning asoslovchi qismi topilmadi — sudya nima uchun "
                "shunday qaror chiqarganini tushuntirmagan."
            ),
            weight=0.25,
        ))

    if not decision.law_references and decision.penalty is not None:
        out.append(RedFlag(
            code="STRUC-002",
            category=FlagCategory.STRUCTURAL,
            severity=Severity.HIGH,
            title="Jazo tayinlangan, qonun koʻrsatilmagan",
            description=(
                "Jazo tayinlangan, lekin birorta qonun moddasiga havola "
                "yoʻq — asossiz jazo."
            ),
            weight=0.30,
        ))

    if (
        decision.is_criminal
        and decision.penalty is not None
        and not decision.has_role("jabrlanuvchi")
    ):
        out.append(RedFlag(
            code="STRUC-003",
            category=FlagCategory.STRUCTURAL,
            severity=Severity.LOW,
            title="Jabrlanuvchi koʻrsatilmagan",
            description=(
                "Jinoyat ishida jabrlanuvchi qayd etilmagan — ishning "
                "toʻliq tasviri yoʻq."
            ),
            weight=0.05,
        ))

    # Yengillashtiruvchi holatlar qayd etilgan, ogʻirlashtiruvchi yoʻq,
    # va jazo shartli — kombinatsiya
    _mitigating = re.compile(
        r"yengillashtiruvchi|birinchi\s+marta|pushaymon|zararni\s+qopla",
        re.IGNORECASE,
    )
    _aggravating = re.compile(
        r"ogʻirlashtiruvchi|takroran|uyushgan\s+guruh|retsidiv",
        re.IGNORECASE,
    )
    body = fold(decision.reasoning + " " + decision.circumstances)
    if (
        _mitigating.search(body)
        and not _aggravating.search(body)
        and decision.penalty is not None
        and decision.penalty.suspended
    ):
        out.append(RedFlag(
            code="STRUC-004",
            category=FlagCategory.STRUCTURAL,
            severity=Severity.MEDIUM,
            title="Faqat yengillashtiruvchi + shartli jazo",
            description=(
                "Faqat yengillashtiruvchi holatlar qayd etilgan va jazo "
                "shartli — qaror bir tomonlama asoslangan boʻlishi mumkin."
            ),
            weight=0.15,
        ))

    return out


# ------------------------------------------------------------------ #
# Barcha tekshiruvlar
# ------------------------------------------------------------------ #

CHECKS: tuple[tuple[str, Callable[[CourtDecision], list[RedFlag]]], ...] = (
    ("sentencing", check_sentencing),
    ("procedural", check_procedural),
    ("evidence", check_evidence_handling),
    ("timing", check_timing),
    ("structural", check_structural),
)


def detect(decision: CourtDecision) -> IntegrityProfile:
    """Bitta qarorni tekshirib profil qaytaradi."""
    flags: list[RedFlag] = []
    caveats: list[str] = []

    for name, check in CHECKS:
        try:
            flags.extend(check(decision))
        except Exception as exc:
            caveats.append(f"«{name}» tekshiruvi bajarilmadi: {exc}")

    flags.sort(key=lambda f: -f.weight)
    score = min(1.0, sum(f.weight for f in flags))

    return IntegrityProfile(
        judge=decision.judge or "",
        court=decision.court or "",
        case_count=1,
        flags=flags,
        risk_score=round(score, 2),
        risk_label=risk_label(score),
        caveats=caveats,
    )


def detect_from_text(text: str) -> IntegrityProfile:
    """Matndan qarorni ajratib tekshiradi."""
    return detect(parse(text))
