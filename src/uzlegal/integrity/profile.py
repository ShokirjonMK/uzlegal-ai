"""Sudya va sud profili — bir nechta qaror boʻyicha statistika.

MUHIM: bu modul bitta qarorga emas, BIR NECHTA qarorga ishlaydi.
Bitta qarordan xulosa chiqarish mumkin emas — u faqat anomaliya.
Anomaliyalar TAKRORLANSA, bu diqqatga loyiq pattern boʻladi.

NIMA HISOBLANADI:
- Oʻrtacha jazo muddati (jinoyat turiga qarab)
- Shartli jazo ulushi
- Protsessual buzilishlar soni
- RedFlag takrorlanish chastotasi
- Risk score trendi

NIMA HISOBLANMAYDI:
- «Bu sudya pora oladi» — hech qachon
- Solishtirma reyting — sudyalarni solishtirish notoʻgʻri
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from uzlegal.court.parser import CourtDecision, PenaltyKind
from uzlegal.integrity.detector import detect
from uzlegal.integrity.patterns import (
    IntegrityProfile,
    RedFlag,
    Severity,
    risk_label,
)


class SentencingStats(BaseModel):
    total_cases: int = 0
    custodial: int = 0
    suspended: int = 0
    fines: int = 0
    average_term_years: float | None = None
    suspended_ratio: float = 0.0


class FlagStats(BaseModel):
    total: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    most_common: list[str] = Field(default_factory=list)


class JudgeProfile(BaseModel):
    """Sudya profili — bir nechta qaror asosida."""

    judge: str
    court: str = ""
    case_count: int = 0
    sentencing: SentencingStats = Field(default_factory=SentencingStats)
    flag_stats: FlagStats = Field(default_factory=FlagStats)
    risk_score: float = 0.0
    risk_label: str = ""
    per_case: list[IntegrityProfile] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Bu profil avtomatik tizim tomonidan tayyorlangan va hech qanday "
        "huquqiy xulosa hisoblanmaydi. Pora yoki suisteʼmol FAKTI faqat "
        "vakolatli organlar tomonidan aniqlanadi."
    )


def build_profile(
    judge: str,
    decisions: list[CourtDecision],
    *,
    court: str = "",
) -> JudgeProfile:
    """Sudya profilini bir nechta qaror asosida tuzadi."""
    profiles: list[IntegrityProfile] = []
    all_flags: list[RedFlag] = []
    terms: list[float] = []
    custodial = 0
    suspended = 0
    fines = 0

    for decision in decisions:
        profile = detect(decision)
        profiles.append(profile)
        all_flags.extend(profile.flags)

        penalty = decision.penalty
        if penalty is not None:
            if penalty.kind is PenaltyKind.OZODLIKDAN_MAHRUM:
                custodial += 1
                if penalty.amount is not None and penalty.unit == "yil":
                    terms.append(penalty.amount)
                if penalty.suspended:
                    suspended += 1
            elif penalty.kind is PenaltyKind.JARIMA:
                fines += 1

    n = len(decisions)
    sentencing = SentencingStats(
        total_cases=n,
        custodial=custodial,
        suspended=suspended,
        fines=fines,
        average_term_years=round(sum(terms) / len(terms), 1) if terms else None,
        suspended_ratio=round(suspended / custodial, 2) if custodial > 0 else 0.0,
    )

    code_counter = Counter(f.code for f in all_flags)
    category_counter = Counter(f.category.value for f in all_flags)
    flag_stats = FlagStats(
        total=len(all_flags),
        high=sum(1 for f in all_flags if f.severity is Severity.HIGH),
        medium=sum(1 for f in all_flags if f.severity is Severity.MEDIUM),
        low=sum(1 for f in all_flags if f.severity is Severity.LOW),
        by_category=dict(category_counter),
        most_common=[code for code, _ in code_counter.most_common(5)],
    )

    risk = _aggregate_risk(profiles) if profiles else 0.0

    caveats: list[str] = []
    if n < 5:
        caveats.append(
            f"Faqat {n} ta qaror tahlil qilingan — statistik xulosa chiqarish uchun yetarli emas."
        )
    if sentencing.suspended_ratio > 0.7 and custodial >= 3:
        caveats.append(
            f"Shartli jazo ulushi yuqori: {sentencing.suspended_ratio:.0%} "
            f"({suspended}/{custodial} ishda) — bu anomaliya boʻlishi mumkin."
        )

    return JudgeProfile(
        judge=judge,
        court=court or (decisions[0].court or "" if decisions else ""),
        case_count=n,
        sentencing=sentencing,
        flag_stats=flag_stats,
        risk_score=round(risk, 2),
        risk_label=risk_label(risk),
        per_case=profiles,
        caveats=caveats,
    )


def _aggregate_risk(profiles: list[IntegrityProfile]) -> float:
    """Bir nechta qarorning risk scorelari oʻrtachasi.

    Oddiy oʻrtacha emas: yuqori risk scorelar ogʻirroq hisoblanadi,
    chunki bitta juda shubhali qaror besh toza qaror bilan
    «yuvilmasligi» kerak.
    """
    if not profiles:
        return 0.0
    scores = [p.risk_score for p in profiles]
    weighted = sum(s**1.5 for s in scores)
    n = len(scores)
    raw = float((weighted / n) ** (1 / 1.5))
    return min(1.0, raw)
