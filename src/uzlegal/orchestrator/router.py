"""Murakkablik routeri — docs/01 § 3.

## Nima uchun router kerak

To'liq debate ~45 s va ~8k token. "MMT stavkasi qancha?" savoliga bu isrof:
o'lchovlar bo'yicha oddiy faktik savolda ko'p-agentli javob bitta agent
javobidan **yaxshi emas** (docs/06 § 1). Router shu isrofni oldini oladi.

| Daraja | Oqim | Kechikish |
|--------|------|-----------|
| `simple` | jurist → gate | ~5 s |
| `standard` | jurist → professor → judge | ~20 s |
| `complex` | to'liq debate | ~45 s |

## Nima uchun qoidalar, model emas

Klassifikator model bu yerda ikki marta yutqazadi: u ham vaqt oladi (tejash
kerak bo'lgan narsani sarflaydi), ham tushuntirib bo'lmaydigan bo'ladi.
Qoidalar esa trace da ko'rinadi — foydalanuvchi nima uchun "complex" rejim
tanlanganini o'qiy oladi. Noaniq holatda **yuqoriroq** daraja tanlanadi:
ortiqcha tahlil qilish yetarli tahlil qilmaslikdan arzonroq.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import fold


class Mode(StrEnum):
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"


# Har rejimda ishtirok etuvchi rollar — docs/01 § 3 jadvali
ROLES_BY_MODE: dict[Mode, list[str]] = {
    Mode.SIMPLE: ["jurist"],
    Mode.STANDARD: ["jurist", "professor", "judge"],
    Mode.COMPLEX: ["jurist", "advocate", "prosecutor", "professor", "judge"],
}

# Nizo alomatlari — ikki tomon va tortishuv bor
_DISPUTE = re.compile(
    r"\b(kim\s+haq|kimning\s+haqqi|nizo\w*|tortishuv\w*|da'vo\s+qil\w*|"
    r"sudga\s+beri\w*|qarshi\s+tomon|mijozim|mening\s+mijoz\w*|"
    r"talab\s+qilmoqda|ayblamoqda|e'tiroz\w*|shikoyat\s+qil\w*|"
    r"himoya\s+qil\w*|yutish\s+imkoniyat\w*|istiqbol\w*)\b"
)

# Tahlil alomatlari — bir tomonlama baho so'ralmoqda
_ANALYTICAL = re.compile(
    r"\b(mumkinmi|bo'ladimi|haqlimi|haqiqiymi|qonuniymi|javobgar\w*mi|"
    r"qanday\s+himoya|qanday\s+asoslan\w*|oqibat\w*|xavf\w*|risk\w*|"
    r"tahlil\s+qil\w*|baholang|qaysi\s+norma|kolliziya\w*|"
    r"nima\s+qilish\s+kerak|qanday\s+yo'l\s+tut\w*)\b"
)

# Faktik so'rov alomatlari — bitta aniq javob kutilmoqda
_FACTUAL = re.compile(
    r"\b(qancha|necha|qachon|kim\s+tasdiqla\w*|qaysi\s+modda|"
    r"stavka\w*|miqdor\w*|muddati\s+qancha|ta'rif\w*|nima\s+deydi|"
    r"nima\s+degani|matni?ni\s+ber)\b"
)

# Uzun bayon — odatda ish holati tasvirlangan, ya'ni nizo
LONG_QUESTION_WORDS = 60
MEDIUM_QUESTION_WORDS = 25


class RouteDecision(BaseModel):
    """Router qarori va uning sababi — trace ga yoziladi.

    Sabab matni majburiy: foydalanuvchi "nima uchun bu savolga 45 soniya
    sarflandi?" deb so'rashi mumkin va javob bo'lishi kerak.
    """

    mode: Mode
    reason: str
    forced: bool = False
    signals: list[str] = Field(default_factory=list)

    @property
    def roles(self) -> list[str]:
        return ROLES_BY_MODE[self.mode]


def route(
    question: str, *, forced: str | None = None, has_client_position: bool = False
) -> RouteDecision:
    """Savolni uch darajadan biriga joylaydi.

    `forced` — foydalanuvchi `--mode` bilan majburlagan qiymat; `auto` yoki
    `None` bo'lsa qoidalar ishlaydi. Foydalanuvchi tanlovi har doim ustun:
    u o'z savolini bizdan yaxshiroq biladi.
    """
    if forced and forced != "auto":
        mode = Mode(forced)
        return RouteDecision(mode=mode, reason="foydalanuvchi majburladi", forced=True)

    text = fold(question)
    words = len(text.split())
    signals: list[str] = []

    if _DISPUTE.search(text):
        signals.append("nizo alomati")
    if has_client_position:
        signals.append("mijoz pozitsiyasi berilgan")
    if words >= LONG_QUESTION_WORDS:
        signals.append(f"uzun bayon ({words} so'z)")
    if _ANALYTICAL.search(text):
        signals.append("tahliliy savol")
    if _FACTUAL.search(text):
        signals.append("faktik so'rov")

    # Nizo — eng kuchli signal: ikki tomon bo'lsa, ularni tortishtirish kerak.
    if _DISPUTE.search(text) or has_client_position or words >= LONG_QUESTION_WORDS:
        return RouteDecision(
            mode=Mode.COMPLEX,
            reason="savolda qarama-qarshi manfaatlar ko'rinadi — to'liq debate",
            signals=signals,
        )

    if _ANALYTICAL.search(text) or words >= MEDIUM_QUESTION_WORDS:
        return RouteDecision(
            mode=Mode.STANDARD,
            reason="bir tomonlama huquqiy tahlil talab qilinadi",
            signals=signals,
        )

    if _FACTUAL.search(text):
        return RouteDecision(
            mode=Mode.SIMPLE,
            reason="faktik so'rov — bitta agent yetarli",
            signals=signals,
        )

    # Noaniq holat: yuqoriroq daraja. Ortiqcha tahlil qilish yetarli tahlil
    # qilmaslikdan arzonroq — ikkinchisi noto'g'ri javob demakdir.
    return RouteDecision(
        mode=Mode.STANDARD,
        reason="savol turi aniq emas — ehtiyot yuzasidan tahliliy oqim",
        signals=signals,
    )
