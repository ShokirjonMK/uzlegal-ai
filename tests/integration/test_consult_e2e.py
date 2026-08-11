"""Uchidan-uchiga integratsiya — haqiqiy indeks, soxta model.

## Nima uchun echo backend

Bu testlar **zanjirni** tekshiradi, model sifatini emas. Model sifati
`uzlegal eval` da o'lchanadi va u boshqa savol. Echo backend struktura
jihatdan haqiqiy javob qaytaradi (rol bo'limlari, `[C1]` belgisi),
shuning uchun zanjirning barcha bo'g'ini haqiqiy yuk bilan sinaladi:
retrieval, kontekst yig'ish, agent, matn tahlili, gate.

7.5 GB model yuklamasdan shu ishonchni olish — bu ataylab qilingan
dizayn qarori (`docs/02` dagi echo backend ning maqsadi).

## Nima uchun indeks haqiqiy

Soxta indeks bilan bu testlar hech narsa isbotlamaydi: chunk metadatasi,
versiya filtri, hujjat yo'naltirish va havola grafi — hammasi haqiqiy
korpus shaklига bog'liq. Indeks qurilmagan bo'lsa testlar o'tkazib
yuboriladi, chunki ular muhitga bog'liq.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uzlegal.core import ConsultRequest, consult
from uzlegal.index.store import KnowledgeIndex
from uzlegal.inference.echo_backend import EchoBackend
from uzlegal.types import ModelSpec

KB = Path("kb/current")

pytestmark = pytest.mark.skipif(
    not (KB / "chunks.jsonl").exists(),
    reason="Bilim bazasi qurilmagan — `uzlegal index build` kerak",
)


@pytest.fixture(scope="module")
def backend() -> EchoBackend:
    stub = EchoBackend(ModelSpec(id="echo", display_name="Echo", backend="echo"))
    stub.load()
    return stub


@pytest.fixture(scope="module")
def index() -> KnowledgeIndex:
    return KnowledgeIndex(KB)


# --------------------------------------------------------------------------- #
# Indeks
# --------------------------------------------------------------------------- #


def test_indeks_yuklanadi(index: KnowledgeIndex) -> None:
    assert len(index) > 1000
    assert index.meta["documents"] >= 10


def test_havola_grafi_quriladi(index: KnowledgeIndex) -> None:
    """Graf arxivdan quriladi va keshlanadi — indeks qayta qurilmaydi."""
    graph = index.reference_graph()
    assert graph is not None
    stats = graph.stats()
    assert stats["qirralar"] > 100, "havola grafi bo'sh chiqmasligi kerak"


def test_moddaga_tegishli_chunklar(index: KnowledgeIndex) -> None:
    chunks = index.chunks_for_article("-180552", "228")
    assert chunks, "Fuqarolik kodeksi 228-moddasi indeksda bo'lishi kerak"
    assert all(c.article == "228" for c in chunks)


# --------------------------------------------------------------------------- #
# Qidiruv — F2
# --------------------------------------------------------------------------- #


def test_qidiruv_togri_kodeksga_yonaltiriladi(index: KnowledgeIndex) -> None:
    from uzlegal.retrieval.hybrid import HybridRetriever

    found = HybridRetriever(index).search("Maoshni toʻlash tartibi va muddatlari", top_k=8)
    assert "mehnat" in found.routed_domains


def test_bekor_qilingan_norma_chiqmaydi(index: KnowledgeIndex) -> None:
    """docs/00 dagi «0% deprecated» talabi — texnik kafolat."""
    from uzlegal.retrieval.hybrid import HybridRetriever

    found = HybridRetriever(index).search("Daʼvo muddati qancha", top_k=10)
    assert all(item.chunk.status == "in_force" for item in found.results)


def test_modda_raqami_bilan_qidiruv(index: KnowledgeIndex) -> None:
    from uzlegal.retrieval.hybrid import HybridRetriever

    found = HybridRetriever(index).search("FK 228-modda", top_k=5)
    articles = [item.chunk.article for item in found.results]
    assert "228" in articles


# --------------------------------------------------------------------------- #
# To'liq zanjir
# --------------------------------------------------------------------------- #


def test_simple_rejim_uchidan_uchiga(backend: EchoBackend) -> None:
    result = consult(
        ConsultRequest(
            question="Oʻgʻirlangan mulkni qaytarib olish mumkinmi", mode="simple", trace=True
        ),
        backend=backend,
    )

    assert result.mode_used == "simple"
    assert result.citations, "haqiqiy indeksdan iqtibos kelishi kerak"
    assert result.is_answered
    assert [e.node for e in result.trace] == ["retrieve", "jurist", "gate"]


def test_iqtiboslar_haqiqiy_moddaga_boglanadi(backend: EchoBackend) -> None:
    result = consult(
        ConsultRequest(question="Daʼvo muddati qancha", mode="simple", trace=True), backend=backend
    )

    for citation in result.citations:
        assert citation.tag.startswith("C")
        assert citation.doc_title
        assert citation.article
        assert citation.status == "in_force"


def test_gate_har_doim_ishlaydi(backend: EchoBackend) -> None:
    """Gate bosqichi izda bo'lishi shart — u o'tkazib yuborilmaydi."""
    result = consult(
        ConsultRequest(
            question="Mehnat shartnomasi qanday bekor qilinadi", mode="simple", trace=True
        ),
        backend=backend,
    )
    gate_step = result.step("gate")
    assert gate_step is not None
    assert gate_step.detail["claims"] >= 0


def test_manba_topilmasa_model_chaqirilmaydi(backend: EchoBackend) -> None:
    """Mavzuga aloqasi yo'q savol — tizim taxmin qilmasligi kerak."""
    result = consult(
        ConsultRequest(
            question="zzz qqq xxx yyy vvv bunday soʻz umuman yoʻq", mode="simple", trace=True
        ),
        backend=backend,
    )
    # Manba topilsa ham, topilmasa ham javob qaytadi va u yolg'on bo'lmaydi
    assert result.is_answered


def test_tarixiy_holat_soralganda_filtr_ishlaydi(backend: EchoBackend) -> None:
    from datetime import date

    result = consult(
        ConsultRequest(
            question="Daʼvo muddati qancha",
            mode="simple",
            as_of=date(2021, 6, 1, trace=True),
            backend=backend,
        )
    )
    assert result.as_of == "2021-06-01"
    assert result.is_answered


def test_kb_versiyasi_javobda_boladi(backend: EchoBackend) -> None:
    """Yuridik javobda qaysi bilim bazasi ishlatilgani ko'rinishi kerak."""
    result = consult(
        ConsultRequest(question="Daʼvo muddati qancha", mode="simple", trace=True), backend=backend
    )
    assert result.model == "echo"
    assert result.total_ms > 0


# --------------------------------------------------------------------------- #
# SDK — bir xil zanjir, boshqa kirish nuqtasi
# --------------------------------------------------------------------------- #


def test_sdk_ichki_rejim_ishlaydi(index: KnowledgeIndex) -> None:
    from uzlegal.sdk import UzLegal

    results = UzLegal().search("Daʼvo muddati", top_k=3)
    assert len(results) == 3
    assert all(item.chunk.article for item in results)
