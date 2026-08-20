"""Kengash tekshiruvi va kelishuv qoidalari (docs/26).

Oqim bitta namuna uchun:

    marshrutlash  →  3 senior mustaqil xulosa  →  kelishuv  →  yo'nalish

Yo'nalish uchta bo'ladi va faqat ikkinchisi odam vaqtini oladi:

| Natija | Nima bo'ladi | Odam vaqti |
|---|---|---|
| `rad` | Namuna tashlanadi, yuristga ko'rsatilmaydi | yo'q |
| `noaniq` | Yuristga **kelishmovchilik bilan** ko'rsatiladi | to'liq |
| `kengash-ma'qulladi` | Namunaviy tekshiruvga tushadi | qisman |
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from uzlegal.agents.base import AgentContext, BaseAgent
from uzlegal.config import PROJECT_ROOT
from uzlegal.panel.seniors import PANEL_SIZE, Senior, select
from uzlegal.training.dataset import TrainingSample

log = logging.getLogger(__name__)

PANEL_PROMPTS_DIR = PROJECT_ROOT / "prompts" / "panel"

#: `kengash-ma'qulladi` uchun eng past ishonch. Undan past bo'lsa —
#: kelishuv bo'lsa ham odamga boradi.
MIN_CONFIDENCE = 0.75

#: Kengash ma'qullagan namunalarning qancha ulushi baribir odamga
#: ko'rsatiladi. Nol emas va bo'lishi ham mumkin emas — sababi § 3.
SPOT_CHECK_RATE = 0.15

Verdict = Literal["to'g'ri", "tuzatish-kerak", "noto'g'ri"]
Outcome = Literal["rad", "noaniq", "kengash-ma'qulladi"]


# --------------------------------------------------------------------------- #
# Sxemalar
# --------------------------------------------------------------------------- #


class SeniorVerdict(BaseModel):
    """Bitta seniorning xulosasi."""

    senior: str
    verdict: Verdict
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)
    note: str = ""

    @property
    def rejects(self) -> bool:
        return self.verdict == "noto'g'ri"

    @property
    def accepts(self) -> bool:
        return self.verdict == "to'g'ri"


class PanelReport(BaseModel):
    """Kengashning namuna bo'yicha yakuniy xulosasi.

    `TrainingSample.panel` ga shu yoziladi. `verified` ga **hech qachon**
    tegilmaydi — bu sinf uni umuman bilmaydi.
    """

    outcome: Outcome
    verdicts: list[SeniorVerdict] = Field(default_factory=list)
    reason: str = ""
    #: Kelishuv darajasi: bir xil xulosa bergan seniorlar ulushi.
    agreement: float = 0.0
    spot_check: bool = False

    @property
    def needs_human(self) -> bool:
        """Odam ko'rishi kerakmi.

        Diqqat: `kengash-ma'qulladi` ham namunaviy tekshiruvga tushishi
        mumkin — shuning uchun bu `outcome == "noaniq"` bilan bir xil emas.
        """
        return self.outcome == "noaniq" or self.spot_check

    @property
    def issues(self) -> list[str]:
        seen: list[str] = []
        for verdict in self.verdicts:
            for issue in verdict.issues:
                if issue not in seen:
                    seen.append(issue)
        return seen


# --------------------------------------------------------------------------- #
# Tekshiruvchi agent
# --------------------------------------------------------------------------- #


class SeniorReviewer(BaseAgent):
    """Bitta senior yuristning tekshiruv agenti.

    `BaseAgent` dan meros oladi, ya'ni qayta urinish, JSON ajratish va
    prefiks cache mantiqi takrorlanmaydi.
    """

    role = "senior"
    output_schema = SeniorVerdict
    temperature = 0.2  # tekshiruvda barqarorlik ijodkorlikdan muhimroq
    max_tokens = 700

    def __init__(self, senior: Senior, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.senior = senior
        self.display_name = senior.name

    @property
    def system_prompt(self) -> str:
        if self._prompt is None:
            path = PANEL_PROMPTS_DIR / "senior.uz.md"
            self._prompt = path.read_text(encoding="utf-8") if path.exists() else ""
            if not self._prompt:
                log.warning("Kengash prompti topilmadi: %s", path)
        return self._prompt.replace("{SOHA}", self.senior.field_of_law).replace(
            "{LINZA}", self.senior.lens
        )

    def task(self, ctx: AgentContext, **inputs: Any) -> str:
        sample: TrainingSample = inputs["sample"]
        blocks = "\n\n".join(f"=== [{ref.tag}] ===\n{ref.text.strip()}" for ref in sample.context)
        return (
            f"Quyidagi trening namunasini tekshir.\n\n"
            f"--- MANBALAR ---\n{blocks}\n\n"
            f"--- SAVOL ---\n{sample.question.strip()}\n\n"
            f"--- TEKSHIRILAYOTGAN JAVOB ---\n{sample.answer.strip()}"
        )

    def output_hint(self) -> str:
        return (
            "{\"verdict\": \"to'g'ri | tuzatish-kerak | noto'g'ri\", "
            '"confidence": 0.0-1.0, '
            '"issues": ["aniq kamchilik", "..."], '
            '"note": "bir jumlalik asos"}'
        )

    def build(self, data: dict[str, Any], ctx: AgentContext) -> SeniorVerdict:
        verdict = str(data.get("verdict", "")).strip().lower()
        if verdict not in ("to'g'ri", "tuzatish-kerak", "noto'g'ri"):
            raise ValueError(f"noma'lum xulosa: {verdict!r}")
        return SeniorVerdict(
            senior=self.senior.key,
            verdict=verdict,  # type: ignore[arg-type]
            confidence=_clamp(data.get("confidence")),
            issues=[str(x).strip() for x in (data.get("issues") or []) if str(x).strip()],
            note=str(data.get("note", "")).strip(),
        )

    def validate(self, result: BaseModel) -> str | None:
        """Rad etish yoki tuzatish talab qilingan bo'lsa — sabab majburiy.

        Asossiz «noto'g'ri» yuristga hech narsa bermaydi: u baribir
        namunani boshidan o'qishga majbur bo'ladi va tejamkorlik yo'qoladi.
        """
        assert isinstance(result, SeniorVerdict)
        if result.verdict != "to'g'ri" and not result.issues:
            return "rad etilgan yoki tuzatish talab qilingan javobda `issues` bo'sh bo'lmasin"
        return None


def _clamp(value: object) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


# --------------------------------------------------------------------------- #
# Kelishuv
# --------------------------------------------------------------------------- #


def decide(verdicts: list[SeniorVerdict], *, spot_check: bool = False) -> PanelReport:
    """Seniorlar xulosasidan yakuniy yo'nalish.

    ## Qoidalar va ularning sababi

    **Rad etish ko'pchilik bilan.** Kamida yarmi «noto'g'ri» desa namuna
    tashlanadi. Bu yerda xato qilish arzon: yaxshi namunani yo'qotish
    generatsiyani qayta yugurtirish bilan tuzatiladi, yomon namunani
    o'tkazib yuborish esa modelga kiradi.

    **Ma'qullash bir ovozdan.** Bittasi ham shubha bildirsa — odamga
    boradi. Kengashning maqsadi odam o'rniga qaror qabul qilish emas,
    **odam ko'radigan oqimni tozalash**.

    **Ishonch chegarasi.** Barcha «to'g'ri» desa ham, ishonch past
    bo'lsa noaniq deb belgilanadi: past ishonchli kelishuv kelishuv emas.
    """
    if not verdicts:
        return PanelReport(outcome="noaniq", reason="kengash xulosa bermadi")

    rejects = sum(1 for v in verdicts if v.rejects)
    accepts = sum(1 for v in verdicts if v.accepts)
    total = len(verdicts)
    agreement = max(rejects, accepts) / total

    if rejects * 2 >= total:
        return PanelReport(
            outcome="rad",
            verdicts=verdicts,
            agreement=agreement,
            reason=_first_issue(verdicts) or "kengash namunani rad etdi",
        )

    if accepts == total:
        weakest = min(v.confidence for v in verdicts)
        if weakest < MIN_CONFIDENCE:
            return PanelReport(
                outcome="noaniq",
                verdicts=verdicts,
                agreement=agreement,
                reason=f"kelishuv bor, lekin ishonch past ({weakest:.2f})",
            )
        return PanelReport(
            outcome="kengash-ma'qulladi",
            verdicts=verdicts,
            agreement=agreement,
            reason="kengash bir ovozdan ma'qulladi",
            spot_check=spot_check,
        )

    return PanelReport(
        outcome="noaniq",
        verdicts=verdicts,
        agreement=agreement,
        reason=_first_issue(verdicts) or "seniorlar kelisha olmadi",
    )


def _first_issue(verdicts: list[SeniorVerdict]) -> str:
    for verdict in verdicts:
        if verdict.issues:
            return verdict.issues[0]
    return ""


# --------------------------------------------------------------------------- #
# Bitta namunani tekshirish
# --------------------------------------------------------------------------- #


def review_sample(
    sample: TrainingSample,
    ctx: AgentContext,
    *,
    size: int = PANEL_SIZE,
    spot_check: bool = False,
    reviewer_factory: Any = SeniorReviewer,
) -> PanelReport:
    """Namunani kengashdan o'tkazadi.

    Marshrutlash **savol va javob matni** bo'yicha ishlaydi, manba
    matni bo'yicha emas: manba butun kodeksdan kelishi mumkin, savol esa
    aniq sohaga tegishli bo'ladi.
    """
    seniors = select(f"{sample.question}\n{sample.answer}", size=size)
    verdicts: list[SeniorVerdict] = []

    for senior in seniors:
        reviewer = reviewer_factory(senior)
        try:
            result = reviewer.run(ctx, sample=sample)
        except Exception as exc:  # pragma: no cover — modelga bog'liq
            log.warning("senior %s xulosa bera olmadi: %s", senior.key, exc)
            continue
        if isinstance(result, SeniorVerdict):
            verdicts.append(result)

    return decide(verdicts, spot_check=spot_check)
