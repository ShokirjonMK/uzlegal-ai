"""Leksiya generatsiyasi — mavzu + bilim bazasidagi normalar.

QANDAY ISHLAYDI. Mavzuning qidiruv soʻrovlari gibrid retrieverga
beriladi, topilgan normalardan leksiya yigʻiladi. Model **ixtiyoriy**:

- backend berilmasa — leksiya normalarning oʻzidan tuziladi. Matn quruq
  boʻladi, lekin har gap haqiqiy hujjatdan keladi va hech narsa
  oʻylab topilmaydi.
- backend berilsa — tushuntirish matni model tomonidan yoziladi, lekin
  faqat topilgan normalar asosida.

NEGA MODELSIZ HAM ISHLASHI KERAK. Leksiyaning qiymati tushuntirishda
emas, TOʻGʻRI NORMADA. Model yoʻq boʻlganda «xizmat ishlamaydi» deyish
oʻrniga normalarni tartiblab koʻrsatish — talaba uchun baribir foydali.
Bu ayni paytda butun modulni modelsiz sinash imkonini beradi.

MANBASIZ LEKSIYA. Bazada mavzuga oid norma topilmasa, leksiya
«manba topilmadi» ogohlantirishi bilan qaytadi. Boʻsh joyni umumiy
gaplar bilan toʻldirish — aynan talabaga zarar yetkazadigan yoʻl.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

from uzlegal.education.curriculum import Topic, find_topic
from uzlegal.retrieval.hybrid import build_context
from uzlegal.types import Citation, GenerationParams

# --------------------------------------------------------------------------- #
# Tashqi bogʻlanishlar
# --------------------------------------------------------------------------- #


class Retriever(Protocol):
    """`HybridRetriever.search` dan kerak boʻladigan qismi."""

    def search(self, query: str, *, top_k: int = 8, **kwargs: Any) -> Any: ...


class Backend(Protocol):
    """`InferenceBackend` dan kerak boʻladigan qismi."""

    def generate(self, prompt: str, params: GenerationParams) -> str: ...


# --------------------------------------------------------------------------- #
# Natija
# --------------------------------------------------------------------------- #


class LectureResult(BaseModel):
    topic: str = Field(description="Mavzu identifikatori")
    title: str = ""
    content: str = ""
    norms_cited: list[Citation] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    practice_questions: list[str] = Field(default_factory=list)

    generated_by: str = Field(
        default="deterministic",
        description="`deterministic` — normalardan yigʻilgan, `model` — model yozgan",
    )
    caveats: list[str] = Field(default_factory=list)

    @property
    def has_sources(self) -> bool:
        """Leksiya haqiqiy normaga tayanadimi."""
        return bool(self.norms_cited)


# --------------------------------------------------------------------------- #
# Normalarni yigʻish
# --------------------------------------------------------------------------- #

_MAX_QUERIES = 4


def collect_norms(
    topic: Topic,
    retriever: Retriever,
    *,
    top_k: int = 6,
) -> list[Any]:
    """Mavzuning barcha soʻrovlari boʻyicha normalarni yigʻadi.

    Bitta soʻrov yetmaydi: «Mehnat shartnomasi» mavzusida tuzish ham,
    sinov muddati ham, shartlar ham kerak — ular boshqa moddalarda.
    Takrorlar `chunk_id` boʻyicha olib tashlanadi, tartib saqlanadi
    (birinchi soʻrovning natijasi birinchi turadi).
    """
    seen: set[str] = set()
    out: list[Any] = []

    queries = topic.search_queries[:_MAX_QUERIES] or [topic.title]
    for query in queries:
        found = retriever.search(query, top_k=top_k)
        for item in getattr(found, "results", []):
            cid = str(getattr(item, "chunk_id", None) or getattr(item.chunk, "chunk_id", ""))
            if cid in seen:
                continue
            seen.add(cid)
            out.append(item)

    return out


def to_citations(scored: list[Any]) -> list[Citation]:
    from uzlegal.orchestrator.graph import to_citation

    return [to_citation(f"C{i}", item.chunk) for i, item in enumerate(scored, start=1)]


# --------------------------------------------------------------------------- #
# Deterministik leksiya
# --------------------------------------------------------------------------- #


def _norm_section(index: int, chunk: Any) -> str:
    """Bitta normaning leksiyadagi boʻlimi."""
    label = getattr(chunk, "citation_label", None) or getattr(chunk, "doc_title", "Manba")
    body = " ".join(str(chunk.content).split())
    return f"### [C{index}] {label}\n\n{body}"


def _deterministic_content(topic: Topic, scored: list[Any]) -> str:
    parts = [f"## {topic.title}"]
    if topic.summary:
        parts.append(topic.summary)

    if not scored:
        parts.append(
            "Bilim bazasida bu mavzu boʻyicha norma topilmadi. "
            "Quyida faqat mavzu tavsifi berilgan — huquqiy asos sifatida "
            "foydalanib boʻlmaydi."
        )
        return "\n\n".join(parts)

    parts.append("### Tegishli normalar")
    parts.extend(_norm_section(i, item.chunk) for i, item in enumerate(scored, start=1))
    return "\n\n".join(parts)


def _examples(topic: Topic, scored: list[Any]) -> list[str]:
    """Amaliy holatlar — har norma uchun bittadan.

    Namuna ataylab SAVOL shaklida: tayyor javob berish oʻrniga talabani
    normani oʻqishga majbur qiladi. Norma matnidan kelib chiqadi,
    shuning uchun oʻylab topilgan holat emas.
    """
    out: list[str] = []
    for i, item in enumerate(scored[:3], start=1):
        chunk = item.chunk
        label = getattr(chunk, "citation_label", None) or getattr(chunk, "doc_title", "norma")
        out.append(
            f"Holat {i}. Tomonlar oʻrtasidagi nizo aynan shu qoidaga tegsa "
            f"({label}), qaysi shart hal qiluvchi boʻladi va nima uchun?"
        )
    return out


def _practice_questions(topic: Topic, scored: list[Any]) -> list[str]:
    """Mustaqil ish savollari."""
    questions = [f"{topic.title} boʻyicha asosiy qoida nimadan iborat?"]
    for item in scored[:3]:
        article = getattr(item.chunk, "article", None)
        title = getattr(item.chunk, "doc_title", "hujjat")
        if article:
            questions.append(f"{title}ning {article}-moddasi qanday holatni tartibga soladi?")
    if topic.prerequisites:
        questions.append(
            "Ushbu mavzu quyidagilar bilan qanday bogʻlangan: "
            + ", ".join(topic.prerequisites)
            + "?"
        )
    return questions


# --------------------------------------------------------------------------- #
# Model bilan
# --------------------------------------------------------------------------- #

_PROMPT = """Sen huquq fanidan dars beruvchi oʻqituvchisan.

MAVZU: {title}

QUYIDAGI NORMALAR — yagona ruxsat etilgan manba:
{context}

VAZIFA. Mavzuni tushuntir. Har bir huquqiy fikrdan keyin manba belgisini
qavsda koʻrsat, masalan [C1]. Manbalarda yoʻq qoidani YOZMA.

Javob tuzilishi:
## Tushuntirish
(matn)
## Misollar
- (misol)
## Savollar
- (savol)
"""


def _model_content(topic: Topic, context: str, backend: Backend, params: GenerationParams) -> str:
    prompt = _PROMPT.format(title=topic.title, context=context)
    return backend.generate(prompt, params)


_SECTION_RE = re.compile(r"^##\s*(.+?)\s*$", re.MULTILINE)


def _split_sections(text: str) -> dict[str, str]:
    """`## Sarlavha` boʻyicha boʻladi. Sarlavhasiz matn `""` kalitiga tushadi."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return {"": text.strip()}
    if matches[0].start() > 0:
        sections[""] = text[: matches[0].start()].strip()
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[m.group(1).strip().lower()] = text[m.end() : end].strip()
    return sections


def _bullets(block: str) -> list[str]:
    out = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•")):
            out.append(line[1:].strip())
    return [b for b in out if b]


# --------------------------------------------------------------------------- #
# Kirish nuqtasi
# --------------------------------------------------------------------------- #


def generate_lecture(
    topic: Topic | str,
    retriever: Retriever | None = None,
    *,
    backend: Backend | None = None,
    params: GenerationParams | None = None,
    top_k: int = 6,
    context_budget: int = 6000,
) -> LectureResult:
    """Mavzu boʻyicha leksiya tayyorlaydi.

    `retriever` berilmasa normalar qidirilmaydi va leksiya faqat mavzu
    tavsifidan iborat boʻladi — bu holat `caveats` da ochiq aytiladi.
    """
    node = find_topic(topic) if isinstance(topic, str) else topic
    if node is None:
        raise ValueError(f"Mavzu topilmadi: {topic!r}")

    caveats: list[str] = []
    scored: list[Any] = []

    if retriever is None:
        caveats.append("Qidiruv ulanmagan — leksiya normalarsiz tayyorlandi.")
    else:
        scored = collect_norms(node, retriever, top_k=top_k)
        if not scored:
            caveats.append(
                "Bilim bazasida bu mavzu boʻyicha norma topilmadi. "
                "Leksiyani huquqiy asos sifatida ishlatib boʻlmaydi."
            )

    citations = to_citations(scored)
    examples = _examples(node, scored)
    questions = _practice_questions(node, scored)
    generated_by = "deterministic"

    if backend is not None and scored:
        context, used = build_context([s for s in scored], budget_tokens=context_budget)
        raw = _model_content(node, context, backend, params or GenerationParams())
        sections = _split_sections(raw)
        body = sections.get("tushuntirish") or sections.get("") or raw.strip()
        content = f"## {node.title}\n\n{body}"
        if model_examples := _bullets(sections.get("misollar", "")):
            examples = model_examples
        if model_questions := _bullets(sections.get("savollar", "")):
            questions = model_questions
        generated_by = "model"
        # Kontekstga sigʻmagan normalar iqtibos roʻyxatida qolmasin —
        # ular modelga koʻrsatilmagan, yaʼni javobni qoʻllab-quvvatlamaydi.
        if len(used) < len(scored):
            citations = to_citations(used)
            caveats.append(
                f"Kontekst chegarasi tufayli {len(scored) - len(used)} ta norma "
                "leksiyaga kiritilmadi."
            )
    else:
        content = _deterministic_content(node, scored)

    return LectureResult(
        topic=node.topic_id,
        title=node.title,
        content=content,
        norms_cited=citations,
        examples=examples,
        practice_questions=questions,
        generated_by=generated_by,
        caveats=caveats,
    )
