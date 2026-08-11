"""Beshta rol — docs/06 § 2 dagi shartnomalar.

Har bir rol uchta narsa bilan belgilanadi:

| Nima | Qayerda |
|------|---------|
| Xatti-harakat (prompt) | `prompts/roles/<role>.uz.md` |
| Sozlama (harorat, adapter) | `configs/agents/<role>.yaml` |
| Shartnoma (kirish/chiqish) | shu fayl |

Kod faqat uchinchisini biladi. Promptni tahrirlash yoki haroratni o'zgartirish
uchun bu faylga tegish shart emas — bu Faza 3 va 4 da yurist ekspert bilan
ishlashni osonlashtiradi.
"""

from __future__ import annotations

import re
from typing import Any

from uzlegal.agents.base import (
    AgentContext,
    BaseAgent,
    as_list,
    extract_tags,
    parse_confidence,
    parse_sections,
    strip_bullet,
)
from uzlegal.agents.schemas import DoctrinalAnalysis, LegalFrame, Verdict
from uzlegal.types import Argument, Citation, Position

ROLE_ORDER = ["jurist", "advocate", "prosecutor", "professor", "judge"]

# Matndagi kuch belgisi → sxema qiymati
_STRENGTH = {
    "kuchli": "strong",
    "strong": "strong",
    "o'rtacha": "moderate",
    "orta": "moderate",
    "moderate": "moderate",
    "zaif": "weak",
    "weak": "weak",
}
_STRENGTH_RE = re.compile(r"^\s*\[([^\]]{2,12})\]\s*")


# --------------------------------------------------------------------------- #
# Prompt uchun ko'rinishlar
# --------------------------------------------------------------------------- #


def render_frame(frame: LegalFrame) -> str:
    """`LegalFrame` ni promptga tushadigan matnga aylantiradi.

    JSON emas, o'qiladigan matn: model o'zbek tilidagi ro'yxatni JSON
    strukturasidan yaxshiroq tushunadi va uni takrorlashga urinmaydi.
    """
    blocks = [_bullets("FAKTLAR", frame.facts), _bullets("HUQUQIY SAVOLLAR", frame.legal_questions)]
    if frame.applicable_norms:
        blocks.append(
            "TEGISHLI NORMALAR\n"
            + "\n".join(
                f"- [{c.tag}] {c.doc_title or c.doc_id}, {c.article}-modda"
                for c in frame.applicable_norms
            )
        )
    blocks.append(_bullets("NOMA'LUM", frame.unknowns))
    return "\n\n".join(b for b in blocks if b)


def render_position(position: Position, title: str | None = None) -> str:
    head = title or f"{position.role.upper()} POZITSIYASI"
    lines = [f"{head}\n{position.stance}"]
    if position.arguments:
        lines.append(
            "DALILLAR\n"
            + "\n".join(
                f"- [{a.strength}] {a.claim} " + " ".join(f"[{t}]" for t in a.citations)
                for a in position.arguments
            )
        )
    lines.append(_bullets("ZAIF TOMONLAR", position.weaknesses))
    lines.append(f"ISHONCH: {position.confidence:.2f}")
    return "\n\n".join(x for x in lines if x)


def render_doctrine(doctrine: DoctrinalAnalysis) -> str:
    blocks = [f"DOKTRINAL SHARH\n{doctrine.summary}" if doctrine.summary else ""]
    blocks.append(_bullets("DOKTRINALAR", doctrine.doctrines))
    blocks.append(_bullets("KOLLIZIYALAR", doctrine.collisions))
    blocks.append(_bullets("QIYOSIY HUQUQ", doctrine.comparative))
    return "\n\n".join(b for b in blocks if b)


def _bullets(title: str, items: list[str]) -> str:
    return f"{title}\n" + "\n".join(f"- {i}" for i in items) if items else ""


def _tags_from(value: Any) -> list[str]:
    """Modeldan kelgan iqtibos maydonini belgilarga keltiradi.

    Model bir joyda `["C1"]`, boshqa joyda `[{"tag": "C1", …}]` yoki
    `"[C1], [C2]"` qaytaradi — uchalasi ham qabul qilinadi.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return extract_tags(value) or [value.strip().strip("[]").upper()]
    out: list[str] = []
    for item in value if isinstance(value, list) else [value]:
        if isinstance(item, dict):
            tag = item.get("tag") or item.get("citation") or item.get("id")
            if tag:
                out.append(str(tag).strip().strip("[]").upper())
        elif isinstance(item, str) and item.strip():
            out.extend(extract_tags(item) or [item.strip().strip("[]").upper()])
    return [t for t in out if re.fullmatch(r"C\d{1,3}", t)]


def _parse_arguments(lines: list[str]) -> list[Argument]:
    """`[kuchli] Da'vo. Asos: [C1], [C4]` ko'rinishidagi satrlarni o'qiydi."""
    out: list[Argument] = []
    for line in lines:
        text = strip_bullet(line)
        strength = "moderate"
        m = _STRENGTH_RE.match(text)
        if m and m.group(1).lower() in _STRENGTH:
            strength = _STRENGTH[m.group(1).lower()]
            text = text[m.end() :]
        tags = extract_tags(text)
        claim = _TAGS_ONLY.sub(" ", text).strip(" .,;")
        if claim:
            out.append(Argument(claim=claim, citations=tags, strength=strength))  # type: ignore[arg-type]
    return out


_TAGS_ONLY = re.compile(r"(?:Asos\s*:\s*)?\[\s*C\d{1,3}\s*\]", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# jurist — neytral ramka
# --------------------------------------------------------------------------- #


def _grounded_answer(answer: str, ctx: AgentContext) -> str:
    """Iqtibosga bog'lanmagan javobni tashlaydi.

    Nima uchun manbada, gate da emas: gate baribir belgisiz huquqiy gapni
    o'chiradi. Lekin u **butun javobni** o'chirsa, `simple` oqim
    «ishonchli javob shakllantirilmadi» deb tugaydi — foydalanuvchi
    topilgan normalarni ham ko'rmaydi.

    Bu yerda tashlansa esa `draft_answer()` tegishli normalar ro'yxatiga
    tushadi va foydalanuvchi kamida qaysi moddalar tegishli ekanini
    ko'radi. Ya'ni bu **yumshoq degradatsiya**, yashirish emas: hech
    qanday tasdiqlanmagan gap javobga chiqmaydi.
    """
    if not answer:
        return ""
    if ctx.resolve(extract_tags(answer)):
        return answer
    return ""


class JuristAgent(BaseAgent):
    """Faktlarni ajratadi va neytral huquqiy ramka quradi.

    Harorat past: bu bosqichda ijodkorlik zarar — fakt o'ylab topilishi
    butun quyi oqimni buzadi.
    """

    role = "jurist"
    display_name = "Jurist"
    output_schema = LegalFrame
    temperature = 0.2
    max_tokens = 1200

    def task(self, ctx: AgentContext, **inputs: Any) -> str:
        parts = [f"FOYDALANUVCHI SAVOLI:\n{ctx.question}"]
        if ctx.client_position:
            parts.append(f"MIJOZ BAYONI:\n{ctx.client_position}")
        if ctx.as_of:
            parts.append(f"HOLAT SANASI: {ctx.as_of.isoformat()}")
        parts.append(
            "Savoldan faktlarni ajrat, hal qilinishi kerak bo'lgan huquqiy savollarni "
            "shakllantir va kontekstdagi qaysi normalar tegishli ekanini ko'rsat. "
            "Hech qanday tomonni tutmaysan — bu neytral ramka."
        )
        if inputs.get("direct"):
            # `simple` oqimda jurist yagona agent — ramka bilan birga qisqa
            # javobni ham u beradi, aks holda foydalanuvchi javobsiz qoladi.
            #
            # Iqtibos talabi bu yerda **takrorlanadi va kuchaytiriladi**:
            # o'lchovda (ADR-001, `cite-01`) baza model to'g'ri javob berib,
            # belgini qo'yishni unutishi eng ko'p uchraydigan xato bo'ldi.
            # Belgisiz gap groundedness gate tomonidan o'chiriladi, ya'ni
            # unutilgan `[C1]` javobning o'zini yo'q qiladi.
            parts.append(
                "Bundan tashqari `answer` maydonida savolga to'g'ridan-to'g'ri, "
                "qisqa (2–4 jumla) javob ber.\n"
                "MAJBURIY: `answer` ichidagi HAR BIR huquqiy gap oxirida "
                "`[C1]` ko'rinishidagi belgi turishi shart — belgisiz gap "
                "javobdan avtomatik o'chiriladi.\n"
                "Namuna: «Mulkdor mol-mulkini qonunsiz egalikdan talab qilib "
                "olishga haqli [C1].»\n"
                "Kontekstda javob bo'lmasa — `answer` ni bo'sh qoldir."
            )
        return "\n\n".join(parts)

    def output_hint(self) -> str:
        return (
            '{"facts": ["..."], "legal_questions": ["..."], '
            '"applicable_norms": ["C1", "C2"], "unknowns": ["..."], "answer": "..."}\n'
            "`applicable_norms` faqat kontekstda mavjud belgilar."
        )

    def build(self, data: dict[str, Any], ctx: AgentContext) -> LegalFrame:
        return LegalFrame(
            facts=as_list(data.get("facts")),
            legal_questions=as_list(data.get("legal_questions")),
            applicable_norms=ctx.resolve(_tags_from(data.get("applicable_norms"))),
            unknowns=as_list(data.get("unknowns")),
            answer=_grounded_answer(str(data.get("answer") or "").strip(), ctx),
        )

    def validate(self, result: LegalFrame) -> str | None:  # type: ignore[override]
        if not result.legal_questions:
            return "`legal_questions` bo'sh — kamida bitta huquqiy savol kerak"
        if not result.applicable_norms:
            # `simple` oqimda ramka yagona grounding manbai: normasiz ramka
            # gate uchun tekshiriladigan hech narsa qoldirmaydi va javob
            # butunlay rad etiladi. Kontekst bo'sh bo'lsa jurist bu yerga
            # umuman kelmaydi (docs/06 § 8), demak norma tanlanmagani —
            # shartnoma buzilishi, retry ga arziydi.
            return "`applicable_norms` bo'sh — kontekstdagi qaysi normalar tegishli?"
        return None

    def build_from_text(self, raw: str, ctx: AgentContext) -> LegalFrame | None:
        s = parse_sections(raw)
        questions = s.get("HUQUQIY SAVOLLAR") or s.get("SAVOLLAR") or []
        return LegalFrame(
            facts=s.get("FAKTLAR", []),
            # Savol ajratilmasa foydalanuvchi savolining o'zi ramka bo'ladi —
            # bu taxmin emas, kirishning aynan ko'chirilishi.
            legal_questions=questions or [ctx.question],
            applicable_norms=ctx.resolve(extract_tags(raw)),
            unknowns=s.get("NOMA'LUM", []) or s.get("NOMALUM", []),
            answer=_grounded_answer(
                " ".join(s.get("JAVOB", []) or s.get("XULOSA", [])).strip(), ctx
            ),
        )


# --------------------------------------------------------------------------- #
# advocate / prosecutor — pozitsiya oluvchi rollar
# --------------------------------------------------------------------------- #


class PositionAgent(BaseAgent):
    """Pozitsiya oluvchi rollar uchun umumiy qism.

    `weaknesses` majburiy — bu rol qulflanishiga qarshi asosiy mexanizm
    (docs/06 § 2). Bo'sh bo'lsa javob qabul qilinmaydi va agent qayta
    so'raladi, chunki «zaif joyi yo'q» degan pozitsiya har doim yolg'on.
    """

    output_schema = Position
    temperature = 0.5
    max_tokens = 1500
    side: str = ""

    def task(self, ctx: AgentContext, **inputs: Any) -> str:
        frame: LegalFrame | None = inputs.get("frame")
        opponent: Position | None = inputs.get("opponent")
        parts = [f"FOYDALANUVCHI SAVOLI:\n{ctx.question}"]
        if frame is not None:
            parts.append("HUQUQIY RAMKA\n" + render_frame(frame))
        if ctx.client_position and self.role == "advocate":
            parts.append(f"MIJOZ POZITSIYASI:\n{ctx.client_position}")
        if opponent is not None:
            parts.append(render_position(opponent, "QARSHI TOMON POZITSIYASI"))
            parts.append(self.rebuttal_instruction())
        else:
            parts.append(self.instruction())
        return "\n\n".join(parts)

    def instruction(self) -> str:
        raise NotImplementedError

    def rebuttal_instruction(self) -> str:
        return (
            "Qarshi tomon dalillarini nuqta-ba-nuqta rad et. Faqat haqiqatan "
            "zaif bo'lgan joyni tanqid qil — kuchli dalilni «zaif» deb atash "
            "sening pozitsiyangni ham zaiflashtiradi. Pozitsiyangni yangilangan "
            "holda qaytadan bayon et."
        )

    def output_hint(self) -> str:
        return (
            '{"stance": "...", "arguments": [{"claim": "...", '
            '"citations": ["C1"], "strength": "strong|moderate|weak"}], '
            '"weaknesses": ["..."], "confidence": 0.0}\n'
            "`weaknesses` bo'sh bo'lmasligi shart — o'z pozitsiyangning zaif joyi."
        )

    def build(self, data: dict[str, Any], ctx: AgentContext) -> Position:
        arguments: list[Argument] = []
        for item in data.get("arguments") or []:
            if isinstance(item, str):
                arguments.append(Argument(claim=item.strip(), citations=extract_tags(item)))
                continue
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or item.get("text") or "").strip()
            if not claim:
                continue
            strength = _STRENGTH.get(str(item.get("strength", "")).lower(), "moderate")
            arguments.append(
                Argument(
                    claim=claim,
                    citations=_tags_from(item.get("citations")),
                    strength=strength,  # type: ignore[arg-type]
                )
            )
        return Position(
            role=self.role,
            stance=str(data.get("stance") or "").strip(),
            arguments=arguments,
            weaknesses=as_list(data.get("weaknesses")),
            confidence=_confidence(data.get("confidence")),
        )

    def validate(self, result: Position) -> str | None:  # type: ignore[override]
        if not result.stance:
            return "`stance` bo'sh"
        if not result.arguments:
            return "`arguments` bo'sh — kamida bitta dalil kerak"
        if not result.weaknesses:
            return "`weaknesses` bo'sh — o'z pozitsiyangning zaif tomonini ko'rsatish majburiy"
        return None

    def build_from_text(self, raw: str, ctx: AgentContext) -> Position | None:
        s = parse_sections(raw)
        stance_lines = s.get("POZITSIYA") or s.get("XULOSA") or []
        argument_lines = s.get("DALILLAR") or s.get("ARGUMENTLAR") or []
        if s.get("PROTSESSUAL IMKONIYATLAR"):
            argument_lines = argument_lines + s["PROTSESSUAL IMKONIYATLAR"]
        return Position(
            role=self.role,
            stance=" ".join(stance_lines).strip(),
            arguments=_parse_arguments(argument_lines),
            weaknesses=s.get("ZAIF TOMONLAR", []) or s.get("ZAIF NUQTALAR", []),
            confidence=parse_confidence(s.get("ISHONCH")),
        )


class AdvocateAgent(PositionAgent):
    role = "advocate"
    display_name = "Advokat"
    side = "defense"

    def instruction(self) -> str:
        return (
            "Mijoz foydasiga eng kuchli huquqiy pozitsiyani shakllantir. "
            "Har bir dalilni kontekstdagi normaga bog'la, protsessual "
            "imkoniyatlarni ko'rsat va o'z pozitsiyangning zaif tomonlarini "
            "halol sanab o't."
        )


class ProsecutorAgent(PositionAgent):
    role = "prosecutor"
    display_name = "Prokuror"
    side = "prosecution"

    def instruction(self) -> str:
        return (
            "Qarshi pozitsiyani — davlat va jamoat manfaati nuqtai nazaridan "
            "shakllantir. Advokat pozitsiyasining zaif joylarini va huquqiy "
            "oqibatlarni ko'rsat. O'z pozitsiyangning zaif tomonlarini ham "
            "halol sanab o't."
        )

    def task(self, ctx: AgentContext, **inputs: Any) -> str:
        # Prokuror raund 1 da ham advokat pozitsiyasini ko'radi (docs/06 § 2
        # jadvali) — u qarshi pozitsiya, mustaqil pozitsiya emas.
        base = super().task(ctx, **inputs)
        advocate: Position | None = inputs.get("advocate")
        if advocate is not None and inputs.get("opponent") is None:
            return base + "\n\n" + render_position(advocate, "ADVOKAT POZITSIYASI")
        return base


# --------------------------------------------------------------------------- #
# professor — doktrinal qatlam
# --------------------------------------------------------------------------- #


class ProfessorAgent(BaseAgent):
    """Doktrinal tahlil: kolliziyalar, tamoyillar, qiyosiy huquq.

    Professor iqtibosdan qisman ozod (docs/06 § 2): doktrina manbasi
    kontekstda bo'lmasligi mumkin. Lekin **norma haqidagi** har qanday
    da'vosi baribir belgiga bog'lanadi — gate buni tekshiradi.
    """

    role = "professor"
    display_name = "Professor"
    output_schema = DoctrinalAnalysis
    temperature = 0.4
    max_tokens = 1200

    def task(self, ctx: AgentContext, **inputs: Any) -> str:
        parts = [f"FOYDALANUVCHI SAVOLI:\n{ctx.question}"]
        frame: LegalFrame | None = inputs.get("frame")
        if frame is not None:
            parts.append("HUQUQIY RAMKA\n" + render_frame(frame))
        for position in (inputs.get("positions") or {}).values():
            parts.append(render_position(position))
        parts.append(
            "Masalani doktrinal darajada tahlil qil: qaysi huquqiy tamoyillar "
            "amal qiladi, normalar orasida kolliziya bormi va u qanday hal "
            "qilinadi, qiyosiy huquqda qanday yondashuvlar bor. Tomon tutmaysan."
        )
        return "\n\n".join(parts)

    def output_hint(self) -> str:
        return (
            '{"summary": "...", "doctrines": ["..."], "collisions": ["..."], '
            '"comparative": ["..."], "citation_tags": ["C1"], "caveats": ["..."]}'
        )

    def build(self, data: dict[str, Any], ctx: AgentContext) -> DoctrinalAnalysis:
        return DoctrinalAnalysis(
            summary=str(data.get("summary") or "").strip(),
            doctrines=as_list(data.get("doctrines")),
            collisions=as_list(data.get("collisions")),
            comparative=as_list(data.get("comparative")),
            citation_tags=[c.tag for c in ctx.resolve(_tags_from(data.get("citation_tags")))],
            caveats=as_list(data.get("caveats")),
        )

    def validate(self, result: DoctrinalAnalysis) -> str | None:  # type: ignore[override]
        if not result.summary and not result.doctrines:
            return "`summary` va `doctrines` ikkalasi ham bo'sh"
        return None

    def build_from_text(self, raw: str, ctx: AgentContext) -> DoctrinalAnalysis | None:
        s = parse_sections(raw)
        summary = s.get("DOKTRINAL SHARH") or s.get("SHARH") or s.get("POZITSIYA") or []
        return DoctrinalAnalysis(
            summary=" ".join(summary).strip(),
            doctrines=s.get("DOKTRINALAR", []),
            collisions=s.get("KOLLIZIYALAR", []),
            comparative=s.get("QIYOSIY HUQUQ", []),
            citation_tags=[c.tag for c in ctx.resolve(extract_tags(raw))],
            caveats=s.get("OGOHLANTIRISHLAR", []),
        )


# --------------------------------------------------------------------------- #
# judge — sintez
# --------------------------------------------------------------------------- #


class JudgeAgent(BaseAgent):
    """Dalillarni tortadi va asoslangan xulosa beradi.

    Harorat past: sintez bosqichida yangi fakt paydo bo'lmasligi kerak —
    sudya faqat oldida turgan pozitsiyalardan xulosa chiqaradi.
    """

    role = "judge"
    display_name = "Sudya"
    output_schema = Verdict
    temperature = 0.2
    max_tokens = 1800

    def task(self, ctx: AgentContext, **inputs: Any) -> str:
        parts = [f"FOYDALANUVCHI SAVOLI:\n{ctx.question}"]
        frame: LegalFrame | None = inputs.get("frame")
        if frame is not None:
            parts.append("HUQUQIY RAMKA\n" + render_frame(frame))
        for position in (inputs.get("positions") or {}).values():
            parts.append(render_position(position))
        doctrine: DoctrinalAnalysis | None = inputs.get("doctrine")
        if doctrine is not None:
            parts.append(render_doctrine(doctrine))
        missing: list[str] = inputs.get("missing") or []
        if missing:
            parts.append("POZITSIYA OLINMADI: " + ", ".join(missing))
        parts.append(
            "Pozitsiyalarni tort va asoslangan xulosa ber. Qaysi dalilni qabul "
            "qilganingni va qaysisini nima uchun rad etganingni aniq ayt. "
            "Har bir xulosa asosini kontekstdagi belgiga bog'la. Ma'lumot "
            "yetishmasa — buni `caveats` da ko'rsat va ishonchni pasaytir."
        )
        return "\n\n".join(parts)

    def output_hint(self) -> str:
        return (
            '{"conclusion": "...", "reasoning": ["..."], '
            '"accepted_arguments": ["..."], "rejected_arguments": ["..."], '
            '"confidence": 0.0, "caveats": ["..."], "citation_tags": ["C1"]}\n'
            "`conclusion` va `reasoning` ichida iqtiboslar `[C1]` shaklida bo'lsin."
        )

    def build(self, data: dict[str, Any], ctx: AgentContext) -> Verdict:
        tags = _tags_from(data.get("citation_tags") or data.get("citations"))
        conclusion = str(data.get("conclusion") or "").strip()
        reasoning = as_list(data.get("reasoning"))
        # Xulosa matnidagi belgilar ham hisobga olinadi: model ularni
        # alohida maydonda takrorlashni ko'pincha unutadi.
        tags += [t for t in extract_tags(conclusion + " " + " ".join(reasoning)) if t not in tags]
        resolved = ctx.resolve(tags)
        return Verdict(
            conclusion=conclusion,
            reasoning=reasoning,
            accepted_arguments=as_list(data.get("accepted_arguments")),
            rejected_arguments=as_list(data.get("rejected_arguments")),
            confidence=_confidence(data.get("confidence")),
            caveats=as_list(data.get("caveats")),
            citation_tags=[c.tag for c in resolved],
            citations=resolved,
        )

    def validate(self, result: Verdict) -> str | None:  # type: ignore[override]
        if not result.conclusion:
            return "`conclusion` bo'sh"
        return None

    def build_from_text(self, raw: str, ctx: AgentContext) -> Verdict | None:
        s = parse_sections(raw)
        conclusion = s.get("XULOSA") or s.get("POZITSIYA") or []
        reasoning = s.get("ASOSLAR") or s.get("DALILLAR") or []
        if not conclusion and not reasoning:
            return None
        resolved = ctx.resolve(extract_tags(raw))
        return Verdict(
            conclusion=" ".join(conclusion).strip(),
            reasoning=[strip_bullet(r) for r in reasoning],
            accepted_arguments=s.get("QABUL QILINGAN", []),
            rejected_arguments=s.get("RAD ETILGAN", []),
            confidence=parse_confidence(s.get("ISHONCH")),
            caveats=s.get("OGOHLANTIRISHLAR", []) or s.get("ZAIF TOMONLAR", []),
            citation_tags=[c.tag for c in resolved],
            citations=resolved,
        )


# --------------------------------------------------------------------------- #
# Reestr
# --------------------------------------------------------------------------- #

AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "jurist": JuristAgent,
    "advocate": AdvocateAgent,
    "prosecutor": ProsecutorAgent,
    "professor": ProfessorAgent,
    "judge": JudgeAgent,
}


def get_agent(role: str) -> BaseAgent:
    """Rol nomi bo'yicha agent nusxasi.

    Har chaqiruvda yangi nusxa: agentlar holatsiz va arzon, umumiy nusxa esa
    ko'p oqimli xizmatda poyga holatiga olib kelardi.
    """
    if role not in AGENT_CLASSES:
        raise KeyError(f"Noma'lum rol: '{role}'. Mavjud: {', '.join(ROLE_ORDER)}")
    return AGENT_CLASSES[role]()


def _confidence(value: Any) -> float:
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return 0.5
    if number > 1.0:
        number /= 100.0
    return max(0.0, min(1.0, number))


def citation_index(citations: list[Citation]) -> dict[str, Citation]:
    return {c.tag.upper(): c for c in citations}
