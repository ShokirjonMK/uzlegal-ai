"""Gibrid qidiruv — vektor + leksik, RRF bilan birlashtirilgan.

## Nima uchun RRF va oddiy ball qo'shish emas

Vektor ballari kosinus (0…1), BM25 ballari chegarasiz (0…30+). Ularni
qo'shish yoki o'rtachasini olish uchun normalizatsiya kerak, lekin har
so'rovda shkala o'zgaradi va normalizatsiya beqaror bo'ladi.

**Reciprocal Rank Fusion** faqat **o'rinni** ishlatadi:

    RRF(d) = Σ  w_i / (k + rank_i(d))        k = 60

Shkala muammosi yo'q. `k=60` — adabiyotdagi standart qiymat; u yuqori
o'rinlarni ustun qo'yadi, lekin quyi o'rinlarni butunlay yo'qotmaydi.

## So'rov turiga qarab vaznlar

Yurist «FK 234-modda» deb so'rasa — leksik moslik hal qiluvchi.
«bu shartnoma haqiqiymi» deb so'rasa — semantik.

Shuning uchun vaznlar so'rov turiga qarab o'zgaradi (docs/04 § 4).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from uzlegal.index.store import KnowledgeIndex, ScoredChunk
from uzlegal.ingest.normalize import fold

log = logging.getLogger(__name__)

RRF_K = 60


class QueryKind(StrEnum):
    ARTICLE_LOOKUP = "article_lookup"  # "FK 234-modda"
    FACTUAL = "factual"  # "MMT stavkasi qancha"
    ANALYTICAL = "analytical"  # "bu shartnoma haqiqiymi"
    PROCEDURAL = "procedural"  # "apellyatsiya muddati"


# So'rov turi → (vektor, leksik) vaznlari
WEIGHTS: dict[QueryKind, tuple[float, float]] = {
    QueryKind.ARTICLE_LOOKUP: (0.2, 0.8),
    QueryKind.FACTUAL: (0.4, 0.6),
    QueryKind.ANALYTICAL: (0.7, 0.3),
    QueryKind.PROCEDURAL: (0.5, 0.5),
}

_ARTICLE_REF = re.compile(r"\b\d{1,4}\s*[-–]?\s*(?:modda|модда)|стать[яи]\s*\d+", re.IGNORECASE)
_ARTICLE_NUMBER = re.compile(
    r"(?:\b(\d{1,4})\s*[-–]?\s*(?:modda|модда)|стать[яи]\s*(\d{1,4}))", re.IGNORECASE
)

# Yuristlar kodekslarni qisqartma bilan ataydi. Bu qisqartmalar rasmiy emas,
# lekin amalda universal — so'rovni to'g'ri hujjatga yo'naltiradi.
DOC_ABBREVIATIONS: dict[str, str] = {
    "fk": "fuqarolik kodeksi",
    "гк": "fuqarolik kodeksi",
    "mk": "mehnat kodeksi",
    "тк": "mehnat kodeksi",
    "jk": "jinoyat kodeksi",
    "ук": "jinoyat kodeksi",
    "jpk": "jinoyat-protsessual kodeksi",
    "fpk": "fuqarolik protsessual kodeksi",
    "ok": "oila kodeksi",
    "sk": "soliq kodeksi",
    "mjtk": "ma'muriy javobgarlik",
}


def extract_article_ref(query: str) -> tuple[str | None, str | None]:
    """So'rovdan modda raqami va hujjat ishorasini ajratadi.

    `("234", "fuqarolik kodeksi")` yoki `(None, None)`.
    """
    m = _ARTICLE_NUMBER.search(query)
    if not m:
        return None, None
    number = next((g for g in m.groups() if g), None)

    folded = fold(query)
    doc_hint = next(
        (full for abbr, full in DOC_ABBREVIATIONS.items() if re.search(rf"\b{abbr}\b", folded)),
        None,
    )
    if doc_hint is None:
        for name in ("fuqarolik", "mehnat", "jinoyat", "oila", "soliq", "yer", "uy-joy"):
            if name in folded:
                doc_hint = name
                break
    return number, doc_hint


_PROCEDURAL = re.compile(
    r"\b(muddat|tartib|ariza|shikoyat|apellyatsiya|kassatsiya|sud\w*\s+murojaat|"
    r"protsessual|срок|порядок|жалоб|апелляц)", re.IGNORECASE
)
_ANALYTICAL = re.compile(
    r"\b(mumkinmi|bo['ʻ]ladimi|haqlimi|haqiqiymi|kim\s+haq|qanday\s+himoya|"
    r"oqibat|javobgar\w*mi|можно\s+ли|вправе\s+ли)", re.IGNORECASE
)


def classify_query(query: str) -> QueryKind:
    """So'rov turini aniqlaydi — bu retrieval vaznlarini belgilaydi."""
    if _ARTICLE_REF.search(query):
        return QueryKind.ARTICLE_LOOKUP
    if _ANALYTICAL.search(query):
        return QueryKind.ANALYTICAL
    if _PROCEDURAL.search(query):
        return QueryKind.PROCEDURAL
    return QueryKind.FACTUAL


# --------------------------------------------------------------------------- #
# Versiya filtri — yuridik RAG ni oddiy RAG dan ajratadigan narsa
# --------------------------------------------------------------------------- #


def version_filter(
    results: list[ScoredChunk], as_of: date | None = None
) -> tuple[list[ScoredChunk], int]:
    """Faqat berilgan sanada amalda bo'lgan normalarni qoldiradi.

    `as_of=None` — bugungi holat. Bekor qilingan norma **hech qachon**
    kontekstga tushmaydi; bu texnik cheklov, model xohishiga bog'liq emas
    (docs/00 dagi «0% deprecated» talabi).

    `(qolganlar, chiqarilganlar_soni)` qaytaradi — chiqarilganlar soni
    monitoring uchun kerak.
    """
    reference = (as_of or date.today()).isoformat()
    kept: list[ScoredChunk] = []
    dropped = 0

    for item in results:
        chunk = item.chunk
        if chunk.status != "in_force" and as_of is None:
            dropped += 1
            continue
        if chunk.valid_from and chunk.valid_from > reference:
            dropped += 1
            continue
        if chunk.valid_to and chunk.valid_to <= reference:
            dropped += 1
            continue
        kept.append(item)

    if dropped:
        log.debug("Versiya filtri %d chunkni chiqardi", dropped)
    return kept, dropped


# --------------------------------------------------------------------------- #
# Natija
# --------------------------------------------------------------------------- #


@dataclass
class RetrievalResult:
    results: list[ScoredChunk]
    query_kind: QueryKind
    vector_hits: int
    lexical_hits: int
    dropped_by_version: int
    exact_hits: int = 0
    reranked: bool = False
    expansion_terms: list[str] = field(default_factory=list)
    latency_ms: int = 0

    @property
    def top_score(self) -> float:
        return self.results[0].score if self.results else 0.0

    @property
    def is_confident(self) -> bool:
        """Ishonch chegarasi — docs/04 § 8.

        RRF ballari kichik (1/61 ≈ 0.016 eng yuqori bitta manbadan),
        shuning uchun chegara ham kichik. Muhimi — ikkala qidiruv ham
        topganmi yoki bittasi tasodifan chiqarganmi.
        """
        if not self.results:
            return False
        # Reranker ballari boshqa shkalada (logit, taxminan −10…+10),
        # RRF ballari esa 0…0.05 atrofida. Chegara shunga qarab tanlanadi.
        threshold = 0.0 if self.reranked else 0.02
        return self.top_score >= threshold


# --------------------------------------------------------------------------- #
# Retriever
# --------------------------------------------------------------------------- #


class HybridRetriever:
    def __init__(
        self,
        index: KnowledgeIndex,
        embedder: object | None = None,
        reranker: object | None = None,
        *,
        use_reranker: bool = False,
        expand: bool = True,
    ) -> None:
        self.index = index
        self._embedder = embedder
        self._reranker = reranker
        self.use_reranker = use_reranker
        self.expand = expand
        self._expander: object | None = None

    @property
    def embedder(self) -> object:
        if self._embedder is None:
            from uzlegal.index.embedder import Embedder

            self._embedder = Embedder()
        return self._embedder

    @property
    def expander(self) -> object:
        if self._expander is None:
            from uzlegal.retrieval.expansion import QueryExpander

            self._expander = QueryExpander()
        return self._expander

    @property
    def reranker(self) -> object:
        if self._reranker is None:
            from uzlegal.retrieval.reranker import Reranker

            self._reranker = Reranker()
        return self._reranker

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        candidates: int = 50,
        as_of: date | None = None,
        kind: QueryKind | None = None,
        rerank: bool | None = None,
        expand: bool | None = None,
    ) -> RetrievalResult:
        import time

        t0 = time.time()
        kind = kind or classify_query(query)
        w_vec, w_lex = WEIGHTS[kind]

        # Kengaytma **faqat leksik qidiruvga** qo'llaniladi. Vektor qidiruvida
        # atama qo'shish semantik markazni siljitadi va sifatni tushiradi —
        # embedding modeli asl savolni yaxshiroq tushunadi.
        search_query = query
        expansion_terms: list[str] = []
        if (self.expand if expand is None else expand) and kind != QueryKind.ARTICLE_LOOKUP:
            search_query, expansion_terms = self.expander.expand(query)  # type: ignore[attr-defined]

        vector_hits: list[ScoredChunk] = []
        if w_vec > 0:
            qvec = self.embedder.encode_one(query, is_query=True)  # type: ignore[attr-defined]
            vector_hits = self.index.search_vector(qvec, top_k=candidates)

        lexical_hits = (
            self.index.search_lexical(search_query, top_k=candidates) if w_lex > 0 else []
        )

        # Uchinchi kanal: modda raqami bo'yicha aniq moslik (docs/04 § 2).
        # BM25 buni uddalay olmaydi — «modda» so'zining IDF si nolga yaqin.
        article, doc_hint = extract_article_ref(query)
        exact_hits = (
            self.index.search_article(article, doc_hint) if article else []
        )

        fused = self._rrf(vector_hits, lexical_hits, w_vec, w_lex, exact_hits)
        filtered, dropped = version_filter(fused, as_of)

        # Cross-encoder faqat versiya filtridan keyin ishlaydi — bekor
        # qilingan normani qayta tartiblashning ma'nosi yo'q va u qimmat.
        reranked = False
        if (self.use_reranker if rerank is None else rerank) and filtered:
            head = filtered[: max(top_k * 3, 20)]
            filtered = self.reranker.rerank(query, head) + filtered[len(head) :]  # type: ignore[attr-defined]
            reranked = True

        return RetrievalResult(
            reranked=reranked,
            results=filtered[:top_k],
            query_kind=kind,
            vector_hits=len(vector_hits),
            lexical_hits=len(lexical_hits),
            exact_hits=len(exact_hits),
            expansion_terms=expansion_terms,
            dropped_by_version=dropped,
            latency_ms=int((time.time() - t0) * 1000),
        )

    @staticmethod
    def _rrf(
        vector_hits: list[ScoredChunk],
        lexical_hits: list[ScoredChunk],
        w_vec: float,
        w_lex: float,
        exact_hits: list[ScoredChunk] | None = None,
    ) -> list[ScoredChunk]:
        scores: dict[str, float] = {}
        chunks: dict[str, ScoredChunk] = {}

        # Aniq moslik vazni yuqori: foydalanuvchi modda raqamini aytgan bo'lsa,
        # u aynan shu moddani so'ragan — taxmin qilishning hojati yo'q.
        sources = [(w_vec, vector_hits), (w_lex, lexical_hits)]
        if exact_hits:
            sources.append((2.0, exact_hits))

        for weight, hits in sources:
            for rank, item in enumerate(hits, start=1):
                scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + weight / (RRF_K + rank)
                chunks.setdefault(item.chunk_id, item)

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [
            ScoredChunk(chunk=chunks[cid].chunk, score=score, source="hybrid")
            for cid, score in ranked
        ]


# --------------------------------------------------------------------------- #
# Kontekstni yig'ish
# --------------------------------------------------------------------------- #


def build_context(
    results: list[ScoredChunk], *, budget_tokens: int = 6000
) -> tuple[str, list[ScoredChunk]]:
    """Agentlarga beriladigan kontekstni yig'adi.

    Har bo'lak `[C1]`, `[C2]` belgisi bilan keladi — shu belgi orqali
    groundedness gate iqtibosni chunkga bog'laydi va tekshiradi.
    """
    lines: list[str] = []
    used: list[ScoredChunk] = []
    spent = 0

    for i, item in enumerate(results, start=1):
        chunk = item.chunk
        cost = chunk.token_count + 40  # sarlavha va belgilar uchun
        if spent + cost > budget_tokens:
            break
        tag = f"C{i}"
        lines.append(
            f"=== [{tag}] {chunk.citation_label} ===\n"
            f"{chunk.content}\n"
            f"=== manba: {chunk.source_url or '—'} ==="
        )
        used.append(item)
        spent += cost

    return "\n\n".join(lines), used


def normalized_query(query: str) -> str:
    """BM25 uchun so'rovni normallashtiradi (test va debug qulayligi uchun)."""
    return fold(query)
