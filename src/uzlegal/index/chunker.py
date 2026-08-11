"""Yuridik matnni bo'laklarga ajratish.

## Nima uchun oddiy chunking yaramaydi

Odatiy RAG «har 500 token» deb kesadi. Yuridik matnda bu halokatli:

    …mulkdor talab qilishga haqli, agar mulk vijdonsiz oluv[KESILDI]
    [YANGI CHUNK]chi qo'lida bo'lsa. Bundan mustasno holatlar…

Kesilgan joydan «bundan mustasno» qismi yo'qoladi va model normani
**teskari** talqin qiladi. Iqtibos ham noto'g'ri bo'ladi: chunk qaysi
moddaga tegishli ekani noaniq.

## Qoida

**Chunk chegarasi = tuzilma chegarasi.** Modda o'rtasidan hech qachon
kesilmaydi. Modda juda uzun bo'lsa — qismlarga, keyin bandlarga bo'linadi,
lekin har doim to'liq mantiqiy birlik saqlanadi.

| Modda hajmi | Strategiya |
|-------------|------------|
| < 800 token | Bitta chunk = bitta modda |
| 800–2000 | Qismlarga (1., 2., …) |
| > 2000 | Bandlarga (a), b), …) |
| < 100 token | Qo'shni moddalar bilan birlashtiriladi (bir bob ichida) |

## Kontekstual sarlavha

Har bir chunk o'z o'rnini biladigan sarlavha oladi:

    [Fuqarolik kodeksi > II bo'lim > 11-bob > 234-modda > 1-qism]

Bu retrieval sifatini sezilarli oshiradi — model chunk qayerdan kelganini
ko'radi va iqtibosni to'g'ri shakllantiradi.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import fold
from uzlegal.ingest.types import Element, ParsedDocument

# Chegara qiymatlari — docs/03 § 3.6
MAX_CHUNK_TOKENS = 800
SPLIT_TO_PARTS_ABOVE = 800
SPLIT_TO_ITEMS_ABOVE = 2000
MERGE_BELOW_TOKENS = 100
MIN_CHUNK_CHARS = 20

# O'zbek/rus matnida token ≈ so'z × 2 (agglyutinatsiya va kirill tufayli)
TOKENS_PER_WORD = 2


def estimate_tokens(text: str) -> int:
    return len(text.split()) * TOKENS_PER_WORD


# --------------------------------------------------------------------------- #
# Qism va band chegaralari
# --------------------------------------------------------------------------- #

# "1. Matn…"  yoki  "1) Matn…"
_PART_RE = re.compile(r"(?m)^\s*(\d{1,2})\s*[.)]\s+")

# "a) matn…"  yoki  "а) matn…" (kirill a)
_ITEM_RE = re.compile(r"(?m)^\s*([a-zа-яʻʼ]{1,2})\s*\)\s+")


def split_by(pattern: re.Pattern[str], text: str) -> list[tuple[str | None, str]]:
    """Matnni belgilangan raqamlash bo'yicha bo'ladi.

    `(belgi, matn)` juftliklari qaytadi. Birinchi bo'lakda belgi bo'lmasligi
    mumkin (raqamlashdan oldingi kirish matni) — u `None` bilan keladi.
    """
    marks = list(pattern.finditer(text))
    if not marks:
        return [(None, text)]

    out: list[tuple[str | None, str]] = []
    if marks[0].start() > 0:
        head = text[: marks[0].start()].strip()
        if head:
            out.append((None, head))

    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.start() : end].strip()
        if body:
            out.append((m.group(1), body))
    return out


# --------------------------------------------------------------------------- #
# Chunk
# --------------------------------------------------------------------------- #


class Chunk(BaseModel):
    """Indekslanadigan eng kichik birlik."""

    chunk_id: str
    doc_id: str
    doc_title: str
    doc_type: str
    lang: str

    article: str | None = None
    part: str | None = None
    item: str | None = None
    hierarchy: list[str] = Field(default_factory=list)

    heading: str = Field(description="Kontekstual sarlavha — modelga beriladi")
    content: str
    token_count: int = 0

    element_id: str | None = None
    source_url: str | None = None
    kind: Literal["article", "part", "item", "merged", "text"] = "article"

    # Versiyalash — Faza 1 ning versioning moduli to'ldiradi
    valid_from: str | None = None
    valid_to: str | None = None
    status: str = "in_force"

    @property
    def indexed_text(self) -> str:
        """Embedding va BM25 uchun matn — sarlavha bilan birga.

        Sarlavhani qo'shish muhim: «234-modda» so'rovi chunk matnida
        uchramasligi mumkin, lekin sarlavhada bor.
        """
        return f"{self.heading}\n\n{self.content}"

    @property
    def search_text(self) -> str:
        """BM25 uchun normallashtirilgan shakl (apostrof, kirill)."""
        return fold(self.indexed_text)

    @property
    def citation_label(self) -> str:
        bits = [self.doc_title]
        if self.article:
            bits.append(f"{self.article}-modda")
        if self.part:
            bits.append(f"{self.part}-qism")
        if self.item:
            bits.append(f'"{self.item}" bandi')
        return ", ".join(bits)


# --------------------------------------------------------------------------- #
# Chunker
# --------------------------------------------------------------------------- #


class Chunker:
    def __init__(
        self,
        max_tokens: int = MAX_CHUNK_TOKENS,
        merge_below: int = MERGE_BELOW_TOKENS,
    ) -> None:
        self.max_tokens = max_tokens
        self.merge_below = merge_below

    def chunk_document(self, doc: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        for article in doc.articles:
            chunks.extend(self._chunk_article(doc, article))
        return self._merge_tiny(chunks)

    # ------------------------------------------------------------------ #

    def _heading(self, doc: ParsedDocument, article: Element, *suffix: str) -> str:
        bits = [doc.title, *article.path, article.title, *suffix]
        return "[" + " > ".join(b.strip() for b in bits if b and b.strip()) + "]"

    def _base(self, doc: ParsedDocument, article: Element) -> dict[str, object]:
        return {
            "doc_id": doc.doc_id,
            "doc_title": doc.title,
            "doc_type": doc.doc_type,
            "lang": doc.lang,
            "article": article.article_number,
            "hierarchy": list(article.path),
            "element_id": article.element_id,
            "source_url": f"{doc.url}#{article.element_id}",
            # Versiya maydonlari `ingest.versioning.apply_versions()` dan keladi.
            # Ular bo'lmasa `version_filter` bo'sh ishlaydi va bekor qilingan
            # norma qidiruvga chiqib ketadi (docs/00 «0% deprecated»).
            "valid_from": article.valid_from,
            "valid_to": article.valid_to,
            "status": article.status,
        }

    def _chunk_article(self, doc: ParsedDocument, article: Element) -> list[Chunk]:
        body = article.body.strip()
        if len(body) < MIN_CHUNK_CHARS:
            return []

        tokens = estimate_tokens(body)
        base = self._base(doc, article)
        num = article.article_number or article.element_id

        # 1. Kichik modda — butunligicha
        if tokens <= SPLIT_TO_PARTS_ABOVE:
            return [
                Chunk(
                    chunk_id=f"{doc.doc_id}:{num}",
                    heading=self._heading(doc, article),
                    content=body,
                    token_count=tokens,
                    kind="article",
                    **base,  # type: ignore[arg-type]
                )
            ]

        # 2. O'rta modda — qismlarga
        parts = split_by(_PART_RE, body)
        if len(parts) > 1 and tokens <= SPLIT_TO_ITEMS_ABOVE:
            return [
                Chunk(
                    chunk_id=f"{doc.doc_id}:{num}:{mark or 'kirish'}",
                    part=mark,
                    heading=self._heading(doc, article, f"{mark}-qism" if mark else "kirish"),
                    content=text,
                    token_count=estimate_tokens(text),
                    kind="part",
                    **base,  # type: ignore[arg-type]
                )
                for mark, text in parts
            ]

        # 3. Katta modda — qism, keyin band
        out: list[Chunk] = []
        for mark, part_text in parts:
            if estimate_tokens(part_text) <= self.max_tokens:
                out.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}:{num}:{mark or 'kirish'}",
                        part=mark,
                        heading=self._heading(doc, article, f"{mark}-qism" if mark else "kirish"),
                        content=part_text,
                        token_count=estimate_tokens(part_text),
                        kind="part",
                        **base,  # type: ignore[arg-type]
                    )
                )
                continue

            items = split_by(_ITEM_RE, part_text)
            if len(items) == 1:
                # Bo'linmaydi — uzun bo'lsa ham butun qoldiramiz.
                # Yuridik matnda to'liqlik uzunlikdan muhimroq.
                out.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}:{num}:{mark or 'kirish'}",
                        part=mark,
                        heading=self._heading(doc, article, f"{mark}-qism" if mark else "kirish"),
                        content=part_text,
                        token_count=estimate_tokens(part_text),
                        kind="part",
                        **base,  # type: ignore[arg-type]
                    )
                )
                continue

            for item_mark, item_text in items:
                suffix = [f"{mark}-qism"] if mark else []
                if item_mark:
                    suffix.append(f'"{item_mark}" bandi')
                out.append(
                    Chunk(
                        chunk_id=f"{doc.doc_id}:{num}:{mark or '0'}:{item_mark or 'kirish'}",
                        part=mark,
                        item=item_mark,
                        heading=self._heading(doc, article, *suffix),
                        content=item_text,
                        token_count=estimate_tokens(item_text),
                        kind="item",
                        **base,  # type: ignore[arg-type]
                    )
                )
        return out

    # ------------------------------------------------------------------ #

    def _merge_tiny(self, chunks: list[Chunk]) -> list[Chunk]:
        """Juda qisqa moddalarni qo'shnisi bilan birlashtiradi.

        «234-modda. Bekor qilingan.» kabi chunklar alohida indekslansa
        qidiruvni ifloslaydi — ular ma'no tashimaydi, lekin ball oladi.

        Birlashtirish faqat **bir bob ichida** va **bir hujjatda** bo'ladi.
        """
        if not chunks:
            return []

        out: list[Chunk] = []
        buffer: list[Chunk] = []

        def flush() -> None:
            if not buffer:
                return
            if len(buffer) == 1:
                out.append(buffer[0])
            else:
                first, last = buffer[0], buffer[-1]
                merged = Chunk(
                    chunk_id=f"{first.chunk_id}+{len(buffer)}",
                    doc_id=first.doc_id,
                    doc_title=first.doc_title,
                    doc_type=first.doc_type,
                    lang=first.lang,
                    article=f"{first.article}-{last.article}",
                    hierarchy=first.hierarchy,
                    heading=first.heading,
                    content="\n\n".join(c.content for c in buffer),
                    token_count=sum(c.token_count for c in buffer),
                    element_id=first.element_id,
                    source_url=first.source_url,
                    kind="merged",
                    valid_from=first.valid_from,
                    valid_to=first.valid_to,
                    status=first.status,
                )
                out.append(merged)
            buffer.clear()

        for chunk in chunks:
            tiny = chunk.token_count < self.merge_below and chunk.kind == "article"
            if not tiny:
                flush()
                out.append(chunk)
                continue

            # Versiyasi boshqacha bo'lgan moddalar birlashtirilmaydi: bekor
            # qilingan norma amaldagisi bilan bir chunkka tushsa, versiya
            # filtri ikkalasini ham chiqarib yuboradi yoki ikkalasini ham
            # o'tkazib yuboradi — ikkalasi ham noto'g'ri.
            same_group = (
                buffer
                and buffer[-1].doc_id == chunk.doc_id
                and buffer[-1].hierarchy == chunk.hierarchy
                and (buffer[-1].valid_from, buffer[-1].valid_to, buffer[-1].status)
                == (chunk.valid_from, chunk.valid_to, chunk.status)
            )
            if buffer and not same_group:
                flush()
            buffer.append(chunk)

        flush()
        return out
