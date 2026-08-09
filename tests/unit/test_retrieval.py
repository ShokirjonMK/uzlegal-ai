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
    build_context,
    classify_query,
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
    """«2021-yilda qanday edi?» — o'sha paytda amalda bo'lgan norma."""
    old = ScoredChunk(
        chunk=make_chunk("2", "eski", valid_from="2019-01-01", valid_to="2022-01-01"),
        score=1.0,
    )
    assert version_filter([old], as_of=date(2021, 6, 1))[0]
    assert version_filter([old], as_of=None)[0] == []


def test_amaldagi_norma_qoladi() -> None:
    chunk = make_chunk("1", "amalda", valid_from="2020-01-01", valid_to=None)
    kept, dropped = version_filter([ScoredChunk(chunk=chunk, score=1.0)])
    assert len(kept) == 1 and dropped == 0


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
    items = [
        ScoredChunk(chunk=make_chunk(str(i), "so'z " * 200), score=1.0) for i in range(20)
    ]
    _, used = build_context(items, budget_tokens=1000)
    assert 0 < len(used) < 20


def test_bosh_natija_bosh_kontekst() -> None:
    context, used = build_context([])
    assert context == "" and used == []
