"""FastAPI ilovasi — model boshqaruvi va (keyinchalik) maslahat endpointlari.

Hozirgi bosqichda (Faza 0) model reestri to'liq ishlaydi. Maslahat oqimi
Faza 2–5 da qo'shiladi; endpoint shakli `schemas/openapi.yaml` da belgilangan.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from uzlegal import signature
from uzlegal.api.auth import access_control, auth_status
from uzlegal.config import DATA_DIR, PROJECT_ROOT, get_registry, get_settings
from uzlegal.core import ConsultRequest, ConsultResult
from uzlegal.court import CourtReport, review
from uzlegal.inference.backend import BackendUnavailableError, available_backends
from uzlegal.inference.registry import ModelSwapError
from uzlegal.ingest.sync import SyncAlreadyRunningError, SyncManager
from uzlegal.types import DateCoverage, GenerationParams
from uzlegal.users.store import UserStore

log = logging.getLogger(__name__)

WEB_DIR = PROJECT_ROOT / "web" / "static"

app = FastAPI(
    title="UzLegal-AI API",
    version="0.1.0",
    description="O'zbekiston huquqiy tizimi uchun ko'p-agentli AI platformasi",
)

# --------------------------------------------------------------------------- #
# Kirish nazorati
#
# NEGA MIDDLEWARE, NEGA HAR ENDPOINTGA `Depends(...)` EMAS. Himoyani
# marshrut yo'li bo'yicha qo'yish uni UNUTIB BO'LMAYDIGAN qiladi: kelajakda
# qo'shiladigan har qanday `/v1/admin/...` avtomatik yopiq bo'ladi.
# `Depends` bilan esa yangi endpoint yozgan odam uni qo'shishni unutsa,
# marshrut jimgina ochiq qolardi — va aynan shu holat bu repoda sodir
# bo'lgan edi: `/v1/admin/users` hech qanday kalitsiz javob berardi.
# --------------------------------------------------------------------------- #

app.middleware("http")(access_control)


@app.middleware("http")
async def attribution_headers(request: Any, call_next: Any) -> Any:
    """Har bir javobga mualliflik sarlavhalarini qo'shadi.

    `X-Author`, `X-Developer`, `X-Contact`, `X-Key-Fingerprint` —
    javob qayerdan kelganini va kim yozganini ko'rsatadi. Bu
    integratsiya qiluvchi uchun ham foydali (qaysi tizim javob berdi),
    mualliflik uchun ham.

    Sarlavhalar **javobdan keyin** qo'shiladi, ya'ni xato javoblarida
    ham bo'ladi — 401 va 500 ham shu tizimdan kelgani ko'rinsin.
    """
    response = await call_next(request)
    for name, value in signature.response_headers().items():
        response.headers[name] = value
    return response


_cors = get_settings().cors_origins
if _cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )


# --------------------------------------------------------------------------- #
# Model boshqaruvi
# --------------------------------------------------------------------------- #


class ActivateRequest(BaseModel):
    model_id: str
    force: bool = False


class AdapterRequest(BaseModel):
    role: str | None = None


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.3
    role: str | None = None


@app.get("/v1/models", tags=["models"])
def list_models() -> dict[str, Any]:
    """Katalogdagi barcha modellar va ularning holati."""
    reg = get_registry()
    return {
        "active": reg.active_id,
        "active_adapter": reg.active_adapter,
        "total_memory_gb": round(reg.total_memory_gb, 1),
        "backends": available_backends(),
        "models": [m.model_dump() for m in reg.list_models()],
    }


@app.post("/v1/models/active", tags=["models"])
def activate_model(req: ActivateRequest) -> dict[str, Any]:
    """Faol modelni almashtirish.

    Eski model bo'shatiladi, yangisi yuklanadi. 24 GB da ikkalasi bir vaqtda
    sig'maydi, shuning uchun bu operatsiya atomik emas — yuklash muvaffaqiyatsiz
    bo'lsa tizim modelsiz qoladi.
    """
    reg = get_registry()
    try:
        info = reg.activate(req.model_id, force=req.force)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except BackendUnavailableError as exc:
        raise HTTPException(501, str(exc)) from exc
    except ModelSwapError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "active": info.model_dump()}


@app.delete("/v1/models/active", tags=["models"])
def unload_model() -> dict[str, Any]:
    """Modelni xotiradan bo'shatish (RAM ni bo'shatish uchun)."""
    reg = get_registry()
    reg.unload()
    return {"ok": True, "active": None}


@app.post("/v1/models/reload-catalog", tags=["models"])
def reload_catalog() -> dict[str, Any]:
    """`configs/models.yaml` ni qayta o'qish — xizmatni to'xtatmasdan.

    YAML ga yangi model qo'shib, shu endpointni chaqirsangiz u ro'yxatda
    paydo bo'ladi. Faol model yuklangan holida qoladi.
    """
    reg = get_registry()
    reg.reload_catalog()
    return {"ok": True, "models": len(reg.list_models())}


@app.post("/v1/adapters/active", tags=["models"])
def set_adapter(req: AdapterRequest) -> dict[str, Any]:
    """Rol adapterini almashtirish (~50 ms) — ADR-003."""
    reg = get_registry()
    try:
        reg.set_adapter(req.role)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc
    except ModelSwapError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "active_adapter": reg.active_adapter}


# --------------------------------------------------------------------------- #
# Generatsiya (xom — maslahat oqimi Faza 5 da)
# --------------------------------------------------------------------------- #


@app.post("/v1/generate", tags=["inference"])
def generate(req: GenerateRequest) -> dict[str, Any]:
    reg = get_registry()
    try:
        if req.role:
            reg.set_adapter(req.role)
        backend = reg.backend
    except (ModelSwapError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(409, str(exc)) from exc

    params = GenerationParams(max_tokens=req.max_tokens, temperature=req.temperature)
    text = backend.generate(req.prompt, params)
    return {"text": text, "model": reg.active_id, "adapter": reg.active_adapter}


@app.post("/v1/generate/stream", tags=["inference"])
def generate_stream(req: GenerateRequest) -> StreamingResponse:
    reg = get_registry()
    try:
        if req.role:
            reg.set_adapter(req.role)
        backend = reg.backend
    except (ModelSwapError, KeyError, FileNotFoundError) as exc:
        raise HTTPException(409, str(exc)) from exc

    params = GenerationParams(max_tokens=req.max_tokens, temperature=req.temperature)

    def event_stream() -> Iterator[str]:
        import json

        for token in backend.stream(req.prompt, params):
            yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"
        yield f"event: done\ndata: {json.dumps({'model': reg.active_id})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# --------------------------------------------------------------------------- #
# Maslahat — asosiy endpoint
# --------------------------------------------------------------------------- #
#
# So'rov va javob shakli `uzlegal.core` da belgilangan va bu yerda
# **qayta e'lon qilinmaydi**. Sabab: shakl ikki joyda turса, ular albatta
# ajralib ketadi va REST mijozi CLI dan boshqa javob oladi.


@app.post("/v1/consult", tags=["consult"])
def consult_endpoint(req: ConsultRequest) -> ConsultResult:
    """Savolga iqtibosga asoslangan javob.

    Javobdagi har bir huquqiy da'vo `citations` dagi manbaga bog'langan —
    bog'lanmagani groundedness gate tomonidan o'chirilgan va sababi
    `caveats` da ko'rinadi.

    Kechikish rejimga bog'liq: `simple` ~5 s, `complex` ~45 s. Uzoq
    so'rov uchun `/v1/consult/stream` ni ishlating.
    """
    from uzlegal.core import consult

    try:
        return consult(req)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        log.exception("Maslahat bajarilmadi")
        raise HTTPException(500, str(exc)) from exc


@app.post("/v1/consult/stream", tags=["consult"])
def consult_stream(req: ConsultRequest) -> StreamingResponse:
    """Maslahat oqimi (SSE) — har bosqich tugagach hodisa yuboriladi.

    Nima uchun **bosqich** oqimi, token oqimi emas: `complex` rejimda
    beshta agent ketma-ket ishlaydi va foydalanuvchi 45 soniya bo'sh
    ekranga qaraydi. Bosqich hodisalari «hozir prokuror javob bermoqda»
    deb ko'rsatadi — bu kutishni tushunarli qiladi.

    Yakuniy javob **oqim tugashida bir marta** yuboriladi: gate uni to'liq
    matn ustida tekshiradi, shuning uchun uni bo'lak-bo'lak yuborish
    tasdiqlanmagan matnni ko'rsatish bo'lardi.

    Hodisalar: `step` · `answer` · `error` · `done`
    """
    import json
    import queue
    import threading

    events: queue.Queue[tuple[str, Any] | None] = queue.Queue()

    def worker() -> None:
        from uzlegal.core import consult

        try:
            # Iz to'liq kerak: bosqichlar aynan undan o'qiladi.
            result = consult(req.model_copy(update={"trace": True}))
            for step in result.trace.steps if result.trace else []:
                events.put(("step", step.model_dump()))
            events.put(("answer", result.model_dump()))
        except ValueError as exc:
            events.put(("error", {"detail": str(exc), "status": 400}))
        except Exception as exc:
            log.exception("Maslahat oqimida xato")
            events.put(("error", {"detail": str(exc), "status": 500}))
        finally:
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def event_stream() -> Iterator[str]:
        while True:
            item = events.get()
            if item is None:
                yield "event: done\ndata: {}\n\n"
                return
            name, payload = item
            yield f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # Nginx oraliqda bo'lsa SSE ni buferlaydi va oqim ma'nosini
        # yo'qotadi — bu sarlavha uni o'chiradi.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/v1/agents", tags=["consult"])
def list_agents() -> dict[str, Any]:
    """Mavjud rollar va har rejimda kimlar ishtirok etishi."""
    from uzlegal.agents.roles import AGENT_CLASSES
    from uzlegal.orchestrator.router import ROLES_BY_MODE

    return {
        "agents": [
            {"role": role, "display_name": cls.display_name, "schema": cls.output_schema.__name__}
            for role, cls in AGENT_CLASSES.items()
        ],
        "modes": {mode.value: roles for mode, roles in ROLES_BY_MODE.items()},
    }


# --------------------------------------------------------------------------- #
# Bilim bazasini yangilash (admin)
# --------------------------------------------------------------------------- #

_sync = SyncManager()


class SyncStartRequest(BaseModel):
    doc_ids: list[str] | None = None


class SyncConfigRequest(BaseModel):
    interval_days: int | None = None
    auto_enabled: bool | None = None


@app.get("/v1/admin/sync", tags=["admin"])
def sync_status() -> dict[str, Any]:
    """Bilim bazasi yangilanishi holati — oxirgi sinxronizatsiya, muddat, tarix."""
    return _sync.info()


@app.post("/v1/admin/sync", tags=["admin"])
def sync_start(req: SyncStartRequest) -> dict[str, Any]:
    """Yangilashni qo'lda ishga tushirish.

    Fonda bajariladi — javob darhol qaytadi. Jarayonni `GET /v1/admin/sync`
    orqali kuzating.

    Diqqat: lex.uz `Crawl-delay: 20` talab qiladi, shuning uchun har bir
    hujjat kamida 20 soniya oladi.
    """
    try:
        report = _sync.start(trigger="manual", doc_ids=req.doc_ids)
    except SyncAlreadyRunningError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "run_id": report.run_id, "total": report.total}


@app.delete("/v1/admin/sync", tags=["admin"])
def sync_cancel() -> dict[str, Any]:
    """Ishlayotgan yangilashni to'xtatish (joriy hujjat tugagach)."""
    return {"ok": True, "cancelled": _sync.cancel()}


@app.patch("/v1/admin/sync/config", tags=["admin"])
def sync_configure(req: SyncConfigRequest) -> dict[str, Any]:
    """Avtomatik yangilash sozlamalari (interval, yoqilgan/o'chirilgan)."""
    try:
        _sync.configure(interval_days=req.interval_days, auto_enabled=req.auto_enabled)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, **_sync.info()}


# --------------------------------------------------------------------------- #
# Tizim
# --------------------------------------------------------------------------- #


def _index_status() -> tuple[bool, str, int]:
    """Indeksning HAQIQIY holati: (qurilganmi, versiya, bo'laklar soni).

    NEGA `_sync.state` YETARLI EMAS. Ilgari `kb_ready` sinxronizatsiya
    holati faylidan (`data/sync-state.json`) o'qilardi. U fayl repoda
    saqlanadi va «oxirgi marta qachondir sync bo'lgan» degani, «hozir
    indeks bor» degani emas. Natijada bo'sh mashinada ham `/v1/health`
    `kb_ready: true, kb_version: "v2026.08.10"` deb javob berardi, o'sha
    paytda `/v1/consult` esa `kb_version: ""` qaytarardi va bitta ham
    manba topmasdi. Monitoring yolg'on gapirsa — u monitoring emas.
    """
    try:
        from uzlegal.index.store import KnowledgeIndex

        index = KnowledgeIndex()
        if not index.exists():
            return False, "", 0
        meta = index.meta
        return True, str(meta.get("kb_version") or ""), int(meta.get("chunks") or 0)
    except Exception:
        return False, "", 0


@app.get("/v1/health", tags=["system"])
def health() -> dict[str, Any]:
    reg = get_registry()
    # `active_id` bo'sh bo'lsa ham saqlangan tanlov tiklanishi mumkin —
    # `consult()` aynan shunday qiladi. Salomatlik u bilan bir xil
    # javob berishi kerak, aks holda bitta jarayonda ikki xil haqiqat
    # paydo bo'ladi: health «model yo'q» deydi, consult esa ishlaydi.
    model_id = reg.active_id
    if model_id is None:
        try:
            if reg.restore_state():
                model_id = reg.active_id
        except Exception:
            model_id = None

    kb_ready, kb_version, kb_chunks = _index_status()

    return {
        "status": "healthy" if (model_id and kb_ready) else "degraded",
        "model_ready": model_id is not None,
        "active_model": model_id,
        "kb_ready": kb_ready,
        "kb_version": kb_version,
        "kb_chunks": kb_chunks,
        "kb_stale": _sync.state.is_stale(),
        "sync_status": _sync.status.value,
        # Kalitlar oshkor qilinmaydi — faqat himoya yoqilgan-yoqilmagani.
        # Bu monitoring uchun kerak: «auth: none bilan ishlab chiqarishda
        # turibmiz» holatini kimdir sezishi kerak.
        "auth": auth_status(),
    }


@app.get("/v1/meta", tags=["system"])
def meta() -> dict[str, Any]:
    settings = get_settings()
    reg = get_registry()
    return {
        "api_version": "0.1.0",
        "profile": settings.profile,
        "phase": "0 — muhit va model tanlovi",
        "active_model": reg.active_id,
        "available_backends": available_backends(),
        "total_memory_gb": round(reg.total_memory_gb, 1),
        # Indeksdan — `_sync.state` dan emas (`_index_status` izohiga qarang)
        "kb_version": _index_status()[1],
        "kb_updated_at": (
            _sync.state.last_sync_at.isoformat() if _sync.state.last_sync_at else None
        ),
        "kb_age_days": _sync.state.age_days(),
        "available_agents": ["jurist", "advocate", "prosecutor", "professor", "judge"],
        "attribution": signature.attribution(),
        "license": signature.license_status(),
    }


# --------------------------------------------------------------------------- #
# Sud jarayoni yordami
# --------------------------------------------------------------------------- #


class LitigationRequest(BaseModel):
    case: dict[str, Any]
    role: str = "advocate"


class CourtAnalysisRequest(BaseModel):
    decision_text: str
    case_type: str = "civil"


@app.post("/v1/litigation/advise", tags=["litigation"])
def litigation_advise(req: LitigationRequest) -> dict[str, Any]:
    from uzlegal.litigation.advisor import advise
    from uzlegal.litigation.case import CaseState

    try:
        case = CaseState.model_validate(req.case)
    except Exception as exc:
        raise HTTPException(422, f"Ish maʼlumotlari notoʻgʻri: {exc}") from exc

    if req.role not in ("advocate", "prosecutor", "judge"):
        raise HTTPException(400, "Rol: advocate, prosecutor yoki judge")

    advice = advise(case, req.role)  # type: ignore[arg-type]
    return advice.model_dump()


@app.post("/v1/litigation/questions", tags=["litigation"])
def litigation_questions(
    req: LitigationRequest,
    target: str = "defendant",
    max_questions: int = 10,
) -> dict[str, Any]:
    from uzlegal.litigation.case import CaseState
    from uzlegal.litigation.questions import generate_questions

    try:
        case = CaseState.model_validate(req.case)
    except Exception as exc:
        raise HTTPException(422, f"Ish maʼlumotlari notoʻgʻri: {exc}") from exc

    if req.role not in ("advocate", "prosecutor", "judge"):
        raise HTTPException(400, "Rol: advocate, prosecutor yoki judge")

    plan = generate_questions(case, target, as_role=req.role, max_questions=max_questions)  # type: ignore[arg-type]
    return plan.model_dump()


@app.post("/v1/court/analyze", tags=["court"])
def court_analyze(req: CourtAnalysisRequest) -> CourtReport:
    """Sud qarorini tekshiradi — yettita deterministik nazorat.

    Model chaqirilmaydi: bir xil matn har doim bir xil topilmalarni
    beradi va har bir topilma qarorning qaysi joyidan kelib chiqqani
    ko'rsatiladi. Tizim qarorning **shakli va izchilligini** tekshiradi,
    ishning mohiyatini emas.
    """
    if not req.decision_text.strip():
        raise HTTPException(400, "`decision_text` bo'sh")
    return review(req.decision_text)


# --------------------------------------------------------------------------- #
# Integrity (pora belgilari)
# --------------------------------------------------------------------------- #


class IntegrityRequest(BaseModel):
    decision_text: str


class IntegrityBatchRequest(BaseModel):
    decision_texts: list[str]
    judge: str = ""


@app.post("/v1/integrity/check", tags=["integrity"])
def integrity_check(req: IntegrityRequest) -> dict[str, Any]:
    """Bitta sud qarorida pora belgilarini tekshiradi.

    Model chaqirilmaydi: deterministik qoidalar asosida ishlaydi.
    Tizim BELGI topadi, XULOSA emas — pora fakti faqat vakolatli
    organlar tomonidan aniqlanadi.
    """
    if not req.decision_text.strip():
        raise HTTPException(400, "`decision_text` bo'sh")
    try:
        from uzlegal.integrity.detector import detect_from_text

        return detect_from_text(req.decision_text).model_dump()
    except Exception as exc:
        raise HTTPException(500, f"Tekshiruv xatosi: {exc}") from exc


@app.post("/v1/integrity/profile", tags=["integrity"])
def integrity_profile(req: IntegrityBatchRequest) -> dict[str, Any]:
    """Bir nechta qaror asosida sudya profilini tuzadi.

    Kamida 5 qaror tavsiya etiladi — kamroq boʻlsa statistik xulosa
    chiqarish qiyin.
    """
    if not req.decision_texts:
        raise HTTPException(400, "`decision_texts` bo'sh")
    try:
        from uzlegal.court.parser import parse
        from uzlegal.integrity.profile import build_profile

        decisions = [parse(text) for text in req.decision_texts if text.strip()]
        judge = req.judge or (decisions[0].judge or "Nomaʼlum" if decisions else "Nomaʼlum")
        return build_profile(judge, decisions).model_dump()
    except Exception as exc:
        raise HTTPException(500, f"Profil tuzish xatosi: {exc}") from exc


# --------------------------------------------------------------------------- #
# Qidiruv (RAG) — TS web app va tashqi mijozlar uchun yagona nuqta
# --------------------------------------------------------------------------- #


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    min_score: float | None = None
    documents: list[str] | None = None
    as_of: date | None = Field(
        default=None,
        description="Qonunchilikning shu sanadagi holati. Ko'rsatilmasa — bugungi.",
    )


class SearchResult(BaseModel):
    chunk_id: str
    document: str
    article: str | None = None
    # Iqtibosning to'liq nomi — birlik («modda»/«band») va bir yorliqqa
    # bir nechta bo'lak tushganda tartib raqami bilan (docs/25).
    citation: str | None = None
    unit: str = "modda"
    occurrence: int = 1
    heading: str | None = None
    text: str
    score: float
    source: str = "hybrid"
    url: str | None = None
    # Versiya maydonlari — mijoz normaning qaysi tahririni ko'rayotganini
    # o'zi ko'rsata olishi kerak (docs/21 § 3.2).
    valid_from: str | None = None
    valid_to: str | None = None
    status: str = "in_force"


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query_kind: str
    total_hits: int
    latency_ms: int
    confident: bool
    as_of: date | None = None
    date_coverage: DateCoverage | None = None
    dropped_by_version: int = 0


@app.post("/v1/search", tags=["search"])
def search(req: SearchRequest) -> SearchResponse:
    """Qonun bazasidan gibrid qidiruv — vektor + leksik + aniq moslik.

    Bu endpoint TS web app va tashqi mijozlar uchun yagona RAG kirish
    nuqtasi. Python va TS da alohida RAG yozish oʻrniga, barcha
    mijozlar shu endpointni ishlatadi.
    """
    if not req.query.strip():
        raise HTTPException(400, "`query` boʻsh")

    try:
        from uzlegal.index.store import KnowledgeIndex
        from uzlegal.retrieval.hybrid import HybridRetriever

        index = KnowledgeIndex()
        retriever = HybridRetriever(index)
        result = retriever.search(req.query, top_k=req.top_k, as_of=req.as_of)

        items = [
            SearchResult(
                chunk_id=item.chunk.chunk_id,
                document=item.chunk.doc_title or item.chunk.doc_id,
                article=item.chunk.article,
                citation=item.chunk.citation_label,
                unit=item.chunk.unit,
                occurrence=item.chunk.occurrence,
                heading=item.chunk.heading,
                text=item.chunk.content,
                score=round(item.score, 4),
                source=item.source,
                url=item.chunk.source_url,
                valid_from=item.chunk.valid_from,
                valid_to=item.chunk.valid_to,
                status=item.chunk.status,
            )
            for item in result.results
        ]

        if req.min_score is not None:
            items = [i for i in items if i.score >= req.min_score]

        return SearchResponse(
            results=items,
            query_kind=result.query_kind.value,
            total_hits=len(result.results),
            latency_ms=result.latency_ms,
            confident=result.is_confident,
            as_of=req.as_of,
            date_coverage=result.coverage,
            dropped_by_version=result.dropped_by_version,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            503, f"Bilim bazasi topilmadi: {exc}. Avval `uzlegal ingest` bajaring."
        ) from exc
    except Exception as exc:
        log.exception("Qidiruv xatosi")
        raise HTTPException(500, f"Qidiruv xatosi: {exc}") from exc


@app.get("/v1/search/stats", tags=["search"])
def search_stats() -> dict[str, Any]:
    """Bilim bazasi statistikasi — hujjat soni, boʻlak soni, embedder."""
    try:
        from uzlegal.index.store import KnowledgeIndex

        index = KnowledgeIndex()
        meta = index.meta
        return {
            "chunks": meta.get("chunks", 0),
            "documents": meta.get("documents", 0),
            "embedder": meta.get("embedder"),
            "kb_version": meta.get("kb_version"),
            "status": "tayyor" if meta else "qurilmagan",
        }
    except FileNotFoundError:
        return {"chunks": 0, "documents": 0, "embedder": None, "status": "qurilmagan"}
    except Exception as exc:
        raise HTTPException(500, f"Statistika xatosi: {exc}") from exc


# --------------------------------------------------------------------------- #
# Javob pasporti (docs/21 § 4)
# --------------------------------------------------------------------------- #


class PassportVerifyRequest(BaseModel):
    token: str


@app.post("/v1/passport/verify", tags=["passport"])
def passport_verify(req: PassportVerifyRequest) -> dict[str, Any]:
    """Javob pasportini tekshiradi — **kalitsiz ochiq marshrut**.

    Tekshirish ommaviy amal: pasportni qo'lida ushlab turgan tomon
    (mijoz, qarshi tomon vakili, sud) uning haqiqiyligini API kalitisiz
    aniqlay olishi kerak. Kalit talab qilinsa isbot faqat obunachiga
    ochiq bo'lardi va pasportning butun ma'nosi yo'qolardi.

    Bu yerda hech qanday maxfiy ma'lumot oshkor bo'lmaydi: pasportda
    savol ham, javob matni ham yo'q — faqat ularning xeshi.

    Yaroqsiz token 4xx emas, **200 va `valid: false`** bilan qaytadi:
    «bu pasport soxta» — so'rovga to'liq javob, so'rovdagi xato emas.
    """
    from uzlegal.passport import PassportError, verify_passport

    try:
        passport = verify_passport(req.token)
    except PassportError as exc:
        return {"valid": False, "reason": str(exc)}
    return {"valid": True, "passport": passport.as_dict()}


# --------------------------------------------------------------------------- #
# Foydalanuvchi tizimi
# --------------------------------------------------------------------------- #


class UserCreateRequest(BaseModel):
    user_id: str
    telegram_id: str | None = None
    name: str = ""
    plan: str = "bepul"


class PlanUpdateRequest(BaseModel):
    plan: str


_user_store: UserStore | None = None


def _get_store() -> UserStore:
    """Foydalanuvchi bazasi — bitta nusxa.

    Ilgari nusxa funksiya atributida saqlanardi (`_get_store._instance`),
    bu esa mypy uchun `Any` edi va tip tekshiruvi shu yerda uzilardi.
    Modul darajasidagi o'zgaruvchi bir xil ishlaydi va tipi ma'lum.
    """
    global _user_store
    if _user_store is None:
        _user_store = UserStore(DATA_DIR / "users.db")
    return _user_store


@app.post("/v1/admin/users", tags=["users"])
def create_user(req: UserCreateRequest) -> dict[str, Any]:
    """Yangi foydalanuvchi yaratadi. API kalitini faqat bir marta koʻrsatadi."""
    from uzlegal.users.models import DuplicateUserError
    from uzlegal.users.plans import PlanTier

    store = _get_store()
    try:
        tier = PlanTier(req.plan)
    except ValueError:
        raise HTTPException(400, f"Notoʻgʻri reja: {req.plan}") from None

    try:
        user, api_key = store.create_user(
            req.user_id,
            telegram_id=req.telegram_id,
            name=req.name,
            plan=tier,
        )
    except DuplicateUserError as exc:
        raise HTTPException(409, str(exc)) from exc

    return {"user": user.model_dump(), "api_key": api_key}


@app.get("/v1/admin/users/{user_id}", tags=["users"])
def get_user(user_id: str) -> dict[str, Any]:
    from uzlegal.users.models import UserNotFoundError

    store = _get_store()
    try:
        user = store.get_user(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return user.model_dump()


@app.patch("/v1/admin/users/{user_id}/plan", tags=["users"])
def update_user_plan(user_id: str, req: PlanUpdateRequest) -> dict[str, Any]:
    from uzlegal.users.models import UserNotFoundError
    from uzlegal.users.plans import PlanTier

    store = _get_store()
    try:
        tier = PlanTier(req.plan)
    except ValueError:
        raise HTTPException(400, f"Notoʻgʻri reja: {req.plan}") from None

    try:
        user = store.update_plan(user_id, tier)
    except UserNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return user.model_dump()


@app.get("/v1/admin/users/{user_id}/usage", tags=["users"])
def user_usage(user_id: str) -> dict[str, Any]:
    from uzlegal.users.models import UserNotFoundError

    store = _get_store()
    try:
        return store.usage_summary(user_id).model_dump()
    except UserNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/admin/users/{user_id}/regenerate-key", tags=["users"])
def regenerate_api_key(user_id: str) -> dict[str, Any]:
    from uzlegal.users.models import UserNotFoundError

    store = _get_store()
    try:
        new_key = store.regenerate_key(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"api_key": new_key}


@app.delete("/v1/admin/users/{user_id}", tags=["users"])
def deactivate_user(user_id: str) -> dict[str, Any]:
    from uzlegal.users.models import UserNotFoundError

    store = _get_store()
    try:
        store.deactivate(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"ok": True}


@app.get("/v1/plans", tags=["users"])
def list_plans() -> dict[str, Any]:
    """Barcha obuna rejalari va toʻlov holati.

    Ommaviy endpoint — narx roʻyxati yashirilmaydi. `billing.enabled`
    ham koʻrsatiladi: bepul davrda foydalanuvchi buni bilishi kerak.
    """
    from uzlegal.users.plans import PLANS, billing

    state = billing()
    return {
        "billing": {"enabled": state.enabled, "note": state.note},
        "plans": [p.model_dump() for p in PLANS.values()],
    }


@app.get("/v1/admin/audit", tags=["admin"])
def audit_status() -> dict[str, Any]:
    """Audit jurnali holati va zanjir butunligi (docs/10 § 5)."""
    from uzlegal import audit

    return {"stats": audit.stats(), "chain": audit.verify_chain()}


@app.get("/v1/traces/{trace_id}", tags=["admin"])
def get_trace(trace_id: str) -> dict[str, Any]:
    """Bitta maslahatning audit yozuvi.

    `docs/10` § 5: foydalanuvchi oʻz tarixini yuklab olishi mumkin.
    Hozircha admin kaliti talab qilinadi — foydalanuvchi darajasidagi
    kirish nazorati hisob tizimi bilan birga qoʻshiladi.
    """
    from uzlegal import audit

    record = audit.find(trace_id)
    if record is None:
        raise HTTPException(404, f"Audit yozuvi topilmadi: {trace_id}")
    return record


@app.post("/v1/admin/plans/reload", tags=["users"])
def reload_plans_endpoint() -> dict[str, Any]:
    """`configs/plans.yaml` ni qayta oʻqish — xizmatni toʻxtatmasdan.

    Narx va chegara — biznes qarori. Uni oʻzgartirish uchun reliz
    chiqarish yoki xizmatni qayta ishga tushirish talab qilinishi
    notoʻgʻri: admin YAML ni tahrirlaydi va shu endpointni chaqiradi.
    """
    from uzlegal.users.plans import reload_plans

    return {"ok": True, **reload_plans()}


# --------------------------------------------------------------------------- #
# Web UI
# --------------------------------------------------------------------------- #

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")


@app.on_event("startup")
def _startup() -> None:
    """Oxirgi tanlangan modelni tiklaydi."""
    reg = get_registry()
    restored = reg.restore_state()
    if restored:
        log.info("Oxirgi model tiklandi: %s", restored)

    if _sync.state.is_stale():
        log.warning(
            "Bilim bazasi eskirgan (%s kun) — yangilash tavsiya etiladi",
            _sync.state.age_days(),
        )


def serve(host: str | None = None, port: int | None = None) -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        app,
        host=host or settings.api_host,
        port=port or settings.api_port,
        log_level=settings.log_level.lower(),
    )
