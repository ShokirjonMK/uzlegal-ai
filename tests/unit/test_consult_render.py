"""Maslahat chiqishi va reranker — E6 (qamrov qarzi).

Bu ikki modul qamrovi **0%** edi: `cli/consult.py` va
`retrieval/reranker.py`. Ikkalasi ham asosiy maslahat yo'lida turadi,
ya'ni ular buzilsa foydalanuvchi buni birinchi bo'lib ko'radi.

Testlarning maqsadi — chiroyli chiqishni emas, **shartnomani**
qo'riqlash: nima ko'rsatiladi, nima ko'rsatilmaydi va ogohlantirish
yo'qolib qolmaydimi.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from uzlegal.cli.consult import _markdown, _render
from uzlegal.core import ConsultResult
from uzlegal.index.chunker import Chunk
from uzlegal.index.store import ScoredChunk
from uzlegal.retrieval.reranker import Reranker
from uzlegal.types import Citation


def _citation(tag: str = "C1", article: str = "228") -> Citation:
    return Citation(
        tag=tag,
        doc_id="-111189",
        doc_title="Fuqarolik kodeksi",
        article=article,
        url="https://lex.uz/docs/-111189#228",
    )


def _result(**kwargs: Any) -> ConsultResult:
    base: dict[str, Any] = {
        "trace_id": "tr-001",
        "answer": "Mulkdor talab qilishga haqli [C1].",
        "citations": [_citation()],
        "confidence": 0.82,
    }
    base.update(kwargs)
    return ConsultResult(**base)


# --------------------------------------------------------------------------- #
# Markdown chiqishi
# --------------------------------------------------------------------------- #


def test_markdown_javob_va_manbani_beradi() -> None:
    out = _markdown(_result())
    assert "Mulkdor talab qilishga haqli" in out
    assert "## Manbalar" in out
    assert "Fuqarolik kodeksi, 228-modda" in out
    assert "https://lex.uz/docs/-111189#228" in out


def test_markdown_ogohlantirish_yoqolmaydi() -> None:
    """Ogohlantirish javobning bir qismi — u tushib qolmasligi kerak."""
    out = _markdown(_result(caveats=["Bekor qilingan norma bo'lishi mumkin"]))
    assert "## Ogohlantirishlar" in out
    assert "Bekor qilingan norma" in out


def test_markdown_disclaimer_har_doim_bor() -> None:
    """Yuridik mas'uliyat izohi hech qanday holatda tushmaydi."""
    for result in (_result(), _result(citations=[], caveats=[])):
        assert result.disclaimer in _markdown(result)


def test_markdown_manbasiz_javobda_bolim_yoq() -> None:
    """Bo'sh «Manbalar» sarlavhasi manba bor degan taassurot qoldiradi."""
    out = _markdown(_result(citations=[]))
    assert "## Manbalar" not in out


def test_markdown_moddasiz_iqtibos_yiqilmaydi() -> None:
    """`article` bo'sh satr — modelda u majburiy maydon, `None` emas.

    Hujjat darajasidagi iqtibos (masalan butun nizom) aynan shunday
    keladi va u «-modda» qo'shimchasisiz ko'rsatilishi kerak.
    """
    out = _markdown(_result(citations=[_citation(article="")]))
    assert "Fuqarolik kodeksi" in out
    assert "-modda" not in out


# --------------------------------------------------------------------------- #
# Konsol chiqishi
# --------------------------------------------------------------------------- #


def test_render_asosiy_qismlarni_chiqaradi(capsys: pytest.CaptureFixture[str]) -> None:
    _render(_result(caveats=["Ehtiyot bo'ling"]), show_trace=False)
    out = capsys.readouterr().out
    assert "Mulkdor talab qilishga haqli" in out
    assert "ISHONCH" in out
    assert "Ehtiyot bo'ling" in out


def test_render_izsiz_chaqiruv_zanjirni_chiqarmaydi(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _render(_result(), show_trace=False)
    assert "Asoslash zanjiri" not in capsys.readouterr().out


def test_render_bosh_natijada_yiqilmaydi(capsys: pytest.CaptureFixture[str]) -> None:
    """Rad javobda iqtibos ham, ogohlantirish ham bo'lmasligi mumkin."""
    _render(_result(answer="Javob shakllantirilmadi.", citations=[], confidence=0.0), False)
    assert "Javob shakllantirilmadi" in capsys.readouterr().out


def test_render_notogri_tur_ushlanadi() -> None:
    with pytest.raises(AssertionError):
        _render({"answer": "yo'q"}, show_trace=False)


def test_as_of_natijada_saqlanadi() -> None:
    """Vaqt mashinasi — javob qaysi sanaga tegishli ekani yo'qolmasin."""
    result = _result(as_of=date(2020, 1, 1))
    assert result.as_of == date(2020, 1, 1)


# --------------------------------------------------------------------------- #
# Reranker
# --------------------------------------------------------------------------- #


class SoxtaModel:
    """Cross-encoder o'rniga — ballarni oldindan beradi.

    Haqiqiy model 500 MB va GPU talab qiladi. Test tekshiradigan narsa
    esa model emas, **tartiblash mantig'i**.
    """

    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs: list[tuple[str, str]], **_: Any) -> list[float]:
        self.calls.append(pairs)
        return self.scores[: len(pairs)]


def _scored(chunk_id: str, score: float, content: str = "matn") -> ScoredChunk:
    return ScoredChunk(
        chunk=Chunk(
            chunk_id=chunk_id,
            doc_id="d-1",
            doc_title="Fuqarolik kodeksi",
            doc_type="kodeks",
            lang="uz",
            article=chunk_id.split(":")[-1],
            heading=f"[Fuqarolik kodeksi > {chunk_id}]",
            content=content,
        ),
        score=score,
        source="hybrid",
    )


def test_reranker_bosh_royxatda_model_yuklamaydi() -> None:
    """Bo'sh natijada 500 MB model yuklash — sof isrof."""
    reranker = Reranker()
    assert reranker.rerank("savol", []) == []
    assert reranker._model is None


def test_reranker_qayta_tartiblaydi() -> None:
    reranker = Reranker()
    reranker._model = SoxtaModel([0.1, 0.9, 0.5])
    items = [_scored("d-1:1", 0.9), _scored("d-1:2", 0.5), _scored("d-1:3", 0.2)]

    out = reranker.rerank("savol", items)

    assert [i.chunk.chunk_id for i in out] == ["d-1:2", "d-1:3", "d-1:1"]
    assert [round(i.score, 2) for i in out] == [0.9, 0.5, 0.1]
    assert all(i.source == "rerank" for i in out)


def test_reranker_top_k_kesadi() -> None:
    reranker = Reranker()
    reranker._model = SoxtaModel([0.1, 0.9, 0.5])
    items = [_scored(f"d-1:{i}", 0.5) for i in (1, 2, 3)]
    assert len(reranker.rerank("savol", items, top_k=2)) == 2


def test_reranker_sarlavha_bilan_baholaydi() -> None:
    """Modda raqami va hujjat nomi ham relevantlikka ta'sir qiladi."""
    model = SoxtaModel([0.5])
    reranker = Reranker()
    reranker._model = model

    reranker.rerank("228-modda", [_scored("d-1:228", 0.5, content="Mulkdor…")])

    _, matn = model.calls[0][0]
    assert "Fuqarolik kodeksi" in matn, "sarlavha modelga berilmagan"
    assert "Mulkdor" in matn


def test_reranker_unload_modelni_bosatadi() -> None:
    reranker = Reranker()
    reranker._model = SoxtaModel([0.5])
    reranker.unload()
    assert reranker._model is None


def test_reranker_qurilma_muhitdan_majburlanadi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Embedder bilan bir xil qurilmada ishlashi shart — 8 GB VRAM cheklovi."""
    monkeypatch.setenv("UZLEGAL_EMBED_DEVICE", "cpu")
    assert Reranker().device == "cpu"
