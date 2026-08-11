"""Retrieval baholash mantiqi testlari.

Indeks yoki model kerak emas — metrikalar va moslik mantiqi tekshiriladi.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uzlegal.eval.retrieval_eval import (
    CaseResult,
    EvalCase,
    EvalReport,
    load_cases,
    render_report,
)
from uzlegal.index.chunker import Chunk


def make_chunk(
    article: str, doc_title: str = "Fuqarolik kodeksi", status: str = "in_force"
) -> Chunk:
    return Chunk(
        chunk_id=f"c:{article}",
        doc_id="fk",
        doc_title=doc_title,
        doc_type="kodeks",
        lang="uz",
        article=article,
        heading=f"[{doc_title} > {article}-modda]",
        content="matn",
        status=status,
    )


def case(**kw: object) -> EvalCase:
    base: dict[str, object] = {"id": "t1", "query": "savol", "expected_articles": ["228"]}
    base.update(kw)
    return EvalCase(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Moslik mantiqi
# --------------------------------------------------------------------------- #


def test_togri_modda_mos_keladi() -> None:
    assert case().matches(make_chunk("228"))


def test_notogri_modda_mos_kelmaydi() -> None:
    assert not case().matches(make_chunk("229"))


def test_birlashtirilgan_chunk_mos_keladi() -> None:
    """«130-131» birlashtirilgan chunk «130» kutilganda hisobga olinishi kerak."""
    assert case(expected_articles=["130"]).matches(make_chunk("130-131"))


def test_prim_modda_aniq_mos() -> None:
    assert case(expected_articles=["497-1"]).matches(make_chunk("497-1"))


def test_bir_nechta_kutilgan_moddadan_biri() -> None:
    assert case(expected_articles=["149", "150"]).matches(make_chunk("150"))


def test_hujjat_ishorasi_hisobga_olinadi() -> None:
    """Boshqa kodeksdagi bir xil raqamli modda to'g'ri javob emas."""
    c = case(expected_articles=["130"], doc_hint="Mehnat")
    assert c.matches(make_chunk("130", doc_title="Mehnat kodeksi"))
    assert not c.matches(make_chunk("130", doc_title="Fuqarolik kodeksi"))


def test_raqamsiz_chunk_mos_kelmaydi() -> None:
    chunk = make_chunk("1")
    chunk.article = None
    assert not case().matches(chunk)


# --------------------------------------------------------------------------- #
# Metrikalar
# --------------------------------------------------------------------------- #


def report_with(*ranks: int | None) -> EvalReport:
    return EvalReport(
        results=[
            CaseResult(case=case(id=f"c{i}"), rank=r, latency_ms=100 + i * 10)
            for i, r in enumerate(ranks)
        ]
    )


def test_recall_at_1() -> None:
    assert report_with(1, 2, 1, None).recall_at(1) == 0.5


def test_recall_at_3() -> None:
    assert report_with(1, 3, 4, None).recall_at(3) == 0.5


def test_recall_at_10_topilmagan() -> None:
    assert report_with(11, None).recall_at(10) == 0.0


def test_mrr() -> None:
    # 1/1 + 1/2 + 0 = 1.5 / 3 = 0.5
    assert report_with(1, 2, None).mrr == pytest.approx(0.5)


def test_bosh_hisobot_xato_bermaydi() -> None:
    empty = EvalReport(results=[])
    assert empty.recall_at(1) == 0.0
    assert empty.mrr == 0.0
    assert empty.median_latency_ms == 0


def test_kechikish_median_va_p95() -> None:
    r = report_with(1, 1, 1, 1, 1)  # 100,110,120,130,140
    assert r.median_latency_ms == 120
    assert r.p95_latency_ms == 140


def test_topilmaganlar_royxati() -> None:
    r = report_with(1, None, 11)
    assert len(r.failures) == 2


def test_deprecated_leak() -> None:
    results = [
        CaseResult(case=case(), rank=1, latency_ms=10, deprecated_leaked=True),
        CaseResult(case=case(), rank=1, latency_ms=10, deprecated_leaked=False),
    ]
    assert EvalReport(results=results).deprecated_leak == 0.5


def test_kategoriya_boyicha() -> None:
    results = [
        CaseResult(case=case(category="mulk"), rank=1, latency_ms=10),
        CaseResult(case=case(category="mulk"), rank=5, latency_ms=10),
        CaseResult(case=case(category="mehnat"), rank=2, latency_ms=10),
    ]
    by_cat = EvalReport(results=results).by_category()
    assert by_cat["mulk"] == 0.5
    assert by_cat["mehnat"] == 1.0


# --------------------------------------------------------------------------- #
# Gold to'plam fayli
# --------------------------------------------------------------------------- #

GOLD = Path(__file__).parents[2] / "data" / "eval" / "retrieval-gold-v1" / "cases.jsonl"


@pytest.mark.skipif(not GOLD.exists(), reason="gold to'plam yo'q")
def test_gold_toplam_ogiladi() -> None:
    cases = load_cases(GOLD)
    assert len(cases) >= 30, "kamida 30 holat bo'lishi kerak"


@pytest.mark.skipif(not GOLD.exists(), reason="gold to'plam yo'q")
def test_gold_id_lari_unikal() -> None:
    ids = [c.id for c in load_cases(GOLD)]
    assert len(ids) == len(set(ids))


@pytest.mark.skipif(not GOLD.exists(), reason="gold to'plam yo'q")
def test_gold_har_holatda_kutilgan_modda_bor() -> None:
    for c in load_cases(GOLD):
        assert c.expected_articles, f"{c.id}: kutilgan modda ko'rsatilmagan"
        assert c.query.strip(), f"{c.id}: savol bo'sh"


@pytest.mark.skipif(not GOLD.exists(), reason="gold to'plam yo'q")
def test_gold_savollar_sarlavha_nusxasi_emas() -> None:
    """Savol «N-modda» shaklida bo'lmasligi kerak — bu o'lchovni soxtalashtiradi.

    Istisno: `modda-lookup` kategoriyasi ataylab shunday.
    """
    for c in load_cases(GOLD):
        if c.category == "modda-lookup":
            continue
        assert "-modda" not in c.query.lower(), f"{c.id}: savol modda raqamini o'z ichiga oladi"


def test_hisobot_render_qilinadi() -> None:
    text = render_report(report_with(1, 2, None))
    assert "recall@1" in text
    assert "MRR" in text or "mrr" in text


def test_gold_json_formati() -> None:
    """Har bir qator yaroqli JSON bo'lishi kerak."""
    if not GOLD.exists():
        pytest.skip("gold to'plam yo'q")
    for line in GOLD.read_text(encoding="utf-8").splitlines():
        if line.strip():
            json.loads(line)  # xato bo'lsa test yiqiladi
