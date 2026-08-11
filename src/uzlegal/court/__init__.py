"""Sud qarori tahlili — deterministik, modelsiz.

    matn → parse() → analyze() → build_report()

Uch bosqich ataylab ajratilgan: parser **nima yozilganini** ajratadi,
analizator qoidalar bo'yicha kamchilik topadi, hisobot esa ularni
foydalanuvchi ko'radigan shaklga keltiradi. Hech bir bosqichda model
chaqirilmaydi — bir xil matn har doim bir xil natija beradi va har bir
topilma qarorning aynan qaysi joyidan kelib chiqqani ko'rsatiladi.
"""

from uzlegal.court.analyzer import (
    CHECKS,
    AnalysisResult,
    Finding,
    Severity,
    analyze,
)
from uzlegal.court.parser import (
    CourtDecision,
    DecisionKind,
    Party,
    Penalty,
    PenaltyKind,
    parse,
)
from uzlegal.court.report import CourtReport, build_report, review

__all__ = [
    "CHECKS",
    "AnalysisResult",
    "CourtDecision",
    "CourtReport",
    "DecisionKind",
    "Finding",
    "Party",
    "Penalty",
    "PenaltyKind",
    "Severity",
    "analyze",
    "build_report",
    "parse",
    "review",
]
