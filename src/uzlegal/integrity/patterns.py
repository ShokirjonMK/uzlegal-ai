"""Pora va nomutanosiblik belgilari — deterministik qoidalar.

## Bu modul nima qiladi va nima qilmaydi

Bu modul sud qarorida PORA BELGILARINI topadi, lekin pora FAKTINI
aniqlamaydi. Farq muhim:

- «Jazo oʻrtachadan 3 marta yengil» — BELGI. Uni matndan koʻrsatish
  mumkin va tekshirish mumkin.
- «Sudya pora olgan» — XULOSA. Uni faqat tergov organlari aytishi mumkin.

Har bir belgi (RedFlag) oʻz mezonlari va ogʻirligi bilan keladi.
Bir nechta belgi yigʻilsa, bu diqqatga loyiq, lekin hamon xulosa emas.

## Nima uchun model chaqirilmaydi

Model «menimcha bu qaror shubhali» desa, buni sudda ishlatib boʻlmaydi.
Qoida esa takrorlanadi: bir xil matn → bir xil belgilar → bir xil
ogʻirlik.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FlagCategory(StrEnum):
    DISPROPORTIONATE = "disproportionate"
    PROCEDURAL = "procedural"
    EVIDENCE = "evidence"
    TIMING = "timing"
    STRUCTURAL = "structural"


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RedFlag(BaseModel):
    code: str
    category: FlagCategory
    severity: Severity
    title: str
    description: str
    evidence: str = ""
    weight: float = Field(
        ge=0.0, le=1.0,
        description="0.0–1.0 ogʻirlik — shubha darajasi emas, belgi kuchi",
    )

    @property
    def is_serious(self) -> bool:
        return self.severity is Severity.HIGH


class IntegrityProfile(BaseModel):
    """Bitta qaror yoki bir nechta qarorlar boʻyicha profil."""

    judge: str = ""
    court: str = ""
    case_count: int = 0
    flags: list[RedFlag] = Field(default_factory=list)
    risk_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Belgilar yigʻindisidan hisoblangan raqam, ehtimollik emas",
    )
    risk_label: str = ""
    caveats: list[str] = Field(default_factory=list)

    @property
    def serious_flags(self) -> list[RedFlag]:
        return [f for f in self.flags if f.is_serious]

    @property
    def by_category(self) -> dict[FlagCategory, list[RedFlag]]:
        out: dict[FlagCategory, list[RedFlag]] = {}
        for flag in self.flags:
            out.setdefault(flag.category, []).append(flag)
        return out


RISK_LABELS: tuple[tuple[float, str], ...] = (
    (0.70, "yuqori xavf — koʻp jiddiy belgilar"),
    (0.40, "oʻrtacha xavf — sezilarli belgilar bor"),
    (0.15, "past xavf — ayrim belgilar"),
    (0.0, "belgi topilmadi"),
)


def risk_label(score: float) -> str:
    return next(text for threshold, text in RISK_LABELS if score >= threshold)
