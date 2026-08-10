"""Retrieval sifatini o'lchash.

## Nima uchun alohida baholanadi

Agar yakuniy javob yomon bo'lsa — sabab retrievalmi yoki modelmi? Bu savolga
javob bermasdan tizimni yaxshilab bo'lmaydi. Shuning uchun RAG qatlami
agentlardan **mustaqil** o'lchanadi (docs/08 § 1).

## Metrikalar

| Metrika | Ma'nosi | Maqsad |
|---------|---------|--------|
| `Recall@1` | To'g'ri modda 1-o'rinda | ≥ 60% |
| `Recall@3` | Top-3 ichida | ≥ 80% |
| `Recall@10` | Top-10 ichida | ≥ 90% |
| `MRR` | O'rtacha teskari o'rin | ≥ 0.75 |
| `Deprecated leak` | Bekor qilingan chunk chiqdi | **0%** |

`Recall@10` eng muhim: agentlarga top-8 beriladi, ya'ni to'g'ri modda shu
oraliqda bo'lmasa model uni **umuman ko'rmaydi** va to'g'ri javob berishi
imkonsiz bo'ladi.

## Gold to'plam qanday tuzilgan

Har bir savol **modda sarlavhasidan boshqa so'zlar bilan** yozilgan. Sabab:
sarlavha so'zlarini takrorlagan savol BM25 uchun juda oson bo'ladi va
o'lchov haqiqiy sifatni ko'rsatmaydi.

    ❌ "Vindikatsiya daʼvosi"           (sarlavhaning nusxasi)
    ✅ "O'g'irlangan mulkni qaytarish"   (boshqa so'zlar, bir ma'no)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uzlegal.retrieval.hybrid import HybridRetriever


@dataclass
class EvalCase:
    """Bitta baholash holati."""

    id: str
    query: str
    expected_articles: list[str]
    doc_hint: str | None = None
    category: str = "general"
    note: str | None = None

    def matches(self, chunk: Any) -> bool:
        """Chunk kutilgan moddalardan biriga tegishlimi.

        Birlashtirilgan chunklar («130-131») va prim moddalar («358-1»)
        hisobga olinadi.
        """
        if chunk.article is None:
            return False
        if self.doc_hint and self.doc_hint.lower() not in chunk.doc_title.lower():
            return False
        parts = set(chunk.article.split("-")) | {chunk.article}
        return any(exp in parts or exp == chunk.article for exp in self.expected_articles)


@dataclass
class CaseResult:
    case: EvalCase
    rank: int | None  # 1 dan boshlab; topilmasa None
    latency_ms: int
    top_articles: list[str] = field(default_factory=list)
    deprecated_leaked: bool = False

    @property
    def reciprocal_rank(self) -> float:
        return 1.0 / self.rank if self.rank else 0.0

    def hit_at(self, k: int) -> bool:
        return self.rank is not None and self.rank <= k


@dataclass
class EvalReport:
    results: list[CaseResult]
    reranked: bool = False

    def recall_at(self, k: int) -> float:
        return sum(r.hit_at(k) for r in self.results) / len(self.results) if self.results else 0.0

    @property
    def mrr(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.reciprocal_rank for r in self.results) / len(self.results)

    @property
    def deprecated_leak(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.deprecated_leaked for r in self.results) / len(self.results)

    @property
    def median_latency_ms(self) -> int:
        if not self.results:
            return 0
        values = sorted(r.latency_ms for r in self.results)
        return values[len(values) // 2]

    @property
    def p95_latency_ms(self) -> int:
        if not self.results:
            return 0
        values = sorted(r.latency_ms for r in self.results)
        return values[min(int(len(values) * 0.95), len(values) - 1)]

    def by_category(self) -> dict[str, float]:
        cats: dict[str, list[CaseResult]] = {}
        for r in self.results:
            cats.setdefault(r.case.category, []).append(r)
        return {
            cat: sum(r.hit_at(3) for r in rows) / len(rows) for cat, rows in sorted(cats.items())
        }

    @property
    def failures(self) -> list[CaseResult]:
        return [r for r in self.results if not r.hit_at(10)]


# --------------------------------------------------------------------------- #
# Ishga tushirish
# --------------------------------------------------------------------------- #


def _label(chunk: Any) -> str:
    """Nosozlik tahlili uchun qisqa, lekin **aniq** yorliq.

    Hujjat nomini shunchaki kesish yaramaydi: barcha kodekslar
    «Oʻzbekiston Respublikasining …» bilan boshlanadi va birinchi 18 belgi
    hammasida bir xil — qaysi kodeks ekani ko'rinmaydi.
    """
    title = chunk.doc_title
    for prefix in ("Oʻzbekiston Respublikasining ", "OʻZBEKISTON RESPUBLIKASINING "):
        if title.upper().startswith(prefix.upper()):
            title = title[len(prefix) :]
            break
    return f"{title[:22].strip()}:{chunk.article}"


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("//"):
            cases.append(EvalCase(**json.loads(line)))
    return cases


def run_eval(
    retriever: HybridRetriever,
    cases: list[EvalCase],
    *,
    top_k: int = 10,
    rerank: bool = False,
) -> EvalReport:
    results: list[CaseResult] = []

    for case in cases:
        t0 = time.time()
        found = retriever.search(case.query, top_k=top_k, rerank=rerank)
        latency = int((time.time() - t0) * 1000)

        rank: int | None = None
        for position, item in enumerate(found.results, start=1):
            if case.matches(item.chunk):
                rank = position
                break

        results.append(
            CaseResult(
                case=case,
                rank=rank,
                latency_ms=latency,
                top_articles=[_label(item.chunk) for item in found.results[:3]],
                deprecated_leaked=any(
                    item.chunk.status != "in_force" for item in found.results
                ),
            )
        )

    return EvalReport(results=results, reranked=rerank)


# --------------------------------------------------------------------------- #
# Hisobot
# --------------------------------------------------------------------------- #

TARGETS = {"recall@1": 0.60, "recall@3": 0.80, "recall@10": 0.90, "mrr": 0.75}


def render_report(report: EvalReport, label: str = "gibrid") -> str:
    def verdict(value: float, target: float) -> str:
        return "✅" if value >= target else "❌"

    lines = [
        f"# Retrieval baholash — {label}",
        "",
        f"Holatlar: {len(report.results)} · reranker: {'yoqilgan' if report.reranked else 'yo‘q'}",
        "",
        "| Metrika | Natija | Maqsad | |",
        "|---------|-------:|-------:|--|",
    ]
    for name, target in TARGETS.items():
        value = report.mrr if name == "mrr" else report.recall_at(int(name.split("@")[1]))
        lines.append(f"| {name} | {value:.0%} | {target:.0%} | {verdict(value, target)} |")

    leak = report.deprecated_leak
    lines.append(f"| deprecated leak | {leak:.0%} | 0% | {'✅' if leak == 0 else '❌'} |")
    lines += [
        f"| kechikish (median) | {report.median_latency_ms} ms | — | |",
        f"| kechikish (p95) | {report.p95_latency_ms} ms | 600 ms | "
        f"{verdict(600 - report.p95_latency_ms, 0)} |",
        "",
        "## Kategoriya bo'yicha (Recall@3)",
        "",
        "| Kategoriya | Recall@3 |",
        "|------------|---------:|",
    ]
    for cat, value in report.by_category().items():
        lines.append(f"| {cat} | {value:.0%} |")

    if report.failures:
        lines += ["", f"## Topilmagan ({len(report.failures)})", ""]
        for r in report.failures:
            lines.append(
                f"- `{r.case.id}` — {r.case.query!r}\n"
                f"  - kutilgan: {r.case.expected_articles}, olindi: {r.top_articles}"
            )

    return "\n".join(lines)
