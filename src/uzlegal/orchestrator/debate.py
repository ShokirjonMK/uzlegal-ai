"""Munozara protokoli — raundlar va kelishmovchilik balli (docs/06 § 3).

## Nima uchun erkin suhbat emas

Agentlar bir-biri bilan erkin gaplashsa konvergensiya kafolatlanmaydi va
xarajat oldindan bilinmaydi. Qat'iy raundli protokol ikkalasini ham
yechadi: raund soni cheklangan, har raundning kirishi aniq.

## Nima uchun maksimum 2 raund

Uchinchi raundda agentlar bir xil dalilni qayta ifodalay boshlaydi,
kontekst o'sadi va sifat tushadi (lost-in-the-middle). Empirik:
raund 1→2 sifat +12%, 2→3 +2%, 3→4 −1%.

## Kelishmovchilik balli

Ikkinchi raund **har doim** o'tkazilmaydi — agentlar aslida rozi bo'lsa
munozaraning ma'nosi yo'q va u vaqtni behuda sarflaydi (o'rtacha 30%).
"""

from __future__ import annotations

import logging

from uzlegal.ingest.normalize import fold
from uzlegal.types import Position

log = logging.getLogger(__name__)

# Undan yuqori bo'lsa ikkinchi raund o'tkaziladi (docs/06 § 3).
DISAGREEMENT_THRESHOLD = 0.4

MAX_ROUNDS = 2


def citation_overlap(a: Position, b: Position) -> float:
    """Ikki pozitsiya bir xil normalarga tayanadimi — Jaccard o'xshashligi.

    Turli normalarga tayanish kuchli kelishmovchilik belgisi: tomonlar
    bir xil huquqiy asosni turlicha talqin qilayotgani emas, balki
    umuman boshqa asosdan kelib chiqayotgani.
    """
    tags_a = {t.upper() for arg in a.arguments for t in arg.citations}
    tags_b = {t.upper() for arg in b.arguments for t in arg.citations}
    if not tags_a and not tags_b:
        return 1.0  # ikkalasi ham iqtibossiz — bu farq emas
    union = tags_a | tags_b
    return len(tags_a & tags_b) / len(union) if union else 1.0


def conclusion_distance(a: Position, b: Position) -> float:
    """Pozitsiya matnlari qanchalik uzoq — 0 (bir xil) … 1 (umuman boshqa).

    Semantik masofa o'rniga leksik: embedding chaqiruvi bu yerda
    kechikishga arzimaydi, chunki ball faqat **chegara** uchun kerak,
    aniq qiymat uchun emas.
    """
    words_a = set(fold(a.stance).split())
    words_b = set(fold(b.stance).split())
    if not words_a or not words_b:
        return 1.0
    return 1.0 - len(words_a & words_b) / len(words_a | words_b)


def disagreement(a: Position, b: Position) -> float:
    """Ikki pozitsiya orasidagi kelishmovchilik — 0…1 (docs/06 § 3)."""
    return round(
        0.4 * abs(a.confidence - b.confidence)
        + 0.4 * (1.0 - citation_overlap(a, b))
        + 0.2 * conclusion_distance(a, b),
        3,
    )


def needs_second_round(
    positions: dict[str, Position], threshold: float = DISAGREEMENT_THRESHOLD
) -> tuple[bool, float]:
    """`(kerakmi, ball)`.

    Pozitsiyalardan biri olinmagan bo'lsa ikkinchi raund o'tkazilmaydi:
    rad etadigan tomon yo'q, munozara bir tomonlama bo'lardi.
    """
    advocate = positions.get("advocate")
    prosecutor = positions.get("prosecutor")
    if advocate is None or prosecutor is None:
        return False, 0.0
    score = disagreement(advocate, prosecutor)
    return score > threshold, score
