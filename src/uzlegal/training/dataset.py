"""Trening ma'lumotini tayyorlash quvuri — Faza 3.

## ⚠️ Eng muhim ogohlantirish

Bu modul **sintetik** namunalar yaratadi. Ular **yurist tomonidan
tekshirilmagan** va shu holida ishlab chiqarish modelini o'qitish uchun
ishlatilmasligi kerak.

Sabab `docs/05-finetuning.md` § 3 da yozilgan: tekshirilmagan yuridik
trening ma'lumoti modelni **ishonch bilan xato qilishga** o'rgatadi — bu
umuman o'qitilmagan modeldan xavfliroq, chunki xato *ishonarli* bo'lib
qoladi.

Shuning uchun har bir namunada `verified: false` turadi va treningga
faqat `verified: true` bo'lganlari olinadi. Bu qattiq cheklov — uni
chetlab o'tish uchun ataylab `--allow-unverified` bayrog'i kerak.

## Quvur

    korpus  →  urug' savollar  →  sintetik javob  →  avtomatik filtr
                                                          ↓
                                    yurist tekshiruvi  ←  nomzodlar hovuzi
                                            ↓
                                      trening to'plami

Avtomatik filtr inson vaqtini tejaydi: aniq yaroqsiz namunalar
yuristga umuman yetib bormaydi.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from uzlegal.index.chunker import Chunk

log = logging.getLogger(__name__)

ROLES = ("jurist", "advocate", "prosecutor", "professor", "judge")


class ContextRef(BaseModel):
    tag: str
    chunk_id: str
    text: str


class TrainingSample(BaseModel):
    """Bitta trening namunasi — `docs/05` § 3 dagi format."""

    id: str
    role: str
    context: list[ContextRef]
    question: str
    answer: str
    citations: list[str] = Field(default_factory=list)

    source: Literal["synthetic", "extracted", "handwritten"] = "synthetic"
    verified: bool = False
    verified_by: str | None = None
    verified_at: str | None = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    legal_area: str | None = None
    rejection_reason: str | None = None

    # Senior yurist kengashining xulosasi (`uzlegal.panel`, docs/26).
    #
    # DIQQAT: bu maydon `verified` ni **almashtirmaydi** va unga ta'sir
    # qilmaydi. Kengash — mashina, `verified` esa odam imzosi.
    # `is_trainable` quyida ataylab faqat `verified` ni tekshiradi:
    # kengash ma'qullagan, lekin odam ko'rmagan namuna treningga
    # tushmaydi (`docs/05 § 3`).
    panel: dict[str, object] | None = None

    @property
    def is_trainable(self) -> bool:
        return self.verified and self.rejection_reason is None

    @property
    def panel_outcome(self) -> str | None:
        """Kengash yo'nalishi: `rad` · `noaniq` · `kengash-ma'qulladi`."""
        if not self.panel:
            return None
        value = self.panel.get("outcome")
        return str(value) if value is not None else None

    @property
    def awaits_human(self) -> bool:
        """Yurist navbatiga tushadimi.

        Kengash rad etganlar navbatga **tushmaydi** — ular yuristga
        ko'rsatilmaydi. Aynan shu odam vaqtini tejaydi.
        """
        if self.verified or self.rejection_reason:
            return False
        outcome = self.panel_outcome
        if outcome is None:
            return True
        if outcome == "rad":
            return False
        return outcome == "noaniq" or bool(self.panel and self.panel.get("spot_check"))


# --------------------------------------------------------------------------- #
# Urug' savollar
# --------------------------------------------------------------------------- #

# Har bir rol uchun savol shakllari. Ular modda **sarlavhasidan** emas,
# uning mazmunidan kelib chiqadi — aks holda model sarlavhani qaytarishni
# o'rganadi, mulohaza yuritishni emas.
_SEED_TEMPLATES: dict[str, list[str]] = {
    "jurist": [
        "{mavzu} bo'yicha qanday qoida belgilangan?",
        "{mavzu} holatida qanday huquqiy oqibat kelib chiqadi?",
        "{mavzu} qanday tartibda amalga oshiriladi?",
    ],
    "advocate": [
        "Mijozim {mavzu} bilan bog'liq muammoga duch keldi. Himoya pozitsiyasi qanday?",
        "{mavzu} bo'yicha mijoz manfaatini qanday himoya qilish mumkin?",
    ],
    "prosecutor": [
        "{mavzu} bo'yicha qanday huquqbuzarlik aniqlanishi mumkin?",
        "{mavzu} holatida javobgarlik qanday asoslanadi?",
    ],
    "professor": [
        "{mavzu} institutining huquqiy tabiati qanday?",
        "{mavzu} bo'yicha normalar orasida kolliziya bormi?",
    ],
    "judge": [
        "{mavzu} bo'yicha nizoda qanday hal qiluv qarori chiqariladi?",
        "{mavzu} holatida tomonlarning dalillari qanday tortiladi?",
    ],
}


def extract_topic(chunk: Chunk) -> str | None:
    """Modda sarlavhasidan mavzuni ajratadi.

    «234-modda. Majburiyat tushunchasi» → «majburiyat tushunchasi»
    """
    title = chunk.heading.rstrip("]").split(">")[-1].strip()
    match = re.sub(r"^\d+(?:-\d+)?\s*[-–]?\s*modda\.?\s*", "", title, flags=re.IGNORECASE)
    match = match.strip()
    if len(match) < 8 or match.lower() in ("kirish", "qism"):
        return None
    return match[0].lower() + match[1:]


def seed_questions(
    chunks: list[Chunk], role: str, limit: int | None = None
) -> Iterator[dict[str, Any]]:
    """Korpusdan urug' savollar yaratadi.

    Har bir chunk uchun bitta savol — ko'proq bo'lsa bir modda haqida
    takroriy namunalar paydo bo'ladi va model o'sha moddaga moslashadi.
    """
    templates = _SEED_TEMPLATES[role]
    produced = 0

    for index, chunk in enumerate(chunks):
        topic = extract_topic(chunk)
        if topic is None:
            continue
        template = templates[index % len(templates)]
        # `chunk` obyektining O'ZI emas, JSON ga yoziladigan ko'rinishi.
        #
        # Ilgari bu yerda `Chunk` modeli to'g'ridan-to'g'ri qaytarilardi va
        # `uzlegal train seed` `json.dumps` da yiqilardi — ya'ni sintetik
        # quvurning BIRINCHI qadami hech qachon ishlamagan. Bu sezilmasdi,
        # chunki `seed_questions` ning unit testlari lug'atning faqat
        # `question` va `role` maydonlarini tekshirardi va natijani hech
        # qachon JSON ga yozmasdi.
        yield {
            "context": [
                ContextRef(tag="C1", chunk_id=chunk.chunk_id, text=chunk.content).model_dump()
            ],
            "chunk_id": chunk.chunk_id,
            "doc_title": chunk.doc_title,
            "article": chunk.article,
            "question": template.format(mavzu=topic),
            "role": role,
        }
        produced += 1
        if limit and produced >= limit:
            return


# --------------------------------------------------------------------------- #
# Avtomatik filtrlar
# --------------------------------------------------------------------------- #

_CITATION_RE = re.compile(r"\[C\d+\]")
_MIN_WORDS = 15
_MAX_WORDS = 600


def check_sample(sample: TrainingSample) -> str | None:
    """Namuna yaroqsiz bo'lsa sababni qaytaradi, aks holda `None`.

    Bu filtr **inson vaqtini tejaydi**: aniq yaroqsiz namunalar yuristga
    umuman yetib bormaydi.
    """
    words = len(sample.answer.split())
    if words < _MIN_WORDS:
        return "javob juda qisqa"
    if words > _MAX_WORDS:
        return "javob juda uzun"

    tags = set(_CITATION_RE.findall(sample.answer))
    if not tags:
        return "iqtibos yo'q"

    known = {c.tag for c in sample.context}
    invalid = tags - {f"[{t}]" for t in known}
    if invalid:
        return f"mavjud bo'lmagan iqtibos: {sorted(invalid)}"

    if sample.role in ("advocate", "prosecutor") and "ZAIF" not in sample.answer.upper():
        return "zaif tomonlar ko'rsatilmagan"

    if sample.question.strip().lower() in sample.answer.strip().lower():
        return "javob savolni takrorlaydi"

    return None


def filter_samples(samples: list[TrainingSample]) -> tuple[list[TrainingSample], dict[str, int]]:
    """Namunalarni filtrlaydi. `(o'tganlar, rad_sabablari)` qaytaradi."""
    passed: list[TrainingSample] = []
    reasons: dict[str, int] = {}

    for sample in samples:
        reason = check_sample(sample)
        if reason is None:
            passed.append(sample)
        else:
            sample.rejection_reason = reason
            reasons[reason] = reasons.get(reason, 0) + 1

    return passed, reasons


# --------------------------------------------------------------------------- #
# Saqlash
# --------------------------------------------------------------------------- #


class Dataset:
    """Trening to'plamini JSONL da saqlaydi va o'qiydi."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, samples: list[TrainingSample]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(s.model_dump_json() for s in samples), encoding="utf-8")

    def read(self) -> list[TrainingSample]:
        if not self.path.exists():
            return []
        return [
            TrainingSample(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def trainable(self, *, allow_unverified: bool = False) -> list[TrainingSample]:
        """Treningga yaroqli namunalar.

        Standart bo'yicha faqat **tekshirilgan** namunalar. Bu qattiq
        cheklov: tekshirilmagan yuridik data modelni ishonch bilan xato
        qilishga o'rgatadi (`docs/05` § 3).
        """
        samples = self.read()
        if allow_unverified:
            return [s for s in samples if s.rejection_reason is None]
        return [s for s in samples if s.is_trainable]

    def stats(self) -> dict[str, object]:
        samples = self.read()
        by_role: dict[str, int] = {}
        for sample in samples:
            by_role[sample.role] = by_role.get(sample.role, 0) + 1
        return {
            "jami": len(samples),
            "tekshirilgan": sum(1 for s in samples if s.verified),
            "rad_etilgan": sum(1 for s in samples if s.rejection_reason),
            "kengashdan_otgan": sum(1 for s in samples if s.panel_outcome),
            "kengash_rad_etdi": sum(1 for s in samples if s.panel_outcome == "rad"),
            "yurist_navbatida": sum(1 for s in samples if s.awaits_human),
            "rollar": by_role,
        }

    def mark_verified(self, sample_id: str, expert: str) -> bool:
        """Namunani tekshirilgan deb belgilaydi (tekshirish interfeysi uchun)."""
        samples = self.read()
        for sample in samples:
            if sample.id == sample_id:
                sample.verified = True
                sample.verified_by = expert
                sample.verified_at = datetime.now(UTC).date().isoformat()
                self.write(samples)
                return True
        return False
