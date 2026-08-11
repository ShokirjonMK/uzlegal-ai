"""Test savollari va baholash.

IKKI QISM. Birinchisi — bilim bazasidagi normalardan test savollari
yasash. Ikkinchisi — talaba javobini rubrika boʻyicha baholash.

BAHOLASH MODELSIZ. Rubrika ataylab deterministik: bir xil javob har doim
bir xil ball oladi va har ball qaysi mezondan kelgani koʻrinadi. Model
bilan baholash qulayroq boʻlardi, lekin talaba «nega 60 ball?» deb
soʻraganda javob bera olmaydigan baho — baho emas.

Buning narxi bor va uni yashirmaslik kerak: rubrika **maʼnoni emas,
belgilarni** oʻlchaydi. Toʻgʻri fikrni boshqa soʻz bilan aytgan talaba
past ball olishi mumkin. Shuning uchun `GradeResult.feedback` da har
mezon boʻyicha nima yetishmagani ochiq yoziladi — bahoni oʻqituvchi
qayta koʻrishi mumkin.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from uzlegal.education.curriculum import Topic, find_topic
from uzlegal.ingest.normalize import fold
from uzlegal.types import Citation

# --------------------------------------------------------------------------- #
# Savol
# --------------------------------------------------------------------------- #


class QuestionKind(StrEnum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    OPEN = "open"


class QuizQuestion(BaseModel):
    question_id: str
    kind: QuestionKind
    prompt: str

    options: list[str] = Field(default_factory=list)
    correct_index: int | None = Field(default=None, description="Koʻp tanlovli savol javobi")
    correct_bool: bool | None = Field(default=None, description="Toʻgʻri/notoʻgʻri javobi")

    expected_points: list[str] = Field(
        default_factory=list, description="Ochiq savolda kutilgan asosiy fikrlar"
    )
    expected_articles: list[str] = Field(
        default_factory=list, description="Javobda boʻlishi kerak boʻlgan modda raqamlari"
    )
    source_text: str = Field(default="", description="Savol olingan norma matni")
    source_tag: str = ""
    explanation: str = ""

    @property
    def is_closed(self) -> bool:
        """Yopiq savolmi (bitta toʻgʻri javobi bor)."""
        return self.kind in (QuestionKind.MULTIPLE_CHOICE, QuestionKind.TRUE_FALSE)


class QuizResult(BaseModel):
    topic: str
    title: str = ""
    questions: list[QuizQuestion] = Field(default_factory=list)
    norms_cited: list[Citation] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Baho
# --------------------------------------------------------------------------- #

#: Rubrika ogʻirliklari. Yigʻindisi 1.0 boʻlishi SHART — test buni tekshiradi.
RUBRIC: dict[str, float] = {
    "completeness": 0.30,  # toʻliqlik
    "accuracy": 0.30,  # aniqlik
    "citation": 0.20,  # iqtibos
    "reasoning": 0.20,  # mantiqiylik
}

#: Shu balldan boshlab javob oʻtgan hisoblanadi.
PASS_SCORE = 0.60

RUBRIC_LABELS: dict[str, str] = {
    "completeness": "toʻliqlik",
    "accuracy": "aniqlik",
    "citation": "iqtibos",
    "reasoning": "mantiqiylik",
}


class GradeResult(BaseModel):
    question_id: str
    score: float = Field(description="0.0–1.0")
    criteria: dict[str, float] = Field(default_factory=dict)
    feedback: list[str] = Field(default_factory=list)
    correct: bool | None = Field(default=None, description="Yopiq savol uchun")

    @property
    def passed(self) -> bool:
        return self.score >= PASS_SCORE

    @property
    def percent(self) -> int:
        return round(self.score * 100)


class QuizGrade(BaseModel):
    topic: str = ""
    grades: list[GradeResult] = Field(default_factory=list)
    score: float = 0.0
    answered: int = 0

    @property
    def passed(self) -> bool:
        return self.score >= PASS_SCORE

    @property
    def percent(self) -> int:
        return round(self.score * 100)


# --------------------------------------------------------------------------- #
# Matn bilan ishlash
# --------------------------------------------------------------------------- #

_ARTICLE_RE = re.compile(r"(\d+)\s*-\s*modda", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"[.!?]+\s+")

#: Fikr bogʻlovchilari — «mantiqiylik» mezoni shularni qidiradi.
_CONNECTIVES = (
    "chunki",
    "shuning uchun",
    "demak",
    "binobarin",
    "zero",
    "shu sababli",
    "birinchidan",
    "ikkinchidan",
    "aks holda",
    "shunga koʻra",
    "asosan",
)

#: Baholashda hisobga olinmaydigan yordamchi soʻzlar.
_STOPWORDS = frozenset(
    [
        "va",
        "bilan",
        "uchun",
        "yoki",
        "ammo",
        "lekin",
        "agar",
        "bu",
        "shu",
        "u",
        "ular",
        "ham",
        "emas",
        "bor",
        "yoq",
        "boladi",
        "bolishi",
        "kerak",
        "mumkin",
        "deb",
        "esa",
        "hamda",
        "hech",
        "har",
        "bir",
        "ushbu",
        "mazkur",
    ]
)

_MIN_TOKEN = 4


def _tokens(text: str) -> set[str]:
    """Maʼnoli soʻzlar toʻplami.

    `fold` apostrof va yozuv farqini yoʻqotadi, shuning uchun `oʻzgartirish`
    va `o'zgartirish` bir xil hisoblanadi.
    """
    words = re.findall(r"[a-z'0-9]+", fold(text))
    return {w for w in words if len(w) >= _MIN_TOKEN and w not in _STOPWORDS}


def _mentioned_articles(text: str) -> set[str]:
    return {m.group(1) for m in _ARTICLE_RE.finditer(text)}


def _distinctive_tokens(points: list[str]) -> list[set[str]]:
    """Har fikrning FAQAT OʻZIGA xos soʻzlari.

    NEGA KERAK. Kutilgan fikrlar bitta normadan olinadi va umumiy oʻzak
    soʻzlarni takrorlaydi: «Sinov muddati kelishuvga koʻra belgilanadi» va
    «Sinov muddati uch oydan oshmasligi kerak» — ikkalasida ham «sinov
    muddati» bor. Umumiy soʻzlar hisobga olinsa, faqat birinchi fikrni
    aytgan talaba ikkinchisini ham «yoritgan» hisoblanardi.
    """
    sets = [_tokens(p) for p in points]
    out: list[set[str]] = []
    for i, own in enumerate(sets):
        others = [s for j, s in enumerate(sets) if j != i]
        shared = set.intersection(*others) if others else set()
        # Hamma soʻzi umumiy boʻlsa — oʻz toʻplamini qoldiramiz, aks holda
        # fikrni qamrab boʻlmaydigan qilib qoʻygan boʻlardik.
        out.append((own - shared) or own)
    return out


def _covers(answer_tokens: set[str], needed: set[str]) -> bool:
    """Javob fikrni qamrab olganmi.

    Fikrga xos soʻzlarning yarmidan koʻpi javobda boʻlsa — qamragan
    hisoblanadi. Toʻliq moslik talab qilinmaydi: talaba gapni oʻz soʻzi
    bilan qurishi tabiiy.
    """
    if not needed:
        return False
    return len(needed & answer_tokens) / len(needed) >= 0.5


# --------------------------------------------------------------------------- #
# Mezonlar
# --------------------------------------------------------------------------- #


def _score_completeness(answer: str, question: QuizQuestion) -> tuple[float, str | None]:
    if not question.expected_points:
        # Kutilgan fikrlar koʻrsatilmagan — mezon qoʻllanmaydi, jazolash
        # notoʻgʻri boʻlardi.
        return 1.0, None
    tokens = _tokens(answer)
    needed = _distinctive_tokens(question.expected_points)
    hits = [_covers(tokens, n) for n in needed]
    score = sum(hits) / len(hits)
    if score < 1.0:
        missing = [p for p, ok in zip(question.expected_points, hits, strict=True) if not ok]
        return score, "Yoritilmagan fikrlar: " + "; ".join(missing[:3])
    return score, None


def _score_accuracy(answer: str, question: QuizQuestion) -> tuple[float, str | None]:
    """Javobdagi atamalar norma matniga mos keladimi.

    Toʻliqlikdan farqi: u javobda NIMA YETISHMAYOTGANINI oʻlchaydi, bu esa
    javobda AYTILGANI normadan kelib chiqqanmi. Shu ikkisi birga
    «hammasini aytdi, lekin oʻzidan toʻqib» holatini ushlaydi.
    """
    source = question.source_text or " ".join(question.expected_points)
    if not source.strip():
        return 1.0, None

    answer_tokens = _tokens(answer)
    if not answer_tokens:
        return 0.0, "Javob boʻsh."

    source_tokens = _tokens(source)
    if not source_tokens:
        return 1.0, None

    supported = len(answer_tokens & source_tokens) / len(answer_tokens)
    # Talaba tabiiy ravishda oʻz soʻzlarini ham qoʻshadi, shuning uchun
    # toʻliq moslik talab qilinmaydi: uchdan biri yetarli deb olinadi.
    score = min(1.0, supported / 0.34)
    if score < 0.7:
        return score, "Javobdagi atamalar norma matniga kam mos keladi."
    return score, None


def _score_citation(answer: str, question: QuizQuestion) -> tuple[float, str | None]:
    if not question.expected_articles:
        return 1.0, None
    found = _mentioned_articles(answer)
    hit = [a for a in question.expected_articles if a in found]
    score = len(hit) / len(question.expected_articles)
    if score < 1.0:
        missing = [a for a in question.expected_articles if a not in found]
        return score, "Iqtibos keltirilmagan modda: " + ", ".join(f"{a}-modda" for a in missing)
    return score, None


def _score_reasoning(answer: str) -> tuple[float, str | None]:
    """Javob asoslanganmi: tuzilishi va bogʻlovchilari bor-yoʻqligi."""
    text = answer.strip()
    if not text:
        return 0.0, "Javob boʻsh."

    sentences = [s for s in _SENTENCE_RE.split(text) if s.strip()]
    folded = fold(text)

    score = 0.0
    if len(sentences) >= 2:
        score += 0.5
    if any(c in folded for c in (fold(x) for x in _CONNECTIVES)):
        score += 0.5

    if score < 1.0:
        return score, "Javobda asoslash yetishmaydi (sabab-natija bogʻlanishi koʻrsatilmagan)."
    return score, None


# --------------------------------------------------------------------------- #
# Baholash
# --------------------------------------------------------------------------- #


def grade_answer(question: QuizQuestion, answer: str | int | bool | None) -> GradeResult:
    """Bitta javobni baholaydi.

    Yopiq savolda rubrika qoʻllanmaydi: u yerda «qisman toʻgʻri» degan
    narsa yoʻq — javob yo toʻgʻri, yo notoʻgʻri.
    """
    if question.is_closed:
        return _grade_closed(question, answer)

    text = "" if answer is None else str(answer)
    criteria: dict[str, float] = {}
    feedback: list[str] = []

    scored: list[tuple[str, tuple[float, str | None]]] = [
        ("completeness", _score_completeness(text, question)),
        ("accuracy", _score_accuracy(text, question)),
        ("citation", _score_citation(text, question)),
        ("reasoning", _score_reasoning(text)),
    ]
    for name, (value, note) in scored:
        criteria[name] = round(value, 3)
        if note:
            feedback.append(f"{RUBRIC_LABELS[name].capitalize()}: {note}")

    total = sum(criteria[name] * weight for name, weight in RUBRIC.items())
    return GradeResult(
        question_id=question.question_id,
        score=round(total, 3),
        criteria=criteria,
        feedback=feedback,
    )


def _grade_closed(question: QuizQuestion, answer: str | int | bool | None) -> GradeResult:
    correct = _closed_is_correct(question, answer)
    feedback: list[str] = []
    if not correct:
        feedback.append("Javob notoʻgʻri.")
        if question.explanation:
            feedback.append(question.explanation)
    return GradeResult(
        question_id=question.question_id,
        score=1.0 if correct else 0.0,
        criteria={"accuracy": 1.0 if correct else 0.0},
        feedback=feedback,
        correct=correct,
    )


def _closed_is_correct(question: QuizQuestion, answer: str | int | bool | None) -> bool:
    if answer is None:
        return False

    if question.kind is QuestionKind.TRUE_FALSE:
        return _as_bool(answer) is question.correct_bool

    # Koʻp tanlovli: raqam ham, variant matni ham qabul qilinadi —
    # foydalanuvchi qobigʻi qaysi shaklda yuborishini bilib boʻlmaydi.
    if isinstance(answer, bool):
        return False
    if isinstance(answer, int):
        return answer == question.correct_index
    text = str(answer).strip()
    if text.isdigit():
        return int(text) == question.correct_index
    if question.correct_index is None:
        return False
    if not 0 <= question.correct_index < len(question.options):
        return False
    return fold(text) == fold(question.options[question.correct_index])


#: Soʻzlar APOSTROFSIZ yozilgan: `fold` apostrofni ASCII `'` ga keltiradi,
#: keyin u ham olib tashlanadi. Shunda `toʻgʻri`, `to'g'ri` va `togri` —
#: uchalasi bir xil kalitga tushadi.
_TRUE_WORDS = frozenset({"ha", "togri", "rost", "true", "1", "+"})
_FALSE_WORDS = frozenset({"yoq", "notogri", "yolgon", "false", "0", "-"})


def _as_bool(answer: str | int | bool) -> bool | None:
    if isinstance(answer, bool):
        return answer
    if isinstance(answer, int):
        return bool(answer)
    word = fold(str(answer)).replace("'", "").strip()
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    return None


def grade_quiz(
    quiz: QuizResult,
    answers: dict[str, str | int | bool | None],
) -> QuizGrade:
    """Butun testni baholaydi.

    Javob berilmagan savol ham baholanadi (nol ball) — aks holda talaba
    savolni tashlab ketib yuqori foiz olardi.
    """
    grades = [grade_answer(q, answers.get(q.question_id)) for q in quiz.questions]
    total = sum(g.score for g in grades) / len(grades) if grades else 0.0
    return QuizGrade(
        topic=quiz.topic,
        grades=grades,
        score=round(total, 3),
        answered=sum(1 for q in quiz.questions if answers.get(q.question_id) is not None),
    )


# --------------------------------------------------------------------------- #
# Savol yasash
# --------------------------------------------------------------------------- #


class Retriever(Protocol):
    def search(self, query: str, *, top_k: int = 8, **kwargs: Any) -> Any: ...


def _first_sentence(text: str) -> str:
    clean = " ".join(str(text).split())
    parts = _SENTENCE_RE.split(clean)
    return (parts[0] if parts else clean).strip()


def _key_points(text: str, limit: int = 3) -> list[str]:
    """Norma matnidan kutilgan fikrlarni ajratadi — gaplar boʻyicha."""
    clean = " ".join(str(text).split())
    sentences = [s.strip() for s in _SENTENCE_RE.split(clean) if len(s.strip()) > 20]
    return sentences[:limit]


def _mc_question(qid: str, index: int, scored: list[Any]) -> QuizQuestion | None:
    """Koʻp tanlovli: qoida qaysi hujjatdan.

    Chalgʻituvchi variantlar boshqa normalarning hujjat nomlaridan olinadi
    — yaʼni oʻylab topilmaydi. Bazada bitta hujjat boʻlsa savol
    yasalmaydi: uch xil variant chiqmaydi.
    """
    chunk = scored[index].chunk
    correct = str(getattr(chunk, "doc_title", "")).strip()
    others: list[str] = []
    for item in scored:
        title = str(getattr(item.chunk, "doc_title", "")).strip()
        if title and title != correct and title not in others:
            others.append(title)
    if not correct or not others:
        return None

    options = [correct, *others[:3]]
    # Tartib barqaror boʻlishi kerak (test takrorlanadigan boʻlsin), lekin
    # toʻgʻri javob doim birinchi boʻlmasligi ham kerak.
    shift = index % len(options)
    rotated = options[shift:] + options[:shift]
    return QuizQuestion(
        question_id=qid,
        kind=QuestionKind.MULTIPLE_CHOICE,
        prompt=f"Quyidagi qoida qaysi hujjatda belgilangan?\n\n«{_first_sentence(chunk.content)}»",
        options=rotated,
        correct_index=rotated.index(correct),
        source_text=str(chunk.content),
        source_tag=f"C{index + 1}",
        explanation=f"Toʻgʻri javob: {correct}.",
    )


def _tf_question(qid: str, index: int, scored: list[Any]) -> QuizQuestion:
    """Toʻgʻri/notoʻgʻri: normadan olingan gap oʻzgartirilmaydi.

    Faqat TOʻGʻRI tasdiq yasaladi. Yolgʻon tasdiq yasash uchun normani
    buzib yozish kerak boʻlardi — bu talabaning xotirasida notoʻgʻri
    matn qoldirishi mumkin.
    """
    chunk = scored[index].chunk
    label = getattr(chunk, "citation_label", None) or getattr(chunk, "doc_title", "hujjat")
    return QuizQuestion(
        question_id=qid,
        kind=QuestionKind.TRUE_FALSE,
        prompt=f"«{_first_sentence(chunk.content)}» — bu qoida {label} da mavjudmi?",
        correct_bool=True,
        source_text=str(chunk.content),
        source_tag=f"C{index + 1}",
        explanation=f"Ha, qoida {label} da keltirilgan.",
    )


def _open_question(qid: str, index: int, scored: list[Any]) -> QuizQuestion:
    chunk = scored[index].chunk
    article = getattr(chunk, "article", None)
    title = getattr(chunk, "doc_title", "hujjat")
    subject = f"{title}ning {article}-moddasi" if article else str(title)
    return QuizQuestion(
        question_id=qid,
        kind=QuestionKind.OPEN,
        prompt=f"{subject} qanday holatni tartibga soladi? Javobingizni asoslang.",
        expected_points=_key_points(chunk.content),
        expected_articles=[str(article)] if article else [],
        source_text=str(chunk.content),
        source_tag=f"C{index + 1}",
    )


def generate_quiz(
    topic: Topic | str,
    retriever: Retriever | None = None,
    *,
    count: int = 6,
    kinds: list[QuestionKind] | None = None,
    top_k: int = 6,
) -> QuizResult:
    """Mavzu boʻyicha test tuzadi.

    Savollar bilim bazasidagi normalardan yasaladi. Norma topilmasa test
    boʻsh qaytadi — savolni oʻzidan toʻqish talabani notoʻgʻri
    oʻrgatishning eng qisqa yoʻli.
    """
    node = find_topic(topic) if isinstance(topic, str) else topic
    if node is None:
        raise ValueError(f"Mavzu topilmadi: {topic!r}")

    order = kinds or [QuestionKind.MULTIPLE_CHOICE, QuestionKind.TRUE_FALSE, QuestionKind.OPEN]
    caveats: list[str] = []

    if retriever is None:
        return QuizResult(
            topic=node.topic_id,
            title=node.title,
            caveats=["Qidiruv ulanmagan — test tuzilmadi."],
        )

    from uzlegal.education.lecture import collect_norms

    scored = collect_norms(node, retriever, top_k=top_k)
    if not scored:
        return QuizResult(
            topic=node.topic_id,
            title=node.title,
            caveats=["Bilim bazasida bu mavzu boʻyicha norma topilmadi — test tuzilmadi."],
        )

    questions: list[QuizQuestion] = []
    for i in range(count):
        index = i % len(scored)
        kind = order[i % len(order)]
        qid = f"{node.topic_id}.q{i + 1}"

        question: QuizQuestion | None
        if kind is QuestionKind.MULTIPLE_CHOICE:
            question = _mc_question(qid, index, scored)
            if question is None:
                # Chalgʻituvchi variant yoʻq — ochiq savolga almashtiramiz.
                question = _open_question(qid, index, scored)
        elif kind is QuestionKind.TRUE_FALSE:
            question = _tf_question(qid, index, scored)
        else:
            question = _open_question(qid, index, scored)
        questions.append(question)

    if len(scored) < count:
        caveats.append(
            f"Bazada {len(scored)} ta norma topildi, {count} ta savol soʻralgan — "
            "baʼzi savollar bir xil normadan tuzildi."
        )

    from uzlegal.education.lecture import to_citations

    return QuizResult(
        topic=node.topic_id,
        title=node.title,
        questions=questions,
        norms_cited=to_citations(scored),
        caveats=caveats,
    )
