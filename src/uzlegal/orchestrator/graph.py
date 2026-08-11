"""Maslahat oqimi — docs/06 § 4.

    route → retrieve → jurist → debate(r1[, r2]) → professor → judge → gate

## Nima uchun LangGraph majburiy emas

Spetsifikatsiya oqimni LangGraph grafi sifatida ifodalaydi va u
checkpointing, qayta boshlash va kuzatiluvchanlik beradi. Lekin oqimning
**o'zi** — sakkizta tugun va uchta shartli o'tish. Uni tashqi kutubxonasiz
ham aynan shu shaklda yozish mumkin va shunda `local-dev` profilida
qo'shimcha bog'liqlik kerak bo'lmaydi (ADR-007).

Shuning uchun bu modul ikki yo'lni ham beradi:

* tugun funksiyalari (`node_*`) — yagona haqiqat manbai, sof funksiyalar
* `run_consult()` — ularni oddiy shartli mantiq bilan bog'laydi
* `build_langgraph()` — langgraph o'rnatilgan bo'lsa **o'sha** funksiyalardan
  graf yig'adi

Mantiq bitta joyda yozilgan, shuning uchun ikki yo'l ajralib keta olmaydi.

## Xatolarga chidamlilik

docs/06 § 8 jadvalidagi qoida: bitta agent yiqilsa quvur to'xtamaydi, u
agent o'tkazib yuboriladi va sudyaga "pozitsiya olinmadi" deb belgilanadi.
Yagona to'xtatuvchi holat — retrieval bo'sh: manbasiz javob berish bu
tizimning butun ma'nosiga zid.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from uzlegal.agents.base import SHARED_PREAMBLE, AgentContext, AgentError, build_prefix
from uzlegal.agents.roles import get_agent, render_position
from uzlegal.agents.schemas import DoctrinalAnalysis, LegalFrame, Verdict
from uzlegal.orchestrator import debate as debate_mod
from uzlegal.orchestrator.gate import GateReport, groundedness_gate
from uzlegal.orchestrator.router import ROLES_BY_MODE, Mode, RouteDecision, route
from uzlegal.orchestrator.trace import Trace, new_trace_id
from uzlegal.types import Citation, Position

log = logging.getLogger(__name__)

DEFAULT_TOP_K = 8
DEFAULT_BUDGET_TOKENS = 6000
NO_SOURCES = "Berilgan bilim bazasida bu savolga tegishli manba topilmadi."
NO_SYNTHESIS = "Avtomatik xulosa shakllantirilmadi — quyida agentlarning xom pozitsiyalari."


# --------------------------------------------------------------------------- #
# Holat va bog'liqliklar
# --------------------------------------------------------------------------- #


@dataclass
class Deps:
    """Oqimning tashqi bog'liqliklari — hammasi almashtiriladigan.

    Test va `echo` backend bilan ishlash aynan shu yerda hal qilinadi:
    haqiqiy retriever va model o'rniga stub berish yetarli, oqim kodi
    o'zgarmaydi.
    """

    backend: Any
    retriever: Any = None
    registry: Any = None
    top_k: int = DEFAULT_TOP_K
    budget_tokens: int = DEFAULT_BUDGET_TOKENS
    use_prefix_cache: bool = True


@dataclass
class ConsultState:
    """docs/06 § 4 dagi `ConsultState`."""

    question: str
    mode: Mode = Mode.STANDARD
    as_of: date | None = None
    client_position: str | None = None
    lang: str = "uz"
    max_tokens: int = 2000
    forced_mode: str | None = None
    only_roles: list[str] | None = None

    decision: RouteDecision | None = None
    context: list[Any] = field(default_factory=list)
    context_text: str = ""
    citations: list[Citation] = field(default_factory=list)
    frame: LegalFrame | None = None
    positions: dict[str, Position] = field(default_factory=dict)
    rebuttals: dict[str, Position] = field(default_factory=dict)
    doctrine: DoctrinalAnalysis | None = None
    verdict: Verdict | None = None
    gate: GateReport | None = None

    disagreement: float = 0.0
    missing: list[str] = field(default_factory=list)
    trace: Trace = field(default_factory=lambda: Trace(trace_id=new_trace_id()))

    # Agent chaqiruvlari uchun tayyorlangan kontekst
    ctx: AgentContext | None = None

    @property
    def final_positions(self) -> dict[str, Position]:
        """Raund 2 bo'lgan bo'lsa yangilangan pozitsiyalar ustun."""
        return {**self.positions, **self.rebuttals}

    def wants(self, role: str) -> bool:
        """Rol shu so'rovda ishtirok etadimi.

        `only_roles` — foydalanuvchi `agents=[…]` bilan aniq ko'rsatgan
        ro'yxat (openapi `ConsultRequest.agents`). Ko'rsatilmasa rejim
        hal qiladi.
        """
        if self.only_roles is not None:
            return role in self.only_roles
        return role in ROLES_BY_MODE[self.mode]


# --------------------------------------------------------------------------- #
# Tugunlar
# --------------------------------------------------------------------------- #


def node_route(state: ConsultState, deps: Deps) -> ConsultState:
    with state.trace.step("route") as step:
        decision = route(
            state.question,
            forced=state.forced_mode,
            has_client_position=bool(state.client_position),
        )
        state.decision = decision
        state.mode = decision.mode
        state.trace.mode = decision.mode.value
        step.set(mode=decision.mode.value, reason=decision.reason, signals=decision.signals)
    return state


def node_retrieve(state: ConsultState, deps: Deps) -> ConsultState:
    """Gibrid qidiruv va agentlar uchun umumiy kontekst.

    Prefix KV-cache shu yerda quriladi — kontekst tayyor bo'lgan zahoti va
    birinchi agent chaqirilishidan oldin (docs/06 § 6).
    """
    from uzlegal.retrieval.hybrid import build_context

    with state.trace.step("retrieve") as step:
        results: list[Any] = []
        if deps.retriever is not None:
            try:
                found = deps.retriever.search(state.question, top_k=deps.top_k, as_of=state.as_of)
                results = list(getattr(found, "results", found) or [])
            except Exception as exc:
                log.warning("Retrieval xatosi: %s", exc)
                step.set(error=str(exc))

        state.context_text, used = build_context(results, budget_tokens=deps.budget_tokens)
        state.context = used
        state.citations = [to_citation(f"C{i}", item.chunk) for i, item in enumerate(used, 1)]
        step.set(chunks=len(used), top_score=round(results[0].score, 4) if results else 0.0)

    state.ctx = AgentContext(
        question=state.question,
        backend=deps.backend,
        context_text=state.context_text,
        citations=state.citations,
        client_position=state.client_position,
        as_of=state.as_of,
        lang=state.lang,
        max_tokens=state.max_tokens,
        prefix=build_prefix(SHARED_PREAMBLE, state.context_text),
        registry=deps.registry,
    )

    if deps.use_prefix_cache and state.citations:
        with state.trace.step("prefix_cache") as step:
            state.ctx.prefix_cache = _make_prefix_cache(deps.backend, state.ctx.prefix)
            step.set(enabled=state.ctx.prefix_cache is not None)
    return state


def node_jurist(state: ConsultState, deps: Deps) -> ConsultState:
    frame = _run_agent(state, "jurist", direct=state.mode is Mode.SIMPLE)
    if isinstance(frame, LegalFrame):
        state.frame = frame
    return state


def node_debate_r1(state: ConsultState, deps: Deps) -> ConsultState:
    """Raund 1 — advokat va prokuror.

    docs/06 § 5: bitta baza modelda **haqiqiy parallellik yo'q**, adapter
    global holat. `local-dev` da bu ketma-ket bajariladi va prefix cache
    tejamkorlikni beradi. Server profilida vLLM multi-LoRA bilan bu bosqich
    haqiqatan parallel bo'ladi — shakl o'zgarmaydi.
    """
    with state.trace.step("debate_r1") as step:
        advocate = _run_agent(state, "advocate", frame=state.frame)
        if isinstance(advocate, Position):
            state.positions["advocate"] = advocate

        prosecutor = _run_agent(
            state, "prosecutor", frame=state.frame, advocate=state.positions.get("advocate")
        )
        if isinstance(prosecutor, Position):
            state.positions["prosecutor"] = prosecutor

        state.disagreement = debate_mod.score(state.positions)
        step.set(
            positions=sorted(state.positions),
            disagreement=round(state.disagreement, 3),
        )
    return state


def node_debate_r2(state: ConsultState, deps: Deps) -> ConsultState:
    """Raund 2 — rebuttal. Har agent qarshi tomonning **raund 1** pozitsiyasini ko'radi."""
    with state.trace.step("debate_r2") as step:
        for role, opponent_role in (("advocate", "prosecutor"), ("prosecutor", "advocate")):
            opponent = state.positions.get(opponent_role)
            if opponent is None:
                continue
            updated = _run_agent(state, role, frame=state.frame, opponent=opponent)
            if isinstance(updated, Position):
                state.rebuttals[role] = updated
        step.set(rebuttals=sorted(state.rebuttals))
    return state


def node_professor(state: ConsultState, deps: Deps) -> ConsultState:
    doctrine = _run_agent(state, "professor", frame=state.frame, positions=state.final_positions)
    if isinstance(doctrine, DoctrinalAnalysis):
        state.doctrine = doctrine
    return state


def node_judge(state: ConsultState, deps: Deps) -> ConsultState:
    verdict = _run_agent(
        state,
        "judge",
        frame=state.frame,
        positions=state.final_positions,
        doctrine=state.doctrine,
        missing=state.missing,
    )
    if isinstance(verdict, Verdict):
        state.verdict = verdict
    return state


def node_gate(state: ConsultState, deps: Deps) -> ConsultState:
    with state.trace.step("gate") as step:
        report = groundedness_gate(draft_answer(state), state.citations)
        state.gate = report
        step.set(**report.summary(), refused=report.refused, reasons=report.drop_reasons or None)
    return state


# --------------------------------------------------------------------------- #
# Oqim
# --------------------------------------------------------------------------- #


def run_consult(state: ConsultState, deps: Deps) -> ConsultState:
    """Oqimni boshidan oxirigacha bajaradi.

    Shartli o'tishlar docs/06 § 4 dagi graf bilan bir xil:
    kontekst bo'sh → to'g'ridan gate; rejimga qarab shoxlanish;
    kelishmovchilik chegarasiga qarab raund 2.
    """
    state.trace.question = state.question
    state.trace.as_of = state.as_of.isoformat() if state.as_of else None

    node_route(state, deps)
    node_retrieve(state, deps)

    # Retrieval bo'sh — agentlar chaqirilmaydi (docs/06 § 8).
    if not state.citations:
        node_gate(state, deps)
        return _finish(state)

    if state.wants("jurist"):
        node_jurist(state, deps)

    if state.mode is Mode.SIMPLE:
        node_gate(state, deps)
        return _finish(state)

    if state.wants("advocate") or state.wants("prosecutor"):
        node_debate_r1(state, deps)
        if debate_mod.needs_round_two(state.positions):
            node_debate_r2(state, deps)
        else:
            state.trace.add("debate_r2", 0, skipped=True, disagreement=round(state.disagreement, 3))

    if state.wants("professor"):
        node_professor(state, deps)
    if state.wants("judge"):
        node_judge(state, deps)

    node_gate(state, deps)
    return _finish(state)


def _finish(state: ConsultState) -> ConsultState:
    state.trace.total_ms = sum(step.ms for step in state.trace.steps)
    return state


# --------------------------------------------------------------------------- #
# LangGraph varianti — o'rnatilgan bo'lsa
# --------------------------------------------------------------------------- #


def langgraph_available() -> bool:
    try:
        import langgraph.graph  # noqa: F401
    except ImportError:
        return False
    return True


def build_langgraph(deps: Deps) -> Any:
    """Yuqoridagi tugunlardan LangGraph grafi yig'adi.

    Tugunlar aynan bir xil funksiyalar, shuning uchun ikki yo'l bir xil
    natija beradi. Graf checkpointing va tugun darajasida to'xtatish
    imkonini qo'shadi (docs/06 § 4).
    """
    from langgraph.graph import END, StateGraph

    def wrap(node: Any) -> Any:
        def run(state: ConsultState) -> ConsultState:
            result: ConsultState = node(state, deps)
            return result

        return run

    g = StateGraph(ConsultState)
    for name, node in (
        ("route", node_route),
        ("retrieve", node_retrieve),
        ("jurist", node_jurist),
        ("debate_r1", node_debate_r1),
        ("debate_r2", node_debate_r2),
        ("professor", node_professor),
        ("judge", node_judge),
        ("gate", node_gate),
    ):
        g.add_node(name, wrap(node))

    g.set_entry_point("route")
    g.add_edge("route", "retrieve")
    g.add_conditional_edges(
        "retrieve",
        lambda s: "insufficient" if not s.citations else "ok",
        {"insufficient": "gate", "ok": "jurist"},
    )
    g.add_conditional_edges(
        "jurist",
        lambda s: s.mode.value,
        {"simple": "gate", "standard": "professor", "complex": "debate_r1"},
    )
    g.add_conditional_edges(
        "debate_r1",
        lambda s: "r2" if debate_mod.needs_round_two(s.positions) else "skip",
        {"r2": "debate_r2", "skip": "professor"},
    )
    g.add_edge("debate_r2", "professor")
    g.add_edge("professor", "judge")
    g.add_edge("judge", "gate")
    g.add_edge("gate", END)
    return g.compile()


# --------------------------------------------------------------------------- #
# Yordamchilar
# --------------------------------------------------------------------------- #


def _run_agent(state: ConsultState, role: str, **inputs: Any) -> Any:
    """Agentni chaqiradi va xatoni yutadi.

    Xato quvurni to'xtatmaydi: rol `missing` ro'yxatiga tushadi va sudya
    "pozitsiya olinmadi" deb ko'radi (docs/06 § 8).
    """
    assert state.ctx is not None
    with state.trace.step(role) as step:
        try:
            result = get_agent(role).run(state.ctx, **inputs)
        except AgentError as exc:
            log.warning("[%s] o'tkazib yuborildi: %s", role, exc)
            if role not in state.missing:
                state.missing.append(role)
            step.set(skipped=True, error=str(exc))
            return None
        step.set(ok=True)
        return result


def draft_answer(state: ConsultState) -> str:
    """Gate ga beriladigan loyiha javob.

    Bu **yig'ish**, generatsiya emas: agentlar aytgan matn qayta tartiblanadi,
    yangi jumla qo'shilmaydi. Uch daraja, sifat pasayish tartibida:
    sudya xulosasi → xom pozitsiyalar → jurist ramkasi.
    """
    if state.verdict is not None:
        return state.verdict.as_answer()

    if state.positions or state.rebuttals:
        blocks = [NO_SYNTHESIS]
        blocks += [render_position(p) for p in state.final_positions.values()]
        return "\n\n".join(blocks)

    if state.frame is not None:
        return _frame_answer(state.frame)

    return ""


def _frame_answer(frame: LegalFrame) -> str:
    if frame.answer:
        blocks = ["XULOSA\n" + frame.answer]
    elif frame.applicable_norms:
        blocks = [
            "TEGISHLI NORMALAR\n"
            + "\n".join(
                f"- [{c.tag}] {c.doc_title or c.doc_id}"
                + (f", {c.article}-modda" if c.article else "")
                for c in frame.applicable_norms
            )
        ]
    else:
        return ""
    if frame.unknowns:
        blocks.append("YETISHMAYOTGAN MA'LUMOT\n" + "\n".join(f"- {u}" for u in frame.unknowns))
    return "\n\n".join(blocks)


def to_citation(tag: str, chunk: Any) -> Citation:
    """Chunkdan iqtibos yasaydi.

    `excerpt` majburiy to'ldiriladi: gate aynan shu matn bo'yicha da'voning
    qo'llab-quvvatlanganini tekshiradi. Uzunligi cheklangan — to'liq matn
    javob hajmini keraksiz shishiradi.
    """
    raw_status = str(getattr(chunk, "status", "in_force"))
    status: Literal["in_force", "superseded", "repealed"] = (
        raw_status  # type: ignore[assignment]
        if raw_status in ("in_force", "superseded", "repealed")
        else "in_force"
    )
    return Citation(
        tag=tag,
        doc_id=chunk.doc_id,
        doc_title=getattr(chunk, "doc_title", None),
        doc_type=getattr(chunk, "doc_type", None),
        article=getattr(chunk, "article", None) or "",
        part=getattr(chunk, "part", None),
        valid_from=getattr(chunk, "valid_from", None),
        valid_to=getattr(chunk, "valid_to", None),
        status=status,
        url=getattr(chunk, "source_url", None),
        excerpt=chunk.content[:600],
    )


def _make_prefix_cache(backend: Any, prefix: str) -> Any:
    """Umumiy prefiks uchun KV-cache. Backend qo'llab-quvvatlamasa `None`.

    Xato yutiladi: cache — tezlashtirish, to'g'rilik sharti emas. U
    qurilmasa tizim sekinroq, lekin bir xil javob beradi.
    """
    maker = getattr(backend, "make_prefix_cache", None)
    if maker is None:
        return None
    try:
        return maker(prefix)
    except Exception as exc:
        log.debug("Prefix cache qurilmadi: %s", exc)
        return None
