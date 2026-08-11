"""`consult()` shartnomasi testlari — `uzlegal.core`.

Haqiqiy model ham, indeks ham kerak emas: `retriever=` va `backend=`
almashtiriladi. Bu shunchaki test qulayligi emas — agar zanjirni soxta
qismlar bilan yig'ib bo'lmasa, demak bog'liqliklar noto'g'ri
chegaralangan.

Bu yerda tekshiriladigan narsa **shartnoma**, oqim emas: oqim
`test_orchestrator.py` da. Shartnoma buzilsa REST, bot, MCP va SDK
mijozlari bir vaqtda buziladi, shuning uchun u alohida qo'riqlanadi.
"""

from __future__ import annotations

from typing import Any

import pytest

from uzlegal.core import DISCLAIMER, ConsultRequest, ConsultResult, consult
from uzlegal.index.chunker import Chunk
from uzlegal.index.store import ScoredChunk
from uzlegal.types import GenerationParams, ModelSpec

# --------------------------------------------------------------------------- #
# Soxta qismlar
# --------------------------------------------------------------------------- #


def chunk(article: str = "228", content: str = "Mulkdor talab qilib olishga haqli") -> Chunk:
    return Chunk(
        chunk_id=f"fk:{article}",
        doc_id="fk",
        doc_title="Fuqarolik kodeksi",
        doc_type="kodeks",
        lang="uz",
        article=article,
        heading=f"[Fuqarolik kodeksi > {article}-modda]",
        content=content,
        token_count=20,
        source_url="https://lex.uz/docs/fk",
    )


class FakeRetriever:
    """Berilgan chunklarni qaytaradi. Qidiruv mantiqi bu yerda sinalmaydi."""

    def __init__(self, chunks: list[Chunk] | None = None, error: Exception | None = None) -> None:
        self.chunks = chunks if chunks is not None else [chunk()]
        self.error = error
        self.index = type("Idx", (), {"meta": {"kb_version": "v2026.08.01"}})()

    def search(self, query: str, **kwargs: Any) -> Any:
        if self.error is not None:
            raise self.error
        return type(
            "Result",
            (),
            {
                "results": [ScoredChunk(chunk=c, score=1.0) for c in self.chunks],
                "query_kind": type("K", (), {"value": "analytical"})(),
                "routed_domains": ["fuqarolik"],
                "graph_hits": 0,
                "exact_hits": 0,
                "dropped_by_version": 0,
                "top_score": 0.9,
                "latency_ms": 12,
            },
        )()


class ScriptedBackend:
    """Har chaqiruvda oldindan yozilgan javobni qaytaradi."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[str] = []
        self.spec = ModelSpec(id="fake", display_name="Fake", backend="echo")

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.calls.append(prompt)
        return self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]

    def stream(self, prompt: str, params: GenerationParams) -> Any:
        yield self.generate(prompt, params)

    def make_prefix_cache(self, prefix: str) -> None:
        return None


class FakeRegistry:
    active_id = "fake"

    def restore_state(self) -> str:
        return "fake"


FRAME_JSON = (
    '{"facts": ["Mulk oʻgʻirlangan"], "legal_questions": ["Talab qilib olish mumkinmi"], '
    '"applicable_norms": ["C1"], "unknowns": []}'
)

VERDICT_JSON = (
    '{"conclusion": "Mulkdor talab qilib olishga haqli [C1]", '
    '"reasoning": ["Norma shuni belgilaydi [C1]"], "confidence": 0.8, '
    '"citation_tags": ["C1"], "caveats": []}'
)


def run(
    question: str = "Oʻgʻirlangan mulkni qaytarib olsam boʻladimi",
    *,
    mode: str = "simple",
    chunks: list[Chunk] | None = None,
    replies: tuple[str, ...] = (FRAME_JSON,),
    **kwargs: Any,
) -> ConsultResult:
    return consult(
        ConsultRequest(question=question, mode=mode, trace=True),  # type: ignore[arg-type]
        retriever=FakeRetriever(chunks),
        backend=ScriptedBackend(*replies),
        registry=FakeRegistry(),
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Kirish tekshiruvlari
# --------------------------------------------------------------------------- #


def test_juda_qisqa_savol_rad_etiladi() -> None:
    with pytest.raises(ValueError):
        ConsultRequest(question="a")


def test_notogri_rejim_rad_etiladi() -> None:
    with pytest.raises(ValueError):
        ConsultRequest(question="Daʼvo muddati qancha", mode="turbo")  # type: ignore[arg-type]


def test_rejim_ochiq_berilsa_ishlatiladi() -> None:
    assert run(mode="simple").mode_used == "simple"


def test_auto_rejimda_router_hal_qiladi() -> None:
    result = run("MMT stavkasi qancha", mode="auto")
    assert result.mode_used in ("simple", "standard", "complex")


# --------------------------------------------------------------------------- #
# Shartnoma — mijozlar tayanadigan maydonlar
# --------------------------------------------------------------------------- #


def test_disclaimer_har_doim_boladi() -> None:
    """Uni ixtiyoriy qilish integratsiya qiluvchiga tashlab ketish imkonini berardi."""
    assert run().disclaimer == DISCLAIMER


def test_trace_id_har_doim_boladi() -> None:
    result = run()
    assert result.trace_id.startswith("cns_")


def test_iz_faqat_soralganda_qaytadi() -> None:
    with_trace = run()
    assert with_trace.trace is not None

    without = consult(
        ConsultRequest(question="Daʼvo muddati qancha", mode="simple"),
        retriever=FakeRetriever(),
        backend=ScriptedBackend(FRAME_JSON),
        registry=FakeRegistry(),
    )
    assert without.trace is None


def test_iqtiboslar_belgilanadi_va_manbaga_boglanadi() -> None:
    result = run(chunks=[chunk("228"), chunk("229")])
    assert result.citations
    assert result.citations[0].tag == "C1"
    assert all(c.doc_title == "Fuqarolik kodeksi" for c in result.citations)


def test_kb_va_model_versiyasi_qaytadi() -> None:
    result = run()
    assert result.model_version == "fake"


# --------------------------------------------------------------------------- #
# Buzilgan holatlar — tizim yolg'on aytmasligi kerak
# --------------------------------------------------------------------------- #


def test_manba_topilmasa_model_chaqirilmaydi() -> None:
    """Bo'sh kontekst modelni xotiradan javob yozishga undaydi."""
    backend = ScriptedBackend(FRAME_JSON)
    result = consult(
        ConsultRequest(question="Daʼvo muddati qancha", mode="simple"),
        retriever=FakeRetriever([]),
        backend=backend,
        registry=FakeRegistry(),
    )
    assert backend.calls == [], "manba yo'q — model umuman chaqirilmasligi kerak"
    assert result.refused
    assert result.confidence == 0.0


def test_agent_yiqilsa_quvur_toxtamaydi() -> None:
    """Jurist sxemani buzsa ham javob qaytishi kerak (docs/06 § 8)."""
    result = run(replies=("bemaʼni javob",))
    assert result.trace is not None
    assert [s.node for s in result.trace.steps][-1] == "gate"


def test_retrieval_yiqilsa_rad_etiladi_lekin_yiqilmaydi() -> None:
    """Indeks o'qilmasa tizim «manba topilmadi» deydi, 500 bermaydi.

    Muhimi — u **javob to'qimaydi**: `refused` va iqtiboslar bo'sh.
    """
    backend = ScriptedBackend(FRAME_JSON)
    result = consult(
        ConsultRequest(question="Daʼvo muddati qancha", mode="simple"),
        retriever=FakeRetriever(error=RuntimeError("indeks yoʻq")),
        backend=backend,
        registry=FakeRegistry(),
    )
    assert result.refused
    assert result.citations == []
    assert backend.calls == []


# --------------------------------------------------------------------------- #
# Gate ta'siri natijaga
# --------------------------------------------------------------------------- #


def test_gate_iqtibossiz_davoni_javobdan_chiqaradi() -> None:
    """Uchidan-uchiga: model iqtibossiz huquqiy daʼvo yozsa u yo'qoladi."""
    verdict = (
        '{"conclusion": "Mulkdor 228-moddaga koʻra talab qilishga haqli", '
        '"reasoning": ["Qonun shuni belgilaydi"], "confidence": 0.9, "citation_tags": []}'
    )
    result = run(mode="standard", replies=(FRAME_JSON, verdict))
    assert "228-moddaga koʻra talab qilishga haqli" not in result.answer


def test_gate_ochirgani_caveats_da_korinadi() -> None:
    verdict = (
        '{"conclusion": "Jarima 10 barobar oshiriladi", '
        '"reasoning": ["Sud xarajatlari yutqazganga yuklanadi"], '
        '"confidence": 0.9, "citation_tags": []}'
    )
    result = run(mode="standard", replies=(FRAME_JSON, verdict))
    assert any("chiqarildi" in c or "topilmadi" in c for c in result.caveats)


def test_ishonch_gate_qisqartirganda_pasayadi() -> None:
    """Sudya o'zi ko'rmagan (qisqartirilgan) javobga baho bergan."""
    partial = (
        '{"conclusion": "Mulkdor talab qilib olishga haqli [C1]", '
        '"reasoning": ["Jarima 10 barobar oshiriladi"], '
        '"confidence": 1.0, "citation_tags": ["C1"]}'
    )
    result = run(mode="standard", replies=(FRAME_JSON, partial))
    assert 0.0 < result.confidence < 1.0
