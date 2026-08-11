"""`consult()` zanjiri testlari.

Haqiqiy model ham, indeks ham kerak emas: `retriever=` va `backend=`
almashtiriladi. Bu shunchaki test qulayligi emas — agar zanjirni soxta
qismlar bilan yig'ib bo'lmasa, demak bog'liqliklar noto'g'ri
chegaralangan.
"""

from __future__ import annotations

from typing import Any

import pytest

from uzlegal.core import NO_MODEL, NO_SOURCES, consult
from uzlegal.index.chunker import Chunk
from uzlegal.index.store import ScoredChunk
from uzlegal.types import ConsultMode, GenerationParams, ModelSpec

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
                "top_score": 0.9,
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


FRAME_JSON = (
    '{"facts": ["Mulk oʻgʻirlangan"], "legal_questions": ["Talab qilib olish mumkinmi"], '
    '"applicable_norms": ["C1"], "unknowns": []}'
)


# --------------------------------------------------------------------------- #
# Kirish tekshiruvlari
# --------------------------------------------------------------------------- #


def test_bosh_savol_rad_etiladi() -> None:
    with pytest.raises(ValueError, match="bo'sh"):
        consult("   ")


def test_notogri_rejim_aniq_xato_beradi() -> None:
    with pytest.raises(ValueError, match="Noma'lum rejim"):
        consult("savol", mode="turbo", retriever=FakeRetriever())


def test_rejim_ochiq_berilsa_router_ishlamaydi() -> None:
    result = consult("MMT stavkasi qancha", mode="complex", retriever=FakeRetriever([]))
    assert result.mode is ConsultMode.COMPLEX


def test_rejim_berilmasa_router_aniqlaydi() -> None:
    result = consult("MMT stavkasi qancha", retriever=FakeRetriever([]))
    assert result.mode is ConsultMode.SIMPLE


# --------------------------------------------------------------------------- #
# Buzilgan holatlar — tizim yolg'on aytmasligi kerak
# --------------------------------------------------------------------------- #


def test_manba_topilmasa_model_chaqirilmaydi() -> None:
    """Bo'sh kontekst modelni xotiradan javob yozishga undaydi."""
    backend = ScriptedBackend(FRAME_JSON)
    result = consult("savol", retriever=FakeRetriever([]), backend=backend)

    assert result.answer == NO_SOURCES
    assert backend.calls == [], "manba yo'q — model umuman chaqirilmasligi kerak"


def test_retrieval_yiqilsa_javob_qaytadi() -> None:
    result = consult("savol", retriever=FakeRetriever(error=RuntimeError("indeks yoʻq")))
    assert result.answer == NO_SOURCES
    assert any("indeks" in w for w in result.warnings)
    assert result.trace[0].error is not None


def test_model_yoq_bolsa_manbalar_baribir_qaytadi() -> None:
    class NoModel:
        backend = property(lambda self: (_ for _ in ()).throw(RuntimeError("model yoʻq")))

        def restore_state(self) -> None:
            return None

    result = consult("savol", retriever=FakeRetriever(), registry=NoModel())
    assert result.answer == NO_MODEL
    assert len(result.citations) == 1, "model yo'q bo'lsa ham topilgan normalar ko'rsatiladi"


def test_agent_yiqilsa_quvur_toxtamaydi() -> None:
    """Jurist sxemani buzsa ham javob qaytishi kerak (docs/06 § 8)."""
    result = consult(
        "savol", mode="simple", retriever=FakeRetriever(), backend=ScriptedBackend("bemaʼni javob")
    )
    assert result.trace[-1].node == "gate"
    assert result.is_answered


# --------------------------------------------------------------------------- #
# Muvaffaqiyatli zanjir
# --------------------------------------------------------------------------- #


def test_simple_rejimda_faqat_jurist_ishlaydi() -> None:
    backend = ScriptedBackend(FRAME_JSON)
    result = consult("savol", mode="simple", retriever=FakeRetriever(), backend=backend)

    nodes = [e.node for e in result.trace]
    assert nodes == ["retrieve", "jurist", "gate"]
    assert "debate_r1" not in nodes


def test_iqtiboslar_belgilanadi_va_manbaga_boglanadi() -> None:
    result = consult(
        "savol",
        mode="simple",
        retriever=FakeRetriever([chunk("228"), chunk("229")]),
        backend=ScriptedBackend(FRAME_JSON),
    )
    tags = [c.tag for c in result.citations]
    assert tags[0] == "C1"
    assert all(c.doc_title == "Fuqarolik kodeksi" for c in result.citations)


def test_iz_har_qadamni_yozadi() -> None:
    result = consult(
        "savol", mode="simple", retriever=FakeRetriever(), backend=ScriptedBackend(FRAME_JSON)
    )
    retrieve = result.step("retrieve")
    assert retrieve is not None
    assert retrieve.detail["chunks"] == 1
    assert result.total_ms >= 0


def test_kb_versiyasi_natijaga_tushadi() -> None:
    result = consult(
        "savol", mode="simple", retriever=FakeRetriever(), backend=ScriptedBackend(FRAME_JSON)
    )
    assert result.kb_version == "v2026.08.01"
    assert result.model == "fake"


def test_kuzatuvchi_hodisalarni_oladi() -> None:
    """SSE oqimi shu mexanizm ustida quriladi."""
    seen: list[str] = []
    consult(
        "savol",
        mode="simple",
        retriever=FakeRetriever(),
        backend=ScriptedBackend(FRAME_JSON),
        observe=lambda e: seen.append(e.node),
    )
    assert seen == ["retrieve", "jurist", "gate"]


def test_gate_iqtibossiz_davoni_javobdan_chiqaradi() -> None:
    """Uchidan-uchiga: model iqtibossiz huquqiy daʼvo yozsa u yo'qoladi."""
    verdict = (
        '{"conclusion": "Mulkdor 228-moddaga koʻra talab qilishga haqli", '
        '"reasoning": ["Qonun shuni belgilaydi"], "confidence": 0.8, "citation_tags": []}'
    )
    result = consult(
        "savol", mode="standard", retriever=FakeRetriever(), backend=ScriptedBackend(verdict)
    )
    assert result.gate.dropped, "iqtibossiz huquqiy daʼvo o'chirilishi kerak"
    assert "228-moddaga koʻra talab qilishga haqli" not in result.answer


# --------------------------------------------------------------------------- #
# Mavjud bo'lmagan modda — taxmin qilinmaydi
# --------------------------------------------------------------------------- #


class ArticleLookupRetriever(FakeRetriever):
    """Modda raqami bo'yicha so'rov, lekin aniq moslik topilmagan."""

    def __init__(self, exact_hits: int = 0) -> None:
        super().__init__()
        self.exact_hits = exact_hits

    def search(self, query: str, **kwargs: Any) -> Any:
        from uzlegal.retrieval.hybrid import QueryKind

        result = super().search(query, **kwargs)
        result.query_kind = QueryKind.ARTICLE_LOOKUP
        result.exact_hits = self.exact_hits
        return result


def test_mavjud_bolmagan_modda_ochiq_aytiladi() -> None:
    """«FK 9999-modda» — o'xshash moddani ko'rsatish xato javob bo'lardi."""
    backend = ScriptedBackend(FRAME_JSON)
    result = consult(
        "Fuqarolik kodeksining 9999-moddasi nima haqida",
        retriever=ArticleLookupRetriever(exact_hits=0),
        backend=backend,
    )

    assert "9999-modda" in result.answer
    assert "topilmadi" in result.answer
    assert backend.calls == [], "modda yo'q — model chaqirilmasligi kerak"
    assert result.citations, "yaqin normalar baribir ko'rsatiladi"


def test_mavjud_modda_odatdagidek_ishlanadi() -> None:
    result = consult(
        "FK 228-modda",
        mode="simple",
        retriever=ArticleLookupRetriever(exact_hits=2),
        backend=ScriptedBackend(FRAME_JSON),
    )
    assert "topilmadi" not in result.answer
    assert result.step("jurist") is not None
