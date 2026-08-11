"""Guvoh va tomonga savol generatsiyasi — maqsadli va qopqon savollari."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from uzlegal.litigation.case import CaseState, CaseType, find_party


class Question(BaseModel):
    text: str
    purpose: str = ""
    target: str = ""
    category: Literal["factual", "clarifying", "challenging", "trap"] = "factual"
    priority: Literal["high", "medium", "low"] = "medium"


class QuestionPlan(BaseModel):
    target_party: str
    role: str
    questions: list[Question] = Field(default_factory=list)
    strategy_note: str = ""


def generate_questions(
    case: CaseState,
    target_role: str,
    *,
    as_role: Literal["advocate", "prosecutor", "judge"] = "advocate",
    max_questions: int = 10,
) -> QuestionPlan:
    target = find_party(case, target_role)
    target_name = target.name if target else target_role

    generators = {
        "advocate": _advocate_questions,
        "prosecutor": _prosecutor_questions,
        "judge": _judge_questions,
    }
    fn = generators.get(as_role, _advocate_questions)
    questions = fn(case, target_role)

    return QuestionPlan(
        target_party=target_name,
        role=as_role,
        questions=questions[:max_questions],
        strategy_note=_strategy_note(as_role, target_role, case),
    )


def _advocate_questions(case: CaseState, target_role: str) -> list[Question]:
    questions: list[Question] = []

    if target_role in ("witness", "victim"):
        questions.append(
            Question(
                text="Voqea sodir boʻlgan vaqtda siz qayerda edingiz?",
                purpose="Guvohning joylashuvini aniqlash",
                target=target_role,
                category="factual",
                priority="high",
            )
        )
        questions.append(
            Question(
                text="Voqeani boshqa kimdir koʻrganmi?",
                purpose="Mustaqil tasdiqlash mavjudligi",
                target=target_role,
                category="clarifying",
            )
        )
        questions.append(
            Question(
                text="Oldingi koʻrsatmalaringiz bilan hozirgi gapingiz "
                "oʻrtasida farq bor — tushuntirib bera olasizmi?",
                purpose="Qarama-qarshiliklarni ochish",
                target=target_role,
                category="challenging",
                priority="high",
            )
        )

    if target_role in ("prosecutor", "plaintiff"):
        for e in case.evidence:
            if e.strength == "strong":
                questions.append(
                    Question(
                        text=f"«{e.description}» dalili qanday olingan? "
                        "Protsessual tartib buzilmaganmi?",
                        purpose="Dalil olish qonuniyligini tekshirish",
                        target=target_role,
                        category="challenging",
                        priority="high",
                    )
                )
            if not e.admissible:
                questions.append(
                    Question(
                        text=f"«{e.description}» dalili qabul qilinmaydigan — "
                        "nima uchun uni keltiryapsiz?",
                        purpose="Noadmissible dalilni rad etish",
                        target=target_role,
                        category="trap",
                        priority="high",
                    )
                )

    if case.case_type == CaseType.CRIMINAL:
        questions.append(
            Question(
                text="Ayblanuvchiga himoyachi tayinlanganmi va qachon?",
                purpose="Himoya huquqi buzilganmi tekshirish",
                target=target_role,
                category="factual",
                priority="high",
            )
        )

    return questions


def _prosecutor_questions(case: CaseState, target_role: str) -> list[Question]:
    questions: list[Question] = []

    if target_role in ("defendant", "accused"):
        questions.append(
            Question(
                text="Voqea sodir boʻlgan vaqtda qayerda edingiz?",
                purpose="Alibini tekshirish",
                target=target_role,
                category="factual",
                priority="high",
            )
        )
        questions.append(
            Question(
                text="Jabrlanuvchi bilan oldindan munosabatingiz bormi?",
                purpose="Motivni aniqlash",
                target=target_role,
                category="factual",
            )
        )

        defendant = find_party(case, target_role)
        if defendant:
            for arg in defendant.arguments:
                questions.append(
                    Question(
                        text=f"Siz «{arg}» deb aytdingiz — buni qanday isbotlaysiz?",
                        purpose="Mudofaa argumentining asossizligini koʻrsatish",
                        target=target_role,
                        category="challenging",
                        priority="high",
                    )
                )

    if target_role == "witness":
        questions.append(
            Question(
                text="Ayblanuvchi bilan qanday tanishsiz?",
                purpose="Guvohning xolisligini tekshirish",
                target=target_role,
                category="clarifying",
            )
        )
        questions.append(
            Question(
                text="Sizga bu koʻrsatma berish uchun kimdir murojaat qildimi?",
                purpose="Guvohga taʼsir qilinganmi aniqlash",
                target=target_role,
                category="trap",
                priority="high",
            )
        )

    return questions


def _judge_questions(case: CaseState, target_role: str) -> list[Question]:
    questions: list[Question] = []

    questions.append(
        Question(
            text="Oʻz pozitsiyangizni qisqacha bayon qiling.",
            purpose="Pozitsiyani aniq tushunish",
            target=target_role,
            category="factual",
            priority="high",
        )
    )
    questions.append(
        Question(
            text="Qoʻshimcha dalil yoki guvoh taqdim etmoqchimisiz?",
            purpose="Dalillar bazasini toʻldirish",
            target=target_role,
            category="clarifying",
        )
    )
    questions.append(
        Question(
            text="Qarshi tomon argumentlariga nima deysiz?",
            purpose="Ikki tomon pozitsiyasini solishtrish",
            target=target_role,
            category="clarifying",
            priority="high",
        )
    )

    if case.disputed_amount:
        questions.append(
            Question(
                text="Da'vo summasini qanday hisoblangansiz?",
                purpose="Summaning asoslanganligini tekshirish",
                target=target_role,
                category="factual",
            )
        )

    return questions


def _strategy_note(as_role: str, target_role: str, case: CaseState) -> str:
    if as_role == "advocate":
        return (
            "Mudofaa strategiyasi: dalillarning olish tartibini tekshiring, "
            "guvoh koʻrsatmalarida qarama-qarshilik qidiring, "
            "protsessual buzilishlarni qayd qiling."
        )
    if as_role == "prosecutor":
        return (
            "Ayblov strategiyasi: har bir element uchun dalil tayyorlang, "
            "mudofaa argumentlarini oldingdan rad eting, "
            "guvoh koʻrsatmalarini tekshiring."
        )
    return (
        "Sud strategiyasi: ikkala tomonni xolisona tinglang, "
        "dalillarni baholang, protsessual qoidalarga rioya qilinishini tekshiring."
    )
