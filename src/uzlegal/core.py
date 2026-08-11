"""`consult()` — tizimning yagona kirish nuqtasi.

CLI, REST API, Telegram bot, MCP server va SDK — hammasi shu funksiyani
chaqiradi. Bu ataylab: maslahat mantiqi bitta joyda bo'lsa, interfeyslar
o'rtasida xatti-harakat farqi paydo bo'lmaydi va yangi interfeys qo'shish
o'ttiz satrlik ish bo'lib qoladi.

## Zanjir

    savol → retrieval → kontekst → agentlar → sudya → gate → javob

Har bir bo'g'in mustaqil almashtiriladi (`retriever=`, `backend=`), shuning
uchun testda haqiqiy model ham, indeks ham kerak emas.

## Nima kafolatlanadi

* **Iqtibossiz huquqiy da'vo javobda qolmaydi** — gate uni o'chiradi
* **Bekor qilingan norma kontekstga tushmaydi** — versiya filtri
* **Har qadam yoziladi** — `result.trace`
* **Zanjir uzilsa ham javob qaytadi** — eng to'liq mavjud shaklda
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date
from typing import Any

from uzlegal.orchestrator.graph import build_context, run
from uzlegal.orchestrator.router import route
from uzlegal.types import Citation, ConsultMode, ConsultResult, TraceEvent

log = logging.getLogger(__name__)

Observer = Callable[[TraceEvent], None]

# Agentlarga beriladigan manbalar soni. Sakkiztadan ko'p berish kontekstni
# uzaytiradi va «lost-in-the-middle» ta'sirini kuchaytiradi (docs/04 § 6).
DEFAULT_TOP_K = 8


def consult(
    question: str,
    *,
    mode: ConsultMode | str | None = None,
    as_of: date | None = None,
    client_position: str | None = None,
    top_k: int = DEFAULT_TOP_K,
    retriever: Any = None,
    backend: Any = None,
    registry: Any = None,
    observe: Observer | None = None,
) -> ConsultResult:
    """Savolga iqtibosga asoslangan javob beradi.

    `mode` berilmasa router uni savol shaklidan aniqlaydi. `as_of` —
    tarixiy holat: «2021-yilda qanday edi?» degan savol uchun.
    """
    started = time.time()
    if not question.strip():
        raise ValueError("Savol bo'sh")

    resolved_mode = _resolve_mode(mode, question, client_position)
    result = ConsultResult(
        question=question,
        mode=resolved_mode,
        as_of=as_of.isoformat() if as_of else None,
    )

    # --- 1. Retrieval --------------------------------------------------- #

    retriever = retriever if retriever is not None else _default_retriever()
    t0 = time.time()
    try:
        found = retriever.search(question, top_k=top_k, as_of=as_of)
    except Exception as exc:
        log.warning("Retrieval bajarilmadi: %s", exc)
        result.trace.append(TraceEvent(node="retrieve", ms=_ms(t0), error=str(exc)))
        result.answer = NO_SOURCES
        result.warnings.append(f"Bilim bazasi o'qilmadi: {exc}")
        result.total_ms = _ms(started)
        return result

    citations, context_text = _to_context(found.results)
    event = TraceEvent(
        node="retrieve",
        ms=_ms(t0),
        detail={
            "chunks": len(citations),
            "kind": found.query_kind.value,
            "routed": found.routed_domains,
            "graph": found.graph_hits,
            "top_score": round(found.top_score, 4),
        },
    )
    result.trace.append(event)
    if observe is not None:
        observe(event)

    # Manba yo'q — agentlar chaqirilmaydi. Modelga bo'sh kontekst berish
    # uni xotiradan javob yozishga undaydi; aynan shuni oldini olamiz.
    if not citations:
        result.answer = NO_SOURCES
        result.warnings.append("Savolga mos ishonchli manba topilmadi")
        result.total_ms = _ms(started)
        return result

    # Foydalanuvchi aniq modda raqamini aytgan, lekin u indeksda yo'q.
    # Bu holatda semantik jihatdan yaqin moddalarni ko'rsatish **xato**:
    # savol «9999-moddada nima yozilgan» edi, javob esa boshqa modda
    # haqida bo'lardi va foydalanuvchi buni sezmasligi mumkin.
    missing = _missing_article(question, found)
    if missing is not None:
        result.answer = NO_SUCH_ARTICLE.format(article=missing)
        result.citations = citations
        result.warnings.append(f"So'ralgan {missing}-modda bilim bazasida topilmadi")
        result.total_ms = _ms(started)
        return result

    # --- 2. Model ------------------------------------------------------- #

    if backend is None:
        registry = registry if registry is not None else _default_registry()
        backend = _backend_from(registry, result)
        if backend is None:
            result.citations = citations
            result.answer = NO_MODEL
            result.total_ms = _ms(started)
            return result

    result.model = getattr(getattr(backend, "spec", None), "id", None)
    result.kb_version = _kb_version(retriever)

    # --- 3. Agentlar va gate -------------------------------------------- #

    ctx = build_context(
        question,
        citations,
        context_text,
        backend,
        as_of=as_of,
        client_position=client_position,
        registry=registry,
    )
    run(ctx, mode=resolved_mode, result=result, observe=observe)

    result.total_ms = _ms(started)
    log.info(
        "Maslahat tugadi: rejim=%s, %d ms, %d iqtibos, gate %d/%d",
        result.mode.value,
        result.total_ms,
        len(result.citations),
        len(result.gate.kept),
        result.gate.total,
    )
    return result


# --------------------------------------------------------------------------- #
# Yordamchi qismlar
# --------------------------------------------------------------------------- #


NO_SOURCES = (
    "Berilgan savol bo'yicha bilim bazasidan ishonchli manba topilmadi.\n\n"
    "Savolni boshqacha ifodalab ko'ring yoki tegishli kodeks nomini "
    "qo'shing (masalan «Mehnat kodeksi bo'yicha…»)."
)

NO_MODEL = (
    "Model tanlanmagan — javob generatsiya qilinmadi.\n\n"
    "Modelni tanlang: `uzlegal models use <model-id>`.\n"
    "Quyida savolga tegishli topilgan normalar keltirilgan."
)

NO_SUCH_ARTICLE = (
    "So'ralgan {article}-modda bilim bazasida topilmadi.\n\n"
    "Modda raqami noto'g'ri bo'lishi yoki hujjat bilim bazasiga hali "
    "qo'shilmagan bo'lishi mumkin. Quyida mavzuga yaqin normalar "
    "keltirilgan — lekin ular so'ralgan modda **emas**."
)


def _missing_article(question: str, found: Any) -> str | None:
    """So'ralgan modda raqami indeksda yo'qmi.

    Faqat foydalanuvchi modda raqamini ochiq aytgan holatda ishlaydi
    (`FK 9999-modda`). Aniq moslik kanali bo'sh qaytgan bo'lsa — bunday
    modda yo'q, va bu deterministik javob: taxmin qilinmaydi.
    """
    from uzlegal.retrieval.hybrid import QueryKind, extract_article_ref

    if found.query_kind is not QueryKind.ARTICLE_LOOKUP or found.exact_hits:
        return None
    article, _ = extract_article_ref(question)
    return article


def _resolve_mode(
    mode: ConsultMode | str | None, question: str, client_position: str | None
) -> ConsultMode:
    if mode is None:
        return route(question, client_position=client_position)
    if isinstance(mode, ConsultMode):
        return mode
    try:
        return ConsultMode(mode)
    except ValueError as exc:
        allowed = ", ".join(m.value for m in ConsultMode)
        raise ValueError(f"Noma'lum rejim: '{mode}'. Mavjud: {allowed}") from exc


def _to_context(results: list[Any]) -> tuple[list[Citation], str]:
    """Qidiruv natijalarini iqtibos va kontekst matniga aylantiradi.

    Belgilar (`C1`, `C2`) shu yerda beriladi va boshqa hech qayerda —
    ular gate uchun yagona bog'lovchi, shuning uchun manbasi bitta
    bo'lishi shart.
    """
    from uzlegal.retrieval.hybrid import build_context as render

    context_text, used = render(results)
    citations: list[Citation] = []
    for i, item in enumerate(used, start=1):
        chunk = item.chunk
        citations.append(
            Citation(
                tag=f"C{i}",
                doc_id=chunk.doc_id,
                doc_title=chunk.doc_title,
                doc_type=chunk.doc_type,
                article=chunk.article or "—",
                part=chunk.part,
                valid_from=chunk.valid_from,
                valid_to=chunk.valid_to,
                status=chunk.status,  # type: ignore[arg-type]
                url=chunk.source_url,
                excerpt=chunk.content,
            )
        )
    return citations, context_text


def _default_retriever() -> Any:
    from uzlegal.index.store import KnowledgeIndex
    from uzlegal.retrieval.hybrid import HybridRetriever

    return HybridRetriever(KnowledgeIndex())


def _default_registry() -> Any:
    from uzlegal.config import get_registry

    return get_registry()


def _backend_from(registry: Any, result: ConsultResult) -> Any:
    """Faol backend. Model yuklanmagan bo'lsa oxirgi tanlov tiklanadi."""
    try:
        return registry.backend
    except Exception:
        pass
    try:
        if registry.restore_state():
            return registry.backend
    except Exception as exc:
        log.warning("Model tiklanmadi: %s", exc)
    result.warnings.append("Faol model yo'q — javob generatsiya qilinmadi")
    return None


def _kb_version(retriever: Any) -> str | None:
    try:
        version = retriever.index.meta.get("kb_version")
    except Exception:
        return None
    return str(version) if version else None


def _ms(since: float) -> int:
    return int((time.time() - since) * 1000)


__all__ = ["ConsultMode", "ConsultResult", "consult"]
