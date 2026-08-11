"""Sud jarayoni yordamchisi testlari."""

from __future__ import annotations

from datetime import date

import pytest

from uzlegal.litigation.advisor import StrategicAdvice, advise
from uzlegal.litigation.case import (
    CaseStage,
    CaseState,
    CaseType,
    Deadline,
    Evidence,
    Party,
    appeal_deadline_days,
    expired_deadlines,
    find_party,
    next_stage,
    strong_evidence,
    weak_evidence,
)
from uzlegal.litigation.questions import generate_questions

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def criminal_case() -> CaseState:
    return CaseState(
        case_number="01-234/2026",
        case_type=CaseType.CRIMINAL,
        stage=CaseStage.FIRST_INSTANCE,
        court="Toshkent shahar jinoyat sudi",
        judge="A. Karimov",
        subject="Oʻgʻirlik — JK 169-modda",
        parties=[
            Party(
                name="Davlat",
                role="prosecutor",
                arguments=["Ayblanuvchi voqea joyidan ushlanib qolgan"],
            ),
            Party(
                name="Aliyev I.R.",
                role="accused",
                arguments=["Men u yerda boʻlmaganman", "Alibi — guvoh bor"],
            ),
            Party(name="Salimov D.K.", role="victim"),
        ],
        evidence=[
            Evidence(
                description="Voqea joyidan barmoq izlari",
                source="Ekspertiza xulosasi #42",
                strength="strong",
            ),
            Evidence(
                description="Guvoh Rahimov koʻrsatmasi",
                source="Tergov bayonnomasi",
                strength="moderate",
                challenges=["Guvoh ayblanuvchining qaridonashisi"],
            ),
            Evidence(
                description="Qoʻlga olingan buyumlar",
                source="Tintuv bayonnomasi",
                strength="strong",
                admissible=True,
            ),
            Evidence(
                description="Noqonuniy tintuv natijasi",
                source="Tintuv bayonnomasi #2",
                strength="weak",
                admissible=False,
                challenges=["Sanksiyasiz oʻtkazilgan"],
            ),
        ],
        deadlines=[
            Deadline(
                action="Sudya rad etish uchun ariza",
                due_date=date(2026, 8, 5),
                legal_basis="JPK 76-modda",
            ),
        ],
        filing_date=date(2026, 7, 1),
    )


@pytest.fixture()
def civil_case() -> CaseState:
    return CaseState(
        case_number="05-678/2026",
        case_type=CaseType.CIVIL,
        stage=CaseStage.APPEAL,
        court="Toshkent viloyati fuqarolik sudi",
        subject="Mulk talabi — FK 206-modda",
        parties=[
            Party(
                name="Karimova S.",
                role="plaintiff",
                arguments=["Mulk sotib olingan", "Shartnoma bor"],
            ),
            Party(
                name="Ergashev B.",
                role="defendant",
                arguments=["Shartnoma soxtalashtrilgan"],
            ),
        ],
        evidence=[
            Evidence(description="Oldi-sotdi shartnomasi", strength="strong"),
            Evidence(description="Guvoh koʻrsatmasi", strength="moderate"),
        ],
        disputed_amount=500_000_000,
    )


# ── Case Model ────────────────────────────────────────────────────────────────


class TestCaseModel:
    def test_find_party_exists(self, criminal_case: CaseState) -> None:
        p = find_party(criminal_case, "accused")
        assert p is not None
        assert p.name == "Aliyev I.R."

    def test_find_party_missing(self, criminal_case: CaseState) -> None:
        assert find_party(criminal_case, "expert") is None

    def test_strong_evidence(self, criminal_case: CaseState) -> None:
        s = strong_evidence(criminal_case)
        assert len(s) == 2
        assert all(e.strength == "strong" for e in s)

    def test_weak_evidence_includes_inadmissible(self, criminal_case: CaseState) -> None:
        w = weak_evidence(criminal_case)
        assert len(w) >= 1
        assert any(not e.admissible for e in w)

    def test_expired_deadlines(self, criminal_case: CaseState) -> None:
        expired = expired_deadlines(criminal_case, today=date(2026, 8, 11))
        assert len(expired) == 1
        assert expired[0].action == "Sudya rad etish uchun ariza"

    def test_no_expired_deadlines(self, criminal_case: CaseState) -> None:
        expired = expired_deadlines(criminal_case, today=date(2026, 7, 1))
        assert len(expired) == 0

    def test_next_stage(self) -> None:
        assert next_stage(CaseStage.FIRST_INSTANCE) == CaseStage.APPEAL
        assert next_stage(CaseStage.APPEAL) == CaseStage.CASSATION
        assert next_stage(CaseStage.EXECUTION) is None

    def test_appeal_deadline_days(self) -> None:
        assert appeal_deadline_days(CaseType.CIVIL, CaseStage.FIRST_INSTANCE) == 30
        assert appeal_deadline_days(CaseType.CRIMINAL, CaseStage.FIRST_INSTANCE) == 20
        assert appeal_deadline_days(CaseType.ADMINISTRATIVE, CaseStage.FIRST_INSTANCE) == 15
        assert appeal_deadline_days(CaseType.CIVIL, CaseStage.EXECUTION) is None


# ── Advisor ───────────────────────────────────────────────────────────────────


class TestAdvisor:
    def test_advocate_strategy_has_strengths(self, criminal_case: CaseState) -> None:
        advice = advise(criminal_case, "advocate")
        assert advice.role == "advocate"
        assert len(advice.strengths) > 0
        assert len(advice.recommended_actions) > 0
        assert advice.disclaimer

    def test_advocate_finds_inadmissible_evidence(self, criminal_case: CaseState) -> None:
        advice = advise(criminal_case, "advocate")
        weakness_text = " ".join(advice.weaknesses)
        assert "qabul qilinmasligi" in weakness_text.lower() or "zaif" in weakness_text.lower()

    def test_advocate_appeal_info(self, criminal_case: CaseState) -> None:
        advice = advise(criminal_case, "advocate")
        assert advice.appeal_info is not None
        assert advice.appeal_info.available
        assert advice.appeal_info.deadline_days == 20
        assert len(advice.appeal_info.grounds) > 0

    def test_prosecutor_strategy(self, criminal_case: CaseState) -> None:
        advice = advise(criminal_case, "prosecutor")
        assert advice.role == "prosecutor"
        assert len(advice.counter_arguments) > 0

    def test_judge_strategy_is_neutral(self, criminal_case: CaseState) -> None:
        advice = advise(criminal_case, "judge")
        assert advice.role == "judge"
        assert advice.confidence == 0.5
        assert len(advice.recommended_actions) >= 3

    def test_civil_case_advocate(self, civil_case: CaseState) -> None:
        advice = advise(civil_case, "advocate")
        assert advice.role == "advocate"
        assert (
            "appeal" in advice.appeal_info.next_stage
            or "cassation" in advice.appeal_info.next_stage
        )

    def test_confidence_calculation(self, criminal_case: CaseState) -> None:
        advice = advise(criminal_case, "advocate")
        assert 0.1 <= advice.confidence <= 0.9

    def test_empty_case_doesnt_crash(self) -> None:
        empty = CaseState()
        for role in ("advocate", "prosecutor", "judge"):
            advice = advise(empty, role)
            assert isinstance(advice, StrategicAdvice)
            assert advice.disclaimer


# ── Questions ─────────────────────────────────────────────────────────────────


class TestQuestions:
    def test_advocate_questions_for_prosecutor(self, criminal_case: CaseState) -> None:
        plan = generate_questions(criminal_case, "prosecutor", as_role="advocate")
        assert plan.role == "advocate"
        assert len(plan.questions) > 0
        assert any(q.category == "challenging" for q in plan.questions)

    def test_advocate_questions_for_witness(self, criminal_case: CaseState) -> None:
        plan = generate_questions(criminal_case, "witness", as_role="advocate")
        assert len(plan.questions) >= 2

    def test_prosecutor_questions_for_accused(self, criminal_case: CaseState) -> None:
        plan = generate_questions(criminal_case, "accused", as_role="prosecutor")
        assert plan.role == "prosecutor"
        assert len(plan.questions) > 0
        assert any(q.priority == "high" for q in plan.questions)

    def test_judge_questions(self, civil_case: CaseState) -> None:
        plan = generate_questions(civil_case, "plaintiff", as_role="judge")
        assert plan.role == "judge"
        assert len(plan.questions) >= 3

    def test_max_questions_limit(self, criminal_case: CaseState) -> None:
        plan = generate_questions(criminal_case, "prosecutor", as_role="advocate", max_questions=3)
        assert len(plan.questions) <= 3

    def test_strategy_note_present(self, criminal_case: CaseState) -> None:
        plan = generate_questions(criminal_case, "accused", as_role="prosecutor")
        assert plan.strategy_note
        assert "ayblov" in plan.strategy_note.lower()

    def test_inadmissible_evidence_generates_trap_question(self, criminal_case: CaseState) -> None:
        plan = generate_questions(criminal_case, "prosecutor", as_role="advocate")
        trap_questions = [q for q in plan.questions if q.category == "trap"]
        assert len(trap_questions) >= 1
