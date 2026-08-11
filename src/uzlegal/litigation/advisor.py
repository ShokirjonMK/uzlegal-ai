"""Rol boʻyicha sud jarayoni strategiyasi — advokat, prokuror yoki sudya."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from uzlegal.litigation.case import (
    CaseStage,
    CaseState,
    CaseType,
    appeal_deadline_days,
    expired_deadlines,
    find_party,
    next_stage,
    strong_evidence,
    weak_evidence,
)
from uzlegal.types import Argument, Citation


class StrategicAdvice(BaseModel):
    role: str
    case_summary: str
    strengths: list[Argument] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    counter_arguments: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    applicable_norms: list[Citation] = Field(default_factory=list)
    appeal_info: AppealInfo | None = None
    confidence: float = 0.5
    disclaimer: str = (
        "Bu strategik tavsiya avtomatik tizim tomonidan tayyorlangan. "
        "Malakali yurist maslahati oʻrnini bosmaydi."
    )


class AppealInfo(BaseModel):
    available: bool = False
    next_stage: str = ""
    deadline_days: int | None = None
    grounds: list[str] = Field(default_factory=list)


StrategicAdvice.model_rebuild()


def advise(
    case: CaseState,
    role: Literal["advocate", "prosecutor", "judge"],
    *,
    norms: list[Citation] | None = None,
) -> StrategicAdvice:
    norms = norms or []
    builders = {
        "advocate": _advocate_strategy,
        "prosecutor": _prosecutor_strategy,
        "judge": _judge_strategy,
    }
    return builders[role](case, norms)


def _advocate_strategy(case: CaseState, norms: list[Citation]) -> StrategicAdvice:
    defendant = find_party(case, "defendant") or find_party(case, "accused")
    strong = strong_evidence(case)
    weak = weak_evidence(case)
    expired = expired_deadlines(case)

    strengths = []
    for e in strong:
        if e.admissible:
            strengths.append(
                Argument(
                    claim=f"Kuchli dalil: {e.description}",
                    citations=[e.source] if e.source else [],
                    strength="strong",
                )
            )

    weaknesses = []
    for e in weak:
        weaknesses.append(f"Zaif dalil: {e.description}")
        if not e.admissible:
            weaknesses.append(f"Dalil qabul qilinmasligi mumkin: {e.description}")

    actions = [
        "Har bir ayblov elementiga alohida javob tayyorlang",
        "Protsessual buzilishlarni aniqlang va qayd qiling",
    ]

    if defendant and defendant.arguments:
        actions.append(f"Mudofaa pozitsiyasini mustahkamlang: {defendant.arguments[0]}")

    if expired:
        actions.append(
            f"Muddati oʻtgan harakatlar topildi ({len(expired)} ta) — "
            "tiklash imkoniyatini tekshiring"
        )

    if case.stage != CaseStage.EXECUTION:
        ns = next_stage(case.stage)
        days = appeal_deadline_days(case.case_type, case.stage)
        appeal = AppealInfo(
            available=ns is not None,
            next_stage=ns.value if ns else "",
            deadline_days=days,
            grounds=_appeal_grounds(case),
        )
    else:
        appeal = AppealInfo(available=False)

    questions = _generate_defense_questions(case)
    risks = _identify_risks(case, "advocate")

    counter_args = []
    plaintiff = find_party(case, "plaintiff") or find_party(case, "prosecutor")
    if plaintiff:
        for arg in plaintiff.arguments:
            counter_args.append(f"Qarshi argument: «{arg}» — dalillar bazasi tekshirilsin")

    return StrategicAdvice(
        role="advocate",
        case_summary=_summarize(case),
        strengths=strengths,
        weaknesses=weaknesses,
        recommended_actions=actions,
        risks=risks,
        counter_arguments=counter_args,
        questions_to_ask=questions,
        applicable_norms=norms,
        appeal_info=appeal,
        confidence=_calc_confidence(strengths, weaknesses),
    )


def _prosecutor_strategy(case: CaseState, norms: list[Citation]) -> StrategicAdvice:
    strong = strong_evidence(case)

    strengths = []
    for e in strong:
        strengths.append(
            Argument(
                claim=f"Ayblov dalili: {e.description}",
                citations=[e.source] if e.source else [],
                strength="strong",
            )
        )

    weaknesses = []
    for e in case.evidence:
        for ch in e.challenges:
            weaknesses.append(f"Dalilga eʼtiroz: {ch}")

    actions = [
        "Ayblov har bir elementini dalillar bilan tasdiqlang",
        "Guvohlarning koʻrsatmalarida qarama-qarshilik bormi tekshiring",
    ]

    if case.case_type == CaseType.CRIMINAL:
        actions.append("Jinoiy javobgarlik elementlarini alohida isbotlang")

    questions = _generate_prosecution_questions(case)
    risks = _identify_risks(case, "prosecutor")

    defendant = find_party(case, "defendant") or find_party(case, "accused")
    counter_args = []
    if defendant:
        for arg in defendant.arguments:
            counter_args.append(f"Mudofaaning «{arg}» argumentiga qarshi dalil tayyorlang")

    return StrategicAdvice(
        role="prosecutor",
        case_summary=_summarize(case),
        strengths=strengths,
        weaknesses=weaknesses,
        recommended_actions=actions,
        risks=risks,
        counter_arguments=counter_args,
        questions_to_ask=questions,
        applicable_norms=norms,
        confidence=_calc_confidence(strengths, weaknesses),
    )


def _judge_strategy(case: CaseState, norms: list[Citation]) -> StrategicAdvice:
    expired = expired_deadlines(case)

    actions = [
        "Har ikkala tomon dalillarini xolisona baholang",
        "Protsessual qoidalarga rioya qilinganligini tekshiring",
        "Qarorni asoslash uchun barcha tegishli normalarni keltiring",
    ]

    if expired:
        actions.append(f"{len(expired)} ta muddati oʻtgan harakat — sababini aniqlang")

    risks = [
        "Xolislikni saqlash — ikki tomon dalillariga teng munosabat",
        "Qaror motivatsiyasi toʻliq boʻlishi kerak",
    ]

    if case.disputed_amount and case.disputed_amount > 1_000_000_000:
        risks.append("Katta summali ish — yuqori diqqat talab qiladi")

    weaknesses = []
    all_admissible = [e for e in case.evidence if e.admissible]
    inadmissible = [e for e in case.evidence if not e.admissible]
    if inadmissible:
        weaknesses.append(f"{len(inadmissible)} ta dalil qabul qilinmasligi mumkin")
    if len(all_admissible) < 2:
        weaknesses.append("Dalillar bazasi juda tor — qaror asossiz boʻlishi mumkin")

    questions = [
        "Ikkala tomon ham oʻz pozitsiyasini toʻliq asosladimi?",
        "Taqdim etilgan dalillar yetarlimi?",
        "Protsessual huquqlar buzilmaganmi?",
    ]

    return StrategicAdvice(
        role="judge",
        case_summary=_summarize(case),
        strengths=[],
        weaknesses=weaknesses,
        recommended_actions=actions,
        risks=risks,
        counter_arguments=[],
        questions_to_ask=questions,
        applicable_norms=norms,
        confidence=0.5,
    )


def _summarize(case: CaseState) -> str:
    parts = []
    if case.case_number:
        parts.append(f"Ish #{case.case_number}")
    parts.append(f"{case.case_type.value} ishi")
    parts.append(f"bosqich: {case.stage.value}")
    if case.court:
        parts.append(f"sud: {case.court}")
    if case.subject:
        parts.append(f"predmet: {case.subject}")
    party_names = [f"{p.name} ({p.role})" for p in case.parties[:4]]
    if party_names:
        parts.append(f"tomonlar: {', '.join(party_names)}")
    return " | ".join(parts)


def _calc_confidence(strengths: list[Argument], weaknesses: list[str]) -> float:
    s = len(strengths)
    w = len(weaknesses)
    if s + w == 0:
        return 0.3
    return round(min(0.9, max(0.1, s / (s + w))), 2)


def _appeal_grounds(case: CaseState) -> list[str]:
    grounds = []
    if expired_deadlines(case):
        grounds.append("Protsessual muddatlar buzilgan")
    inadmissible = [e for e in case.evidence if not e.admissible]
    if inadmissible:
        grounds.append("Qabul qilinmaydigan dalillar asosida qaror chiqarilgan")
    if len(case.evidence) < 2:
        grounds.append("Dalillar bazasi yetarli emas")
    grounds.append("Moddiy yoki protsessual qonun notoʻgʻri qoʻllanilgan")
    return grounds


def _identify_risks(case: CaseState, role: str) -> list[str]:
    risks = []
    if not case.evidence:
        risks.append("Dalillar taqdim etilmagan — pozitsiya zaif")
    weak = [e for e in case.evidence if e.strength == "weak"]
    if len(weak) > len(case.evidence) // 2:
        risks.append("Koʻpchilik dalillar zaif — natija noaniq")
    if case.stage == CaseStage.CASSATION:
        risks.append("Kassatsiyada yangi dalil qabul qilinmaydi")
    if role == "advocate" and case.case_type == CaseType.CRIMINAL:
        risks.append("Jinoyat ishida isbotlash yuki prokurorda — lekin faol mudofaa zarur")
    return risks


def _generate_defense_questions(case: CaseState) -> list[str]:
    questions = []
    plaintiff = find_party(case, "plaintiff") or find_party(case, "prosecutor")
    if plaintiff:
        questions.append(f"{plaintiff.name} ning da'vosi uchun barcha dalillar bormi?")
    for e in case.evidence:
        if e.strength == "strong" and e.challenges:
            questions.append(f"«{e.description}» dalilining olish tartibi qonuniymi?")
    if case.case_type == CaseType.CRIMINAL:
        questions.append("Ayblanuvchining himoya huquqi toʻliq taʼminlanganmi?")
        questions.append("Tekshiruv xarakatlari sanksiya bilan bajarilganmi?")
    return questions[:8]


def _generate_prosecution_questions(case: CaseState) -> list[str]:
    questions = []
    defendant = find_party(case, "defendant") or find_party(case, "accused")
    if defendant and defendant.arguments:
        for arg in defendant.arguments[:3]:
            questions.append(f"«{arg}» da'vosini qanday dalil bilan rad etasiz?")
    questions.append("Barcha guvohlar koʻrsatmalari bir-biriga mosmi?")
    if case.case_type == CaseType.CRIMINAL:
        questions.append("Jinoiy niyat (umid) qanday isbotlanadi?")
    return questions[:8]
