"""Murakkablik yo'naltiruvchisi — qancha agent ishlashini hal qiladi.

## Nima uchun kerak

Ko'p-agentli munozara murakkab nizoli savollarda javob sifatini sezilarli
oshiradi, **oddiy faktik savollarda esa farq bermaydi** (docs/06 § 1).
Farq bermaydigan joyda beshta agent ishlatish — 60 soniyani 5 soniyalik
javobga sarflash demakdir.

Shuning uchun router: savol shakli rejimni tanlaydi.

| Rejim | Savol turi | Zanjir | Vaqt |
|-------|-----------|--------|------|
| `simple` | "MMT stavkasi qancha" | RAG → jurist → gate | ~5 s |
| `standard` | "Sinov muddati qanday belgilanadi" | + professor | ~20 s |
| `complex` | "Kim haq: ish beruvchimi yoki xodimmi" | to'liq munozara | ~60 s |

Router **evristik** va u xato qilishi mumkin. Shuning uchun rejimni
foydalanuvchi ham, API ham ochiq belgilashi mumkin — router faqat
standart qiymat beradi.
"""

from __future__ import annotations

import re

from uzlegal.types import ConsultMode

# Nizo belgilari: savol ikki tomonli va tortishuvli.
_DISPUTE = re.compile(
    r"\b(kim\s+haq|haqlimi|haqmi|nizo|da[ʼ']?vo\s+qil|sudga\s+ber|"
    r"javobgar\w*mi|aybdor|qarshi|talab\s+qilishi\s+mumkinmi|"
    r"himoya\s+qil|e[ʼ']tiroz|shikoyat\s+qil|bekor\s+qildir)",
    re.IGNORECASE,
)

# Tahlil belgilari: bitta javob yo'q, shart-sharoit bor.
_ANALYTICAL = re.compile(
    r"\b(mumkinmi|bo[ʻ']?ladimi|haqiqiymi|qanday\s+himoya|oqibat|"
    r"qaysi\s+holatda|shartlari|asoslari|farqi|qanday\s+hisoblanadi|"
    r"nima\s+qilish\s+kerak)",
    re.IGNORECASE,
)

# Faktik belgilar: bitta aniq javob bor.
_FACTUAL = re.compile(
    r"\b(qancha|nechta|necha\s+kun|necha\s+yil|stavka|miqdor|muddati\s+qancha|"
    r"qachon|kim\s+belgilaydi|nima\s+deb\s+ataladi)",
    re.IGNORECASE,
)

# Mijoz o'z holatini bayon qilgan bo'lsa savol deyarli har doim nizoli.
CLIENT_POSITION_BUMP = True


def route(question: str, *, client_position: str | None = None) -> ConsultMode:
    """Savol uchun standart rejim.

    Tartib muhim: nizo belgisi eng kuchli signal — u faktik belgi bilan
    birga kelsa ham («Ishdan bo'shatilganda necha oylik to'lanadi va men
    sudga bera olamanmi») munozara kerak.
    """
    if client_position and CLIENT_POSITION_BUMP:
        return ConsultMode.COMPLEX
    if _DISPUTE.search(question):
        return ConsultMode.COMPLEX
    if _ANALYTICAL.search(question):
        return ConsultMode.STANDARD
    if _FACTUAL.search(question):
        return ConsultMode.SIMPLE
    # Noaniq savol — o'rtacha yo'l. `simple` tanlash arzon, lekin savol
    # aslida murakkab bo'lsa javob yuzaki chiqadi; `complex` esa oddiy
    # savolga bir daqiqa sarflaydi. `standard` ikkalasidan xavfsizroq.
    return ConsultMode.STANDARD


def roles_for(mode: ConsultMode) -> list[str]:
    """Rejimda ishtirok etadigan rollar — trace va UI uchun."""
    if mode is ConsultMode.SIMPLE:
        return ["jurist"]
    if mode is ConsultMode.STANDARD:
        return ["jurist", "professor", "judge"]
    return ["jurist", "advocate", "prosecutor", "professor", "judge"]
