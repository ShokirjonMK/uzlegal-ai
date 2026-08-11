"""Ish holati modeli — sud jarayonining tuzilishi va bosqichlari."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class CaseStage(StrEnum):
    PRETRIAL = "pretrial"
    FIRST_INSTANCE = "first_instance"
    APPEAL = "appeal"
    CASSATION = "cassation"
    SUPERVISORY = "supervisory"
    EXECUTION = "execution"


class CaseType(StrEnum):
    CRIMINAL = "criminal"
    CIVIL = "civil"
    ADMINISTRATIVE = "administrative"
    ECONOMIC = "economic"


class Party(BaseModel):
    name: str
    role: Literal[
        "plaintiff", "defendant", "prosecutor", "victim",
        "third_party", "witness", "accused", "civil_claimant",
    ]
    position: str = ""
    arguments: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    description: str
    source: str = ""
    strength: Literal["strong", "moderate", "weak"] = "moderate"
    admissible: bool = True
    challenges: list[str] = Field(default_factory=list)


class Deadline(BaseModel):
    action: str
    due_date: date
    legal_basis: str = ""
    extendable: bool = False


class CaseState(BaseModel):
    case_number: str = ""
    case_type: CaseType = CaseType.CIVIL
    stage: CaseStage = CaseStage.FIRST_INSTANCE
    court: str = ""
    judge: str = ""

    parties: list[Party] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)

    subject: str = ""
    disputed_amount: float | None = None
    filing_date: date | None = None
    hearing_date: date | None = None

    prior_decisions: list[str] = Field(default_factory=list)
    notes: str = ""


STAGE_ORDER = list(CaseStage)


def next_stage(current: CaseStage) -> CaseStage | None:
    idx = STAGE_ORDER.index(current)
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return None


def appeal_deadline_days(case_type: CaseType, stage: CaseStage) -> int | None:
    table: dict[tuple[CaseType, CaseStage], int] = {
        (CaseType.CIVIL, CaseStage.FIRST_INSTANCE): 30,
        (CaseType.CIVIL, CaseStage.APPEAL): 30,
        (CaseType.CRIMINAL, CaseStage.FIRST_INSTANCE): 20,
        (CaseType.CRIMINAL, CaseStage.APPEAL): 30,
        (CaseType.ADMINISTRATIVE, CaseStage.FIRST_INSTANCE): 15,
        (CaseType.ECONOMIC, CaseStage.FIRST_INSTANCE): 30,
        (CaseType.ECONOMIC, CaseStage.APPEAL): 30,
    }
    return table.get((case_type, stage))


def find_party(case: CaseState, role: str) -> Party | None:
    for p in case.parties:
        if p.role == role:
            return p
    return None


def strong_evidence(case: CaseState) -> list[Evidence]:
    return [e for e in case.evidence if e.strength == "strong" and e.admissible]


def weak_evidence(case: CaseState) -> list[Evidence]:
    return [e for e in case.evidence if e.strength == "weak" or not e.admissible]


def expired_deadlines(case: CaseState, today: date | None = None) -> list[Deadline]:
    today = today or date.today()
    return [d for d in case.deadlines if d.due_date < today]
