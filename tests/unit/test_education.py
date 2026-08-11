"""Taʼlim moduli testlari.

Model YUKLANMAYDI. Leksiyaning model yoʻli soxta backend bilan, qidiruv
esa `StubRetriever` bilan sinaladi — shuning uchun testlar tez va
takrorlanadigan.
"""

from __future__ import annotations

import pytest
from conftest import ScriptedBackend, StubRetriever, make_chunk  # tests/unit sys.path da

from uzlegal.education import curriculum as cur
from uzlegal.education.lecture import generate_lecture
from uzlegal.education.quiz import (
    PASS_SCORE,
    RUBRIC,
    QuestionKind,
    QuizQuestion,
    generate_quiz,
    grade_answer,
    grade_quiz,
)
from uzlegal.types import GenerationParams

# --------------------------------------------------------------------------- #
# Fikstura
# --------------------------------------------------------------------------- #

MEHNAT_MATN = (
    "Mehnat shartnomasi tuzishda tomonlarning kelishuviga koʻra sinov muddati "
    "belgilanishi mumkin. Sinov muddati uch oydan oshmasligi kerak. Sinov "
    "muddatiga vaqtincha mehnatga qobiliyatsizlik davri kirmaydi."
)

IJARA_MATN = (
    "Ijara shartnomasi boʻyicha ijaraga beruvchi mulkni haq evaziga vaqtincha "
    "foydalanishga berish majburiyatini oladi. Shartnomada muddat "
    "koʻrsatilmagan boʻlsa, u nomuayyan muddatga tuzilgan hisoblanadi."
)


@pytest.fixture
def retriever() -> StubRetriever:
    return StubRetriever(
        [
            make_chunk(
                "mk:76",
                MEHNAT_MATN,
                article="76",
                doc_id="-6257288",
                doc_title="Mehnat kodeksi",
            ),
            make_chunk(
                "fk:535",
                IJARA_MATN,
                article="535",
                doc_id="-180552",
                doc_title="Fuqarolik kodeksi",
            ),
        ]
    )


@pytest.fixture
def labor_topic() -> cur.Topic:
    topic = cur.find_topic("labor.contract")
    assert topic is not None
    return topic


# --------------------------------------------------------------------------- #
# Dastur
# --------------------------------------------------------------------------- #


def test_yettita_fan_bor() -> None:
    assert len(cur.SUBJECTS) == 7
    assert set(cur.SUBJECTS) == set(cur.Branch)


def test_har_fanda_mavzu_bor() -> None:
    for branch, subj in cur.SUBJECTS.items():
        assert subj.topics, f"{branch} fanida mavzu yoʻq"
        assert subj.branch is branch


def test_mavzu_identifikatorlari_takrorlanmaydi() -> None:
    ids = [t.topic_id for t in cur.all_topics()]
    assert len(ids) == len(set(ids))


def test_mavzu_oz_fanining_sohasini_koersatadi() -> None:
    for subj in cur.SUBJECTS.values():
        for topic in subj.topics:
            assert topic.branch is subj.branch


def test_shartlar_haqiqiy_mavzuga_ishora_qiladi() -> None:
    """Bogʻlanish buzilgan boʻlsa oʻquv yoʻli jimgina qisqarib qoladi."""
    known = {t.topic_id for t in cur.all_topics()}
    for topic in cur.all_topics():
        for prereq in topic.prerequisites:
            assert prereq in known, f"{topic.topic_id} → {prereq} topilmadi"


def test_modda_raqami_dasturga_yozilmagan() -> None:
    """Dasturda modda raqami boʻlmasligi — ataylab qilingan qaror.

    Sabab `curriculum.py` boshida yozilgan: tekshirilmagan raqam bazaga
    mos kelmay qolsa, talaba notoʻgʻri havolani yodlaydi.
    """
    for topic in cur.all_topics():
        matn = " ".join([topic.title, topic.summary, *topic.search_queries])
        assert "-modda" not in matn


def test_organish_yoli_shartlardan_boshlanadi(labor_topic: cur.Topic) -> None:
    yol = cur.learning_path("labor.disputes")
    ids = [t.topic_id for t in yol]
    assert ids[-1] == "labor.disputes"
    assert ids.index("labor.contract") < ids.index("labor.termination")
    assert labor_topic.topic_id in ids


def test_organish_yoli_halqada_tolib_qolmaydi(monkeypatch: pytest.MonkeyPatch) -> None:
    a = cur._topic("x.a", "A", cur.Branch.CIVIL, [], [], prerequisites=["x.b"])
    b = cur._topic("x.b", "B", cur.Branch.CIVIL, [], [], prerequisites=["x.a"])
    monkeypatch.setattr(cur, "all_topics", lambda: [a, b])
    assert [t.topic_id for t in cur.learning_path("x.a")] == ["x.b", "x.a"]


def test_qidiruv_mavzu_topadi() -> None:
    topilgan = cur.search_topics("sinov muddati")
    assert any(t.topic_id == "labor.contract" for t in topilgan)
    assert cur.search_topics("  ") == []


def test_qamrov_bazadagi_hujjatlarga_qarab_hisoblanadi() -> None:
    qamrov = cur.coverage({cur.DOC_LABOR})
    assert qamrov[cur.Branch.LABOR] == 1.0
    # Xalqaro huquq boʻyicha bazada hujjat yoʻq — bu ochiq koʻrsatiladi.
    assert qamrov[cur.Branch.INTERNATIONAL] == 0.0
    assert qamrov[cur.Branch.CIVIL] == 0.0


# --------------------------------------------------------------------------- #
# Leksiya
# --------------------------------------------------------------------------- #


def test_leksiya_normalardan_yigiladi(labor_topic: cur.Topic, retriever: StubRetriever) -> None:
    natija = generate_lecture(labor_topic, retriever)
    assert natija.topic == "labor.contract"
    assert natija.generated_by == "deterministic"
    assert natija.has_sources
    assert "sinov muddati" in natija.content.lower()
    assert natija.norms_cited[0].article == "76"
    assert natija.practice_questions
    assert not natija.caveats


def test_leksiya_takrorlangan_normani_bir_marta_oladi(
    labor_topic: cur.Topic, retriever: StubRetriever
) -> None:
    """Mavzuda uch soʻrov bor, stub har safar bir xil chunklarni qaytaradi."""
    natija = generate_lecture(labor_topic, retriever)
    assert len(retriever.queries) == len(labor_topic.search_queries)
    assert len(natija.norms_cited) == 2


def test_qidiruvsiz_leksiya_ogohlantiradi(labor_topic: cur.Topic) -> None:
    natija = generate_lecture(labor_topic)
    assert not natija.has_sources
    assert natija.caveats
    assert "Qidiruv ulanmagan" in natija.caveats[0]


def test_norma_topilmasa_leksiya_toqimaydi(labor_topic: cur.Topic) -> None:
    natija = generate_lecture(labor_topic, StubRetriever([]))
    assert not natija.has_sources
    assert any("norma topilmadi" in c for c in natija.caveats)
    assert "huquqiy asos sifatida" in natija.content


def test_nomalum_mavzu_xato_beradi() -> None:
    with pytest.raises(ValueError, match="Mavzu topilmadi"):
        generate_lecture("yoq.mavzu")


def test_model_yoli_soxta_backend_bilan(labor_topic: cur.Topic, retriever: StubRetriever) -> None:
    backend = ScriptedBackend(
        [
            "## Tushuntirish\nSinov muddati uch oydan oshmaydi [C1].\n"
            "## Misollar\n- Ish beruvchi sinovni olti oy qilib belgiladi.\n"
            "## Savollar\n- Sinov muddati qachon uzaytiriladi?\n"
        ]
    )
    natija = generate_lecture(labor_topic, retriever, backend=backend, params=GenerationParams())

    assert natija.generated_by == "model"
    assert "[C1]" in natija.content
    assert natija.examples == ["Ish beruvchi sinovni olti oy qilib belgiladi."]
    assert natija.practice_questions == ["Sinov muddati qachon uzaytiriladi?"]
    # Prompt ichida normalar boʻlishi shart — modelga manba koʻrsatilgan.
    assert "Mehnat kodeksi" in backend.prompts[0]


def test_kontekstga_sigmagan_norma_iqtibosda_qolmaydi(
    labor_topic: cur.Topic, retriever: StubRetriever
) -> None:
    """Modelga koʻrsatilmagan norma javobni qoʻllab-quvvatlamaydi."""
    backend = ScriptedBackend(["## Tushuntirish\nMatn [C1]."])
    natija = generate_lecture(labor_topic, retriever, backend=backend, context_budget=60)
    assert len(natija.norms_cited) < 2
    assert any("kiritilmadi" in c for c in natija.caveats)


# --------------------------------------------------------------------------- #
# Test tuzish
# --------------------------------------------------------------------------- #


def test_savollar_normalardan_tuziladi(labor_topic: cur.Topic, retriever: StubRetriever) -> None:
    quiz = generate_quiz(labor_topic, retriever, count=6)
    assert len(quiz.questions) == 6
    assert {q.kind for q in quiz.questions} == set(QuestionKind)
    assert all(q.source_text for q in quiz.questions)
    assert quiz.norms_cited


def test_savollar_takrorlanadigan(labor_topic: cur.Topic, retriever: StubRetriever) -> None:
    """Bir xil kirish — bir xil test. Tasodifiylik yoʻq."""
    a = generate_quiz(labor_topic, retriever, count=6)
    b = generate_quiz(labor_topic, StubRetriever(retriever.chunks), count=6)
    assert a.model_dump() == b.model_dump()


def test_kop_tanlovli_savol_togri_javobni_biladi(
    labor_topic: cur.Topic, retriever: StubRetriever
) -> None:
    quiz = generate_quiz(labor_topic, retriever, count=3, kinds=[QuestionKind.MULTIPLE_CHOICE])
    savol = quiz.questions[0]
    assert savol.correct_index is not None
    assert savol.options[savol.correct_index] == "Mehnat kodeksi"
    assert len(set(savol.options)) == len(savol.options)


def test_bitta_hujjatda_kop_tanlovli_savol_ochiqqa_almashadi(labor_topic: cur.Topic) -> None:
    """Chalgʻituvchi variant yoʻq boʻlsa — soxta variant oʻylab topilmaydi."""
    yagona = StubRetriever(
        [make_chunk("mk:76", MEHNAT_MATN, article="76", doc_title="Mehnat kodeksi")]
    )
    quiz = generate_quiz(labor_topic, yagona, count=2, kinds=[QuestionKind.MULTIPLE_CHOICE])
    assert all(q.kind is QuestionKind.OPEN for q in quiz.questions)


def test_norma_yoq_bolsa_test_tuzilmaydi(labor_topic: cur.Topic) -> None:
    quiz = generate_quiz(labor_topic, StubRetriever([]))
    assert quiz.questions == []
    assert quiz.caveats

    quiz2 = generate_quiz(labor_topic)
    assert quiz2.questions == []
    assert "Qidiruv ulanmagan" in quiz2.caveats[0]


def test_normadan_kam_savol_ogohlantiriladi(
    labor_topic: cur.Topic, retriever: StubRetriever
) -> None:
    quiz = generate_quiz(labor_topic, retriever, count=6)
    assert any("bir xil normadan" in c for c in quiz.caveats)


# --------------------------------------------------------------------------- #
# Baholash — yopiq savollar
# --------------------------------------------------------------------------- #


def _mc() -> QuizQuestion:
    return QuizQuestion(
        question_id="q1",
        kind=QuestionKind.MULTIPLE_CHOICE,
        prompt="Qaysi hujjat?",
        options=["Mehnat kodeksi", "Fuqarolik kodeksi"],
        correct_index=0,
        explanation="Toʻgʻri javob: Mehnat kodeksi.",
    )


def _tf() -> QuizQuestion:
    return QuizQuestion(
        question_id="q2",
        kind=QuestionKind.TRUE_FALSE,
        prompt="Shundaymi?",
        correct_bool=True,
    )


@pytest.mark.parametrize("javob", [0, "0", "Mehnat kodeksi", "mehnat kodeksi"])
def test_kop_tanlovli_togri_javob(javob: str | int) -> None:
    baho = grade_answer(_mc(), javob)
    assert baho.correct is True
    assert baho.score == 1.0
    assert baho.passed


@pytest.mark.parametrize("javob", [1, "1", "Fuqarolik kodeksi", None, ""])
def test_kop_tanlovli_notogri_javob(javob: str | int | None) -> None:
    baho = grade_answer(_mc(), javob)
    assert baho.correct is False
    assert baho.score == 0.0
    assert "notoʻgʻri" in baho.feedback[0]


@pytest.mark.parametrize("javob", [True, "ha", "toʻgʻri", "rost", 1])
def test_togri_notogri_savol_ha(javob: str | bool | int) -> None:
    assert grade_answer(_tf(), javob).correct is True


@pytest.mark.parametrize("javob", [False, "yoʻq", "notoʻgʻri", "nimadir", None])
def test_togri_notogri_savol_yoq(javob: str | bool | int | None) -> None:
    assert grade_answer(_tf(), javob).correct is False


def test_kop_tanlovlida_mantiq_qiymati_qollanmaydi() -> None:
    """Yopiq savolda rubrika ishlamaydi — faqat aniqlik."""
    baho = grade_answer(_mc(), 0)
    assert set(baho.criteria) == {"accuracy"}


# --------------------------------------------------------------------------- #
# Baholash — ochiq savollar (rubrika)
# --------------------------------------------------------------------------- #


def _open() -> QuizQuestion:
    return QuizQuestion(
        question_id="q3",
        kind=QuestionKind.OPEN,
        prompt="Sinov muddati qanday belgilanadi?",
        expected_points=[
            "Sinov muddati tomonlarning kelishuviga koʻra belgilanadi",
            "Sinov muddati uch oydan oshmasligi kerak",
        ],
        expected_articles=["76"],
        source_text=MEHNAT_MATN,
    )


def test_rubrika_ogirliklari_bir_boladi() -> None:
    assert sum(RUBRIC.values()) == pytest.approx(1.0)
    assert set(RUBRIC) == {"completeness", "accuracy", "citation", "reasoning"}


def test_mukammal_javob_toliq_ball_oladi() -> None:
    javob = (
        "Mehnat kodeksining 76-moddasiga koʻra sinov muddati tomonlarning "
        "kelishuviga koʻra belgilanadi. Sinov muddati uch oydan oshmasligi "
        "kerak, chunki qonun bunga aniq chegara qoʻygan."
    )
    baho = grade_answer(_open(), javob)
    assert baho.criteria["completeness"] == 1.0
    assert baho.criteria["citation"] == 1.0
    assert baho.criteria["reasoning"] == 1.0
    assert baho.score >= 0.9
    assert baho.passed


def test_bosh_javob_nol_oladi() -> None:
    baho = grade_answer(_open(), "")
    assert baho.score == 0.0
    assert not baho.passed
    assert baho.criteria["accuracy"] == 0.0
    assert baho.criteria["reasoning"] == 0.0


def test_javob_berilmagan_savol_ham_baholanadi() -> None:
    assert grade_answer(_open(), None).score == 0.0


def test_iqtibossiz_javob_iqtibos_ballini_yoqotadi() -> None:
    javob = (
        "Sinov muddati tomonlarning kelishuviga koʻra belgilanadi va uch "
        "oydan oshmasligi kerak, chunki qonun chegara qoʻygan."
    )
    baho = grade_answer(_open(), javob)
    assert baho.criteria["citation"] == 0.0
    assert any("76-modda" in f for f in baho.feedback)
    assert baho.passed  # iqtibos 20% — qolgani yaxshi boʻlsa javob oʻtadi

    # Ayni javobga modda havolasi qoʻshilsa, farq aynan iqtibos ogʻirligicha
    # boʻlishi kerak. Bu rubrikaning ogʻirliklarini tekshiradi.
    bilan = grade_answer(_open(), f"Mehnat kodeksining 76-moddasiga koʻra {javob}")
    assert bilan.score - baho.score == pytest.approx(RUBRIC["citation"], abs=0.02)


def test_yarim_javob_toliqlikni_yoqotadi() -> None:
    """Birinchi fikr toʻliq, ikkinchisi (uch oy chegarasi) umuman yoʻq."""
    javob = (
        "Mehnat kodeksining 76-moddasiga koʻra sinov muddati tomonlarning "
        "kelishuviga koʻra belgilanadi."
    )
    baho = grade_answer(_open(), javob)
    assert baho.criteria["completeness"] == 0.5
    assert any("oydan oshmasligi" in f for f in baho.feedback)


def test_umumiy_sozlar_fikrni_yopmaydi() -> None:
    """«Sinov muddati» ikkala kutilgan fikrda ham bor.

    Bu soʻzlarning oʻzi bitta fikrni ham yopmasligi kerak — aks holda
    mavzuni takrorlagan talaba hech narsa aytmasdan ball olardi.
    """
    baho = grade_answer(_open(), "Sinov muddati.")
    assert baho.criteria["completeness"] == 0.0


def test_normadan_uzoq_javob_aniqlikni_yoqotadi() -> None:
    """Mavzuga aloqasiz, lekin uzun javob — «aniqlik» aynan shuni ushlaydi."""
    javob = (
        "Kosmik kemalarni ijaraga berish narxlari bozor konyunkturasiga bogʻliq, "
        "chunki talab va taklif muvozanati doimiy oʻzgarib turadi."
    )
    baho = grade_answer(_open(), javob)
    assert baho.criteria["accuracy"] < 0.5
    assert baho.criteria["completeness"] == 0.0
    assert not baho.passed


def test_kutilgan_fikr_korsatilmasa_jazolanmaydi() -> None:
    savol = QuizQuestion(
        question_id="q4",
        kind=QuestionKind.OPEN,
        prompt="Fikringiz?",
    )
    baho = grade_answer(savol, "Qisqa javob.")
    assert baho.criteria["completeness"] == 1.0
    assert baho.criteria["accuracy"] == 1.0
    assert baho.criteria["citation"] == 1.0


def test_apostrof_yozuvi_bahoga_tasir_qilmaydi() -> None:
    """`oʻ` va `o'` bir xil hisoblanishi kerak."""
    a = grade_answer(_open(), "76-moddaga koʻra sinov muddati kelishuvga koʻra belgilanadi.")
    b = grade_answer(_open(), "76-moddaga ko'ra sinov muddati kelishuvga ko'ra belgilanadi.")
    assert a.criteria == b.criteria


# --------------------------------------------------------------------------- #
# Butun test
# --------------------------------------------------------------------------- #


def test_butun_testni_baholash(labor_topic: cur.Topic, retriever: StubRetriever) -> None:
    quiz = generate_quiz(labor_topic, retriever, count=3)
    javoblar: dict[str, str | int | bool | None] = {}
    for q in quiz.questions:
        if q.kind is QuestionKind.MULTIPLE_CHOICE:
            javoblar[q.question_id] = q.correct_index
        elif q.kind is QuestionKind.TRUE_FALSE:
            javoblar[q.question_id] = True

    natija = grade_quiz(quiz, javoblar)
    assert len(natija.grades) == 3
    assert natija.answered == 2
    # Ikkita yopiq savol toʻgʻri, ochigʻiga javob berilmagan.
    assert natija.score == pytest.approx(2 / 3, abs=0.01)
    assert natija.percent == 67


def test_javobsiz_test_nol_oladi(labor_topic: cur.Topic, retriever: StubRetriever) -> None:
    quiz = generate_quiz(labor_topic, retriever, count=3)
    natija = grade_quiz(quiz, {})
    assert natija.score == 0.0
    assert natija.answered == 0
    assert not natija.passed


def test_bosh_test_yiqilmaydi(labor_topic: cur.Topic) -> None:
    quiz = generate_quiz(labor_topic, StubRetriever([]))
    natija = grade_quiz(quiz, {})
    assert natija.score == 0.0
    assert natija.grades == []


def test_otish_chegarasi_bir_joyda_belgilangan() -> None:
    assert 0.0 < PASS_SCORE < 1.0
