"""Agent chiqish shartnomalari — docs/06 § 2.

Nima uchun har rol uchun alohida sxema: rollarni **mustaqil testlash** uchun.
Agent «yaxshi javob berdi» degan mavhum baho o'rniga aniq savol qo'yiladi —
`LegalFrame.applicable_norms` bo'shmi? `Position.weaknesses` to'ldirilganmi?
Bunga avtomatik javob berish mumkin, «javob sifatli»ga esa yo'q.

`Position`, `Argument` va `Citation` `uzlegal.types` da — ular API
shartnomasining bir qismi va agent qatlamidan tashqarida ham ishlatiladi.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from uzlegal.types import Citation

# --------------------------------------------------------------------------- #
# jurist
# --------------------------------------------------------------------------- #


class LegalFrame(BaseModel):
    """Neytral huquqiy ramka — debate shu ramka ustida quriladi.

    Ramkani bitta neytral agent qurishi muhim: aks holda advokat va prokuror
    turli faktlardan kelib chiqadi va ularning tortishuvi ma'nosini yo'qotadi.
    """

    facts: list[str] = Field(default_factory=list, description="Savoldan ajratilgan faktlar")
    legal_questions: list[str] = Field(default_factory=list)
    applicable_norms: list[Citation] = Field(
        default_factory=list,
        description="Kontekstdagi belgilar bo'yicha hal qilingan normalar",
    )
    unknowns: list[str] = Field(
        default_factory=list,
        description="Yetishmayotgan ma'lumot — javobning ishonchini cheklaydi",
    )
    answer: str = Field(
        default="",
        description=(
            "Faqat `simple` rejimda to'ldiriladi: bu oqimda jurist yagona agent "
            "va javobni o'zi beradi (docs/01 § 3). Debate oqimida bo'sh qoladi — "
            "u yerda javobni sudya shakllantiradi."
        ),
    )

    @property
    def norm_tags(self) -> list[str]:
        return [c.tag for c in self.applicable_norms]


# --------------------------------------------------------------------------- #
# professor
# --------------------------------------------------------------------------- #


class DoctrinalAnalysis(BaseModel):
    """Doktrinal qatlam — normadan yuqoridagi tahlil.

    Kolliziya (normalar to'qnashuvi) alohida maydonda: sudya uchun bu eng
    muhim signal, chunki qaysi norma ustun ekanini u hal qiladi.
    """

    summary: str = ""
    doctrines: list[str] = Field(default_factory=list, description="Tegishli huquqiy doktrinalar")
    collisions: list[str] = Field(default_factory=list, description="Normalar to'qnashuvi")
    comparative: list[str] = Field(default_factory=list, description="Qiyosiy huquq eslatmalari")
    citation_tags: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# judge
# --------------------------------------------------------------------------- #


class Verdict(BaseModel):
    """Sudya xulosasi.

    `rejected_arguments` majburiy ravishda ma'noli: sudya nimani rad etganini
    aytmasa, uning xulosasi tortishuv natijasi emas, shunchaki takrorlash
    bo'lib qoladi.

    `citation_tags` — modeldan kelgan xom belgilar (`C1`), `citations` esa
    orkestrator ularni kontekstga bog'lagandan keyin to'ldiradi. Ikkalasi
    ajratilgan, chunki model belgini o'ylab topishi mumkin — bog'lanmagani
    `citations` ga hech qachon tushmaydi.
    """

    conclusion: str = ""
    reasoning: list[str] = Field(default_factory=list)
    accepted_arguments: list[str] = Field(default_factory=list)
    rejected_arguments: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    caveats: list[str] = Field(default_factory=list)
    citation_tags: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    def as_answer(self) -> str:
        """Gate ga beriladigan matn ko'rinishi.

        Struktura saqlanadi (sarlavhalar), chunki gate da'volarni satr va gap
        chegarasi bo'yicha ajratadi — bir satrda bitta da'vo bo'lishi
        tekshiruvni aniqroq qiladi.
        """
        blocks: list[str] = []
        if self.conclusion:
            blocks.append("XULOSA\n" + self.conclusion)
        if self.reasoning:
            blocks.append("ASOSLAR\n" + "\n".join(f"- {r}" for r in self.reasoning))
        if self.caveats:
            blocks.append("OGOHLANTIRISHLAR\n" + "\n".join(f"- {c}" for c in self.caveats))
        return "\n\n".join(blocks)
