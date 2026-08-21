"""Gold set holatlarini tayyorlash va tekshirish (docs/29).

## Muammo

`retrieval-gold-v1` da 36 holat bor. Bu ±16 p.p. shovqin degani —
ya'ni har qanday yaxshilanish statistik jihatdan **isbotlanmaydi**.
Kengaytirish kerak, lekin holat yozish yurist vaqtini oladi.

## Yondashuv

Ish ikkiga bo'linadi:

| Qadam | Kim | Nima |
|---|---|---|
| Manba tanlash | mashina | Korpusdan xilma-xil moddalar |
| Savol yozish | tahlilchi | Tabiiy savol + kutilgan modda |
| **Tekshirish** | **mashina** | Har holat korpusga mos keladimi |

Uchinchi qadam eng muhimi: u holatni **avtomatik rad etadi** agar
kutilgan modda korpusda bo'lmasa yoki savol modda raqamini o'zi
aytib qo'ysa.

## Ishonch darajasi ochiq yoziladi

Har holatda `verified_by` bo'ladi va u **yashirilmaydi**:

    machine   — mashina tekshiruvidan o'tgan
    expert    — malakali yurist tasdiqlagan

Ikkalasi bir xil emas va ularni bir xil deb ko'rsatish ma'lumot
qiymatini yo'qotadi. Yurist kelganda u nolni emas **tayyor ishni**
tekshiradi va qaysi qismga ishonish mumkinligini biladi.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Savolda modda raqami aytilmasligi kerak: aks holda test qidiruvni
#: emas, raqamni topishni o'lchaydi.
_ARTICLE_IN_QUERY = re.compile(r"\b\d{1,4}\s*-?\s*(modda|band|qism)", re.IGNORECASE)

_MIN_QUERY_WORDS = 4

#: Bu toifada savol ATAYLAB modda raqamidan iborat: «FK 228-modda».
#: U qidiruvning boshqa qobiliyatini o'lchaydi — aniq murojaatni topish.
#: Shuning uchun «savolda raqam bor» va «juda qisqa» qoidalari
#: bu toifaga qo'llanmaydi.
LOOKUP_CATEGORY = "modda-lookup"


@dataclass
class GoldCase:
    """Bitta gold holat — `EvalCase` ustiga ishonch maydonlari qo'shilgan."""

    id: str
    query: str
    expected_articles: list[str]
    doc_hint: str | None = None
    category: str = "general"
    note: str | None = None
    #: `machine` yoki `expert`. Standart qiymat yo'q — ataylab majburiy.
    verified_by: str = "machine"
    verified_at: str | None = None

    def as_json(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "query": self.query,
            "expected_articles": self.expected_articles,
            "category": self.category,
            "verified_by": self.verified_by,
        }
        if self.doc_hint:
            data["doc_hint"] = self.doc_hint
        if self.note:
            data["note"] = self.note
        if self.verified_at:
            data["verified_at"] = self.verified_at
        return data


@dataclass
class CaseIssue:
    """Holatdagi nuqson — nima va nima uchun."""

    case_id: str
    problem: str
    detail: str = ""


@dataclass
class CheckReport:
    ok: list[GoldCase] = field(default_factory=list)
    issues: list[CaseIssue] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        by: dict[str, int] = {}
        for issue in self.issues:
            by[issue.problem] = by.get(issue.problem, 0) + 1
        return {"o'tdi": len(self.ok), "rad etildi": len(self.issues), **by}


# --------------------------------------------------------------------------- #
# Tekshirish
# --------------------------------------------------------------------------- #


def check_case(case: GoldCase, index: Any) -> CaseIssue | None:
    """Holat korpusga mos keladimi.

    Tekshiruvlar tartibi arzondan qimmatga: matn shakli avval, korpus
    murojaati keyin.
    """
    if case.category != LOOKUP_CATEGORY:
        if len(case.query.split()) < _MIN_QUERY_WORDS:
            return CaseIssue(case.id, "savol juda qisqa", case.query)

        if _ARTICLE_IN_QUERY.search(case.query):
            # Savol modda raqamini aytsa, test qidiruv sifatini emas,
            # raqamni topishni o'lchaydi — bu boshqa narsa.
            return CaseIssue(case.id, "savolda modda raqami bor", case.query)

    if not case.expected_articles:
        return CaseIssue(case.id, "kutilgan modda ko'rsatilmagan")

    found = _articles_in_corpus(case, index)
    missing = [a for a in case.expected_articles if a not in found]
    if missing:
        return CaseIssue(
            case.id,
            "kutilgan modda korpusda yo'q",
            f"{', '.join(missing)}" + (f" ({case.doc_hint})" if case.doc_hint else ""),
        )
    return None


def _articles_in_corpus(case: GoldCase, index: Any) -> set[str]:
    """Kutilgan moddalardan qaysilari korpusda bor.

    `doc_hint` berilgan bo'lsa faqat o'sha hujjatda izlanadi — aks holda
    boshqa kodeksdagi bir xil raqamli modda holatni «to'g'ri» qilib
    ko'rsatardi (docs/24 § 3 dagi noaniqlik).
    """
    hint = (case.doc_hint or "").casefold()
    wanted = set(case.expected_articles)
    found: set[str] = set()

    for chunk in index._chunks.values():
        if not chunk.article:
            continue
        if hint and hint not in (chunk.doc_title or "").casefold():
            continue
        # Birlashtirilgan bo'lak «130-131» yorlig'ini oladi (`_merge_tiny`).
        # 130-modda korpusda BOR, faqat o'z nomi bilan emas. `EvalCase.matches()`
        # aynan shu mantiqni ishlatadi — tekshirgich undan qattiqroq
        # bo'lsa, ishlaydigan holatni rad etardi.
        labels = set(chunk.article.split("-")) | {chunk.article}
        found |= wanted & labels
    return found


def check_all(cases: list[GoldCase], index: Any) -> CheckReport:
    report = CheckReport()
    seen: set[str] = set()

    for case in cases:
        if case.id in seen:
            report.issues.append(CaseIssue(case.id, "identifikator takrorlangan"))
            continue
        seen.add(case.id)

        issue = check_case(case, index)
        if issue is None:
            report.ok.append(case)
        else:
            report.issues.append(issue)
    return report


# --------------------------------------------------------------------------- #
# O'qish va yozish
# --------------------------------------------------------------------------- #


def read_cases(path: Path) -> list[GoldCase]:
    cases: list[GoldCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        data = json.loads(line)
        cases.append(
            GoldCase(
                id=data["id"],
                query=data["query"],
                expected_articles=list(data.get("expected_articles") or []),
                doc_hint=data.get("doc_hint"),
                category=data.get("category", "general"),
                note=data.get("note"),
                # Eski holatlarda maydon yo'q. Ular yurist tomonidan
                # yozilgan deb FARAZ QILINMAYDI — noma'lum deb belgilanadi.
                verified_by=data.get("verified_by", "noma'lum"),
                verified_at=data.get("verified_at"),
            )
        )
    return cases


def write_cases(path: Path, cases: list[GoldCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(c.as_json(), ensure_ascii=False) for c in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Manba tanlash
# --------------------------------------------------------------------------- #


def sample_articles(
    index: Any,
    *,
    doc_hint: str | None = None,
    limit: int = 20,
    min_chars: int = 300,
    offset: int = 0,
) -> list[dict[str, str]]:
    """Holat yozish uchun moddalar tanlaydi.

    Tanlov **deterministik**: har hujjatdan modda raqami bo'yicha
    tartiblangan ro'yxat. Tasodifiy tanlash bir xil korpusda har safar
    boshqa natija berardi va ishni takrorlab bo'lmasdi.

    Juda qisqa moddalar chiqarib tashlanadi: «234-modda. Bekor
    qilingan» dan savol yasab bo'lmaydi.
    """
    hint = (doc_hint or "").casefold()
    seen: set[str] = set()
    rows: list[dict[str, str]] = []

    for chunk in index._chunks.values():
        if not chunk.article or chunk.kind not in ("article", "merged"):
            continue
        if hint and hint not in (chunk.doc_title or "").casefold():
            continue
        if len(chunk.content) < min_chars:
            continue
        key = f"{chunk.doc_id}:{chunk.article}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "doc_title": chunk.doc_title or "",
                "article": chunk.article,
                "unit": chunk.unit,
                "text": chunk.content[:600],
            }
        )

    rows.sort(key=lambda r: (r["doc_title"], _article_key(r["article"])))
    return rows[offset : offset + limit]


def _article_key(article: str) -> tuple[int, int]:
    """«244-3» → (244, 3). Tartiblash raqam bo'yicha, matn bo'yicha emas."""
    parts = article.split("-")
    try:
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return 10**9, 0
