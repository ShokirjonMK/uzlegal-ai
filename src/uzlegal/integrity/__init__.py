"""Pora va nomutanosiblik belgilarini aniqlash — deterministik.

    qaror → detect() → IntegrityProfile (belgilar + risk score)
    [qarorlar] → build_profile() → JudgeProfile (statistika)

Ikkala bosqichda ham model chaqirilmaydi. Har bir belgi qarorning
aynan qaysi joyidan kelib chiqqanini koʻrsatadi. Tizim BELGI topadi,
XULOSA emas — pora fakti faqat vakolatli organlar tomonidan aniqlanadi.
"""

from uzlegal.integrity.detector import CHECKS, detect, detect_from_text
from uzlegal.integrity.patterns import (
    FlagCategory,
    IntegrityProfile,
    RedFlag,
    Severity,
    risk_label,
)
from uzlegal.integrity.profile import JudgeProfile, build_profile

__all__ = [
    "CHECKS",
    "FlagCategory",
    "IntegrityProfile",
    "JudgeProfile",
    "RedFlag",
    "Severity",
    "build_profile",
    "detect",
    "detect_from_text",
    "risk_label",
]
