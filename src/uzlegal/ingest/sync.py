"""Bilim bazasini yangilab turish.

## Nima uchun bu majburiy

O'zbekiston qonunchiligi doimiy o'zgaradi. Eskirgan bilim bazasi bilan tizim
**bekor qilingan normani amaldagidek** taqdim etishi mumkin — bu
`docs/09-deployment.md` da P0 (kritik) insident deb belgilangan va
`docs/00-overview.md` dagi «0% deprecated» talabini buzadi.

Shuning uchun yangilanish ixtiyoriy funksiya emas, tizimning bir qismi.

## Ikki rejim

**Avtomatik** — har 7 kunda (sozlanadi). Ustuvor hujjatlar qayta tekshiriladi,
`sha256` bo'yicha o'zgarganlari qayta ishlanadi.

**Qo'lda** — admin panelidan yoki CLI dan istalgan vaqtda. Muhim qonun
o'zgarishi e'lon qilinganda 7 kun kutish shart emas.

## Nima uchun 7 kun

| Interval | Ijobiy | Salbiy |
|----------|--------|--------|
| 1 kun | Eng yangi | lex.uz ga ortiqcha yuk (Crawl-delay 20 s) |
| **7 kun** | **Muvozanat** | Eng yomon holatda 7 kunlik kechikish |
| 30 kun | Yengil | Yuridik ish uchun juda eskirgan |

Qonun kuchga kirishi odatda e'lon qilinganidan keyin kamida 10 kun o'tadi,
shuning uchun 7 kunlik sikl amalda kechikish yaratmaydi.

Har sinxronizatsiyada bilim bazasi versiyasi yangilanadi va `/v1/meta` da
`kb_version` va `kb_updated_at` sifatida ko'rinadi — foydalanuvchi ma'lumot
qanchalik yangi ekanini bilishi kerak.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from uzlegal.ingest.connectors.lex_uz import PRIORITY_DOCS, LexUzConnector
from uzlegal.ingest.parsers.lex_uz import LexUzParser

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_DAYS = 7
STALE_WARNING_DAYS = 14  # bundan keyin ogohlantirish (docs/09 § 6)


class SyncStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentOutcome(BaseModel):
    doc_id: str
    title: str | None = None
    status: str  # new · changed · unchanged · error
    articles: int | None = None
    amendments: int | None = None
    error: str | None = None


class SyncReport(BaseModel):
    """Bitta sinxronizatsiya natijasi — audit uchun saqlanadi."""

    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    trigger: str = "scheduled"  # scheduled · manual · startup
    status: SyncStatus = SyncStatus.RUNNING

    total: int = 0
    processed: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    errors: int = 0

    documents: list[DocumentOutcome] = Field(default_factory=list)
    kb_version: str | None = None
    message: str | None = None

    @property
    def progress(self) -> float:
        return self.processed / self.total if self.total else 0.0

    @property
    def duration_s(self) -> float | None:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class SyncState(BaseModel):
    """Sinxronizatsiya holati — qayta ishga tushirishdan keyin ham saqlanadi."""

    last_sync_at: datetime | None = None
    last_run_id: str | None = None
    interval_days: int = DEFAULT_INTERVAL_DAYS
    auto_enabled: bool = True
    kb_version: str | None = None
    history: list[SyncReport] = Field(default_factory=list)

    def next_due(self) -> datetime | None:
        if self.last_sync_at is None:
            return None
        return self.last_sync_at + timedelta(days=self.interval_days)

    def is_due(self, now: datetime | None = None) -> bool:
        if not self.auto_enabled:
            return False
        if self.last_sync_at is None:
            return True
        return (now or datetime.now(UTC)) >= self.next_due()  # type: ignore[operator]

    def age_days(self, now: datetime | None = None) -> float | None:
        if self.last_sync_at is None:
            return None
        return ((now or datetime.now(UTC)) - self.last_sync_at).total_seconds() / 86400

    def is_stale(self) -> bool:
        age = self.age_days()
        return age is None or age > STALE_WARNING_DAYS


# --------------------------------------------------------------------------- #
# Boshqaruvchi
# --------------------------------------------------------------------------- #


class SyncManager:
    """Yangilanishni boshqaradi: rejalashtirish, ishga tushirish, holat.

    Bir vaqtda faqat bitta sinxronizatsiya ishlaydi — lex.uz ga parallel
    murojaat Crawl-delay ni buzardi.
    """

    def __init__(self, state_path: Path = Path("data/sync-state.json")) -> None:
        self.state_path = state_path
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self._current: SyncReport | None = None
        self.state = self._load_state()

    # ------------------------------------------------------------------ #

    def _load_state(self) -> SyncState:
        if not self.state_path.exists():
            return SyncState()
        try:
            return SyncState(**json.loads(self.state_path.read_text(encoding="utf-8")))
        except Exception as exc:
            log.warning("Sinxronizatsiya holati o'qilmadi: %s", exc)
            return SyncState()

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Tarixni cheklaymiz — fayl cheksiz o'smasligi uchun
        self.state.history = self.state.history[-20:]
        self.state_path.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Holat
    # ------------------------------------------------------------------ #

    @property
    def status(self) -> SyncStatus:
        if self._thread is not None and self._thread.is_alive():
            return SyncStatus.RUNNING
        return self._current.status if self._current else SyncStatus.IDLE

    @property
    def current(self) -> SyncReport | None:
        return self._current

    def info(self) -> dict[str, object]:
        """Admin paneli uchun to'liq holat."""
        age = self.state.age_days()
        return {
            "status": self.status.value,
            "auto_enabled": self.state.auto_enabled,
            "interval_days": self.state.interval_days,
            "last_sync_at": self.state.last_sync_at.isoformat() if self.state.last_sync_at else None,
            "next_due_at": self.state.next_due().isoformat() if self.state.next_due() else None,
            "age_days": round(age, 1) if age is not None else None,
            "is_due": self.state.is_due(),
            "is_stale": self.state.is_stale(),
            "kb_version": self.state.kb_version,
            "current": self._current.model_dump(mode="json") if self._current else None,
            "history": [r.model_dump(mode="json") for r in self.state.history[-5:]],
        }

    # ------------------------------------------------------------------ #
    # Ishga tushirish
    # ------------------------------------------------------------------ #

    def start(self, *, trigger: str = "manual", doc_ids: list[str] | None = None) -> SyncReport:
        """Sinxronizatsiyani fonda boshlaydi.

        Allaqachon ishlab turgan bo'lsa xato beradi — parallel yig'ish
        Crawl-delay ni buzadi.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise SyncAlreadyRunningError(
                    f"Sinxronizatsiya allaqachon ishlamoqda "
                    f"({self._current.processed if self._current else 0}"
                    f"/{self._current.total if self._current else 0})"
                )

            ids = doc_ids or [d.doc_id for d in PRIORITY_DOCS]
            run_id = f"sync_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
            self._current = SyncReport(
                run_id=run_id,
                started_at=datetime.now(UTC),
                trigger=trigger,
                total=len(ids),
            )
            self._cancel.clear()
            self._thread = threading.Thread(
                target=self._run, args=(ids,), name="uzlegal-sync", daemon=True
            )
            self._thread.start()
            log.info("Sinxronizatsiya boshlandi: %s (%d hujjat, %s)", run_id, len(ids), trigger)
            return self._current

    def cancel(self) -> bool:
        """Ishlayotgan sinxronizatsiyani to'xtatadi (joriy hujjatdan keyin)."""
        if self._thread is None or not self._thread.is_alive():
            return False
        self._cancel.set()
        return True

    def _run(self, doc_ids: list[str]) -> None:
        report = self._current
        assert report is not None
        titles = {d.doc_id: d.title for d in PRIORITY_DOCS}
        parser = LexUzParser()

        try:
            with LexUzConnector() as connector:
                connector.read_crawl_delay()

                for doc_id, status, raw in connector.fetch_many(doc_ids, skip_unchanged=True):
                    if self._cancel.is_set():
                        report.status = SyncStatus.CANCELLED
                        report.message = "Foydalanuvchi tomonidan to'xtatildi"
                        break

                    outcome = DocumentOutcome(
                        doc_id=doc_id, title=titles.get(doc_id), status=status
                    )

                    if status in ("new", "changed") and raw is not None:
                        try:
                            parsed = parser.parse(raw)
                            outcome.articles = len(parsed.articles)
                            outcome.amendments = len(parsed.amendments)
                            outcome.title = parsed.title[:120]
                        except Exception as exc:
                            outcome.status = "error"
                            outcome.error = f"parsing: {exc}"
                            status = "error"

                    report.documents.append(outcome)
                    report.processed += 1
                    setattr(report, status, getattr(report, status, 0) + 1)
                    log.info("[%d/%d] %s — %s", report.processed, report.total, doc_id, status)

            if report.status != SyncStatus.CANCELLED:
                report.status = SyncStatus.COMPLETED

        except Exception as exc:
            log.exception("Sinxronizatsiya xatosi")
            report.status = SyncStatus.FAILED
            report.message = str(exc)

        finally:
            report.finished_at = datetime.now(UTC)
            if report.status == SyncStatus.COMPLETED:
                report.kb_version = f"v{datetime.now(UTC).strftime('%Y.%m.%d')}"
                self.state.last_sync_at = report.finished_at
                self.state.last_run_id = report.run_id
                self.state.kb_version = report.kb_version
            self.state.history.append(report)
            self._save_state()
            log.info(
                "Sinxronizatsiya tugadi: %s — %s (yangi %d, o'zgargan %d, o'zgarmagan %d, xato %d)",
                report.run_id, report.status.value,
                report.new, report.changed, report.unchanged, report.errors,
            )

    # ------------------------------------------------------------------ #
    # Sozlamalar
    # ------------------------------------------------------------------ #

    def configure(self, *, interval_days: int | None = None, auto_enabled: bool | None = None) -> None:
        if interval_days is not None:
            if not 1 <= interval_days <= 90:
                raise ValueError("interval_days 1 dan 90 gacha bo'lishi kerak")
            self.state.interval_days = interval_days
        if auto_enabled is not None:
            self.state.auto_enabled = auto_enabled
        self._save_state()

    def maybe_run_scheduled(self) -> SyncReport | None:
        """Muddati kelgan bo'lsa avtomatik ishga tushiradi.

        Xizmat ishga tushganda va davriy taymer bilan chaqiriladi.
        """
        if not self.state.is_due():
            return None
        if self._thread is not None and self._thread.is_alive():
            return None
        log.info("Rejalashtirilgan sinxronizatsiya muddati keldi")
        return self.start(trigger="scheduled")


class SyncAlreadyRunningError(RuntimeError):
    pass
