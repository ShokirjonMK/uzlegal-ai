"""Debate protokoli — kelishmovchilikni o'lchash va raund 2 sharti (docs/06 § 3).

## Nima uchun ball kerak

Agentlar erkin suhbatlashmaydi. Ular qat'iy raundlarda ishlaydi va ikkinchi
raund **faqat kerak bo'lganda** o'tkaziladi. Kerakligini o'lchash uchun
kelishmovchilik balli bor:

    0.4 · |Δishonch| + 0.4 · (1 − iqtibos qoplamasi) + 0.2 · xulosa masofasi

Chegara `0.4`. Undan past bo'lsa agentlar aslida rozi va munozara yangi
ma'lumot bermaydi — o'rtacha 30% vaqt tejaladi.

## Nima uchun aynan shu uch signal

* **Ishonch farqi** — eng arzon signal, lekin yolg'iz yetarli emas: ikkala
  agent 0.8 ishonch bilan **qarama-qarshi** xulosaga kelishi mumkin.
* **Iqtibos qoplamasi** — eng informativ. Agentlar turli normalarga tayansa,
  ular turli huquqiy asosda turibdi va tortishuv haqiqiy.
* **Xulosa masofasi** — leksik yaqinlik. Eng shovqinli signal, shuning uchun
  vazni eng past.

Semantik masofa uchun embedding ishlatilmaydi: bu qadam har so'rovda
bajariladi va 1.2 GB modelni faqat ikkita jumlani solishtirish uchun yuklash
narxga arzimaydi.
"""

from __future__ import annotations

from uzlegal.orchestrator.text import content_words, jaccard
from uzlegal.types import Position

DISAGREEMENT_THRESHOLD = 0.4

W_CONFIDENCE = 0.4
W_CITATION = 0.4
W_CONCLUSION = 0.2


def citation_tags(position: Position) -> set[str]:
    return {t.upper() for a in position.arguments for t in a.citations}


def citation_overlap(a: Position, b: Position) -> float:
    """Ikki pozitsiya bir xil normalarga tayanadimi (Jaccard).

    Ikkalasi ham iqtibossiz bo'lsa `1.0` — ular «bir xil (bo'sh) asosda»
    turibdi va bu signal hech narsa aytmaydi. Bunday holda kelishmovchilik
    boshqa ikki signaldan kelishi kerak, iqtibosdan emas.
    """
    return jaccard(citation_tags(a), citation_tags(b))


def conclusion_distance(a: Position, b: Position) -> float:
    """Xulosalar o'rtasidagi leksik masofa (0 — bir xil, 1 — umumiyligi yo'q).

    Bittasi bo'sh bo'lsa masofa maksimal: bo'sh pozitsiya bilan kelishib
    bo'lmaydi, u shunchaki mavjud emas.
    """
    words_a, words_b = content_words(a.stance), content_words(b.stance)
    if not words_a or not words_b:
        return 0.0 if words_a == words_b else 1.0
    return 1.0 - jaccard(words_a, words_b)


def disagreement(a: Position, b: Position) -> float:
    """Kelishmovchilik balli, 0…1 — docs/06 § 3 dagi formula."""
    return (
        W_CONFIDENCE * abs(a.confidence - b.confidence)
        + W_CITATION * (1.0 - citation_overlap(a, b))
        + W_CONCLUSION * conclusion_distance(a, b)
    )


def needs_round_two(
    positions: dict[str, Position], *, threshold: float = DISAGREEMENT_THRESHOLD
) -> bool:
    """Raund 2 kerakmi.

    Ikkitadan kam pozitsiya bo'lsa tortishadigan hech kim yo'q — raund 2
    o'tkazib yuboriladi (masalan prokuror sxema xatosi tufayli tushib qolgan).
    """
    return score(positions) > threshold


def score(positions: dict[str, Position]) -> float:
    """Pozitsiyalar to'plami uchun kelishmovchilik. Juftlik yo'q bo'lsa 0."""
    advocate = positions.get("advocate")
    prosecutor = positions.get("prosecutor")
    if advocate is None or prosecutor is None:
        return 0.0
    return disagreement(advocate, prosecutor)
