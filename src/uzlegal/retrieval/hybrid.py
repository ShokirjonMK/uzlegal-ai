"""Gibrid qidiruv — vektor + leksik, RRF bilan birlashtirilgan.

## Nima uchun RRF va oddiy ball qo'shish emas

Vektor ballari kosinus (0…1), BM25 ballari chegarasiz (0…30+). Ularni
qo'shish yoki o'rtachasini olish uchun normalizatsiya kerak, lekin har
so'rovda shkala o'zgaradi va normalizatsiya beqaror bo'ladi.

**Reciprocal Rank Fusion** faqat **o'rinni** ishlatadi:

    RRF(d) = Σ  w_i / (k + rank_i(d))

Shkala muammosi yo'q.

## Nima uchun k = 3, adabiyotdagi 60 emas

`k=60` standart qiymat, lekin u **ikkala kanal ham teng ishonchli**
bo'lgan holat uchun. Bizda ular teng emas va k=60 aynan shuning uchun
zarar keltirardi (`retrieval-gold-v1` da o'lchangan):

    savol:  "Yangi xodimni tekshirib ko'rish uchun qancha vaqt"
    vektor: to'g'ri modda — 1-o'rin
    leksik: umuman topmagan
    RRF60:  29-o'rin  ← to'g'ri javob top-10 dan chiqib ketdi

Sabab arifmetik: k=60 da 1-o'rin `1/61`, 50-o'rin `1/110` — farq 1.8x.
Ikkala kanalda ham o'rtacha turgan chunk bitta kanalda birinchi turgan
chunkni bosib ketadi. k=3 da esa farq `1/4` va `1/53` — 13x, ya'ni
ishonchli kanalning birinchi o'rni saqlanadi.

O'lchangan ta'sir: Recall@10 **69% → 89%**, modda-lookup 100% da qoldi.

## So'rov turiga qarab vaznlar

Yurist «FK 234-modda» deb so'rasa — leksik moslik hal qiluvchi (aslida
uchinchi, aniq moslik kanali hal qiladi). «bu shartnoma haqiqiymi» deb
so'rasa — semantik.

Vaznlar ham o'lchab tanlangan: ma'noga asoslangan savollarda vektor
kanali ustun (0.8), chunki o'zbek yuridik matnida so'rov so'zlari qonun
matnida deyarli hech qachon uchramaydi (docs/04 § 4).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from uzlegal.index.store import KnowledgeIndex, ScoredChunk
from uzlegal.ingest.linking import ReferenceGraph
from uzlegal.ingest.normalize import fold
from uzlegal.retrieval.routing import DocumentRouter, Route

log = logging.getLogger(__name__)

RRF_K = 3


class QueryKind(StrEnum):
    ARTICLE_LOOKUP = "article_lookup"  # "FK 234-modda"
    FACTUAL = "factual"  # "MMT stavkasi qancha"
    ANALYTICAL = "analytical"  # "bu shartnoma haqiqiymi"
    PROCEDURAL = "procedural"  # "apellyatsiya muddati"


# So'rov turi → (vektor, leksik) vaznlari.
# Qiymatlar `retrieval-gold-v1` da o'lchab tanlangan, taxmin qilinmagan.
WEIGHTS: dict[QueryKind, tuple[float, float]] = {
    # Modda raqami aytilgan: uchinchi kanal (aniq moslik) hal qiladi,
    # shuning uchun bu ikkisining nisbati unchalik muhim emas.
    QueryKind.ARTICLE_LOOKUP: (0.4, 0.6),
    QueryKind.FACTUAL: (0.8, 0.2),
    QueryKind.ANALYTICAL: (0.8, 0.2),
    QueryKind.PROCEDURAL: (0.8, 0.2),
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
    routed_domains: list[str] = field(default_factory=list)
    graph_hits: int = 0
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
        route: bool = True,
        graph_expand: int = 3,
    ) -> None:
        self.index = index
        self._embedder = embedder
        self._reranker = reranker
        self.use_reranker = use_reranker
        self.expand = expand
        self.route = route
        self.graph_expand = graph_expand
        self._expander: object | None = None
        self._router: DocumentRouter | None = None
        self._graph: ReferenceGraph | None = None
        self._graph_loaded = False

    @property
    def embedder(self) -> object:
        if self._embedder is None:
            from uzlegal.index.embedder import Embedder

            self._embedder = Embedder()
        return self._embedder

    @property
    def router(self) -> DocumentRouter:
        if self._router is None:
            self._router = DocumentRouter()
        return self._router

    @property
    def graph(self) -> ReferenceGraph | None:
        """Havola grafi — birinchi murojaatda quriladi va keshlanadi.

        Graf ixtiyoriy: u yo'q bo'lsa qidiruv ishlaydi, faqat havola
        qilingan normalar kontekstga qo'shilmaydi.
        """
        if not self._graph_loaded:
            self._graph_loaded = True
            self._graph = self.index.reference_graph()
        return self._graph

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
        candidates: int = 100,
        as_of: date | None = None,
        kind: QueryKind | None = None,
        rerank: bool | None = None,
        expand: bool | None = None,
        route: bool | None = None,
        graph_expand: int | None = None,
    ) -> RetrievalResult:
        import time

        t0 = time.time()
        kind = kind or classify_query(query)
        w_vec, w_lex = WEIGHTS[kind]

        routing = (
            self.router.route(query) if (self.route if route is None else route) else Route()
        )

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
        # Savolda hujjat aytilmagan bo'lsa yo'naltirish uni to'ldiradi:
        # «234-modda» yolg'iz kelganda ham savol matni sohani ko'rsatadi.
        exact_hits = (
            self.index.search_article(article, doc_hint or routing.primary_document)
            if article
            else []
        )

        fused = self._rrf(vector_hits, lexical_hits, w_vec, w_lex, exact_hits)
        fused = self._apply_routing(fused, routing)
        filtered, dropped = version_filter(fused, as_of)

        # Cross-encoder faqat versiya filtridan keyin ishlaydi — bekor
        # qilingan normani qayta tartiblashning ma'nosi yo'q va u qimmat.
        reranked = False
        if (self.use_reranker if rerank is None else rerank) and filtered:
            head = filtered[: max(top_k * 3, 20)]
            filtered = self.reranker.rerank(query, head) + filtered[len(head) :]  # type: ignore[attr-defined]
            reranked = True

        # Graf kengaytmasi **top-k tanlangandan keyin** qo'llaniladi va
        # natijalar oxiriga qo'shiladi. Nima uchun keyin: havola qilingan
        # norma asosiy natijalarni pastga surib yuborsa, to'g'ri modda
        # top-k dan chiqib ketishi mumkin edi — kengaytma sifatni
        # oshirish o'rniga buzardi.
        results = filtered[:top_k]
        limit = self.graph_expand if graph_expand is None else graph_expand
        linked = self._graph_neighbours(results, limit=limit, as_of=as_of)

        return RetrievalResult(
            reranked=reranked,
            results=results + linked,
            query_kind=kind,
            vector_hits=len(vector_hits),
            lexical_hits=len(lexical_hits),
            exact_hits=len(exact_hits),
            expansion_terms=expansion_terms,
            routed_domains=routing.domains,
            graph_hits=len(linked),
            dropped_by_version=dropped,
            latency_ms=int((time.time() - t0) * 1000),
        )

    # ------------------------------------------------------------------ #
    # Yo'naltirish va graf
    # ------------------------------------------------------------------ #

    def _apply_routing(
        self, results: list[ScoredChunk], routing: Route
    ) -> list[ScoredChunk]:
        """Yo'naltirilgan hujjatlarning ballini ko'taradi.

        Bu **qat'iy filtr emas**: mos kelmagan hujjat ro'yxatda qoladi,
        faqat pastroq o'rinda. Yo'naltirish xato qilsa to'g'ri javob
        yo'qolmaydi — docs/04 § 4 dagi tamoyil.
        """
        if not routing.is_routed:
            return results

        boosted = [
            ScoredChunk(
                chunk=item.chunk,
                score=item.score * self.router.boost_factor(routing, item.chunk.doc_title),
                source=item.source,
            )
            for item in results
        ]
        boosted.sort(key=lambda item: item.score, reverse=True)
        return boosted

    def _graph_neighbours(
        self, results: list[ScoredChunk], *, limit: int, as_of: date | None
    ) -> list[ScoredChunk]:
        """Topilgan normalar havola qiladigan normalarni qo'shadi.

        Ball ota-normanikidan past qilib beriladi — bu qo'shimcha kontekst,
        asosiy javob emas.
        """
        if limit <= 0 or not results:
            return []
        graph = self.graph
        if graph is None:
            return []

        present = {item.chunk_id for item in results}
        seen_norms = {
            (item.chunk.doc_id, item.chunk.article)
            for item in results
            if item.chunk.article
        }
        added: list[ScoredChunk] = []

        for item in results:
            if len(added) >= limit:
                break
            if item.chunk.article is None:
                continue
            node = f"{item.chunk.doc_id}:{item.chunk.article}"
            for key in graph.neighbors(node):
                if len(added) >= limit:
                    break
                doc_id, _, article = key.rpartition(":")
                if (doc_id, article) in seen_norms:
                    continue
                for chunk in self.index.chunks_for_article(doc_id, article, limit=1):
                    if chunk.chunk_id in present:
                        continue
                    present.add(chunk.chunk_id)
                    seen_norms.add((doc_id, article))
                    added.append(
                        ScoredChunk(chunk=chunk, score=item.score * 0.4, source="graph")
                    )

        kept, _ = version_filter(added, as_of)
        return kept

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
