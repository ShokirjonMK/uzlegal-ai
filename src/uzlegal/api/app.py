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
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from uzlegal.config import PROJECT_ROOT, get_registry, get_settings
from uzlegal.inference.backend import BackendUnavailableError, available_backends
from uzlegal.inference.registry import ModelSwapError
from uzlegal.ingest.sync import SyncAlreadyRunningError, SyncManager
from uzlegal.types import GenerationParams

log = logging.getLogger(__name__)

WEB_DIR = PROJECT_ROOT / "web" / "static"

app = FastAPI(
    title="UzLegal-AI API",
    version="0.1.0",
    description="O'zbekiston huquqiy tizimi uchun ko'p-agentli AI platformasi",
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


class ConsultRequest(BaseModel):
    """`POST /v1/consult` kirishi — `schemas/consult.schema.json` bilan bir xil."""

    question: str = Field(min_length=1, max_length=4000)
    mode: str | None = Field(
        default=None, description="simple · standard · complex. Berilmasa router tanlaydi."
    )
    as_of: str | None = Field(default=None, description="Tarixiy holat, YYYY-MM-DD")
    client_position: str | None = Field(default=None, max_length=8000)
    top_k: int = Field(default=8, ge=1, le=20)


def _parse_as_of(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, f"`as_of` noto'g'ri formatda: {value!r} (YYYY-MM-DD)") from exc


def _run_consult(req: ConsultRequest, observe: object | None = None) -> Any:
    from uzlegal.core import consult

    try:
        return consult(
            req.question,
            mode=req.mode,
            as_of=_parse_as_of(req.as_of),
            client_position=req.client_position,
            top_k=req.top_k,
            observe=observe,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/v1/consult", tags=["consult"])
def consult_endpoint(req: ConsultRequest) -> dict[str, Any]:
    """Savolga iqtibosga asoslangan javob.

    Javobdagi har bir huquqiy da'vo `citations` dagi manbaga bog'langan —
    bog'lanmagani groundedness gate tomonidan o'chirilgan va `gate.dropped`
    da ko'rinadi.

    Kechikish rejimga bog'liq: `simple` ~5 s, `complex` ~60 s. Uzoq
    so'rov uchun `/v1/consult/stream` ni ishlating.
    """
    return _run_consult(req).model_dump()  # type: ignore[no-any-return]


@app.post("/v1/consult/stream", tags=["consult"])
def consult_stream(req: ConsultRequest) -> StreamingResponse:
    """Maslahat oqimi (SSE) — har bosqich tugagach hodisa yuboriladi.

    Nima uchun bosqich oqimi, token oqimi emas: `complex` rejimda beshta
    agent ketma-ket ishlaydi va foydalanuvchi 60 soniya bo'sh ekranga
    qaraydi. Bosqich hodisalari «hozir prokuror javob bermoqda» deb
    ko'rsatadi — bu kutishni tushunarli qiladi.

    Yakuniy javob **oqim tugashida bir marta** yuboriladi: gate uni
    to'liq matn ustida tekshiradi, shuning uchun uni bo'lak-bo'lak
    yuborish tekshiruvdan oldin tasdiqlanmagan matnni ko'rsatish
    bo'lardi.

    Hodisalar: `step` · `answer` · `error` · `done`
    """
    import json
    import queue
    import threading

    events: queue.Queue[tuple[str, Any] | None] = queue.Queue()

    def worker() -> None:
        try:
            result = _run_consult(req, observe=lambda e: events.put(("step", e.model_dump())))
            events.put(("answer", result.model_dump()))
        except HTTPException as exc:
            events.put(("error", {"detail": exc.detail, "status": exc.status_code}))
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
    from uzlegal.orchestrator.router import roles_for
    from uzlegal.types import ConsultMode

    return {
        "agents": [
            {"role": role, "display_name": cls.display_name, "schema": cls.output_schema.__name__}
            for role, cls in AGENT_CLASSES.items()
        ],
        "modes": {mode.value: roles_for(mode) for mode in ConsultMode},
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


@app.get("/v1/health", tags=["system"])
def health() -> dict[str, Any]:
    reg = get_registry()
    return {
        "status": "healthy" if reg.active_id else "degraded",
        "model_ready": reg.active_id is not None,
        "active_model": reg.active_id,
        "kb_ready": _sync.state.kb_version is not None,
        "kb_version": _sync.state.kb_version,
        "kb_stale": _sync.state.is_stale(),
        "sync_status": _sync.status.value,
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
        "kb_version": _sync.state.kb_version,
        "kb_updated_at": (
            _sync.state.last_sync_at.isoformat() if _sync.state.last_sync_at else None
        ),
        "kb_age_days": _sync.state.age_days(),
        "available_agents": ["jurist", "advocate", "prosecutor", "professor", "judge"],
    }


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
