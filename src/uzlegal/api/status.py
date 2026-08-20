"""Yadroning to'liq holati — admin paneli uchun (docs/28).

## Nima uchun `/v1/health` dan alohida

`/v1/health` — **monitoring** uchun: tez, yengil, «tirikmi yoki yo'q».
U indeksni ochmaydi va faqat metafayl o'qiydi.

Bu modul boshqa savolga javob beradi: **mahsulot qanday holatda.**
Uning javobi og'irroq (indeksni ochadi va korpus ustidan o'tadi),
lekin u kuniga bir necha marta so'raladi, sekundiga emas.

## Prinsip

Har raqam **o'lchanadi**, metafayldan ko'chirilmaydi. Bu loyihada
qayta-qayta ushlangan naqsh (`docs/23`, `docs/24`): e'lon qilingan
raqam amaldagi raqam emas. Panel shu naqshni takrorlamasligi kerak —
aks holda u nosozlikni ko'rsatish o'rniga yashiradi.
"""

from __future__ import annotations

import collections
from typing import Any

CACHE_TTL_SECONDS = 60


def _corpus_report() -> dict[str, Any]:
    """Korpus tarkibi va indeks sog'lig'i — o'lchangan."""
    from uzlegal.index.store import KnowledgeIndex

    index = KnowledgeIndex()
    if not index.exists():
        return {"tayyor": False, "sabab": "indeks qurilmagan"}

    index.read_chunks()
    chunks = list(index._chunks.values())
    if not chunks:
        return {"tayyor": False, "sabab": "indeks bo'sh"}

    docs: dict[str, tuple[str, str]] = {}
    units: collections.Counter[str] = collections.Counter()
    dated = 0
    repealed = 0
    for chunk in chunks:
        docs.setdefault(chunk.doc_id, (chunk.doc_type, chunk.doc_title or ""))
        units[chunk.unit] += 1
        if chunk.valid_from:
            dated += 1
        if chunk.status != "in_force":
            repealed += 1

    types: collections.Counter[str] = collections.Counter(t for t, _ in docs.values())
    meta = index.meta
    ambiguous = index.ambiguous_articles()

    return {
        "tayyor": True,
        "hujjat": len(docs),
        "bolak": len(chunks),
        # `meta` dagi raqam — QURISH paytida yozilgani. Farq bo'lsa
        # indeks fayllari qo'lda o'zgartirilgan yoki qurish yarim
        # qolgan. Ikkalasini ko'rsatamiz, chunki farqning o'zi signal.
        "meta_bolak": int(meta.get("chunks") or 0),
        "takror_satr": index.duplicate_rows,
        "kb_versiya": str(meta.get("kb_version") or ""),
        "turlari": dict(types.most_common()),
        "birlik": dict(units),
        "sanali_bolak": dated,
        "sanali_ulush": round(dated / len(chunks), 4),
        "bekor_qilingan": repealed,
        "noaniq_raqamli_hujjat": len(ambiguous),
        "noaniq_raqam": sum(ambiguous.values()),
    }


def _coverage_report() -> dict[str, Any]:
    """Qamrov darvozasi nimalarni to'sadi (docs/27).

    Panel uchun muhim: foydalanuvchi «nega javob bermadi» deb
    so'raganda, javob shu yerda ko'rinadi.
    """
    from uzlegal.index.store import KnowledgeIndex
    from uzlegal.retrieval.coverage import _SOURCE_CLASSES, _corpus_has

    index = KnowledgeIndex()
    if not index.exists():
        return {"tayyor": False}

    index.read_chunks()
    classes = []
    for source in _SOURCE_CLASSES:
        count = _corpus_has(index, source)
        classes.append(
            {
                "nom": source.label,
                "hujjat": max(count, 0),
                "chegara": source.min_docs,
                "qoplangan": count >= source.min_docs,
            }
        )
    return {"tayyor": True, "manba_turlari": classes}


def _training_report() -> dict[str, Any]:
    """Trening to'plami va kengash holati (docs/26)."""
    from pathlib import Path

    from uzlegal.training.dataset import Dataset

    root = Path("data/sft")
    if not root.exists():
        return {"toplam": 0, "rollar": {}}

    rollar: dict[str, Any] = {}
    for path in sorted(root.glob("*/*.jsonl")):
        try:
            stats = Dataset(path).stats()
        except Exception:
            # Urug' savollar fayli `TrainingSample` emas — bu xato emas,
            # shunchaki boshqa bosqichdagi fayl.
            rollar[f"{path.parent.name}/{path.stem}"] = {"xato": "namuna formatida emas"}
            continue
        rollar[f"{path.parent.name}/{path.stem}"] = stats
    return {"toplam": len(rollar), "rollar": rollar}


def _sync_report(sync: Any) -> dict[str, Any]:
    state = sync.state
    return {
        "holat": sync.status.value,
        "versiya": state.kb_version,
        "oxirgi": state.last_sync_at.isoformat() if state.last_sync_at else None,
        "yosh_kun": state.age_days(),
        "eskirgan": state.is_stale(),
        "avtomatik": state.auto_enabled,
        "oraliq_kun": state.interval_days,
    }


def build_status(sync: Any) -> dict[str, Any]:
    """Panel uchun to'liq holat.

    Har bo'lim alohida o'raladi: bittasi yiqilsa qolganlari baribir
    ko'rsatiladi. Bo'sh panel «hammasi yaxshi» degan taassurot
    qoldiradi va bu eng yomon variant.
    """
    sections: dict[str, Any] = {}
    for name, fn in (
        ("korpus", _corpus_report),
        ("qamrov", _coverage_report),
        ("trening", _training_report),
    ):
        try:
            sections[name] = fn()
        except Exception as exc:
            sections[name] = {"xato": f"{type(exc).__name__}: {exc}"}

    try:
        sections["sinxronizatsiya"] = _sync_report(sync)
    except Exception as exc:
        sections["sinxronizatsiya"] = {"xato": str(exc)}

    return sections
