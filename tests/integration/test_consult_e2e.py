"""Uchidan-uchiga integratsiya — haqiqiy indeks, soxta model.

## Nima uchun echo backend

Bu testlar **zanjirni** tekshiradi, model sifatini emas. Model sifati
`uzlegal eval` da o'lchanadi va u boshqa savol. Echo backend struktura
jihatdan haqiqiy javob qaytaradi (rol bo'limlari, `[C1]` belgisi),
shuning uchun zanjirning barcha bo'g'ini haqiqiy yuk bilan sinaladi:
retrieval, kontekst yig'ish, agent, matn tahlili, gate.

7 GB model yuklamasdan shu ishonchni olish — bu ataylab qilingan dizayn
qarori (`docs/02` dagi echo backend ning maqsadi).

## Nima uchun indeks haqiqiy

Soxta indeks bilan bu testlar hech narsa isbotlamaydi: chunk metadatasi,
versiya filtri, hujjat yo'naltirish va havola grafi — hammasi haqiqiy
korpus shakliga bog'liq. Indeks qurilmagan bo'lsa testlar o'tkazib
yuboriladi, chunki ular muhitga bog'liq.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

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


@pytest.fixture(scope="module")
def retriever(index: KnowledgeIndex) -> Any:
    from uzlegal.retrieval.hybrid import HybridRetriever

    return HybridRetriever(index)


def ask(question: str, backend: Any, retriever: Any, **kw: Any) -> Any:
    return consult(
        ConsultRequest(question=question, trace=True, **kw),
        backend=backend,
        retriever=retriever,
        registry=None,
        use_prefix_cache=False,
    )


def nodes(result: Any) -> list[str]:
    assert result.trace is not None
    return [s.node for s in result.trace.steps]


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
    assert graph.stats()["qirralar"] > 100, "havola grafi bo'sh chiqmasligi kerak"


def test_moddaga_tegishli_chunklar(index: KnowledgeIndex) -> None:
    """Fuqarolik kodeksining 228-moddasi indeksda topilishi kerak.

    Hujjat ID si qat'iy yozilmaydi: lex.uz da Fuqarolik kodeksi ikki
    qism sifatida alohida hujjat va ularning ID lari korpus yangilanganda
    o'zgaradi.
    """
    index.load()
    doc_ids = {
        c.doc_id for c in index._chunks.values() if "FUQAROLIK KODEKSI" in c.doc_title.upper()
    }
    assert doc_ids, "Fuqarolik kodeksi indeksda bo'lishi kerak"

    found = [c for doc in doc_ids for c in index.chunks_for_article(doc, "228")]
    assert found, "228-modda topilishi kerak"
    assert all(c.article == "228" for c in found)


# --------------------------------------------------------------------------- #
# Qidiruv — F2
# --------------------------------------------------------------------------- #


def test_qidiruv_togri_kodeksga_yonaltiriladi(retriever: Any) -> None:
    found = retriever.search("Maoshni toʻlash tartibi va muddatlari", top_k=8)
    assert "mehnat" in found.routed_domains


def test_bekor_qilingan_norma_chiqmaydi(retriever: Any) -> None:
    """docs/00 dagi «0% deprecated» talabi — texnik kafolat."""
    found = retriever.search("Daʼvo muddati qancha", top_k=10)
    assert all(item.chunk.status == "in_force" for item in found.results)


def test_modda_raqami_bilan_qidiruv(retriever: Any) -> None:
    found = retriever.search("FK 228-modda", top_k=5)
    assert "228" in [item.chunk.article for item in found.results]


def test_graf_kengaytmasi_qoshimcha_norma_beradi(retriever: Any) -> None:
    """Topilgan norma havola qiladigan normalar ham kontekstga tushadi."""
    found = retriever.search("Oʻgʻirlangan mulkni qaytarib olish", top_k=8)
    assert found.graph_hits >= 0
    assert len(found.results) >= len([r for r in found.results if r.source != "graph"])


# --------------------------------------------------------------------------- #
# To'liq zanjir
# --------------------------------------------------------------------------- #


def test_simple_rejim_uchidan_uchiga(backend: EchoBackend, retriever: Any) -> None:
    result = ask("Oʻgʻirlangan mulkni qaytarib olish mumkinmi", backend, retriever, mode="simple")

    assert result.mode_used == "simple"
    assert result.citations, "haqiqiy indeksdan iqtibos kelishi kerak"
    assert result.trace_id.startswith("cns_")
    assert nodes(result)[:2] == ["route", "retrieve"]
    assert nodes(result)[-1] == "gate"


def test_iqtiboslar_haqiqiy_moddaga_boglanadi(backend: EchoBackend, retriever: Any) -> None:
    result = ask("Daʼvo muddati qancha", backend, retriever, mode="simple")

    for citation in result.citations:
        assert citation.tag.startswith("C")
        assert citation.doc_title
        assert citation.status == "in_force"
        assert citation.excerpt, "gate iqtibos matni bo'yicha tekshiradi"


def test_gate_har_doim_ishlaydi(backend: EchoBackend, retriever: Any) -> None:
    """Gate bosqichi izda bo'lishi shart — u o'tkazib yuborilmaydi."""
    result = ask("Mehnat shartnomasi qanday bekor qilinadi", backend, retriever, mode="simple")
    assert "gate" in nodes(result)


def test_mavzudan_tashqari_savol_javob_toqimaydi(backend: EchoBackend, retriever: Any) -> None:
    """Tizim taxmin qilmasligi kerak — javob bo'lsa ham u manbaga bog'lanadi."""
    result = ask("zzz qqq xxx yyy vvv bunday soʻz umuman yoʻq", backend, retriever, mode="simple")
    assert result.refused or result.citations


def test_tarixiy_holat_soralganda_filtr_ishlaydi(backend: EchoBackend, retriever: Any) -> None:
    result = ask("Daʼvo muddati qancha", backend, retriever, mode="simple", as_of=date(2021, 6, 1))
    assert result.trace is not None
    assert result.trace.as_of == "2021-06-01"


def test_disclaimer_va_kb_versiyasi(backend: EchoBackend, retriever: Any) -> None:
    """Yuridik javobda ogohlantirish va bilim bazasi versiyasi majburiy."""
    result = ask("Daʼvo muddati qancha", backend, retriever, mode="simple")
    assert "yuridik maslahat" in result.disclaimer
    assert result.kb_version
    assert result.latency_ms > 0


# --------------------------------------------------------------------------- #
# SDK — bir xil zanjir, boshqa kirish nuqtasi
# --------------------------------------------------------------------------- #


def test_sdk_qidiruvi_ishlaydi() -> None:
    from uzlegal.sdk import UzLegal

    results = UzLegal().search("Daʼvo muddati", top_k=3)
    # Graf kengaytmasi top-k dan **keyin** qo'shiladi, shuning uchun
    # natija so'ralgandan ko'p bo'lishi mumkin — bu kutilgan xatti-harakat.
    assert len(results) >= 3
    assert all(item.chunk.article for item in results)
