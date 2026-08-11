"""Orkestratsiya testlari — router, debate protokoli va to'liq oqim.

Hammasi modelsiz: `echo` backend yoki rolga qarab javob qaytaradigan stub
ishlatiladi. Bu Faza 5 ning talabi — CI da GPU yo'q (docs/09 § CI).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from conftest import RoleBackend, ScriptedBackend, StubRetriever  # tests/unit sys.path da

from uzlegal.core import DISCLAIMER, ConsultRequest, ConsultResult, consult
from uzlegal.index.chunker import Chunk
from uzlegal.orchestrator.debate import (
    DISAGREEMENT_THRESHOLD,
    citation_overlap,
    conclusion_distance,
    disagreement,
    needs_round_two,
)
from uzlegal.orchestrator.gate import REFUSAL
from uzlegal.orchestrator.graph import NO_SYNTHESIS
from uzlegal.orchestrator.router import ROLES_BY_MODE, Mode, route
from uzlegal.types import Argument, Position

REGISTRY = SimpleNamespace(active_id="echo", set_adapter=lambda role: None)


def ask(
    question: str,
    chunks: list[Chunk],
    backend: object,
    **kw: object,
) -> ConsultResult:
    request = ConsultRequest(question=question, trace=True, **kw)  # type: ignore[arg-type]
    return consult(
        request,
        backend=backend,
        retriever=StubRetriever(chunks),
        registry=REGISTRY,
    )


def nodes(result: ConsultResult) -> list[str]:
    assert result.trace is not None
    return [s.node for s in result.trace.steps]


def position(role: str, stance: str, tags: list[str], confidence: float) -> Position:
    return Position(
        role=role,
        stance=stance,
        arguments=[Argument(claim="dalil", citations=tags)],
        weaknesses=["zaif joy"],
        confidence=confidence,
    )


# --------------------------------------------------------------------------- #
# Router — docs/01 § 3
# --------------------------------------------------------------------------- #


def test_faktik_sorov_simple_boladi() -> None:
    assert route("MMT stavkasi qancha?").mode is Mode.SIMPLE


def test_tahliliy_savol_standard_boladi() -> None:
    assert route("Bu shartnoma haqiqiymi?").mode is Mode.STANDARD


def test_nizoli_savol_complex_boladi() -> None:
    decision = route("Mijozim sotib olgan uyni haqiqiy mulkdor talab qilmoqda. Kim haq?")
    assert decision.mode is Mode.COMPLEX
    assert decision.signals


def test_mijoz_pozitsiyasi_debate_talab_qiladi() -> None:
    decision = route("Ishdan bo'shatish tartibi", has_client_position=True)
    assert decision.mode is Mode.COMPLEX


def test_foydalanuvchi_tanlovi_ustun() -> None:
    decision = route("MMT stavkasi qancha?", forced="complex")
    assert decision.mode is Mode.COMPLEX
    assert decision.forced


def test_noaniq_savol_yuqoriroq_darajaga_tushadi() -> None:
    """Ortiqcha tahlil qilish yetarli tahlil qilmaslikdan arzonroq."""
    assert route("Ijara haqida").mode is Mode.STANDARD


def test_har_rejim_uchun_rollar_belgilangan() -> None:
    assert ROLES_BY_MODE[Mode.SIMPLE] == ["jurist"]
    assert "advocate" not in ROLES_BY_MODE[Mode.STANDARD]
    assert len(ROLES_BY_MODE[Mode.COMPLEX]) == 5


# --------------------------------------------------------------------------- #
# Kelishmovchilik balli — docs/06 § 3
# --------------------------------------------------------------------------- #


def test_bir_xil_pozitsiyalar_kelishmovchiligi_past() -> None:
    a = position("advocate", "Shartnoma haqiqiy hisoblanadi", ["C1"], 0.8)
    p = position("prosecutor", "Shartnoma haqiqiy hisoblanadi", ["C1"], 0.75)
    assert disagreement(a, p) < DISAGREEMENT_THRESHOLD


def test_qarama_qarshi_pozitsiyalar_raund_2_talab_qiladi() -> None:
    a = position("advocate", "Mijoz vijdonli oluvchi va mulkni saqlaydi", ["C1"], 0.85)
    p = position("prosecutor", "Bitim ishonchsiz, mulk qaytarilishi kerak", ["C4"], 0.35)
    assert disagreement(a, p) > DISAGREEMENT_THRESHOLD
    assert needs_round_two({"advocate": a, "prosecutor": p})


def test_iqtibos_qoplamasi_jaccard() -> None:
    a = position("advocate", "x", ["C1", "C2"], 0.5)
    p = position("prosecutor", "x", ["C2", "C3"], 0.5)
    assert citation_overlap(a, p) == pytest.approx(1 / 3)


def test_ikkalasi_iqtibossiz_bolsa_qoplama_tola() -> None:
    """Bo'sh asos farqni ko'rsatmaydi — signal boshqa joydan kelishi kerak."""
    a = position("advocate", "x", [], 0.5)
    p = position("prosecutor", "y", [], 0.5)
    assert citation_overlap(a, p) == pytest.approx(1.0)


def test_bosh_xulosa_masofasi_maksimal() -> None:
    a = position("advocate", "", [], 0.5)
    p = position("prosecutor", "Mulk qaytarilishi kerak", [], 0.5)
    assert conclusion_distance(a, p) == pytest.approx(1.0)


def test_bitta_pozitsiya_bolsa_raund_2_otkaziladi() -> None:
    a = position("advocate", "Mijoz haq", ["C1"], 0.9)
    assert not needs_round_two({"advocate": a})


def test_ball_formuladagi_vaznlarga_mos() -> None:
    """0.4·|Δishonch| + 0.4·(1−qoplama) + 0.2·masofa."""
    a = position("advocate", "bir xil matn", ["C1"], 1.0)
    p = position("prosecutor", "bir xil matn", ["C2"], 0.0)
    # |Δ| = 1, qoplama = 0, masofa = 0  →  0.4 + 0.4 + 0 = 0.8
    assert disagreement(a, p) == pytest.approx(0.8)


# --------------------------------------------------------------------------- #
# To'liq oqim — echo backend
# --------------------------------------------------------------------------- #


def test_echo_bilan_uchdan_uchgacha_ishlaydi(chunks: list[Chunk], echo_backend: object) -> None:
    result = ask("Mehnat shartnomasi qanday bekor qilinadi?", chunks, echo_backend)

    assert isinstance(result, ConsultResult)
    assert result.trace_id.startswith("cns_")
    assert result.answer
    assert result.citations
    assert result.mode_used in {"simple", "standard", "complex"}


def test_disclaimer_har_doim_toldiriladi(chunks: list[Chunk], echo_backend: object) -> None:
    """docs/10 § 1 — integratsiya qiluvchi uni tashlab keta olmasligi kerak."""
    result = ask("Ijara shartnomasi haqiqiymi?", chunks, echo_backend)
    assert result.disclaimer == DISCLAIMER
    assert "yuridik maslahat" in result.disclaimer


def test_manba_topilmasa_agentlar_chaqirilmaydi(echo_backend: object) -> None:
    result = ask("Mehnat shartnomasi haqiqiymi?", [], echo_backend)

    assert result.refused
    assert result.answer.startswith(REFUSAL)
    assert nodes(result) == ["route", "retrieve", "gate"]
    assert any("manba topilmadi" in c for c in result.caveats)


def test_trace_har_qadamni_yozadi(chunks: list[Chunk], echo_backend: object) -> None:
    result = ask("Bu shartnoma haqiqiymi?", chunks, echo_backend)

    assert result.trace is not None
    assert nodes(result)[:2] == ["route", "retrieve"]
    assert nodes(result)[-1] == "gate"
    assert result.trace.total_ms >= 0
    route_step = result.trace.steps[0]
    assert "reason" in route_step.detail


# --------------------------------------------------------------------------- #
# Rejimga qarab shoxlanish
# --------------------------------------------------------------------------- #


def test_simple_rejimda_faqat_jurist_ishlaydi(chunks: list[Chunk], echo_backend: object) -> None:
    result = ask("MMT stavkasi qancha?", chunks, echo_backend, mode="simple")

    assert result.mode_used == "simple"
    assert "jurist" in nodes(result)
    assert "advocate" not in nodes(result)
    assert "judge" not in nodes(result)


def test_standard_rejimda_debate_yoq(chunks: list[Chunk], echo_backend: object) -> None:
    result = ask("Bu shartnoma haqiqiymi?", chunks, echo_backend, mode="standard")

    assert {"jurist", "professor", "judge"} <= set(nodes(result))
    assert "advocate" not in nodes(result)


def test_agents_royxati_rejimdan_ustun(chunks: list[Chunk], echo_backend: object) -> None:
    result = ask("Kim haq?", chunks, echo_backend, agents=["jurist"])
    assert "advocate" not in nodes(result)
    assert "jurist" in nodes(result)


# --------------------------------------------------------------------------- #
# Debate oqimi — rolga qarab javob beruvchi stub bilan
# --------------------------------------------------------------------------- #

FRAME = json.dumps(
    {
        "facts": ["Uy 3 yil oldin sotib olingan"],
        "legal_questions": ["Vijdonli oluvchi himoyalanadimi?"],
        "applicable_norms": ["C2"],
        "unknowns": ["To'lov hujjati yo'q"],
    },
    ensure_ascii=False,
)


def _position_json(stance: str, tags: list[str], confidence: float) -> str:
    return json.dumps(
        {
            "stance": stance,
            "arguments": [
                {
                    "claim": "Mulkdor mulkini qonunsiz egalikdan talab qilishga haqli",
                    "citations": tags,
                    "strength": "strong",
                }
            ],
            "weaknesses": ["Hujjat yetishmaydi"],
            "confidence": confidence,
        },
        ensure_ascii=False,
    )


VERDICT = json.dumps(
    {
        "conclusion": "Mulkdor mulkini qonunsiz egalikdan talab qilishga haqli [C2]",
        "reasoning": ["Norma bevosita qo'llaniladi [C2]"],
        "accepted_arguments": ["Advokat dalili"],
        "rejected_arguments": ["Prokuror dalili — asossiz"],
        "confidence": 0.8,
        "caveats": [],
    },
    ensure_ascii=False,
)


def test_kuchli_kelishmovchilikda_raund_2_otkaziladi(chunks: list[Chunk]) -> None:
    backend = RoleBackend(
        {
            "jurist": FRAME,
            "advocate": _position_json("Mijoz vijdonli oluvchi va mulkni saqlaydi", ["C1"], 0.9),
            "prosecutor": _position_json("Bitim ishonchsiz, mulk qaytarilsin", ["C2"], 0.2),
            "professor": json.dumps({"summary": "Kolliziya bor", "collisions": ["C1 va C2"]}),
            "judge": VERDICT,
        }
    )
    result = ask("Mijozim sotib olgan uyni mulkdor talab qilmoqda. Kim haq?", chunks, backend)

    assert result.mode_used == "complex"
    assert backend.roles.count("advocate") == 2  # raund 1 + rebuttal
    assert backend.roles.count("prosecutor") == 2
    assert "debate_r2" in nodes(result)


def test_past_kelishmovchilikda_raund_2_otkazib_yuboriladi(chunks: list[Chunk]) -> None:
    same = _position_json("Mulkdor mulkini talab qilishga haqli", ["C2"], 0.8)
    backend = RoleBackend(
        {
            "jurist": FRAME,
            "advocate": same,
            "prosecutor": same,
            "professor": json.dumps({"summary": "Kelishuv bor"}),
            "judge": VERDICT,
        }
    )
    result = ask("Mijozim sotib olgan uyni mulkdor talab qilmoqda. Kim haq?", chunks, backend)

    assert backend.roles.count("advocate") == 1
    assert result.trace is not None
    skipped = next(s for s in result.trace.steps if s.node == "debate_r2")
    assert skipped.detail["skipped"] is True


def test_sudya_yiqilsa_xom_pozitsiyalar_korsatiladi(chunks: list[Chunk]) -> None:
    """docs/06 § 8 — «avtomatik xulosa yo'q» ogohlantirishi bilan."""
    backend = RoleBackend(
        {
            "jurist": FRAME,
            "advocate": _position_json("Mijoz vijdonli oluvchi", ["C2"], 0.7),
            "prosecutor": _position_json("Mulk qaytarilsin", ["C2"], 0.6),
            "professor": json.dumps({"summary": "Sharh"}),
            "judge": "sxemaga tushmaydigan matn",
        }
    )
    result = ask("Mijozim sotib olgan uyni mulkdor talab qilmoqda. Kim haq?", chunks, backend)

    assert result.verdict is None
    assert NO_SYNTHESIS in result.answer
    assert any("Pozitsiya olinmadi: judge" in c for c in result.caveats)
    assert result.positions


def test_backend_yiqilsa_quvur_toxtamaydi(chunks: list[Chunk]) -> None:
    class BrokenBackend(ScriptedBackend):
        def generate(self, prompt: str, params: object) -> str:
            raise RuntimeError("model xotiraga sig'madi")

    result = ask("Bu shartnoma haqiqiymi?", chunks, BrokenBackend(["—"]))

    assert result.refused
    assert result.answer.startswith(REFUSAL)
    assert result.citations  # manbalar baribir ko'rsatiladi


# --------------------------------------------------------------------------- #
# Gate va ishonch
# --------------------------------------------------------------------------- #


def test_gate_javobni_tozalaydi_va_ishonchni_pasaytiradi(chunks: list[Chunk]) -> None:
    dirty = json.dumps(
        {
            "conclusion": "Mulkdor mulkini qonunsiz egalikdan talab qilishga haqli [C2]",
            "reasoning": [
                "Ishdan bo'shatish uchun sud qarori majburiy",  # iqtibossiz huquqiy da'vo
                "Mulk vijdonli oluvchidan talab qilinmaydi [C9]",  # yolg'on iqtibos
            ],
            "confidence": 1.0,
        },
        ensure_ascii=False,
    )
    backend = RoleBackend(
        {"jurist": FRAME, "professor": json.dumps({"summary": "x"}), "judge": dirty}
    )
    result = ask("Bu bitim haqiqiymi?", chunks, backend, mode="standard")

    assert "[C9]" not in result.answer
    assert "sud qarori majburiy" not in result.answer
    assert result.confidence < 1.0
    assert any("chiqarildi" in c for c in result.caveats)


def test_prefix_cache_bir_marta_hisoblanadi(chunks: list[Chunk]) -> None:
    """Umumiy kontekst besh agent uchun bir marta — docs/06 § 6."""
    backend = RoleBackend(
        {"jurist": FRAME, "professor": json.dumps({"summary": "x"}), "judge": VERDICT}
    )
    ask("Bu shartnoma haqiqiymi?", chunks, backend, mode="standard")

    assert backend.cache_calls == 1
    assert backend.calls >= 3


def test_cache_ochirilsa_umuman_hisoblanmaydi(chunks: list[Chunk]) -> None:
    backend = RoleBackend({"jurist": FRAME})
    consult(
        ConsultRequest(question="MMT stavkasi qancha?", mode="simple"),
        backend=backend,
        retriever=StubRetriever(chunks),
        registry=REGISTRY,
        use_prefix_cache=False,
    )
    assert backend.cache_calls == 0
