"""`simple` oqimda iqtibos intizomi.

## Nima uchun alohida fayl

Bu oqimda jurist **yagona** agent: u ham ramkani, ham javobni beradi va
undan keyin gate turadi. Boshqa oqimlarda sudya javobni sintez qiladi va
uning prompti iqtibosni alohida talab qiladi; bu yerda esa zanjirda
boshqa hech kim yo'q.

## Tuzatilgan nosozlik

Haqiqiy sinovda (gemma3-12b, 8 627 chunkli indeks) shunday bo'ldi:

    retrieve  11 norma topdi
    jurist    javob yozdi, lekin `[C1]` belgisini qo'ymadi
    gate      claims=3 · kept=0 · dropped=3 · refused
    natija    «Ishonchli javob shakllantirilmadi»

Ya'ni tizim to'g'ri normalarni topgan, lekin foydalanuvchiga hech narsa
ko'rsatmagan. ADR-001 o'lchovi ham aynan shuni bashorat qilgan edi
(`cite-01`: «iqtibos yo'q: [C1]»).

Yechim ikki qismli va **hech qanday tasdiqlanmagan gapni javobga
qo'shmaydi**:

1. Iqtibossiz javob **manbada** tashlanadi (`_grounded_answer`)
2. Tegishli normalar ro'yxati har doim qo'shiladi — uning har bir satri
   o'z belgisini olib yuradi va gate dan o'tadi
"""

from __future__ import annotations

from typing import Any

from uzlegal.agents.base import AgentContext
from uzlegal.agents.roles import get_agent
from uzlegal.agents.schemas import LegalFrame
from uzlegal.orchestrator.gate import groundedness_gate
from uzlegal.orchestrator.graph import draft_answer
from uzlegal.types import Citation, GenerationParams, ModelSpec

# --------------------------------------------------------------------------- #
# Yordamchilar
# --------------------------------------------------------------------------- #


def citations() -> list[Citation]:
    return [
        Citation(
            tag="C1",
            doc_id="fk",
            doc_title="Fuqarolik kodeksi",
            article="228",
            excerpt=(
                "Mulkdor oʻz mol-mulkini boshqa shaxsning qonunsiz egaligidan "
                "talab qilib olishga haqli"
            ),
        ),
        Citation(
            tag="C2",
            doc_id="fk",
            doc_title="Fuqarolik kodeksi",
            article="229",
            excerpt="Mol-mulk vijdonli oluvchidan faqat qonunda koʻrsatilgan hollarda olinadi",
        ),
    ]


class Replay:
    """Oldindan yozilgan javobni qaytaradi va chaqiruvlarni sanaydi."""

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


def context(backend: Any) -> AgentContext:
    return AgentContext(
        question="Oʻgʻirlangan mulkni qaytarib olsam boʻladimi",
        backend=backend,
        context_text="=== [C1] Fuqarolik kodeksi, 228-modda ===",
        citations=citations(),
    )


def frame_json(answer: str, norms: str = '["C1", "C2"]') -> str:
    return (
        '{"facts": ["Mulk oʻgʻirlangan"], '
        '"legal_questions": ["Talab qilib olish mumkinmi"], '
        f'"applicable_norms": {norms}, "unknowns": [], '
        f'"answer": "{answer}"}}'
    )


class Draft:
    """`draft_answer()` uchun minimal holat — faqat ramka bilan."""

    def __init__(self, frame: LegalFrame | None) -> None:
        self.verdict = None
        self.positions: dict[str, Any] = {}
        self.rebuttals: dict[str, Any] = {}
        self.final_positions: dict[str, Any] = {}
        self.frame = frame


# --------------------------------------------------------------------------- #
# 1-qism: iqtibossiz javob manbada tashlanadi
# --------------------------------------------------------------------------- #


def test_iqtibosli_javob_saqlanadi() -> None:
    backend = Replay(frame_json("Mulkdor talab qilib olishga haqli [C1]."))
    frame = get_agent("jurist").run(context(backend), direct=True)

    assert isinstance(frame, LegalFrame)
    assert "[C1]" in frame.answer


def test_iqtibossiz_javob_tashlanadi() -> None:
    """Belgisiz gap gate da baribir o'chirilardi — uni manbada tashlaymiz.

    Bu yashirish emas: javob o'rniga ramka normalari ko'rsatiladi va
    foydalanuvchi tasdiqlanmagan gapni umuman ko'rmaydi.
    """
    backend = Replay(frame_json("Mulkdor talab qilib olishga haqli."))
    frame = get_agent("jurist").run(context(backend), direct=True)

    assert isinstance(frame, LegalFrame)
    assert frame.answer == ""
    assert frame.applicable_norms, "normalar saqlanishi kerak"


def test_oylab_topilgan_belgi_javobni_saqlamaydi() -> None:
    """`[C9]` kontekstda yo'q — u javobni «bog'langan» qilmaydi."""
    backend = Replay(frame_json("Mulkdor talab qilib olishga haqli [C9]."))
    frame = get_agent("jurist").run(context(backend), direct=True)

    assert isinstance(frame, LegalFrame)
    assert frame.answer == ""


def test_normasiz_ramka_qayta_soraladi() -> None:
    """Norma tanlanmagan ramka gate uchun tekshiriladigan narsa qoldirmaydi."""
    backend = Replay(
        frame_json("Javob [C1].", norms="[]"),
        frame_json("Mulkdor talab qilib olishga haqli [C1].", norms='["C1"]'),
    )
    frame = get_agent("jurist").run(context(backend), direct=True)

    assert isinstance(frame, LegalFrame)
    assert len(backend.calls) == 2, "birinchi urinish rad etilib, qayta so'ralishi kerak"
    assert frame.applicable_norms


def test_qayta_sorovda_tuzatish_korsatmasi_boladi() -> None:
    backend = Replay(
        frame_json("Javob [C1].", norms="[]"),
        frame_json("Javob [C1].", norms='["C1"]'),
    )
    get_agent("jurist").run(context(backend), direct=True)

    assert "TUZATISH" in backend.calls[1]
    assert "applicable_norms" in backend.calls[1]


# --------------------------------------------------------------------------- #
# 2-qism: normalar ro'yxati har doim ko'rsatiladi
# --------------------------------------------------------------------------- #


def test_javob_bilan_birga_normalar_ham_chiqadi() -> None:
    frame = LegalFrame(
        legal_questions=["Talab qilish mumkinmi"],
        applicable_norms=citations(),
        answer="Mulkdor talab qilib olishga haqli [C1].",
    )
    text = draft_answer(Draft(frame))

    assert "XULOSA" in text
    assert "TEGISHLI NORMALAR" in text
    assert "[C2]" in text, "javob ishlatmagan norma ham ko'rsatiladi"


def test_javobsiz_ramka_normalarni_beradi() -> None:
    frame = LegalFrame(legal_questions=["Savol"], applicable_norms=citations())
    text = draft_answer(Draft(frame))

    assert "TEGISHLI NORMALAR" in text
    assert "228-modda" in text


def test_bosh_ramka_bosh_javob() -> None:
    assert draft_answer(Draft(LegalFrame())) == ""


# --------------------------------------------------------------------------- #
# 3-qism: yakuniy natija — gate dan o'tishi
# --------------------------------------------------------------------------- #


def test_iqtibossiz_javobda_ham_gate_rad_etmaydi() -> None:
    """Aynan tuzatilgan nosozlik.

    Jurist belgini unutgan; ilgari bu «ishonchli javob shakllantirilmadi»
    bilan tugardi. Endi normalar ro'yxati qoladi va foydalanuvchi qaysi
    moddalar tegishli ekanini ko'radi.
    """
    frame = LegalFrame(legal_questions=["Savol"], applicable_norms=citations(), answer="")
    report = groundedness_gate(draft_answer(Draft(frame)), citations())

    assert not report.refused
    assert report.kept_legal > 0
    assert "228-modda" in report.answer


def test_iqtibosli_javob_toliq_otadi() -> None:
    frame = LegalFrame(
        legal_questions=["Savol"],
        applicable_norms=citations(),
        answer="Mulkdor mol-mulkini qonunsiz egalikdan talab qilib olishga haqli [C1].",
    )
    report = groundedness_gate(draft_answer(Draft(frame)), citations())

    assert not report.refused
    assert report.dropped == 0
    assert "talab qilib olishga haqli" in report.answer


def test_gate_baribir_iqtibossiz_davoni_ochiradi() -> None:
    """Tuzatish gate ni bo'shashtirmasligi kerak — u hamon qattiq."""
    frame = LegalFrame(
        legal_questions=["Savol"],
        applicable_norms=citations(),
        answer="Jarima 10 barobar oshiriladi",
    )
    report = groundedness_gate(draft_answer(Draft(frame)), citations())

    assert report.dropped >= 1
    assert "Jarima 10 barobar" not in report.answer
