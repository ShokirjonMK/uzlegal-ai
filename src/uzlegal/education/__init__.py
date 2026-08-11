"""Taʼlim moduli — oʻquv dasturi, leksiya va test.

Uch qism bir-biriga tayanadi: dastur mavzuni beradi, leksiya mavzu
boʻyicha normalarni topib tushuntiradi, test oʻsha normalardan savol
yasab talabani baholaydi. Uchalasi ham bilim bazasidagi HAQIQIY
matnga tayanadi — modda raqamlari hech qayerda qoʻlda yozilmagan.
"""

from uzlegal.education.curriculum import (
    SUBJECTS,
    Branch,
    Level,
    Subject,
    Topic,
    all_topics,
    coverage,
    find_topic,
    learning_path,
    search_topics,
    subject,
)
from uzlegal.education.lecture import LectureResult, collect_norms, generate_lecture
from uzlegal.education.quiz import (
    PASS_SCORE,
    RUBRIC,
    GradeResult,
    QuestionKind,
    QuizGrade,
    QuizQuestion,
    QuizResult,
    generate_quiz,
    grade_answer,
    grade_quiz,
)

__all__ = [
    "PASS_SCORE",
    "RUBRIC",
    "SUBJECTS",
    "Branch",
    "GradeResult",
    "LectureResult",
    "Level",
    "QuestionKind",
    "QuizGrade",
    "QuizQuestion",
    "QuizResult",
    "Subject",
    "Topic",
    "all_topics",
    "collect_norms",
    "coverage",
    "find_topic",
    "generate_lecture",
    "generate_quiz",
    "grade_answer",
    "grade_quiz",
    "learning_path",
    "search_topics",
    "subject",
]
