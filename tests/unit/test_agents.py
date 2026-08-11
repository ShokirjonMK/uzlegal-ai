"""Agent qatlami testlari — docs/06 § 2, § 6, § 8.

Rollar qat'iy shartnomaga ega, shuning uchun ularni **mustaqil** sinash
mumkin: model o'rniga oldindan yozilgan javob beriladi va agent uni to'g'ri
sxemaga solganini tekshiriladi. Hech qanday model yuklanmaydi.
"""

from __future__ import annotations

import json

import pytest
from conftest import CountingCache, ScriptedBackend  # tests/unit sys.path da

from uzlegal.agents.base import (
    PROMPTS_DIR,
    AgentContext,
    AgentSchemaError,
    build_prefix,
    extract_json,
    extract_tags,
    parse_confidence,
    parse_sections,
)
from uzlegal.agents.roles import ROLE_ORDER, get_agent, render_position
from uzlegal.agents.schemas import DoctrinalAnalysis, LegalFrame, Verdict
from uzlegal.types import Citation, Position

ADVOCATE_JSON = json.dumps(
    {
        "stance": "Mijoz vijdonli oluvchi hisoblanadi",
        "arguments": [
            {
                "claim": "Mulk vijdonli oluvchidan talab qilinmaydi",
                "citations": ["C2"],
                "strength": "strong",
            }
        ],
        "weaknesses": ["Kvitansiya yo'q"],
        "confidence": 0.72,
    },
    ensure_ascii=False,
)


def context(citations: list[Citation], backend: object) -> AgentContext:
    return AgentContext(
        question="Mehnat shartnomasi qanday bekor qilinadi?",
        backend=backend,  # type: ignore[arg-type]
        context_text="=== [C1] Mehnat kodeksi, 106-modda ===\nMatn",
        citations=citations,
        prefix=build_prefix("Tizim ko'rsatmasi", "kontekst"),
    )


# --------------------------------------------------------------------------- #
# Promptlar va reestr
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("role", ROLE_ORDER)
def test_har_rol_uchun_prompt_fayli_bor(role: str) -> None:
    path = PROMPTS_DIR / f"{role}.uz.md"
    assert path.exists(), f"{path} yo'q"
    assert len(path.read_text(encoding="utf-8")) > 500


@pytest.mark.parametrize("role", ROLE_ORDER)
def test_har_rol_shartnomasi_toliq(role: str) -> None:
    agent = get_agent(role)
    assert agent.role == role
    assert agent.output_schema is not None
    assert 0.0 <= agent.temperature <= 1.0
    assert agent.system_prompt


def test_notogri_rol_xato_beradi() -> None:
    with pytest.raises(KeyError, match="Noma'lum rol"):
        get_agent("notarius")


def test_rol_sozlamasi_yamldan_oqiladi() -> None:
    """`configs/agents/advocate.yaml` da `base_temperature: 0.5`."""
    assert get_agent("advocate").temperature == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Javobni ajratish
# --------------------------------------------------------------------------- #


def test_json_kod_blokidan_ajratiladi() -> None:
    raw = 'Mana javob:\n```json\n{"stance": "ha"}\n```\nUmid qilamanki foydali.'
    assert extract_json(raw) == {"stance": "ha"}


def test_json_izohlar_orasidan_ajratiladi() -> None:
    raw = 'Javob: {"a": 1, "b": {"c": "}"}} — tugadi'
    assert extract_json(raw) == {"a": 1, "b": {"c": "}"}}


def test_json_bolmasa_none() -> None:
    assert extract_json("Hech qanday struktura yo'q") is None


def test_bolimlar_katta_harfli_sarlavha_boyicha_ajratiladi() -> None:
    sections = parse_sections(
        "POZITSIYA\nMijoz haq.\n\nZAIF TOMONLAR\n- Dalil yo'q\n\nISHONCH: 0.8"
    )
    assert sections["POZITSIYA"] == ["Mijoz haq."]
    assert sections["ZAIF TOMONLAR"] == ["Dalil yo'q"]
    assert sections["ISHONCH"] == ["0.8"]


def test_iqtibos_belgilari_tartibda_takrorsiz() -> None:
    assert extract_tags("[C2] va yana [c1], keyin [C2]") == ["C2", "C1"]


def test_ishonch_foizdan_ham_oqiladi() -> None:
    assert parse_confidence(["78%"]) == pytest.approx(0.78)
    assert parse_confidence(["0,65"]) == pytest.approx(0.65)
    assert parse_confidence([]) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Rollar
# --------------------------------------------------------------------------- #


def test_advokat_json_javobni_sxemaga_soladi(citations: list[Citation]) -> None:
    backend = ScriptedBackend([ADVOCATE_JSON])
    result = get_agent("advocate").run(context(citations, backend))

    assert isinstance(result, Position)
    assert result.role == "advocate"
    assert result.confidence == pytest.approx(0.72)
    assert result.arguments[0].strength == "strong"
    assert result.weaknesses == ["Kvitansiya yo'q"]
    assert backend.calls == 1


def test_jurist_ramka_quradi(citations: list[Citation]) -> None:
    raw = json.dumps(
        {
            "facts": ["Shartnoma 2023-yilda imzolangan"],
            "legal_questions": ["Shartnoma haqiqiymi?"],
            "applicable_norms": ["C1", "C2"],
            "unknowns": ["To'lov hujjatlari yo'q"],
        },
        ensure_ascii=False,
    )
    frame = get_agent("jurist").run(context(citations, ScriptedBackend([raw])))

    assert isinstance(frame, LegalFrame)
    assert frame.norm_tags == ["C1", "C2"]
    assert frame.unknowns == ["To'lov hujjatlari yo'q"]


def test_professor_kolliziyani_qaytaradi(citations: list[Citation]) -> None:
    raw = json.dumps(
        {"summary": "Ikki norma to'qnashadi", "collisions": ["C1 va C2 lex specialis"]},
        ensure_ascii=False,
    )
    doctrine = get_agent("professor").run(context(citations, ScriptedBackend([raw])))

    assert isinstance(doctrine, DoctrinalAnalysis)
    assert doctrine.collisions


def test_sudya_verdikt_quradi(citations: list[Citation]) -> None:
    raw = json.dumps(
        {
            "conclusion": "Shartnoma haqiqiy [C1]",
            "reasoning": ["Norma bevosita qo'llaniladi [C1]"],
            "accepted_arguments": ["Advokat dalili"],
            "rejected_arguments": ["Prokuror dalili — asossiz"],
            "confidence": 0.81,
            "caveats": ["To'lov hujjati yo'q"],
        },
        ensure_ascii=False,
    )
    verdict = get_agent("judge").run(context(citations, ScriptedBackend([raw])))

    assert isinstance(verdict, Verdict)
    assert verdict.confidence == pytest.approx(0.81)
    assert "XULOSA" in verdict.as_answer()
    assert "ASOSLAR" in verdict.as_answer()


def test_notogri_iqtibos_agent_darajasidayoq_tashlanadi(citations: list[Citation]) -> None:
    """Gate gacha yetib bormaydigan birinchi filtr — mavjud bo'lmagan belgi."""
    raw = json.dumps({"conclusion": "Xulosa [C9]", "citation_tags": ["C9", "C1"]})
    verdict = get_agent("judge").run(context(citations, ScriptedBackend([raw])))

    assert isinstance(verdict, Verdict)
    assert verdict.citation_tags == ["C1"]


# --------------------------------------------------------------------------- #
# Shartnoma buzilishi va qayta urinish — docs/06 § 8
# --------------------------------------------------------------------------- #


def test_zaif_tomonlar_bosh_bolsa_qayta_soraladi(citations: list[Citation]) -> None:
    """`weaknesses` majburiy — rol qulflanishiga qarshi asosiy mexanizm."""
    bad = json.dumps({"stance": "Mijoz haq", "arguments": [{"claim": "Dalil"}], "weaknesses": []})
    backend = ScriptedBackend([bad, ADVOCATE_JSON])
    result = get_agent("advocate").run(context(citations, backend))

    assert backend.calls == 2
    assert result.weaknesses  # type: ignore[union-attr]
    assert "ZAIF" in backend.prompts[1].upper()


def test_uch_urinishdan_keyin_agent_tushib_qoladi(citations: list[Citation]) -> None:
    backend = ScriptedBackend(["Hech qanday struktura yo'q, faqat matn."])
    with pytest.raises(AgentSchemaError):
        get_agent("advocate").run(context(citations, backend))
    assert backend.calls == 3


def test_matn_strukturasi_zaxira_yol_bolib_ishlaydi(citations: list[Citation]) -> None:
    """JSON chiqmasa — promptdagi matn shakli o'qiladi (echo backend shu shaklda)."""
    text = (
        "POZITSIYA\nMijoz vijdonli oluvchi.\n\n"
        "DALILLAR\n1. [kuchli] Mulk talab qilinmaydi. Asos: [C2]\n\n"
        "ZAIF TOMONLAR\n- Kvitansiya yo'q\n\n"
        "ISHONCH: 0.7\n"
    )
    result = get_agent("advocate").run(context(citations, ScriptedBackend([text])))

    assert isinstance(result, Position)
    assert result.stance == "Mijoz vijdonli oluvchi."
    assert result.arguments[0].citations == ["C2"]
    assert result.arguments[0].strength == "strong"
    assert result.confidence == pytest.approx(0.7)


def test_echo_backend_bilan_pozitsiya_olinadi(
    citations: list[Citation], echo_backend: object
) -> None:
    result = get_agent("advocate").run(context(citations, echo_backend))
    assert isinstance(result, Position)
    assert result.weaknesses


# --------------------------------------------------------------------------- #
# Prefix KV-cache — docs/06 § 6
# --------------------------------------------------------------------------- #


def test_cache_bolsa_prefiks_promptga_qoshilmaydi(citations: list[Citation]) -> None:
    """Prefiks cache da — uni qayta yuborish cache ni ma'nosiz qiladi."""
    cache = CountingCache()
    backend = ScriptedBackend([ADVOCATE_JSON])
    ctx = context(citations, backend)
    ctx.prefix_cache = cache

    get_agent("advocate").run(ctx)

    assert ctx.prefix not in backend.prompts[0]
    assert backend.params[0].raw is True
    assert backend.params[0].prefix_cache is cache


def test_cache_har_agent_uchun_nusxalanadi(citations: list[Citation]) -> None:
    """Asl cache buzilmasligi kerak — keyingi agent ham undan foydalanadi."""
    cache = CountingCache()
    backend = ScriptedBackend([ADVOCATE_JSON])
    ctx = context(citations, backend)
    ctx.prefix_cache = cache

    get_agent("advocate").run(ctx)
    get_agent("advocate").run(ctx)

    assert cache.copies == 2


def test_cachesiz_prefiks_promptga_qoshiladi(citations: list[Citation]) -> None:
    backend = ScriptedBackend([ADVOCATE_JSON])
    ctx = context(citations, backend)

    get_agent("advocate").run(ctx)

    assert backend.prompts[0].startswith(ctx.prefix)
    assert backend.params[0].raw is False


def test_prefiks_barcha_agentlar_uchun_bir_xil(citations: list[Citation]) -> None:
    """Bayt-baytga bir xil bo'lmasa cache yaroqsiz (docs/06 § 6)."""
    backend = ScriptedBackend([ADVOCATE_JSON, ADVOCATE_JSON])
    ctx = context(citations, backend)

    get_agent("advocate").run(ctx)
    get_agent("prosecutor").run(ctx)

    prefix = ctx.prefix
    assert all(p.startswith(prefix) for p in backend.prompts)


# --------------------------------------------------------------------------- #
# Promptga tushadigan ko'rinishlar
# --------------------------------------------------------------------------- #


def test_pozitsiya_promptda_zaif_tomonlar_bilan_korsatiladi() -> None:
    position = Position(
        role="advocate",
        stance="Mijoz haq",
        weaknesses=["Dalil kam"],
        confidence=0.6,
    )
    rendered = render_position(position)
    assert "ZAIF TOMONLAR" in rendered
    assert "ISHONCH: 0.60" in rendered


def test_prokuror_advokat_pozitsiyasini_koradi(citations: list[Citation]) -> None:
    backend = ScriptedBackend([ADVOCATE_JSON])
    advocate = Position(role="advocate", stance="Mijoz haq", weaknesses=["—"], confidence=0.6)

    get_agent("prosecutor").run(context(citations, backend), advocate=advocate)

    assert "ADVOKAT POZITSIYASI" in backend.prompts[0]
