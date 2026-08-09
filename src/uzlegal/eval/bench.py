"""Faza 0 baza model baholash dvigateli — ADR-001.

Barcha tekshiruvlar **deterministik**: LLM-judge ishlatilmaydi. Sabab:

* Natija takrorlanadi (bir xil javob → bir xil ball)
* Judge bias'i yo'q (self-preference, uzunlik afzalligi)
* Bepul va tez — har o'zgarishdan keyin qayta ishga tushirish mumkin

Kamchiligi: uslub va nozik sifat o'lchanmaydi. Ular Faza 6 dagi inson
bahosiga qoldiriladi. Faza 0 uchun kerakli narsa — nomzodlarni **ajratish**,
va buning uchun deterministik signal yetarli.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uzlegal.types import GenerationParams

# --------------------------------------------------------------------------- #
# Til tekshiruvi
# --------------------------------------------------------------------------- #

CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# Rus tiliga xos, o'zbek lotin matnida uchramaydigan so'zlar
RUSSIAN_MARKERS = re.compile(
    r"\b(что|это|который|также|если|быть|может|должен|право|закон|договор|"
    r"статья|срок|лицо|случае|соответствии|является)\b",
    re.IGNORECASE,
)

# Inglizcha "sizib chiqish" — model o'zbekcha o'rniga inglizcha javob bersa
ENGLISH_MARKERS = re.compile(
    r"\b(the|and|is|are|that|this|which|shall|must|according|therefore|"
    r"contract|law|article|court)\b",
    re.IGNORECASE,
)

# O'zbek tiliga xos morfologiya — javob haqiqatan o'zbekcha ekanini tasdiqlaydi
UZBEK_MARKERS = re.compile(
    r"(lar\b|ning\b|ga\b|da\b|dan\b|ni\b|bo'l|qil|kerak|mumkin|hisoblanadi|"
    r"belgilangan|nazarda|bo‘l|emas\b|uchun\b|bilan\b)",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    """Taqqoslash uchun matnni normallashtiradi.

    O'zbek apostrofining barcha variantlari (' ʻ ‘ ') bir shaklga keltiriladi —
    aks holda "bo'lmaydi" va "boʻlmaydi" turli satr hisoblanadi.
    """
    text = unicodedata.normalize("NFKC", text)
    for ch in ("ʻ", "ʼ", "‘", "’", "`", "´"):
        text = text.replace(ch, "'")
    return re.sub(r"\s+", " ", text).strip().lower()


# --------------------------------------------------------------------------- #
# Natija strukturalari
# --------------------------------------------------------------------------- #


@dataclass
class ItemResult:
    item_id: str
    category: str
    answer: str
    latency_s: float
    tokens: int

    passed_expect: bool = True
    passed_forbid: bool = True
    passed_cite: bool = True
    passed_length: bool = True
    passed_refusal: bool = True

    lang_score: float = 1.0
    failures: list[str] = field(default_factory=list)

    @property
    def content_ok(self) -> bool:
        return self.passed_expect and self.passed_forbid and self.passed_refusal

    @property
    def instruction_ok(self) -> bool:
        return self.passed_cite and self.passed_length


@dataclass
class ModelScore:
    model_id: str
    items: list[ItemResult]
    load_s: float
    memory_gb: float

    def _mean(self, fn: Any, category: str | None = None) -> float:
        rows = [i for i in self.items if category is None or i.category == category]
        return sum(1.0 if fn(i) else 0.0 for i in rows) / len(rows) if rows else 0.0

    @property
    def context_reasoning(self) -> float:
        return self._mean(lambda i: i.content_ok)

    @property
    def uzbek_fluency(self) -> float:
        return sum(i.lang_score for i in self.items) / len(self.items) if self.items else 0.0

    @property
    def legal_terminology(self) -> float:
        return self._mean(lambda i: i.content_ok, "terminology")

    @property
    def instruction_following(self) -> float:
        return self._mean(lambda i: i.instruction_ok)

    @property
    def refusal_accuracy(self) -> float:
        return self._mean(lambda i: i.content_ok, "refusal")

    @property
    def tokens_per_second(self) -> float:
        total_t = sum(i.latency_s for i in self.items)
        total_n = sum(i.tokens for i in self.items)
        return total_n / total_t if total_t else 0.0

    @property
    def weighted(self) -> float:
        """ADR-001 dagi vaznlar bo'yicha umumiy ball (0–5 shkalasida)."""
        return 5.0 * (
            0.30 * self.context_reasoning
            + 0.30 * self.uzbek_fluency
            + 0.25 * self.legal_terminology
            + 0.15 * self.instruction_following
        )


# --------------------------------------------------------------------------- #
# Tekshiruvlar
# --------------------------------------------------------------------------- #


def score_language(answer: str) -> tuple[float, list[str]]:
    """Javob toza o'zbek (lotin) tilidami — 0.0…1.0.

    Yuridik tizimda bu muhim: kirill yoki rus tilidagi javob foydalanuvchi
    uchun yaroqsiz, va u modelning o'zbek tilini yetarli egallamaganini
    ko'rsatadi.
    """
    if not answer.strip():
        return 0.0, ["bo'sh javob"]

    problems: list[str] = []
    score = 1.0
    words = max(len(answer.split()), 1)

    cyr = len(CYRILLIC.findall(answer)) / max(len(answer), 1)
    if cyr > 0.02:
        penalty = min(0.6, cyr * 3)
        score -= penalty
        problems.append(f"kirill {cyr:.0%}")

    ru = len(RUSSIAN_MARKERS.findall(answer)) / words
    if ru > 0.02:
        score -= min(0.5, ru * 5)
        problems.append(f"rus so'zlari {ru:.0%}")

    en = len(ENGLISH_MARKERS.findall(answer)) / words
    if en > 0.05:
        score -= min(0.5, en * 4)
        problems.append(f"ingliz so'zlari {en:.0%}")

    if len(UZBEK_MARKERS.findall(answer)) / words < 0.08:
        score -= 0.3
        problems.append("o'zbek morfologiyasi kam")

    return max(0.0, score), problems


def check_item(item: dict[str, Any], answer: str, latency: float, tokens: int) -> ItemResult:
    norm = normalize(answer)
    res = ItemResult(
        item_id=item["id"],
        category=item["category"],
        answer=answer,
        latency_s=latency,
        tokens=tokens,
    )

    for group in item.get("expect_any", []):
        if not any(normalize(v) in norm for v in group):
            res.passed_expect = False
            res.failures.append(f"kutilgan yo'q: {group[0]}")

    for bad in item.get("forbid", []):
        if normalize(bad) in norm:
            res.passed_forbid = False
            res.failures.append(f"taqiqlangan bor: {bad}")

    for tag in item.get("must_cite", []):
        if tag.lower() not in norm:
            res.passed_cite = False
            res.failures.append(f"iqtibos yo'q: [{tag}]")

    limit = item.get("max_words")
    if limit and len(answer.split()) > limit * 1.5:
        res.passed_length = False
        res.failures.append(f"juda uzun: {len(answer.split())} > {limit}")

    if item.get("must_refuse") and res.passed_expect is False:
        res.passed_refusal = False

    res.lang_score, lang_problems = score_language(answer)
    res.failures.extend(lang_problems)
    return res


# --------------------------------------------------------------------------- #
# Ishga tushirish
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = (
    "Sen O'zbekiston qonunchiligi bo'yicha yuridik yordamchisan.\n\n"
    "QAT'IY QOIDALAR:\n"
    "1. Faqat berilgan [C1], [C2] manbalariga tayanib javob ber.\n"
    "2. Har bir huquqiy da'voga manba belgisini qo'y, masalan [C1].\n"
    "3. Agar berilgan manbalarda javob bo'lmasa, aniq ayt: "
    "\"Berilgan manbalarda bu savolga javob yo'q\". Taxmin qilma.\n"
    "4. Faqat o'zbek tilida (lotin yozuvida) javob ber.\n"
    "5. Qisqa va aniq yoz."
)


def load_items(suite_dir: Path, limit: int | None = None) -> list[dict[str, Any]]:
    path = suite_dir / "items.jsonl"
    items = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return items[:limit] if limit else items


def run_model(registry: Any, model_id: str, items: list[dict[str, Any]]) -> ModelScore:
    t0 = time.time()
    registry.activate(model_id)
    load_s = time.time() - t0
    backend = registry.backend

    results: list[ItemResult] = []
    for item in items:
        prompt = f"{item['context']}\n\nSavol: {item['question']}"
        params = GenerationParams(
            max_tokens=int(item.get("max_words", 100) * 3),
            temperature=0.1,  # baholashda past — takrorlanuvchanlik uchun
            system=SYSTEM_PROMPT,
        )

        t1 = time.time()
        chunks: list[str] = list(backend.stream(prompt, params))
        latency = time.time() - t1

        results.append(check_item(item, "".join(chunks), latency, len(chunks)))

    return ModelScore(
        model_id=model_id,
        items=results,
        load_s=load_s,
        memory_gb=backend.memory_usage_gb(),
    )


# --------------------------------------------------------------------------- #
# Hisobot
# --------------------------------------------------------------------------- #


def decide(scores: list[ModelScore]) -> tuple[str | None, list[str]]:
    """ADR-001 dagi qaror qoidalarini qo'llaydi."""
    notes: list[str] = []
    eligible: list[ModelScore] = []

    for s in scores:
        fluency_5 = s.uzbek_fluency * 5
        if fluency_5 < 3.0:
            notes.append(f"❌ {s.model_id} rad etildi: o'zbek tili {fluency_5:.2f} < 3.0")
        else:
            eligible.append(s)

    if not eligible:
        notes.append("⚠️ Hech bir nomzod o'zbek tili chegarasidan o'tmadi.")
        return None, notes

    eligible.sort(key=lambda s: s.weighted, reverse=True)
    best = eligible[0]

    if len(eligible) > 1 and (best.weighted - eligible[1].weighted) < 0.3:
        notes.append(
            f"Farq < 0.3 ({best.weighted:.2f} vs {eligible[1].weighted:.2f}) → "
            f"qoida bo'yicha kichikroq model tanlanadi"
        )
        close = [s for s in eligible if best.weighted - s.weighted < 0.3]
        best = min(close, key=lambda s: s.memory_gb or 999)

    if best.uzbek_fluency * 5 < 3.5:
        notes.append(
            f"⚠️ CPT tavsiya etiladi: o'zbek tili {best.uzbek_fluency * 5:.2f} < 3.5 (ADR-002)"
        )
    else:
        notes.append(f"✅ CPT shart emas: o'zbek tili {best.uzbek_fluency * 5:.2f} ≥ 3.5")

    return best.model_id, notes


def render_report(scores: list[ModelScore], winner: str | None, notes: list[str]) -> str:
    lines = [
        "# Faza 0 — baza model tanlovi natijalari",
        "",
        "`bench-uz-legal-v0` · deterministik baholash, LLM-judge ishlatilmagan.",
        "",
        "## Umumiy ball (ADR-001 vaznlari, 0–5)",
        "",
        "| Model | Umumiy | Mulohaza | O'zbek tili | Atamalar | Ko'rsatma | Rad etish | tok/s | Xotira |",
        "|-------|-------:|---------:|------------:|---------:|----------:|----------:|------:|-------:|",
    ]
    for s in sorted(scores, key=lambda x: x.weighted, reverse=True):
        mark = " ⭐" if s.model_id == winner else ""
        lines.append(
            f"| **{s.model_id}**{mark} | **{s.weighted:.2f}** | "
            f"{s.context_reasoning:.0%} | {s.uzbek_fluency * 5:.2f} | "
            f"{s.legal_terminology:.0%} | {s.instruction_following:.0%} | "
            f"{s.refusal_accuracy:.0%} | {s.tokens_per_second:.1f} | {s.memory_gb:.1f} GB |"
        )

    lines += ["", "## Kategoriya bo'yicha", "", "| Model | " + " | ".join(
        c for c in ["reasoning", "refusal", "citation", "terminology", "language", "format"]
    ) + " |", "|---|" + "---|" * 6]
    for s in sorted(scores, key=lambda x: x.weighted, reverse=True):
        cells = []
        for cat in ["reasoning", "refusal", "citation", "terminology", "language", "format"]:
            rows = [i for i in s.items if i.category == cat]
            ok = sum(1 for i in rows if i.content_ok and i.instruction_ok)
            cells.append(f"{ok}/{len(rows)}" if rows else "—")
        lines.append(f"| {s.model_id} | " + " | ".join(cells) + " |")

    lines += ["", "## Qaror", ""]
    lines += [f"- {n}" for n in notes]
    lines += ["", f"**Tanlangan model: `{winner}`**" if winner else "**Tanlov qilinmadi.**", ""]

    lines += ["## Eng ko'p uchragan nosozliklar", ""]
    for s in sorted(scores, key=lambda x: x.weighted, reverse=True):
        bad = [i for i in s.items if not (i.content_ok and i.instruction_ok)]
        lines.append(f"### {s.model_id} — {len(bad)}/{len(s.items)} muvaffaqiyatsiz")
        lines.append("")
        for i in bad[:8]:
            lines.append(f"- `{i.item_id}` ({i.category}): {'; '.join(i.failures[:3])}")
        lines.append("")

    return "\n".join(lines)
