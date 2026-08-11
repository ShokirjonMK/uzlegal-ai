"""Kuzatiluvchanlik — docs/06 § 9.

Yuridik tizimda **javobning o'zi yetarli emas**: "model shunday dedi" degan
asos sudda ham, ichki tekshiruvda ham ish bermaydi. Shuning uchun har bir
qadam — retrieval natijasi, har agentning ishlagan vaqti, gate qarori —
yoziladi va foydalanuvchiga ochiq.

Trace `ConsultResult` dan alohida: javob qisqa bo'lishi kerak, audit zanjiri
esa to'liq. Ular bir strukturaga sig'maydi.
"""

from __future__ import annotations

import secrets
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    node: str
    ms: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    trace_id: str
    question: str = ""
    mode: str = ""
    as_of: str | None = None
    started_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    steps: list[TraceEvent] = Field(default_factory=list)
    model_version: str | None = None
    kb_version: str | None = None
    total_ms: int = 0

    def add(self, node: str, ms: int = 0, **detail: Any) -> TraceEvent:
        event = TraceEvent(
            node=node, ms=ms, detail={k: v for k, v in detail.items() if v is not None}
        )
        self.steps.append(event)
        return event

    def step(self, node: str) -> _Step:
        """Kontekst menejeri: `with trace.step("jurist") as s: …`.

        Vaqtni qo'lda o'lchash unutiladi va o'lchanmagan qadam trace ni
        yaroqsiz qiladi — shuning uchun o'lchov chaqiruv shakliga kiritilgan.
        """
        return _Step(self, node)


class _Step:
    def __init__(self, trace: Trace, node: str) -> None:
        self.trace = trace
        self.node = node
        self.detail: dict[str, Any] = {}
        self._t0 = 0.0

    def __enter__(self) -> _Step:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        ms = int((time.perf_counter() - self._t0) * 1000)
        self.trace.add(self.node, ms, **self.detail)

    def set(self, **detail: Any) -> None:
        self.detail.update(detail)


def new_trace_id() -> str:
    """`cns_` prefiksi bilan qisqa, tartiblanadigan identifikator.

    Vaqt qismi oldinda: identifikatorlar leksikografik tartibda ham vaqt
    bo'yicha tartiblanadi, bu log va fayl nomlarida qulay.
    """
    stamp = format(int(time.time() * 1000), "x")
    return f"cns_{stamp}{secrets.token_hex(3)}"
