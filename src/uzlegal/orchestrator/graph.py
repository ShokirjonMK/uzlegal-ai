"""Maslahat oqimi — RAG dan gate gacha bo'lgan zanjir.

## Nima uchun LangGraph emas

docs/06 § 4 LangGraph ni taklif qiladi va uning sabablari to'g'ri:
kuzatiluvchanlik, qayta boshlash, shartli oqim. Lekin bu grafda
**ettita tugun va ikkita shart** bor — LangGraph beradigan narsani
oddiy funksiya ham beradi, qo'shimcha bog'liqlik va abstraksiyasiz.

Muhimi grafning o'zi emas, u kafolatlaydigan uchta narsa:

* **Iz** — har qadam `TraceEvent` sifatida yoziladi (docs/06 § 9)
* **Xatolarga chidamlilik** — bitta agent yiqilsa quvur to'xtamaydi
* **Shartli oqim** — rejim va kelishmovchilikka qarab shoxlanish

Uchalasi ham shu yerda bor. Graf kutubxonasi checkpoint uchun kerak
bo'lganda (`server` profili, insonni jalb qilish) qo'shiladi — shartnoma
o'zgarmaydi, chunki tashqi dunyo faqat `consult()` ni ko'radi.

## Xatolarga chidamlilik (docs/06 § 8)

| Nosozlik | Harakat |
|----------|---------|
| Agent sxemani buzdi | 3 urinishdan keyin **o'tkazib yuboriladi** |
| Retrieval bo'sh | Agentlar chaqirilmaydi, darhol «manba topilmadi» |
| Sudya sintez qilmadi | Xom pozitsiyalar ko'rsatiladi, ogohlantirish bilan |
| Gate hamma da'voni o'chirdi | «Ishonchli javob yo'q» + manbalar ro'yxati |

Tamoyil: tizim buzilgan holatda **kamroq ma'lumot beradi, lekin yolg'on
aytmaydi**.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date
from typing import Any

from uzlegal.agents.base import SHARED_PREAMBLE, AgentContext, AgentError, build_prefix
from uzlegal.agents.roles import get_agent
from uzlegal.agents.schemas import DoctrinalAnalysis, LegalFrame, Verdict
from uzlegal.orchestrator.debate import needs_second_round
from uzlegal.orchestrator.gate import REFUSAL, GroundednessGate
from uzlegal.orchestrator.router import roles_for
from uzlegal.types import (
    Citation,
    ConsultMode,
    ConsultResult,
    Position,
    TraceEvent,
)

log = logging.getLogger(__name__)

# Kuzatuvchi: har tugun tugagach chaqiriladi (SSE oqimi shu orqali ishlaydi).
Observer = Callable[[TraceEvent], None]


class Stopwatch:
    def __init__(self) -> None:
        self.t0 = time.time()

    def ms(self) -> int:
        return int((time.time() - self.t0) * 1000)


def run(
    ctx: AgentContext,
    *,
    mode: ConsultMode,
    result: ConsultResult,
    observe: Observer | None = None,
) -> ConsultResult:
    """Agent zanjirini bajaradi va `result` ni to'ldiradi.

    `ctx` o'zgarmas deb qaraladi (docs/06): agentlar uni o'qiydi, lekin
    o'zgartirmaydi — aks holda prefix cache yaroqsiz bo'ladi.
    """
    emit = _emitter(result, observe)

    frame = _run_jurist(ctx, emit)
    result.frame = frame

    positions: dict[str, Position] = {}
    doctrine: DoctrinalAnalysis | None = None

    if mode is ConsultMode.COMPLEX:
        positions = _run_debate(ctx, frame, emit)
        result.positions = positions

    if mode in (ConsultMode.STANDARD, ConsultMode.COMPLEX):
        doctrine = _run_professor(ctx, frame, positions, emit)
        result.doctrine = doctrine

    verdict: Verdict | None = None
    if mode in (ConsultMode.STANDARD, ConsultMode.COMPLEX):
        verdict = _run_judge(ctx, frame, positions, doctrine, emit)
        result.verdict = verdict

    answer, confidence = _compose(frame, positions, verdict, mode)
    result.confidence = confidence

    # Gate — oxirgi to'siq. U javobni faqat qisqartiradi.
    watch = Stopwatch()
    gate = GroundednessGate(ctx.citations)
    checked, report = gate.check(answer)
    emit(
        TraceEvent(
            node="gate",
            ms=watch.ms(),
            detail={
                "claims": report.total,
                "kept": len(report.kept),
                "dropped": len(report.dropped),
                "flagged": len(report.flagged),
            },
        )
    )
    result.gate = report

    if report.is_empty or not checked.strip():
        result.answer = REFUSAL
        result.citations = ctx.citations
        result.confidence = 0.0
        result.warnings.append(
            "Gate barcha huquqiy da'voni rad etdi — javob manbalarga bog'lanmadi"
        )
    else:
        result.answer = checked
        result.citations = report.citations or ctx.citations
        if report.dropped:
            result.warnings.append(
                f"{len(report.dropped)} ta iqtibossiz da'vo javobdan chiqarildi"
            )
        if report.flagged:
            result.warnings.append(
                f"{len(report.flagged)} ta da'vo «noaniq» deb belgilandi (⚠)"
            )

    return result


# --------------------------------------------------------------------------- #
# Tugunlar
# --------------------------------------------------------------------------- #


def _run_jurist(ctx: AgentContext, emit: Observer) -> LegalFrame | None:
    watch = Stopwatch()
    try:
        frame = get_agent("jurist").run(ctx)
    except AgentError as exc:
        emit(TraceEvent(node="jurist", ms=watch.ms(), error=str(exc)))
        return None
    assert isinstance(frame, LegalFrame)
    emit(
        TraceEvent(
            node="jurist",
            ms=watch.ms(),
            detail={
                "facts": len(frame.facts),
                "questions": len(frame.legal_questions),
                "norms": len(frame.applicable_norms),
            },
        )
    )
    return frame


def _run_debate(
    ctx: AgentContext, frame: LegalFrame | None, emit: Observer
) -> dict[str, Position]:
    """Ikki raundli munozara. Ikkinchi raund shartli.

    Advokat va prokuror **ketma-ket** ishlaydi: bitta baza modelda
    haqiqiy parallellik yo'q, chunki adapter global holat (docs/06 § 5).
    """
    positions: dict[str, Position] = {}

    watch = Stopwatch()
    for role in ("advocate", "prosecutor"):
        try:
            # Prokuror raund 1 da ham advokat pozitsiyasini ko'radi —
            # u qarshi pozitsiya, mustaqil pozitsiya emas.
            position = get_agent(role).run(ctx, frame=frame, advocate=positions.get("advocate"))
        except AgentError as exc:
            log.warning("[%s] pozitsiya olinmadi: %s", role, exc)
            continue
        assert isinstance(position, Position)
        positions[role] = position

    second, score = needs_second_round(positions)
    emit(
        TraceEvent(
            node="debate_r1",
            ms=watch.ms(),
            detail={
                "positions": sorted(positions),
                "disagreement": score,
                "second_round": second,
            },
        )
    )
    if not second:
        return positions

    watch = Stopwatch()
    rebuttals: dict[str, Position] = {}
    for role, opponent in (("advocate", "prosecutor"), ("prosecutor", "advocate")):
        try:
            updated = get_agent(role).run(ctx, frame=frame, opponent=positions[opponent])
        except AgentError as exc:
            log.warning("[%s] rebuttal olinmadi: %s", role, exc)
            continue
        assert isinstance(updated, Position)
        rebuttals[role] = updated

    emit(TraceEvent(node="debate_r2", ms=watch.ms(), detail={"rebuttals": sorted(rebuttals)}))
    # Yangilangan pozitsiya eskisining o'rnini oladi — sudya oxirgi
    # holatni ko'rishi kerak, oraliq bosqichni emas.
    positions.update(rebuttals)
    return positions


def _run_professor(
    ctx: AgentContext,
    frame: LegalFrame | None,
    positions: dict[str, Position],
    emit: Observer,
) -> DoctrinalAnalysis | None:
    watch = Stopwatch()
    try:
        doctrine = get_agent("professor").run(ctx, frame=frame, positions=positions)
    except AgentError as exc:
        emit(TraceEvent(node="professor", ms=watch.ms(), error=str(exc)))
        return None
    assert isinstance(doctrine, DoctrinalAnalysis)
    emit(
        TraceEvent(
            node="professor",
            ms=watch.ms(),
            detail={"collisions": len(doctrine.collisions), "doctrines": len(doctrine.doctrines)},
        )
    )
    return doctrine


def _run_judge(
    ctx: AgentContext,
    frame: LegalFrame | None,
    positions: dict[str, Position],
    doctrine: DoctrinalAnalysis | None,
    emit: Observer,
) -> Verdict | None:
    watch = Stopwatch()
    missing = [r for r in ("advocate", "prosecutor") if r not in positions and positions]
    try:
        verdict = get_agent("judge").run(
            ctx, frame=frame, positions=positions, doctrine=doctrine, missing=missing
        )
    except AgentError as exc:
        emit(TraceEvent(node="judge", ms=watch.ms(), error=str(exc)))
        return None
    assert isinstance(verdict, Verdict)
    emit(
        TraceEvent(
            node="judge",
            ms=watch.ms(),
            detail={
                "confidence": verdict.confidence,
                "accepted": len(verdict.accepted_arguments),
                "rejected": len(verdict.rejected_arguments),
            },
        )
    )
    return verdict


# --------------------------------------------------------------------------- #
# Javobni yig'ish
# --------------------------------------------------------------------------- #


def _compose(
    frame: LegalFrame | None,
    positions: dict[str, Position],
    verdict: Verdict | None,
    mode: ConsultMode,
) -> tuple[str, float]:
    """Gate ga beriladigan matn va ishonch darajasi.

    Tartib: sudya xulosasi → pozitsiyalar → ramka. Har biri oldingisi
    bo'lmagan holda ishlaydi, ya'ni zanjir istalgan joyda uzilsa ham
    foydalanuvchi eng to'liq mavjud javobni oladi.
    """
    if verdict is not None:
        return verdict.as_answer(), verdict.confidence

    if positions:
        blocks = ["POZITSIYALAR"]
        for role, position in positions.items():
            blocks.append(f"{role.upper()}: {position.stance}")
            blocks += [
                f"- {arg.claim} " + " ".join(f"[{t}]" for t in arg.citations)
                for arg in position.arguments
            ]
        confidence = sum(p.confidence for p in positions.values()) / len(positions)
        return "\n".join(blocks), confidence * 0.7  # sintezsiz — ishonch pastroq

    if frame is not None:
        blocks = []
        if frame.legal_questions:
            blocks.append("HUQUQIY SAVOLLAR\n" + "\n".join(f"- {q}" for q in frame.legal_questions))
        if frame.applicable_norms:
            blocks.append(
                "TEGISHLI NORMALAR\n"
                + "\n".join(
                    f"- [{c.tag}] {c.doc_title or c.doc_id}, {c.article}-modda"
                    for c in frame.applicable_norms
                )
            )
        if frame.unknowns:
            blocks.append("YETISHMAYOTGAN MA'LUMOT\n" + "\n".join(f"- {u}" for u in frame.unknowns))
        # `simple` rejimda ramka **javobning o'zi**, buzilgan holat emas.
        return "\n\n".join(blocks), 0.5 if mode is ConsultMode.SIMPLE else 0.3

    return "", 0.0


def _emitter(result: ConsultResult, observe: Observer | None) -> Observer:
    def emit(event: TraceEvent) -> None:
        result.trace.append(event)
        if event.error:
            result.warnings.append(f"«{event.node}» bosqichi bajarilmadi: {event.error}")
        if observe is not None:
            observe(event)

    return emit


def build_context(
    question: str,
    citations: list[Citation],
    context_text: str,
    backend: Any,
    *,
    as_of: date | None = None,
    client_position: str | None = None,
    registry: Any = None,
    prefix_cache: bool = True,
) -> AgentContext:
    """Agentlar bo'lishadigan kontekstni tayyorlaydi.

    Prefix KV-cache shu yerda hisoblanadi: umumiy prefiks (tizim
    ko'rsatmasi + huquqiy kontekst) barcha agentlar uchun bayt-baytga bir
    xil, shuning uchun uni bir marta hisoblash 3.8x tezlashtiradi
    (ADR-005). Backend qo'llab-quvvatlamasa `None` qaytadi va agentlar
    to'liq promptni yuboradi — sekinroq, lekin to'g'ri.
    """
    prefix = build_prefix(SHARED_PREAMBLE, context_text)
    cache = None
    if prefix_cache:
        try:
            cache = backend.make_prefix_cache(prefix)
        except Exception as exc:
            log.debug("Prefix cache tayyorlanmadi: %s", exc)

    return AgentContext(
        question=question,
        backend=backend,
        context_text=context_text,
        citations=citations,
        client_position=client_position,
        as_of=as_of,
        prefix=prefix,
        prefix_cache=cache,
        registry=registry,
    )


__all__ = ["build_context", "roles_for", "run"]
