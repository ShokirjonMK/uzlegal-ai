"""Audit jurnali — o'zgarmas yozuv har bir maslahat uchun.

`docs/10-security-compliance.md` § 5 talabi. Spetsifikatsiya to'liq
yozilgan edi, lekin **amalga oshirilmagan** — bu modul o'sha
bo'shliqni yopadi.

## Nima uchun bu majburiy

Yuridik tizimda audit texnik xususiyat emas. Agar foydalanuvchi tizim
javobiga tayanib qaror qabul qilgan bo'lsa va keyinchalik nizo kelib
chiqsa, **aynan nima aytilgani** hujjatlashtirilgan bo'lishi kerak.

Davlat organlari uchun bu ayniqsa muhim: ular har bir avtomatik qaror
uchun izoh bera olishi shart.

## Uch qaror va ularning sababi

### 1. Savol MASKALANADI, javob esa SAQLANMAYDI

Savolda shaxsiy ma'lumot bo'lishi mumkin («Alisher Karimovni ishdan
bo'shatish…»). U `ingest.redact` orqali maskalanadi va jurnalga
`[SHAXS-1]` ko'rinishida tushadi.

Javobning **o'zi emas, xeshi** saqlanadi. Sabab: javob uzun va uni
saqlash jurnalni maxfiy ma'lumot omboriga aylantiradi. Xesh esa
«bu javob aynan shu edi» degan da'voni **isbotlash** uchun yetarli —
foydalanuvchida javob nusxasi bo'lsa, uni tekshirib ko'rish mumkin.

### 2. Hash zanjiri — o'zgartirishni aniqlaydi

Har yozuv oldingi yozuvning xeshini o'z ichiga oladi. Bitta yozuvni
o'zgartirish yoki o'chirish butun keyingi zanjirni buzadi va
`verify_chain()` buni ko'rsatadi.

Bu **o'zgartirishni taqiqlamaydi** — fayl tizimida buni taqiqlab
bo'lmaydi. Lekin u o'zgartirishni **sezilmas qilmaydi**, va audit
uchun aynan shu kerak.

### 3. JSONL fayl, ma'lumotlar bazasi emas

Air-gapped muhitda tashqi baza bo'lmasligi mumkin. Append-only fayl
esa har joyda ishlaydi, zaxira nusxasi oddiy `cp`, va uni o'qish
uchun maxsus vosita kerak emas.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_PATH = Path("data/audit/consult.jsonl")
PATH_ENV = "UZLEGAL_AUDIT_PATH"
ENABLED_ENV = "UZLEGAL_AUDIT"

GENESIS = "0" * 64


def audit_path() -> Path:
    return Path(os.getenv(PATH_ENV) or DEFAULT_PATH)


def is_enabled() -> bool:
    """Audit yoqilganmi.

    Standart holda **yoqilgan**. Uni o'chirish uchun aniq
    `UZLEGAL_AUDIT=0` yozish kerak — audit majburiyat bo'lgani uchun
    uning yo'qligi tasodifiy bo'lmasligi kerak.
    """
    return os.getenv(ENABLED_ENV, "1").strip().lower() not in {"0", "false", "no", "off"}


# --------------------------------------------------------------------------- #
# Yozish
# --------------------------------------------------------------------------- #


def _digest(record: dict[str, Any]) -> str:
    """Yozuvning xeshi — `hash` maydonisiz hisoblanadi.

    `sort_keys` majburiy: JSON kalitlari tartibi o'zgarsa xesh ham
    o'zgaradi va zanjir sababsiz buziladi.
    """
    body = {k: v for k, v in record.items() if k != "hash"}
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _last_hash(path: Path) -> str:
    """Oxirgi yozuvning xeshi. Fayl bo'sh bo'lsa — genezis.

    Faylning oxiridan o'qiydi: butun jurnalni yuklash 7 yillik yozuvda
    qimmatga tushadi.
    """
    if not path.exists() or path.stat().st_size == 0:
        return GENESIS
    try:
        with path.open("rb") as fh:
            fh.seek(max(0, path.stat().st_size - 8192))
            tail = fh.read().decode("utf-8", errors="ignore")
        lines = [line for line in tail.splitlines() if line.strip()]
        if not lines:
            return GENESIS
        return str(json.loads(lines[-1]).get("hash") or GENESIS)
    except Exception as exc:
        log.warning("Audit zanjiri o'qilmadi (%s) — genezisdan boshlanadi", exc)
        return GENESIS


def _mask(question: str) -> str:
    """Savoldagi shaxsiy ma'lumotni maskalaydi."""
    try:
        from uzlegal.ingest.redact import redact_text

        return str(redact_text(question).text)
    except Exception as exc:  # pragma: no cover
        log.warning("Maskalash bajarilmadi (%s) — savol yozilmaydi", exc)
        # Maskalab bo'lmasa savol UMUMAN yozilmaydi. Maskasiz yozish
        # audit jurnalini shaxsiy ma'lumot omboriga aylantirardi.
        return "[MASKALANMADI]"


def record_consult(
    *,
    trace_id: str,
    question: str,
    answer: str,
    mode: str,
    confidence: float,
    citations: list[str],
    kb_version: str,
    model_version: str | None,
    latency_ms: int,
    gate: dict[str, Any] | None = None,
    retrieval: dict[str, Any] | None = None,
    user_hash: str | None = None,
    as_of: str | None = None,
) -> str | None:
    """Bitta maslahatni jurnalga yozadi. Yozuv xeshini qaytaradi.

    Audit **hech qachon so'rovni yiqitmasligi kerak**: yozib bo'lmasa
    xato log ga tushadi va `None` qaytadi. Foydalanuvchi javobsiz
    qolgandan ko'ra jurnalda bo'shliq bo'lgani yaxshiroq — bo'shliq
    ko'rinadi, javobsizlik esa xizmatni to'xtatadi.
    """
    if not is_enabled():
        return None

    path = audit_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        record: dict[str, Any] = {
            "trace_id": trace_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_hash": user_hash,
            "question_masked": _mask(question),
            "mode": mode,
            "kb_version": kb_version,
            "model_version": model_version,
            # Javob qaysi sanadagi qonunchilikka ko'ra berilgani (docs/21 § 1.1).
            # Busiz jurnal savolga qaysi holat bo'yicha javob berilganini
            # ko'rsata olmaydi — nizoda esa aynan shu hal qiluvchi.
            "as_of": as_of,
            "retrieval": retrieval or {},
            "gate": gate or {},
            # Javobning O'ZI emas, xeshi — modul izohiga qarang.
            "answer_hash": "sha256:" + hashlib.sha256(answer.encode("utf-8")).hexdigest(),
            "answer_chars": len(answer),
            "citations": citations,
            "confidence": confidence,
            "disclaimer_shown": True,
            "latency_ms": latency_ms,
            "prev": _last_hash(path),
        }
        record["hash"] = _digest(record)

        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        return str(record["hash"])
    except Exception as exc:
        log.error("Audit yozuvi saqlanmadi: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# O'qish va tekshirish
# --------------------------------------------------------------------------- #


def read_all(path: Path | None = None) -> Iterator[dict[str, Any]]:
    target = path or audit_path()
    if not target.exists():
        return
    with target.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def find(trace_id: str, path: Path | None = None) -> dict[str, Any] | None:
    """Bitta yozuvni `trace_id` bo'yicha topadi."""
    for record in read_all(path):
        if record.get("trace_id") == trace_id:
            return record
    return None


def verify_chain(path: Path | None = None) -> dict[str, Any]:
    """Zanjir buzilmaganini tekshiradi.

    Ikki narsa tekshiriladi:

    1. Har yozuvning xeshi uning mazmuniga mos keladimi — yozuv
       o'zgartirilganmi;
    2. `prev` oldingi yozuvning xeshiga tengmi — yozuv o'chirilgan yoki
       qo'shilganmi.

    Birinchi buzilgan yozuv raqami qaytariladi: undan keyingi hamma
    narsa baribir shubhali, shuning uchun ro'yxat emas, **birinchi**
    nuqta muhim.
    """
    target = path or audit_path()
    total = 0
    expected_prev = GENESIS

    for index, record in enumerate(read_all(target), start=1):
        total = index

        stored = record.get("hash")
        if stored != _digest(record):
            return {
                "ok": False,
                "records": total,
                "broken_at": index,
                "reason": "yozuv o'zgartirilgan — xesh mazmuniga mos kelmaydi",
                "trace_id": record.get("trace_id"),
            }

        if record.get("prev") != expected_prev:
            return {
                "ok": False,
                "records": total,
                "broken_at": index,
                "reason": "zanjir uzilgan — yozuv o'chirilgan yoki qo'shilgan",
                "trace_id": record.get("trace_id"),
            }

        expected_prev = str(stored)

    return {"ok": True, "records": total, "last_hash": expected_prev}


def stats(path: Path | None = None) -> dict[str, Any]:
    """Jurnal holati — hajm, davr, yozuvlar soni."""
    target = path or audit_path()
    if not target.exists():
        return {"enabled": is_enabled(), "records": 0, "path": str(target)}

    first: str | None = None
    last: str | None = None
    count = 0
    for record in read_all(target):
        count += 1
        first = first or record.get("timestamp")
        last = record.get("timestamp")

    return {
        "enabled": is_enabled(),
        "records": count,
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "first": first,
        "last": last,
    }


__all__ = [
    "audit_path",
    "find",
    "is_enabled",
    "read_all",
    "record_consult",
    "stats",
    "verify_chain",
]
