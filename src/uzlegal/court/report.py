"""Sud qarori tahlili hisoboti — `ConsultResult` shakliga o'xshash.

## Nima uchun `ConsultResult` bilan bir xil ruh

Maslahat javobi va sud qarori tahlili ikki xil ish, lekin ikkalasi ham
bir xil va'da beradi: **har bir da'vo manbaga bog'langan va tekshirish
mumkin**. Shuning uchun bu hisobot ham `citations`, `caveats` va
majburiy `disclaimer` bilan keladi.

## Apellyatsiya istiqboli — nima u emas

`appeal_prospect` — **yutish ehtimoli emas**. U topilgan kamchiliklarning
og'irligidan hisoblanadigan raqam va u faqat bitta savolga javob beradi:
«bu qarorda yuqori instansiya e'tibor qaratadigan shakl kamchiliklari
qanchalik ko'p?».

Ishning mohiyati, dalillar kuchi va sud amaliyoti bu raqamga umuman
kirmaydi. Shuning uchun u foiz sifatida emas, **daraja** sifatida
ko'rsatiladi va yoniga har doim ogohlantirish qo'yiladi.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from uzlegal.court.analyzer import (
    SEVERITY_ORDER,
    AnalysisResult,
    Finding,
    Severity,
    analyze,
)
from uzlegal.court.parser import CourtDecision, parse
from uzlegal.types import Citation

DISCLAIMER = (
    "⚠️ Bu tahlil avtomatik tizim tomonidan tayyorlangan va yuridik xulosa "
    "hisoblanmaydi. Tizim qarorning shakli va ichki izchilligini tekshiradi, "
    "ishning mohiyatini baholamaydi. Har qanday protsessual harakatdan oldin "
    "malakali yurist bilan maslahatlashing."
)

# Har bir topilma apellyatsiya istiqboliga qo'shadigan ulush.
PROSPECT_WEIGHTS: dict[Severity, float] = {
    Severity.CRITICAL: 0.30,
    Severity.MAJOR: 0.12,
    Severity.MINOR: 0.03,
    Severity.INFO: 0.0,
}

PROSPECT_LABELS: tuple[tuple[float, str], ...] = (
    (0.60, "yuqori — bir nechta jiddiy shakl kamchiligi"),
    (0.30, "o'rtacha — asos bo'lishi mumkin bo'lgan kamchiliklar bor"),
    (0.10, "past — sezilarli shakl kamchiligi topilmadi"),
    (0.0, "kamchilik topilmadi"),
)


class CourtReport(BaseModel):
    decision: CourtDecision
    findings: list[Finding] = Field(default_factory=list)
    severity: Severity | None = None
    appeal_prospect: float = 0.0
    appeal_label: str = ""
    corrections: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    checks_run: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER

    @property
    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in Severity}
        for finding in self.findings:
            out[finding.severity.value] += 1
        return out

    @property
    def is_clean(self) -> bool:
        return not any(f.severity is not Severity.INFO for f in self.findings)

    def by_check(self, name: str) -> list[Finding]:
        return [f for f in self.findings if f.check == name]

    def as_text(self) -> str:
        lines = [
            f"SUD QARORI TAHLILI — {self.decision.kind.value.upper()}",
            "",
            f"Ish: {self.decision.case_number or '—'}",
            f"Sud: {self.decision.court or '—'}",
            f"Sudya: {self.decision.judge or '—'}",
            f"Sana: {self.decision.decided_at or '—'}",
            "",
            f"TOPILMALAR ({len(self.findings)})",
        ]
        for finding in self.findings:
            mark = {"critical": "✕", "major": "!", "minor": "·", "info": "i"}[
                finding.severity.value
            ]
            source = ""
            if finding.citation is not None:
                source = f" [{finding.citation.doc_title}, {finding.citation.article}-modda]"
            lines.append(f"  {mark} {finding.code}  {finding.description}{source}")

        if self.corrections:
            lines += ["", "TUZATISH TAVSIYALARI"]
            lines += [f"  {i}. {c}" for i, c in enumerate(self.corrections, 1)]

        lines += [
            "",
            f"Apellyatsiya istiqboli: {self.appeal_label}",
        ]
        if self.caveats:
            lines += ["", "ESLATMALAR"] + [f"  • {c}" for c in self.caveats]
        lines += ["", self.disclaimer]
        return "\n".join(lines)


def _prospect(findings: list[Finding]) -> tuple[float, str]:
    score = min(1.0, sum(PROSPECT_WEIGHTS[f.severity] for f in findings))
    label = next(text for threshold, text in PROSPECT_LABELS if score >= threshold)
    return round(score, 2), label


def _corrections(findings: list[Finding]) -> list[str]:
    out: list[str] = []
    # Tartib jiddiylik bo'yicha: eng og'ir kamchilik birinchi tuzatiladi.
    for finding in sorted(findings, key=lambda f: -SEVERITY_ORDER[f.severity]):
        if finding.severity is Severity.INFO:
            continue
        if finding.recommendation not in out:
            out.append(finding.recommendation)
    return out


def _citations(findings: list[Finding], decision: CourtDecision) -> list[Citation]:
    out: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for citation in [f.citation for f in findings if f.citation] + decision.law_references:
        key = (citation.doc_id, citation.article)
        if key not in seen:
            seen.add(key)
            out.append(citation)
    return out


def build_report(decision: CourtDecision, analysis: AnalysisResult) -> CourtReport:
    prospect, label = _prospect(analysis.findings)

    caveats = list(decision.warnings)
    caveats += [
        f"«{name}» tekshiruvi bajarilmadi: {error}"
        for name, error in analysis.checks_failed.items()
    ]
    if not decision.sections:
        caveats.append("Hujjat bo'limlarga ajralmadi — tahlil to'liq bo'lmasligi mumkin.")

    return CourtReport(
        decision=decision,
        findings=analysis.findings,
        severity=analysis.worst,
        appeal_prospect=prospect,
        appeal_label=label,
        corrections=_corrections(analysis.findings),
        citations=_citations(analysis.findings, decision),
        caveats=caveats,
        checks_run=analysis.checks_run,
    )


def review(text: str) -> CourtReport:
    decision = parse(text)
    return build_report(decision, analyze(decision))
