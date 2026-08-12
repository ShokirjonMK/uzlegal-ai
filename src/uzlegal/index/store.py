"""Bilim bazasi indeksi — vektor + leksik.

## Nima uchun ikkalasi ham kerak

Yuristlar **aniq atama va raqam** bilan qidiradi: «234-modda»,
«vindikatsiya», «ЗРУ-110». Semantik qidiruv bunday aniq mosliklarni
ba'zan o'tkazib yuboradi, chunki u ma'noga qaraydi, harfga emas.

Teskarisi ham to'g'ri: «ishdan bo'shatish» so'rovi «mehnat shartnomasini
bekor qilish» matnini leksik qidiruvda topmaydi.

Shuning uchun ikkalasi parallel ishlaydi va natijalar RRF bilan
birlashtiriladi (`retrieval/hybrid.py`).

## Nima uchun LanceDB

`local-dev` profilida **hech qanday server jarayoni ishlamasligi** kerak
(ADR-007). LanceDB — kutubxona: `pip install`, tayyor. Docker, Postgres
yoki alohida xizmat talab qilmaydi. Bu `air-gapped` profil uchun ham shart.

Server profilida `VectorStore` protokoli orqasida Qdrant ga o'tiladi.
"""

from __future__ import annotations

import json
import logging
import math
import pickle
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from uzlegal.index.chunker import Chunk
from uzlegal.ingest.linking import ReferenceGraph
from uzlegal.ingest.normalize import fold

if TYPE_CHECKING:
    from numpy.typing import NDArray

log = logging.getLogger(__name__)

TABLE_NAME = "chunks"


class ScoredChunk(BaseModel):
    chunk: Chunk
    score: float
    source: str = "vector"  # vector · lexical · hybrid

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id


# --------------------------------------------------------------------------- #
# Leksik indeks (BM25)
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(r"[a-zʻʼ0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """O'zbek matnini tokenlarga ajratadi.

    `fold()` avval qo'llaniladi — kirill lotinga o'giriladi va apostrofning
    barcha variantlari bir shaklga keladi. Busiz «oʻzgartirish» va
    «o'zgartirish» turli token bo'lardi va BM25 ishlamasdi.
    """
    return _TOKEN_RE.findall(fold(text))


class BM25Index:
    """Okapi BM25 — tashqi bog'liqliksiz.

    `rank_bm25` kutubxonasi o'zbek tokenizatsiyasini bilmaydi va butun
    korpusni xotirada saqlaydi. Bu amalga oshirish ~250k chunk uchun
    yetarli va tokenizatsiyani biz nazorat qilamiz.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.doc_freqs: list[Counter[str]] = []
        self.doc_lens: list[int] = []
        self.df: Counter[str] = Counter()
        self.avg_len: float = 0.0

    def build(self, chunks: list[Chunk]) -> None:
        self.doc_ids = [c.chunk_id for c in chunks]
        self.doc_freqs = []
        self.doc_lens = []
        self.df = Counter()

        for chunk in chunks:
            tokens = tokenize(chunk.indexed_text)
            freqs = Counter(tokens)
            self.doc_freqs.append(freqs)
            self.doc_lens.append(len(tokens))
            self.df.update(freqs.keys())

        self.avg_len = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0.0

    def search(self, query: str, top_k: int = 50) -> list[tuple[str, float]]:
        if not self.doc_ids:
            return []
        terms = tokenize(query)
        n = len(self.doc_ids)
        scores: dict[int, float] = {}

        for term in terms:
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(term, 0)
                if tf == 0:
                    continue
                norm = 1 - self.b + self.b * (self.doc_lens[i] / (self.avg_len or 1))
                scores[i] = scores.get(i, 0.0) + idf * (tf * (self.k1 + 1)) / (tf + self.k1 * norm)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [(self.doc_ids[i], s) for i, s in ranked]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump(
                {
                    "k1": self.k1,
                    "b": self.b,
                    "doc_ids": self.doc_ids,
                    "doc_freqs": self.doc_freqs,
                    "doc_lens": self.doc_lens,
                    "df": self.df,
                    "avg_len": self.avg_len,
                },
                fh,
            )

    @classmethod
    def load(cls, path: Path) -> BM25Index:
        with path.open("rb") as fh:
            data = pickle.load(fh)
        index = cls(k1=data["k1"], b=data["b"])
        index.doc_ids = data["doc_ids"]
        index.doc_freqs = data["doc_freqs"]
        index.doc_lens = data["doc_lens"]
        index.df = data["df"]
        index.avg_len = data["avg_len"]
        return index


# --------------------------------------------------------------------------- #
# Birlashgan indeks
# --------------------------------------------------------------------------- #


class KnowledgeIndex:
    """Vektor (LanceDB) + leksik (BM25) indeks va chunk saqlagichi."""

    def __init__(self, path: Path = Path("kb/current")) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
        self._db: Any = None
        self._table: Any = None
        self._bm25: BM25Index | None = None
        self._chunks: dict[str, Chunk] = {}
        self._graph: ReferenceGraph | None = None

    # ------------------------------------------------------------------ #

    @property
    def chunks_path(self) -> Path:
        return self.path / "chunks.jsonl"

    @property
    def bm25_path(self) -> Path:
        return self.path / "bm25.pkl"

    @property
    def vectors_path(self) -> Path:
        return self.path / "vectors"

    @property
    def meta_path(self) -> Path:
        return self.path / "index-meta.json"

    @property
    def graph_path(self) -> Path:
        return self.path / "refs.jsonl"

    def exists(self) -> bool:
        return self.chunks_path.exists() and self.bm25_path.exists()

    # ------------------------------------------------------------------ #
    # Qurish
    # ------------------------------------------------------------------ #

    def build(
        self,
        chunks: list[Chunk],
        vectors: NDArray[Any],
        *,
        kb_version: str | None = None,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(f"chunk ({len(chunks)}) va vektor ({len(vectors)}) soni mos emas")

        import lancedb

        self.chunks_path.write_text(
            "\n".join(c.model_dump_json() for c in chunks), encoding="utf-8"
        )
        self._chunks = {c.chunk_id: c for c in chunks}

        log.info("BM25 indeksi qurilmoqda (%d chunk)…", len(chunks))
        bm25 = BM25Index()
        bm25.build(chunks)
        bm25.save(self.bm25_path)
        self._bm25 = bm25

        log.info("Vektor indeksi qurilmoqda…")
        rows = [
            {
                "chunk_id": c.chunk_id,
                "vector": vectors[i].tolist(),
                "doc_id": c.doc_id,
                "doc_type": c.doc_type,
                "article": c.article or "",
                "status": c.status,
                "valid_to": c.valid_to or "",
                "lang": c.lang,
            }
            for i, c in enumerate(chunks)
        ]
        db = lancedb.connect(str(self.vectors_path))
        if TABLE_NAME in db.table_names():
            db.drop_table(TABLE_NAME)
        self._table = db.create_table(TABLE_NAME, data=rows)
        self._db = db

        self.meta_path.write_text(
            json.dumps(
                {
                    "chunks": len(chunks),
                    "dim": int(vectors.shape[1]),
                    "kb_version": kb_version,
                    "documents": len({c.doc_id for c in chunks}),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log.info("Indeks tayyor: %d chunk", len(chunks))

    # ------------------------------------------------------------------ #
    # Yuklash
    # ------------------------------------------------------------------ #

    def load(self) -> None:
        if self._chunks:
            return
        if not self.exists():
            raise IndexNotBuiltError(
                f"Indeks topilmadi: {self.path}. Avval quring: uzlegal index build"
            )

        import lancedb

        self._chunks = {}
        for line in self.chunks_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunk = Chunk(**json.loads(line))
                self._chunks[chunk.chunk_id] = chunk

        self._bm25 = BM25Index.load(self.bm25_path)
        self._db = lancedb.connect(str(self.vectors_path))
        self._table = self._db.open_table(TABLE_NAME)

    def doc_titles(self) -> set[str]:
        """Indeksdagi hujjat sarlavhalari (normallashtirilgan).

        Foydalanuvchi «Raqamli aktivlar kodeksi» kabi mavjud bo'lmagan
        hujjatni so'raganda buni **aniq** aytish uchun kerak: semantik
        jihatdan yaqin boshqa kodeksni ko'rsatish javob emas.
        """
        self.load()
        return {fold(c.doc_title) for c in self._chunks.values() if c.doc_title}

    @property
    def meta(self) -> dict[str, Any]:
        if self.meta_path.exists():
            return json.loads(self.meta_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        return {}

    def get(self, chunk_id: str) -> Chunk | None:
        self.load()
        return self._chunks.get(chunk_id)

    def chunks_for_article(self, doc_id: str, article: str, *, limit: int = 4) -> list[Chunk]:
        """Berilgan hujjatning berilgan moddasiga tegishli bo'laklar.

        Uzun modda bir nechta chunkka bo'lingan bo'lishi mumkin, shuning
        uchun ro'yxat qaytadi. Tartib — qism/band raqami bo'yicha, ya'ni
        birinchi chunk moddaning boshi bo'ladi.
        """
        self.load()
        found = [
            chunk
            for chunk in self._chunks.values()
            if chunk.doc_id == doc_id and chunk.article == article
        ]
        found.sort(key=lambda c: (c.part or "", c.item or "", c.chunk_id))
        return found[:limit]

    def reference_graph(self, *, rebuild: bool = False) -> ReferenceGraph | None:
        """Havola grafi — keshdan o'qiladi yoki arxivdan quriladi.

        Grafni `ingest.linking` quradi (u HTML havolalarini ham ko'radi,
        shuning uchun matn shablonlaridan aniqroq). Bu yerda faqat
        **keshlash** bor: graf embedding talab qilmaydi, lekin arxivni
        qayta ajratish ~10 s oladi va uni har qidiruvda takrorlash
        ma'nosiz.

        Xato yuz bersa `None` qaytadi — graf ixtiyoriy qatlam, usiz
        qidiruv to'liq ishlaydi, faqat havola qilingan normalar
        kontekstga qo'shilmaydi.
        """
        if self._graph is not None and not rebuild:
            return self._graph
        try:
            if self.graph_path.exists() and not rebuild:
                self._graph = ReferenceGraph.load(self.graph_path)
                return self._graph
            self._graph = self._build_graph()
            self._graph.save(self.graph_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            log.warning("Havola grafi tayyorlanmadi: %s", exc)
            return None
        return self._graph

    def _build_graph(self) -> ReferenceGraph:
        """Arxivdagi hujjatlardan grafni quradi.

        Faqat indeksdagi hujjatlar olinadi — arxivda indekslanmagan
        (masalan boshqa tildagi) nashrlar bo'lishi mumkin va ular grafga
        indeksda mavjud bo'lmagan tugunlarni qo'shardi.
        """
        from uzlegal.ingest.connectors.lex_uz import LexUzConnector
        from uzlegal.ingest.linking import build_graph
        from uzlegal.ingest.parsers.lex_uz import LexUzParser

        self.load()
        connector, parser = LexUzConnector(), LexUzParser()
        docs, pages = [], {}

        for doc_id in sorted({c.doc_id for c in self._chunks.values()}):
            raw = connector.load_cached(doc_id)
            if raw is None:
                continue
            docs.append(parser.parse(raw))
            pages[doc_id] = raw.content

        log.info("Havola grafi qurilmoqda (%d hujjat)…", len(docs))
        graph = build_graph(docs, pages)
        log.info("Havola grafi: %s", graph.stats())
        return graph

    def __len__(self) -> int:
        self.load()
        return len(self._chunks)

    # ------------------------------------------------------------------ #
    # Qidiruv
    # ------------------------------------------------------------------ #

    def search_vector(self, query_vector: NDArray[Any], top_k: int = 50) -> list[ScoredChunk]:
        self.load()
        assert self._table is not None
        rows = self._table.search(query_vector.tolist()).limit(top_k).to_list()
        out: list[ScoredChunk] = []
        for row in rows:
            chunk = self._chunks.get(row["chunk_id"])
            if chunk is None:
                continue
            # LanceDB L2 masofa qaytaradi; vektorlar normallashtirilgani uchun
            # kosinus o'xshashlik = 1 - d²/2
            distance = float(row.get("_distance", 0.0))
            out.append(
                ScoredChunk(
                    chunk=chunk,
                    score=max(0.0, 1.0 - distance**2 / 2),
                    source="vector",
                )
            )
        return out

    def search_article(
        self, article: str, doc_hint: str | None = None, top_k: int = 10
    ) -> list[ScoredChunk]:
        """Modda raqami bo'yicha **aniq** moslik.

        Nima uchun bu alohida kanal: «234-modda» so'rovida BM25 ishlamaydi,
        chunki «modda» so'zi har bir chunk sarlavhasida bor va uning IDF si
        nolga yaqin, «234» esa boshqa moddalarning matnida havola sifatida
        uchraydi. Natijada to'g'ri modda yuqoriga chiqmaydi.

        Metadata bo'yicha to'g'ridan-to'g'ri qidirish bu muammoni butunlay
        hal qiladi — docs/04 § 2 dagi «aniq moslik» kanali.
        """
        self.load()
        hint = fold(doc_hint) if doc_hint else None
        matched: list[ScoredChunk] = []
        others: list[ScoredChunk] = []

        for chunk in self._chunks.values():
            if chunk.article is None:
                continue
            # "130-131" kabi birlashtirilgan chunklar ham hisobga olinadi
            numbers = chunk.article.split("-") if "-" in chunk.article else [chunk.article]
            if article not in numbers and chunk.article != article:
                continue

            score = 1.2 if chunk.article == article else 1.0
            item = ScoredChunk(chunk=chunk, score=score, source="exact")

            if hint and hint in fold(chunk.doc_title):
                matched.append(item)
            else:
                others.append(item)

        # Foydalanuvchi hujjatni aytgan bo'lsa («FK 234-modda»), u aynan shuni
        # so'ragan. Boshqa kodeksdagi bir xil raqamli modda faqat mos hujjat
        # topilmagan holda ko'rsatiladi — aks holda ular chalkashtiradi.
        chosen = matched or others
        chosen.sort(key=lambda item: item.score, reverse=True)
        return chosen[:top_k]

    def search_lexical(self, query: str, top_k: int = 50) -> list[ScoredChunk]:
        self.load()
        assert self._bm25 is not None
        out: list[ScoredChunk] = []
        for chunk_id, score in self._bm25.search(query, top_k):
            chunk = self._chunks.get(chunk_id)
            if chunk is not None:
                out.append(ScoredChunk(chunk=chunk, score=score, source="lexical"))
        return out


class IndexNotBuiltError(RuntimeError):
    pass
