"""Gibrid qidiruv testlari — BM25, RRF, versiya filtri.

Embedding modeli kerak emas: leksik qatlam va birlashtirish mantiqi
mustaqil tekshiriladi.
"""

from __future__ import annotations

from datetime import date

import pytest

from uzlegal.index.chunker import Chunk
from uzlegal.index.store import BM25Index, ScoredChunk, tokenize
from uzlegal.retrieval.hybrid import (
    HybridRetriever,
    QueryKind,
    RetrievalResult,
    build_context,
    classify_query,
    date_coverage,
    version_filter,
)


def make_chunk(cid: str, content: str, **kw: object) -> Chunk:
    return Chunk(
        chunk_id=cid,
        doc_id="fk",
        doc_title="Fuqarolik kodeksi",
        doc_type="kodeks",
        lang="uz",
        article=kw.pop("article", cid),  # type: ignore[arg-type]
        heading=f"[Fuqarolik kodeksi > {cid}-modda]",
        content=content,
        token_count=len(content.split()) * 2,
        **kw,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# Tokenizatsiya — o'zbek apostrofi
# --------------------------------------------------------------------------- #


def test_apostrof_variantlari_bir_token() -> None:
    assert tokenize("oʻzgartirish") == tokenize("o'zgartirish") == tokenize("o‘zgartirish")


def test_kirill_lotinga_ogiriladi() -> None:
    assert tokenize("модда") == ["modda"]


def test_raqamlar_saqlanadi() -> None:
    assert "234" in tokenize("234-modda")


# --------------------------------------------------------------------------- #
# BM25
# --------------------------------------------------------------------------- #


@pytest.fixture
def bm25() -> BM25Index:
    index = BM25Index()
    index.build(
        [
            make_chunk("234", "Mulkdor oʻzgalarning qonunsiz egaligidagi mulkni talab qiladi"),
            make_chunk("106", "Mehnat shartnomasi tomonlarning kelishuvi bilan bekor qilinadi"),
            make_chunk("111", "Sinov muddati olti oydan oshmasligi kerak"),
        ]
    )
    return index


def test_bm25_topadi(bm25: BM25Index) -> None:
    hits = bm25.search("mehnat shartnomasi", top_k=3)
    assert hits and hits[0][0] == "106"


def test_bm25_apostrof_farq_qilmaydi(bm25: BM25Index) -> None:
    """Foydalanuvchi ASCII apostrof yozadi, korpusda esa oʻ turibdi."""
    assert bm25.search("o'zgalarning", top_k=3)[0][0] == "234"


def test_bm25_kirill_sorov(bm25: BM25Index) -> None:
    assert bm25.search("мулкдор", top_k=3)[0][0] == "234"


def test_bm25_yoq_soz_bosh_natija(bm25: BM25Index) -> None:
    assert bm25.search("bunday-soz-yoq-albatta", top_k=3) == []


def test_bosh_indeks_xato_bermaydi() -> None:
    assert BM25Index().search("nimadir") == []


def test_bm25_saqlanadi_va_yuklanadi(bm25: BM25Index, tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "bm25.pkl"
    bm25.save(path)
    assert BM25Index.load(path).search("sinov muddati", top_k=1)[0][0] == "111"


# --------------------------------------------------------------------------- #
# So'rov turini aniqlash — retrieval vaznlarini belgilaydi
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("query", "kind"),
    [
        ("FK 234-modda", QueryKind.ARTICLE_LOOKUP),
        ("Статья 234", QueryKind.ARTICLE_LOOKUP),
        ("Bu shartnoma haqiqiymi", QueryKind.ANALYTICAL),
        ("Ishdan boʻshatish mumkinmi", QueryKind.ANALYTICAL),
        ("Apellyatsiya muddati qancha", QueryKind.PROCEDURAL),
        ("MMT stavkasi", QueryKind.FACTUAL),
    ],
)
def test_sorov_turi(query: str, kind: QueryKind) -> None:
    assert classify_query(query) == kind


# --------------------------------------------------------------------------- #
# RRF birlashtirish
# --------------------------------------------------------------------------- #


def test_rrf_ikkala_manbadagi_natijani_yuqori_qoyadi() -> None:
    a, b, c = (make_chunk(x, f"matn {x}") for x in ("A", "B", "C"))
    vector = [ScoredChunk(chunk=a, score=0.9), ScoredChunk(chunk=b, score=0.8)]
    lexical = [ScoredChunk(chunk=c, score=9.0), ScoredChunk(chunk=a, score=5.0)]

    fused = HybridRetriever._rrf(vector, lexical, 0.5, 0.5)

    assert fused[0].chunk_id == "A", "ikkala qidiruvda ham bor — birinchi bo'lishi kerak"
    assert {f.chunk_id for f in fused} == {"A", "B", "C"}


def test_rrf_vaznlar_tasir_qiladi() -> None:
    a, b = make_chunk("A", "x"), make_chunk("B", "y")
    vector = [ScoredChunk(chunk=a, score=0.9)]
    lexical = [ScoredChunk(chunk=b, score=9.0)]

    assert HybridRetriever._rrf(vector, lexical, 0.9, 0.1)[0].chunk_id == "A"
    assert HybridRetriever._rrf(vector, lexical, 0.1, 0.9)[0].chunk_id == "B"


def test_rrf_bosh_royxatlar() -> None:
    assert HybridRetriever._rrf([], [], 0.5, 0.5) == []


# --------------------------------------------------------------------------- #
# Versiya filtri — yuridik RAG ning ajratuvchi xususiyati
# --------------------------------------------------------------------------- #


def test_bekor_qilingan_norma_chiqariladi() -> None:
    live = ScoredChunk(chunk=make_chunk("1", "amaldagi"), score=1.0)
    dead = ScoredChunk(chunk=make_chunk("2", "eski", status="repealed"), score=2.0)

    kept, dropped = version_filter([dead, live])

    assert [k.chunk_id for k in kept] == ["1"]
    assert dropped == 1


def test_muddati_tugagan_chiqariladi() -> None:
    old = ScoredChunk(chunk=make_chunk("2", "eski", valid_to="2020-01-01"), score=1.0)
    kept, dropped = version_filter([old])
    assert kept == [] and dropped == 1


def test_kelajakdagi_norma_chiqariladi() -> None:
    future = ScoredChunk(chunk=make_chunk("3", "hali", valid_from="2099-01-01"), score=1.0)
    kept, _ = version_filter([future])
    assert kept == []


def test_as_of_bilan_tarixiy_holat() -> None:
    """«2021-yilda qanday edi?» — o'sha paytda amalda bo'lgan norma.

    O'ZGARTIRILDI (docs/21 § 2.2). Ilgari bu test faqat `in_force`
    bo'lakni tekshirardi va shu bilan «`as_of` berilganda status
    umuman qaralmaydi» degan xatti-harakatni to'g'ri deb qayd etardi.
    Endi shartnoma boshqa: `as_of` berilganda ham status qaraladi va
    bekor qilinganlik sanasi **ma'lum** bo'lgandagina bo'lak o'sha
    sanadagi holat sifatida qoldiriladi. Shu sababli testga bekor
    qilingan, lekin `valid_to` si ma'lum bo'lgan bo'lak qo'shildi.
    """
    old = ScoredChunk(
        chunk=make_chunk("2", "eski", valid_from="2019-01-01", valid_to="2022-01-01"),
        score=1.0,
    )
    assert version_filter([old], as_of=date(2021, 6, 1))[0]
    assert version_filter([old], as_of=None)[0] == []

    # Bekor qilingan, ammo qachon bekor qilingani MA'LUM: 2021-yilda
    # hali amalda edi, bugun esa yo'q.
    repealed = ScoredChunk(
        chunk=make_chunk(
            "3", "bekor", status="repealed", valid_from="2019-01-01", valid_to="2022-01-01"
        ),
        score=1.0,
    )
    assert version_filter([repealed], as_of=date(2021, 6, 1))[0]
    assert version_filter([repealed], as_of=None)[0] == []


def test_bekor_qilingan_norma_as_of_bilan_ham_chiqariladi() -> None:
    """`valid_to` bo'sh bo'lsa bekor qilingan norma `as_of` da ham chiqariladi.

    Bu docs/21 § 2.1 dagi uchinchi qator: bekor qilingan sana noma'lum
    bo'lsa, bo'lak `as_of` da amalda bo'lganini tasdiqlab bo'lmaydi.
    `ingest/versioning.py` sanani aniqlay olmaganda `valid_to` ni
    ataylab bo'sh qoldiradi — ya'ni bu holat faraziy emas.
    """
    dead = ScoredChunk(chunk=make_chunk("2", "eski", status="repealed"), score=1.0)

    kept, dropped = version_filter([dead], as_of=date(2021, 6, 1))

    assert kept == []
    assert dropped == 1


def test_bekor_qilingan_norma_faqat_valid_from_bilan_chiqariladi() -> None:
    """`valid_from` bor, `valid_to` yo'q — baribir tasdiqlab bo'lmaydi."""
    dead = ScoredChunk(
        chunk=make_chunk("2", "eski", status="repealed", valid_from="2019-01-01"),
        score=1.0,
    )
    assert version_filter([dead], as_of=date(2021, 6, 1)) == ([], 1)


def test_amaldagi_norma_as_of_bilan_qoladi() -> None:
    """`in_force` va sanalari bo'sh bo'lsa — `as_of` da qoldiriladi (§ 2.1)."""
    live = ScoredChunk(chunk=make_chunk("1", "amaldagi"), score=1.0)
    kept, dropped = version_filter([live], as_of=date(2021, 6, 1))
    assert len(kept) == 1 and dropped == 0


def test_amaldagi_norma_qoladi() -> None:
    chunk = make_chunk("1", "amalda", valid_from="2020-01-01", valid_to=None)
    kept, dropped = version_filter([ScoredChunk(chunk=chunk, score=1.0)])
    assert len(kept) == 1 and dropped == 0


# --------------------------------------------------------------------------- #
# Sana qamrovi — docs/21 § 3
# --------------------------------------------------------------------------- #


def test_sana_qamrovi_sanaydi() -> None:
    known = ScoredChunk(chunk=make_chunk("1", "a", valid_from="2019-01-01"), score=1.0)
    unknown = ScoredChunk(chunk=make_chunk("2", "b"), score=1.0)

    coverage = date_coverage([known, unknown], date(2021, 6, 1))

    assert (coverage.confirmed, coverage.unknown, coverage.total) == (1, 1, 2)
    assert coverage.as_of == date(2021, 6, 1)


def test_bosh_natijada_qamrov_nol() -> None:
    coverage = date_coverage([], date(2021, 6, 1))
    assert coverage.confirmed == 0 and coverage.unknown == 0


def test_natijada_qamrov_yoq_bolishi_mumkin() -> None:
    """`as_of` so'ralmagan bo'lsa qamrov ham bo'lmaydi — bu shartnoma."""
    result = RetrievalResult(
        results=[],
        query_kind=QueryKind.FACTUAL,
        vector_hits=0,
        lexical_hits=0,
        dropped_by_version=0,
    )
    assert result.as_of is None and result.coverage is None


# --------------------------------------------------------------------------- #
# Kontekstni yig'ish
# --------------------------------------------------------------------------- #


def test_kontekst_belgilari() -> None:
    items = [ScoredChunk(chunk=make_chunk(str(i), f"matn {i}"), score=1.0) for i in (1, 2)]
    context, used = build_context(items)
    assert "[C1]" in context and "[C2]" in context
    assert len(used) == 2


def test_kontekst_iqtibos_va_manba() -> None:
    item = ScoredChunk(chunk=make_chunk("234", "Mulk huquqi"), score=1.0)
    context, _ = build_context([item])
    assert "234-modda" in context
    assert "manba:" in context


def test_kontekst_byudjeti_hurmat_qilinadi() -> None:
    items = [ScoredChunk(chunk=make_chunk(str(i), "so'z " * 200), score=1.0) for i in range(20)]
    _, used = build_context(items, budget_tokens=1000)
    assert 0 < len(used) < 20


def test_bosh_natija_bosh_kontekst() -> None:
    context, used = build_context([])
    assert context == "" and used == []


# --------------------------------------------------------------------------- #
# Aniq moslik — modda raqami bo'yicha (uchinchi kanal)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("query", "number", "hint_contains"),
    [
        ("FK 234-modda", "234", "fuqarolik"),
        ("MK 170-modda", "170", "mehnat"),
        ("Oila kodeksi 50-modda", "50", "oila"),
        ("Статья 234", "234", None),
        ("228-modda", "228", None),
        ("shartnoma haqida", None, None),
    ],
)
def test_modda_havolasi_ajratiladi(
    query: str, number: str | None, hint_contains: str | None
) -> None:
    from uzlegal.retrieval.hybrid import extract_article_ref

    got_number, got_hint = extract_article_ref(query)
    assert got_number == number
    if hint_contains:
        assert got_hint and hint_contains in got_hint


def test_hujjat_ishorasi_boshqa_kodeksni_chiqaradi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """«FK 234-modda» — boshqa kodeksdagi 234-modda chalkashtirmasligi kerak."""
    from uzlegal.index.store import KnowledgeIndex

    index = KnowledgeIndex(tmp_path / "kb")
    index._chunks = {
        "fk:234": make_chunk("fk:234", "Majburiyat", article="234"),
        "mk:234": make_chunk("mk:234", "Mehnat ta'tili", article="234"),
    }
    index._chunks["mk:234"].doc_title = "Mehnat kodeksi"

    hits = index.search_article("234", doc_hint="fuqarolik kodeksi")

    assert len(hits) == 1
    assert hits[0].chunk_id == "fk:234"


def test_ishorasiz_barcha_kodekslar(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from uzlegal.index.store import KnowledgeIndex

    index = KnowledgeIndex(tmp_path / "kb")
    index._chunks = {
        "fk:234": make_chunk("fk:234", "Majburiyat", article="234"),
        "mk:234": make_chunk("mk:234", "Ta'til", article="234"),
    }
    assert len(index.search_article("234")) == 2


def test_mos_hujjat_yoq_bolsa_boshqalar_korsatiladi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Ishora mos kelmasa ham natijasiz qoldirmaslik kerak."""
    from uzlegal.index.store import KnowledgeIndex

    index = KnowledgeIndex(tmp_path / "kb")
    index._chunks = {"fk:234": make_chunk("fk:234", "Majburiyat", article="234")}
    assert len(index.search_article("234", doc_hint="soliq kodeksi")) == 1


def test_birlashtirilgan_chunk_topiladi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """«130-131» birlashtirilgan chunk «130» so'roviga javob berishi kerak."""
    from uzlegal.index.store import KnowledgeIndex

    index = KnowledgeIndex(tmp_path / "kb")
    index._chunks = {"mk:130": make_chunk("mk:130", "Sinov muddati", article="130-131")}
    assert len(index.search_article("130")) == 1


def test_aniq_moslik_rrf_da_ustun() -> None:
    a, b = make_chunk("A", "x"), make_chunk("B", "y")
    vector = [ScoredChunk(chunk=b, score=0.9)]
    exact = [ScoredChunk(chunk=a, score=1.2, source="exact")]
    fused = HybridRetriever._rrf(vector, [], 0.7, 0.3, exact)
    assert fused[0].chunk_id == "A"


# --------------------------------------------------------------------------- #
# Graf kengaytmasi — havola qilingan normalarni qo'shish (F2)
# --------------------------------------------------------------------------- #


def _index_with(tmp_path, chunks: dict[str, object]):  # type: ignore[no-untyped-def]
    from uzlegal.index.store import KnowledgeIndex

    index = KnowledgeIndex(tmp_path / "kb")
    index._chunks = chunks  # type: ignore[assignment]
    index.load = lambda: None  # type: ignore[method-assign]
    return index


def _graph(edges: list[tuple[str, str]]):  # type: ignore[no-untyped-def]
    from uzlegal.ingest.linking import Reference, ReferenceGraph

    graph = ReferenceGraph()
    for source, target in edges:
        from_doc, _, from_article = source.rpartition(":")
        to_doc, _, to_article = target.rpartition(":")
        graph.add(
            Reference(
                from_doc=from_doc,
                from_article=from_article,
                to_doc=to_doc,
                to_article=to_article,
                kind="internal",
            )
        )
    return graph


def test_graf_havola_qilingan_norma_qoshiladi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """228-modda 229-moddaga havola qilsa, 229 ham kontekstga tushishi kerak."""
    found = make_chunk("fk:228", "Vindikatsiya", article="228")
    linked = make_chunk("fk:229", "Vijdonli oluvchi", article="229")
    index = _index_with(tmp_path, {"fk:228": found, "fk:229": linked})

    retriever = HybridRetriever(index)
    retriever._graph, retriever._graph_loaded = _graph([("fk:228", "fk:229")]), True

    added = retriever._graph_neighbours([ScoredChunk(chunk=found, score=1.0)], limit=3, as_of=None)

    assert [a.chunk_id for a in added] == ["fk:229"]
    assert added[0].source == "graph"
    assert added[0].score < 1.0, "qo'shimcha kontekst asosiy natijadan past turishi kerak"


def test_graf_allaqachon_topilgan_normani_takrorlamaydi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    a = make_chunk("fk:228", "Vindikatsiya", article="228")
    b = make_chunk("fk:229", "Vijdonli oluvchi", article="229")
    index = _index_with(tmp_path, {"fk:228": a, "fk:229": b})

    retriever = HybridRetriever(index)
    retriever._graph, retriever._graph_loaded = _graph([("fk:228", "fk:229")]), True

    results = [ScoredChunk(chunk=a, score=1.0), ScoredChunk(chunk=b, score=0.9)]
    assert retriever._graph_neighbours(results, limit=3, as_of=None) == []


def test_graf_bekor_qilingan_normani_qoshmaydi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Versiya filtri graf orqali kelgan normaga ham qo'llaniladi."""
    found = make_chunk("fk:228", "Vindikatsiya", article="228")
    dead = make_chunk("fk:229", "Eski norma", article="229", status="repealed")
    index = _index_with(tmp_path, {"fk:228": found, "fk:229": dead})

    retriever = HybridRetriever(index)
    retriever._graph, retriever._graph_loaded = _graph([("fk:228", "fk:229")]), True

    assert (
        retriever._graph_neighbours([ScoredChunk(chunk=found, score=1.0)], limit=3, as_of=None)
        == []
    )


def test_graf_ochirilganda_hech_narsa_qoshilmaydi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    found = make_chunk("fk:228", "Vindikatsiya", article="228")
    index = _index_with(tmp_path, {"fk:228": found})
    retriever = HybridRetriever(index)
    retriever._graph, retriever._graph_loaded = _graph([("fk:228", "fk:229")]), True

    assert (
        retriever._graph_neighbours([ScoredChunk(chunk=found, score=1.0)], limit=0, as_of=None)
        == []
    )


def test_graf_yoq_bolsa_qidiruv_ishlayveradi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Graf ixtiyoriy qatlam — u yo'q bo'lsa xato bermasligi kerak."""
    found = make_chunk("fk:228", "Vindikatsiya", article="228")
    index = _index_with(tmp_path, {"fk:228": found})
    retriever = HybridRetriever(index)
    retriever._graph, retriever._graph_loaded = None, True

    assert (
        retriever._graph_neighbours([ScoredChunk(chunk=found, score=1.0)], limit=3, as_of=None)
        == []
    )


# --------------------------------------------------------------------------- #
# Yo'naltirish fusion ballariga ta'siri (F2)
# --------------------------------------------------------------------------- #


def test_yonaltirish_mos_hujjatni_kotaradi(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from uzlegal.retrieval.routing import DocumentRouter, Domain, RoutingConfig

    mehnat = make_chunk("mk:333", "Ish haqi toʻlash", article="333")
    mehnat.doc_title = "Oʻzbekiston Respublikasining Mehnat kodeksi"
    bojxona = make_chunk("bk:333", "Boj toʻlash", article="333")
    bojxona.doc_title = "Oʻzbekiston Respublikasining Bojxona kodeksi"

    retriever = HybridRetriever(_index_with(tmp_path, {}))
    retriever._router = DocumentRouter(
        RoutingConfig(
            domains=(Domain(name="mehnat", documents=("mehnat kodeksi",), triggers=("maosh",)),),
            boost=0.8,
            min_score=1.0,
        )
    )
    route = retriever.router.route("Maoshni toʻlash tartibi")

    # Bojxona fusionda oldinda turibdi — yo'naltirish uni almashtirishi kerak
    fused = [
        ScoredChunk(chunk=bojxona, score=0.10),
        ScoredChunk(chunk=mehnat, score=0.08),
    ]
    boosted = retriever._apply_routing(fused, route)

    assert boosted[0].chunk_id == "mk:333"
    assert boosted[1].score == 0.10, "mos kelmagan hujjat jazolanmasligi kerak"


def test_ishonch_chegarasi_rrf_k_dan_kelib_chiqadi() -> None:
    """Chegara qo'lda yozilmaydi — `k` o'zgarganda u ham to'g'rilanadi.

    Bu haqiqiy tuzoq edi: `k` 60 dan 3 ga tushganda ballar shkalasi
    10 barobar siljidi va qo'lda yozilgan 0.02 chegarasi hamma narsani
    «ishonchli» deb ko'rsatardi.
    """
    from uzlegal.retrieval.hybrid import CONFIDENCE_RANK, CONFIDENCE_RANK_EQUIVALENT, RRF_K

    assert CONFIDENCE_RANK_EQUIVALENT == 1.0 / (RRF_K + CONFIDENCE_RANK)

    def result(score: float, reranked: bool = False) -> RetrievalResult:
        return RetrievalResult(
            results=[ScoredChunk(chunk=make_chunk("A", "matn"), score=score)],
            query_kind=QueryKind.FACTUAL,
            vector_hits=1,
            lexical_hits=0,
            dropped_by_version=0,
            reranked=reranked,
        )

    # Ustun kanalda 1-o'rin (0.8 vazn) — ishonchli
    assert result(0.8 / (RRF_K + 1)).is_confident
    # 50-o'rin — ishonchsiz
    assert not result(0.8 / (RRF_K + 50)).is_confident


def test_bosh_natija_ishonchsiz() -> None:
    empty = RetrievalResult(
        results=[],
        query_kind=QueryKind.FACTUAL,
        vector_hits=0,
        lexical_hits=0,
        dropped_by_version=0,
    )
    assert not empty.is_confident
