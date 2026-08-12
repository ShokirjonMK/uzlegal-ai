"""`consult()` — tizimning yagona kirish nuqtasi (docs/07 § 1).

CLI, REST API, MCP server, Telegram bot va SDK — hammasi shu funksiyani
chaqiradi. Ularning ishi ikkitagina: kirishni `ConsultRequest` ga aylantirish
va `ConsultResult` ni o'z formatiga chiqarish. Biznes mantiq qobiqda
**umuman yo'q**, aks holda har bir kanal uni o'zicha buzardi.

## Nima uchun `disclaimer` majburiy maydon

Uni ixtiyoriy qilish integratsiya qiluvchiga uni tashlab ketish imkonini
beradi. Shartnomada majburiy bo'lgani uchun `ConsultResult` disclaimer siz
umuman qurilmaydi (docs/10 § 1).

## Sinxron va asinxron

`consult()` sinxron: model chaqiruvi baribir bloklovchi va MLX da GIL dan
foyda yo'q. `aconsult()` — FastAPI va boshqa async kanallar uchun o'ram; u
ishni ipga chiqaradi, shunda hodisa halqasi bloklanmaydi.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from uzlegal.agents.schemas import Verdict
from uzlegal.orchestrator.graph import ConsultState, Deps, run_consult
from uzlegal.orchestrator.router import Mode
from uzlegal.orchestrator.trace import Trace, new_trace_id
from uzlegal.types import Citation, Position

log = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ Bu javob avtomatik tizim tomonidan tayyorlangan va yuridik maslahat "
    "hisoblanmaydi. Keltirilgan normalar javob tayyorlangan sanada amalda "
    "bo'lgan. Har qanday huquqiy qaror qabul qilishdan oldin malakali yurist "
    "bilan maslahatlashing va manbalarni mustaqil tekshiring."
)

LOW_CONFIDENCE = 0.4
LOW_CONFIDENCE_CAVEAT = (
    "Ishonch darajasi past — javobni mustaqil tekshirmasdan qaror qabul qilmang."
)


# --------------------------------------------------------------------------- #
# Shartnoma — schemas/openapi.yaml dagi ConsultRequest / ConsultResult
# --------------------------------------------------------------------------- #


class ConsultRequest(BaseModel):
    question: str = Field(min_length=3, max_length=8000)
    mode: Literal["auto", "simple", "standard", "complex"] = "auto"
    agents: list[str] | None = Field(
        default=None, description="Aniq rollar. Ko'rsatilmasa — router tanlaydi."
    )
    as_of: date | None = Field(default=None, description="Qonunchilikning shu sanadagi holati")
    lang: Literal["uz", "ru", "en"] = "uz"
    client_position: str | None = None
    max_tokens: int = Field(default=2000, le=8000)
    stream: bool = False
    trace: bool = False


class ConsultResult(BaseModel):
    trace_id: str
    answer: str
    verdict: Verdict | None = None
    positions: dict[str, Position] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    caveats: list[str] = Field(default_factory=list)
    mode_used: str = ""
    latency_ms: int = 0
    model_version: str | None = None
    kb_version: str = ""
    disclaimer: str = DISCLAIMER
    trace: Trace | None = None

    @property
    def refused(self) -> bool:
        """Tizim ishonchli javob bera olmadimi.

        Bu holat xato emas: "bilmayman" to'liq huquqli javob va u
        `citations` bilan birga keladi — foydalanuvchi o'zi qarashi mumkin.
        """
        return self.confidence == 0.0


# --------------------------------------------------------------------------- #
# Kirish nuqtasi
# --------------------------------------------------------------------------- #


def consult(
    request: ConsultRequest,
    *,
    backend: Any = None,
    retriever: Any = None,
    registry: Any = None,
    use_prefix_cache: bool = True,
) -> ConsultResult:
    """Savolga to'liq maslahat beradi: router → RAG → agentlar → gate.

    Bog'liqliklar nomlangan argument sifatida beriladi va standart holatda
    global reestrdan olinadi. Bu testlarni model va indekssiz o'tkazish
    imkonini beradi — `echo` backend va kichik stub retriever yetarli.
    """
    import time

    started = time.perf_counter()
    registry = registry if registry is not None else _default_registry()
    backend = backend if backend is not None else _default_backend(registry)
    retriever = retriever if retriever is not None else _default_retriever()

    state = ConsultState(
        question=request.question,
        as_of=request.as_of,
        client_position=request.client_position,
        lang=request.lang,
        max_tokens=request.max_tokens,
        forced_mode=request.mode,
        only_roles=list(request.agents) if request.agents else None,
        trace=Trace(trace_id=new_trace_id()),
    )
    deps = Deps(
        backend=backend,
        retriever=retriever,
        registry=registry,
        use_prefix_cache=use_prefix_cache,
    )

    state = run_consult(state, deps)
    latency_ms = int((time.perf_counter() - started) * 1000)
    return _to_result(state, request, latency_ms, registry)


async def aconsult(request: ConsultRequest, **kwargs: Any) -> ConsultResult:
    """`consult()` ning asinxron o'rami — hodisa halqasini bloklamaydi."""
    import asyncio
    import functools

    return await asyncio.to_thread(functools.partial(consult, request, **kwargs))


# --------------------------------------------------------------------------- #
# Natijani yig'ish
# --------------------------------------------------------------------------- #


NO_SUCH_ARTICLE = (
    "So'ralgan {article}-modda bilim bazasida topilmadi.\n\n"
    "Modda raqami noto'g'ri bo'lishi yoki hujjat bilim bazasiga hali "
    "qo'shilmagan bo'lishi mumkin. Quyida mavzuga yaqin normalar "
    "keltirilgan — lekin ular so'ralgan modda **emas**."
)


def _to_result(
    state: ConsultState, request: ConsultRequest, latency_ms: int, registry: Any
) -> ConsultResult:
    gate = state.gate
    answer = gate.answer if gate else ""
    confidence = _confidence(state)

    # Foydalanuvchi aniq modda raqamini so'radi, lekin u indeksda yo'q.
    # Bunday holatda modelning javobi o'rniga deterministik xabar
    # beriladi va ishonch nolga tushadi: yaqin moddalarni «javob» deb
    # ko'rsatish savolga JAVOB EMAS, boshqa savolga javob bo'lardi.
    if state.missing_article:
        return ConsultResult(
            trace_id=state.trace.trace_id,
            answer=NO_SUCH_ARTICLE.format(article=state.missing_article),
            citations=gate.citations if gate else state.citations,
            confidence=0.0,
            caveats=[f"So'ralgan {state.missing_article}-modda bilim bazasida topilmadi"],
            mode_used=state.mode.value,
            latency_ms=latency_ms,
            model_version=getattr(registry, "active_id", None),
            kb_version=_kb_version(),
            disclaimer=DISCLAIMER,
            trace=state.trace if request.trace else None,
        )

    caveats = list(state.verdict.caveats) if state.verdict else []
    caveats += _gate_caveats(state)
    if state.missing:
        caveats.append("Pozitsiya olinmadi: " + ", ".join(state.missing))
    if state.frame and state.frame.unknowns:
        caveats += [f"Yetishmayotgan ma'lumot: {u}" for u in state.frame.unknowns[:3]]
    if 0.0 < confidence < LOW_CONFIDENCE:
        caveats.append(LOW_CONFIDENCE_CAVEAT)

    model_version = getattr(registry, "active_id", None)
    state.trace.model_version = model_version
    state.trace.kb_version = _kb_version()

    return ConsultResult(
        trace_id=state.trace.trace_id,
        answer=answer,
        verdict=state.verdict,
        positions=state.final_positions,
        citations=gate.citations if gate else state.citations,
        confidence=confidence,
        caveats=_dedupe(caveats),
        mode_used=state.mode.value,
        latency_ms=latency_ms,
        model_version=model_version,
        kb_version=_kb_version(),
        disclaimer=DISCLAIMER,
        trace=state.trace if request.trace else None,
    )


def _confidence(state: ConsultState) -> float:
    """Yakuniy ishonch.

    Gate rad etgan bo'lsa — 0.0 va boshqa hisob-kitob yo'q: tasdiqlanmagan
    javobga ishonch bermaslik tizimning asosiy va'dasi. Gate da'volarni
    o'chirgan bo'lsa, sudyaning ishonchi shunga mutanosib pasayadi — u
    hozir o'zi ko'rmagan (qisqartirilgan) javobga baho bergan.
    """
    gate = state.gate
    if gate is None or gate.refused:
        return 0.0

    base = state.verdict.confidence if state.verdict else _positions_confidence(state)
    if gate.claims:
        base *= gate.kept / gate.claims
    if state.missing:
        base *= 0.8
    return round(max(0.0, min(1.0, base)), 2)


def _positions_confidence(state: ConsultState) -> float:
    """Sudya yo'q bo'lsa — pozitsiyalarning eng pastini olamiz.

    O'rtacha emas, minimum: bitta agent ishonchsiz bo'lsa, javob ham
    ishonchsiz. Optimistik agregatsiya bu yerda foydalanuvchini chalg'itadi.
    """
    positions = state.final_positions
    if not positions:
        return 0.3 if state.frame else 0.0
    return min(p.confidence for p in positions.values())


def _gate_caveats(state: ConsultState) -> list[str]:
    gate = state.gate
    if gate is None:
        return []
    out: list[str] = []
    if gate.dropped:
        out.append(
            f"{gate.dropped} ta da'vo manbaga bog'lanmagani uchun javobdan chiqarildi "
            f"({'; '.join(gate.drop_reasons)})."
        )
    if gate.flagged:
        out.append(f"{gate.flagged} ta da'vo «noaniq» deb belgilandi — manba to'liq mos kelmadi.")
    if not state.citations:
        out.append("Bilim bazasida tegishli manba topilmadi.")
    return out


def _dedupe(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


# --------------------------------------------------------------------------- #
# Standart bog'liqliklar
# --------------------------------------------------------------------------- #


def _default_registry() -> Any:
    from uzlegal.config import get_registry

    return get_registry()


def _default_backend(registry: Any) -> Any:
    """Faol model backendi; model tanlanmagan bo'lsa oxirgi tanlov tiklanadi."""
    try:
        return registry.backend
    except Exception:
        if registry.restore_state():
            return registry.backend
        raise


def _default_retriever() -> Any:
    from uzlegal.index.store import KnowledgeIndex
    from uzlegal.retrieval.hybrid import HybridRetriever

    return HybridRetriever(KnowledgeIndex())


def _kb_version() -> str:
    """Bilim bazasi versiyasi — javob qaysi holatga asoslanganini bildiradi.

    Topilmasa bo'sh satr, `unknown` emas: shartnomada maydon majburiy, lekin
    soxta qiymat auditda chalg'itadi.
    """
    try:
        from uzlegal.index.store import KnowledgeIndex

        return str(KnowledgeIndex().meta.get("kb_version") or "")
    except Exception:
        return ""


__all__ = [
    "DISCLAIMER",
    "ConsultRequest",
    "ConsultResult",
    "Mode",
    "aconsult",
    "consult",
]
