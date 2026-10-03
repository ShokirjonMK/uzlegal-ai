"""Sifat hisoboti — audit jurnalidan oʻlchangan raqamlar.

## Nima uchun bu modul kerak boʻldi

Audit jurnalida 2 803 ta konsultatsiya yozuvi bor va u loyihadagi eng
boy maʼlumot manbai: har yozuvda darvoza natijasi, kechikish, iqtiboslar
va bilim bazasi versiyasi. Lekin **hech kim uni koʻra olmasdi** —
uni oʻqish uchun har safar alohida skript yozish kerak edi.

Natijada 24-avgustdagi taftishgacha quyidagilar nomaʼlum edi:

| Nima | Qiymat |
|---|---|
| Darvoza oʻchiradigan daʼvolar | **24.8%** (standart rejimda 32%) |
| `/v1/consult` p95 kechikishi | **149 s** |
| Iqtibossiz javoblar | 5.6% |
| Haqiqiy foydalanuvchilar | **0** |

Bularning har biri mahsulot qarorini oʻzgartiradi. Ular koʻrinmasa
qaror his-tuygʻu bilan qabul qilinadi.

## Nima uchun oyna cheklangan

Jurnal faqat **oʻsadi** va hech qachon kesilmaydi. Bugun 2 803 yozuv —
bir soniyada oʻqiladi; yuz mingta boʻlganda esa panel har ochilganda
diskni toʻliq oʻqishga majbur boʻlardi.

Shuning uchun hisobot oxirgi `WINDOW` yozuv boʻyicha hisoblanadi va
javobda **qancha yozuv koʻrilgani aytiladi**. Jimgina kesish yomon
boʻlardi: foydalanuvchi raqamni butun tarix deb oʻqirdi.
"""

from __future__ import annotations

import collections
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from uzlegal import audit

# Hisobot uchun oxirgi nechta yozuv oʻqiladi.
#
# 20 000 — bugungi jurnaldan yetti barobar katta, yaʼni amalda hozir
# hamma narsa koʻriladi. Ayni paytda u chegarani KOD DA belgilaydi:
# jurnal oʻsganda panel sekinlashmaydi va buni keyin eslab qolish
# shart boʻlmaydi.
WINDOW = 20_000

# Kechikish taqsimoti uchun foizlar.
PERCENTILES = (50, 95, 99)


def _tail(limit: int) -> list[dict[str, Any]]:
    """Jurnalning oxirgi `limit` yozuvi.

    Butun fayl oʻqiladi va oxiri olinadi. Teskari oʻqish (`seek`) tezroq
    boʻlardi, lekin yozuvlar turli uzunlikda va JSON satrini oʻrtasidan
    boshlash xatoga olib kelardi. `WINDOW` chegarasi bilan bu farq
    sezilmaydi — 20 000 satr diskdan bir soniyadan kam vaqtda oʻqiladi.
    """
    rows: collections.deque[dict[str, Any]] = collections.deque(maxlen=limit)
    try:
        rows.extend(audit.read_all())
    except Exception:  # jurnal buzilgan boʻlsa ham panel ochilsin
        return []
    return list(rows)


def _percentiles(values: list[float]) -> dict[str, int]:
    if not values:
        return {f"p{p}": 0 for p in PERCENTILES} | {"max": 0}
    ordered = sorted(values)
    out = {
        f"p{p}": int(ordered[min(int(len(ordered) * p / 100), len(ordered) - 1)])
        for p in PERCENTILES
    }
    out["max"] = int(ordered[-1])
    return out


def _mode_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rejim boʻyicha darvoza va kechikish.

    Rejimlar ATAYLAB alohida koʻrsatiladi. Umumiy oʻrtacha yolgʻon
    tasvir beradi: `simple` rejimda daʼvolarning 10% i oʻchiriladi,
    `standard` da esa 32% — ikkalasini qoʻshib «24.8%» deyish
    muammoning qayerdaligini yashiradi.
    """
    by: dict[str, dict[str, Any]] = {}
    for row in rows:
        mode = str(row.get("mode") or "?")
        slot = by.setdefault(
            mode,
            {"mode": mode, "soni": 0, "claims": 0, "dropped": 0, "flagged": 0, "_lat": []},
        )
        slot["soni"] += 1
        gate = row.get("gate") or {}
        slot["claims"] += int(gate.get("claims") or 0)
        slot["dropped"] += int(gate.get("dropped") or 0)
        slot["flagged"] += int(gate.get("flagged") or 0)
        if row.get("latency_ms"):
            slot["_lat"].append(float(row["latency_ms"]))

    out: list[dict[str, Any]] = []
    for slot in by.values():
        lat = slot.pop("_lat")
        slot["kechikish"] = _percentiles(lat)
        claims = slot["claims"]
        slot["drop_ulush"] = round(slot["dropped"] / claims * 100, 1) if claims else 0.0
        out.append(slot)
    return sorted(out, key=lambda s: -int(s["soni"]))


def _trend(rows: list[dict[str, Any]], days: int = 14) -> list[dict[str, Any]]:
    """Kunlik tendensiya — muammo oʻsayaptimi yoki kamayayaptimi.

    Bitta kesim («bugun 24.8%») yaxshilanish yoki yomonlashuvni
    koʻrsatmaydi. Tuzatish ishlaganini faqat vaqt boʻyicha qator
    isbotlaydi.
    """
    chegara = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    by: dict[str, dict[str, Any]] = {}
    for row in rows:
        ts = str(row.get("timestamp") or "")
        if ts < chegara:
            continue
        kun = ts[:10]
        slot = by.setdefault(kun, {"kun": kun, "soni": 0, "claims": 0, "dropped": 0})
        slot["soni"] += 1
        gate = row.get("gate") or {}
        slot["claims"] += int(gate.get("claims") or 0)
        slot["dropped"] += int(gate.get("dropped") or 0)

    out = []
    for slot in by.values():
        claims = slot["claims"]
        slot["drop_ulush"] = round(slot["dropped"] / claims * 100, 1) if claims else 0.0
        out.append(slot)
    return sorted(out, key=lambda s: str(s["kun"]))


def summary() -> dict[str, Any]:
    """Sifat hisoboti — panelning «Sifat» boʻlimi uchun."""
    rows = _tail(WINDOW)
    if not rows:
        return {"records": 0, "note": "Audit jurnali boʻsh yoki oʻqilmadi."}

    claims = sum(int((r.get("gate") or {}).get("claims") or 0) for r in rows)
    dropped = sum(int((r.get("gate") or {}).get("dropped") or 0) for r in rows)
    flagged = sum(int((r.get("gate") or {}).get("flagged") or 0) for r in rows)

    reasons: collections.Counter[str] = collections.Counter()
    for row in rows:
        for reason, n in ((row.get("gate") or {}).get("reasons") or {}).items():
            reasons[str(reason)] += int(n)

    iqtibossiz = sum(1 for r in rows if not (r.get("retrieval") or {}).get("citations"))
    rad = sum(1 for r in rows if (r.get("gate") or {}).get("refused"))

    # Haqiqiy foydalanuvchilar. Bu raqam mahsulotning eng muhim
    # koʻrsatkichi va u ATAYLAB birinchi qatorda turadi: 2 803
    # konsultatsiyaning hammasi `user_hash: null` boʻlgan holat
    # panelda darhol koʻrinishi kerak.
    foydalanuvchilar = len({r.get("user_hash") for r in rows if r.get("user_hash")})

    return {
        "records": len(rows),
        "window": WINDOW,
        "truncated": len(rows) >= WINDOW,
        "davr": {"boshi": rows[0].get("timestamp"), "oxiri": rows[-1].get("timestamp")},
        "foydalanuvchilar": foydalanuvchilar,
        "darvoza": {
            "claims": claims,
            "dropped": dropped,
            "flagged": flagged,
            "drop_ulush": round(dropped / claims * 100, 1) if claims else 0.0,
            "reasons": dict(reasons.most_common()),
            # Sabablar eski yozuvlarda yoʻq — ular `reasons` maydoni
            # qoʻshilishidan oldin yozilgan. Buni AYTAMIZ, aks holda
            # boʻsh roʻyxat «sabab yoʻq» deb oʻqilardi.
            "reasons_available": bool(reasons),
        },
        "javoblar": {
            "jami": len(rows),
            "iqtibossiz": iqtibossiz,
            "iqtibossiz_ulush": round(iqtibossiz / len(rows) * 100, 1),
            "rad_etilgan": rad,
        },
        "rejimlar": _mode_report(rows),
        "tendensiya": _trend(rows),
        "zanjir": audit.verify_chain(),
    }


def records(*, limit: int = 50, offset: int = 0, filtr: str = "") -> dict[str, Any]:
    """Savollar roʻyxati — panelning «Savollar» boʻlimi uchun.

    ## Nima uchun bu boʻlim strategik

    A4 (yopiq sinov) ning butun maqsadi — **haqiqiy foydalanuvchi
    savollarini** yigʻish. Ular kelganda ularni koʻrish, saralash va
    gold setga oʻtkazish kerak boʻladi. Bu roʻyxat oʻsha asbob.

    Savollar jurnalda MASKALANGAN holda yotadi (`audit._mask`), yaʼni
    ularni koʻrsatish shaxsiy maʼlumotni oshkor qilmaydi.

    ## Filtrlar

    | `filtr` | Nimani koʻrsatadi |
    |---|---|
    | `""` | hammasi |
    | `dropped` | darvoza biror daʼvoni oʻchirgan javoblar |
    | `no_citations` | iqtibossiz javoblar |
    | `slow` | 30 soniyadan uzoq |
    | `refused` | rad etilgan |

    Uchalasi ham «nimadir notoʻgʻri ketdi» degan holatlar — aynan
    ularni koʻrish kerak, muvaffaqiyatli javoblarni emas.
    """
    rows = _tail(WINDOW)

    def mos(row: dict[str, Any]) -> bool:
        gate = row.get("gate") or {}
        if filtr == "dropped":
            return int(gate.get("dropped") or 0) > 0
        if filtr == "no_citations":
            return not (row.get("retrieval") or {}).get("citations")
        if filtr == "slow":
            return float(row.get("latency_ms") or 0) > 30_000
        if filtr == "refused":
            return bool(gate.get("refused"))
        return True

    tanlangan = [r for r in rows if mos(r)]
    tanlangan.reverse()  # yangi yozuvlar tepada

    bolak = tanlangan[offset : offset + limit]
    return {
        "jami": len(tanlangan),
        "offset": offset,
        "limit": limit,
        "filtr": filtr,
        "yozuvlar": [
            {
                "trace_id": r.get("trace_id"),
                "timestamp": r.get("timestamp"),
                "savol": r.get("question_masked"),
                "mode": r.get("mode"),
                "kb_version": r.get("kb_version"),
                "latency_ms": r.get("latency_ms"),
                "confidence": r.get("confidence"),
                "answer_chars": r.get("answer_chars"),
                "citations": r.get("citations") or [],
                "gate": r.get("gate") or {},
                "retrieval": r.get("retrieval") or {},
                "user_hash": r.get("user_hash"),
            }
            for r in bolak
        ],
    }


def export_jsonl(*, filtr: str = "") -> str:
    """Tanlangan yozuvlarni JSONL sifatida qaytaradi — gold set uchun.

    Nega kerak: A4 dan kelgan savollar qoʻlda koʻchirilmasin. Yurist
    tasdiqlashi kerak boʻlgan holatlar shu yerdan chiqadi va
    `data/eval/` ga tushadi.
    """
    data = records(limit=WINDOW, filtr=filtr)
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in data["yozuvlar"])
