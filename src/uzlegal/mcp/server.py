"""MCP server — UzLegal ni boshqa AI mijozlariga ochadi.

Model Context Protocol orqali Claude Desktop, Claude Code va boshqa
mijozlar O'zbekiston qonunchiligidan **iqtibos bilan** qidira oladi.

## Nima uchun bu qimmatli

Umumiy modellar o'zbek qonunchiligini bilmaydi va bilgandek qilib javob
beradi — bu eng xavfli holat. MCP orqali ular haqiqiy manbadan o'qiydi
va iqtibos oladi.

## Nima uchun `mcp` kutubxonasisiz

Protokol — stdio ustidagi JSON-RPC 2.0 va bizga uch metod kerak:
`initialize`, `tools/list`, `tools/call`. Bu ~150 satr va nol yangi
bog'liqlik; `mcp` paketi esa asyncio va o'z hayot siklini olib keladi.

## Ishga tushirish

    uzlegal mcp

Claude Desktop sozlamasiga:

```json
{"mcpServers": {"uzlegal": {"command": "uzlegal", "args": ["mcp"]}}}
```
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from datetime import date
from typing import Any, TextIO

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "uzlegal", "version": "0.1.0"}

# JSON-RPC xato kodlari
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603


TOOLS: list[dict[str, Any]] = [
    {
        "name": "uzlegal_search",
        "description": (
            "Oʻzbekiston qonunchiligidan qidiradi (modelsiz, tez). "
            "Amaldagi normalarni qaytaradi — bekor qilinganlari filtrlanadi. "
            "Aniq modda matni kerak boʻlganda shuni ishlating."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Savol yoki atama"},
                "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                "as_of": {
                    "type": "string",
                    "description": "Tarixiy holat, YYYY-MM-DD. Berilmasa — bugungi holat.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "uzlegal_consult",
        "description": (
            "Toʻliq huquqiy tahlil: qidiruv, agentlar muhokamasi, sudya xulosasi. "
            "Javobdagi har bir huquqiy daʼvo qonun moddasiga bogʻlanadi; "
            "bogʻlanmagani oʻchiriladi. Sekin (5–60 s) — murakkab savol uchun."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "mode": {"type": "string", "enum": ["simple", "standard", "complex"]},
                "as_of": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "uzlegal_status",
        "description": "Bilim bazasi versiyasi, hujjatlar soni va faol model.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# --------------------------------------------------------------------------- #
# Vositalar
# --------------------------------------------------------------------------- #


def _as_of(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def tool_search(args: dict[str, Any]) -> str:
    from uzlegal.index.store import KnowledgeIndex
    from uzlegal.retrieval.hybrid import HybridRetriever

    found = HybridRetriever(KnowledgeIndex()).search(
        args["query"], top_k=int(args.get("top_k", 5)), as_of=_as_of(args.get("as_of"))
    )
    if not found.results:
        return "Ishonchli manba topilmadi."

    blocks = []
    for i, item in enumerate(found.results, 1):
        chunk = item.chunk
        blocks.append(
            f"### {i}. {chunk.citation_label}\n{chunk.content}\nManba: {chunk.source_url or '—'}"
        )
    return "\n\n".join(blocks)


def tool_consult(args: dict[str, Any]) -> str:
    from uzlegal.core import consult

    result = consult(args["question"], mode=args.get("mode"), as_of=_as_of(args.get("as_of")))
    lines = [result.answer]
    if result.citations:
        lines.append("\n## Manbalar")
        lines += [
            f"- [{c.tag}] {c.doc_title}, {c.article}-modda — {c.url or '—'}"
            for c in result.citations
        ]
    if result.gate.dropped:
        # Mijoz modeli buni ko'rishi kerak: tizim nimanidir rad etgan
        # bo'lsa, javob to'liq emas va uni shunday taqdim etish kerak.
        lines.append(
            f"\n_{len(result.gate.dropped)} ta daʼvo manbaga bogʻlanmagani "
            f"uchun javobdan chiqarildi._"
        )
    lines.append(f"\n_Rejim: {result.mode.value} · {result.total_ms / 1000:.0f} s_")
    return "\n".join(lines)


def tool_status(args: dict[str, Any]) -> str:
    from uzlegal.config import get_registry
    from uzlegal.index.store import KnowledgeIndex
    from uzlegal.ingest.sync import SyncManager

    meta = KnowledgeIndex().meta
    state = SyncManager().state
    return json.dumps(
        {
            "kb_version": state.kb_version,
            "chunks": meta.get("chunks"),
            "documents": meta.get("documents"),
            "kb_age_days": state.age_days(),
            "kb_stale": state.is_stale(),
            "active_model": get_registry().active_id,
        },
        ensure_ascii=False,
        indent=2,
    )


HANDLERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "uzlegal_search": tool_search,
    "uzlegal_consult": tool_consult,
    "uzlegal_status": tool_status,
}


# --------------------------------------------------------------------------- #
# JSON-RPC
# --------------------------------------------------------------------------- #


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    """Bitta so'rovni qayta ishlaydi. Bildirishnomaga `None` qaytadi."""
    method = request.get("method", "")
    request_id = request.get("id")

    # Bildirishnoma (`id` yo'q) — javob talab qilinmaydi
    if request_id is None:
        return None

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            }
        )
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name", "")
        handler = HANDLERS.get(name)
        if handler is None:
            return ok(
                {
                    "content": [{"type": "text", "text": f"Noma'lum vosita: {name}"}],
                    "isError": True,
                }
            )
        try:
            text = handler(params.get("arguments") or {})
        except Exception as exc:
            # MCP da xato **natija sifatida** qaytadi, protokol xatosi
            # sifatida emas — mijoz modeli uni o'qib, boshqacha urinishi
            # mumkin. Protokol xatosi esa ulanishni buzadi.
            log.exception("Vosita bajarilmadi: %s", name)
            return ok({"content": [{"type": "text", "text": f"Xato: {exc}"}], "isError": True})
        return ok({"content": [{"type": "text", "text": text}]})

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": METHOD_NOT_FOUND, "message": f"Noma'lum metod: {method}"},
    }


def serve(stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    """stdio ustida MCP serverini yuritadi.

    Diqqat: **stdout faqat protokol uchun**. Har qanday chiqish (print,
    log) protokolni buzadi, shuning uchun loglar stderr ga yo'naltiriladi.
    """
    source = stdin or sys.stdin
    sink = stdout or sys.stdout
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

    for line in source:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            log.warning("JSON o'qilmadi: %.80s", line)
            continue

        try:
            response = handle(request)
        except Exception as exc:
            log.exception("So'rov qayta ishlanmadi")
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": INTERNAL_ERROR, "message": str(exc)},
            }

        if response is not None:
            sink.write(json.dumps(response, ensure_ascii=False) + "\n")
            sink.flush()


if __name__ == "__main__":
    serve()
