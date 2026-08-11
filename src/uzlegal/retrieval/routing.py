"""Hujjat yo'naltirish — savolni to'g'ri kodeksga bog'lash.

## Muammo (baholashda o'lchangan)

Indeksda 20 ta kodeks bor. Ularning modda raqamlari **takrorlanadi** va
ko'p atama ham umumiy («to'lash», «muddat», «tartib»). Natijada:

    savol:   "Maoshni toʻlash tartibi va muddatlari"
    kerak:   Mehnat kodeksi, 333-modda
    olindi:  Bojxona kodeksi 327 · Bojxona kodeksi 333

Ikkala kodeksda ham 333-modda bor va ikkalasi ham «toʻlash muddati»
haqida. Leksik va semantik qidiruv ularni ajrata olmaydi, chunki farq
so'zda emas — **sohada**.

## Yechim: yumshoq ko'tarish, qat'iy filtr emas

Savoldagi soha belgilari sanaladi va g'olib sohaning hujjatlari fusion
ballida ko'tariladi. Nima uchun filtr emas:

* Yo'naltirish evristika — u xato qilishi mumkin
* Filtr xato qilganda to'g'ri javob **butunlay** yo'qoladi
* Ko'tarish xato qilganda u faqat bir necha o'rin pastga tushadi

Yuridik qidiruvda ikkinchi xato birinchisidan ancha arzon.

## Protsessual savollar

«Sudga qanday shikoyat qilaman» savoli qaysi kodeksga tegishli — bu nizo
turiga bog'liq (jinoiy → JPK, fuqarolik → FPK, iqtisodiy → IPK). Shuning
uchun protsessual sohalar moddiy sohalarni **almashtirmaydi**, ularga
qo'shiladi: ikkalasi ham ko'tariladi.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from uzlegal.ingest.normalize import fold

log = logging.getLogger(__name__)

DEFAULT_ROUTING = Path("configs/retrieval/routing.yaml")


@dataclass(frozen=True)
class Domain:
    """Bitta huquq sohasi va uning hujjatlari."""

    name: str
    documents: tuple[str, ...]
    triggers: tuple[str, ...]
    weight: float = 1.0


@dataclass
class Route:
    """Yo'naltirish natijasi.

    `scores` — barcha sohalar ballari (debug va hisobot uchun), `documents`
    esa ko'tariladigan hujjat bo'laklari. Ikkinchisi asosiy natija.
    """

    domains: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0

    @property
    def is_routed(self) -> bool:
        return bool(self.documents)

    def matches(self, doc_title: str) -> bool:
        """Hujjat sarlavhasi yo'naltirilgan hujjatlardan biriga mos keladimi."""
        folded = fold(doc_title)
        return any(doc in folded for doc in self.documents)

    @property
    def primary_document(self) -> str | None:
        """Eng ishonchli hujjat — `search_article` uchun doc_hint."""
        return self.documents[0] if self.documents else None


@dataclass(frozen=True)
class RoutingConfig:
    domains: tuple[Domain, ...]
    boost: float = 0.8
    min_score: float = 1.0
    term_weight: float = 1.0
    phrase_bonus: float = 0.5


def _parse_config(data: dict[str, object]) -> RoutingConfig:
    domains: list[Domain] = []
    raw_domains = data.get("domains") or {}
    if not isinstance(raw_domains, dict):
        raise ValueError("routing.yaml: 'domains' lug'at bo'lishi kerak")

    for name, body in raw_domains.items():
        body = dict(body or {})  # type: ignore[arg-type]
        documents = tuple(fold(str(d)) for d in (body.get("documents") or []))
        triggers = tuple(fold(str(t)) for t in (body.get("triggers") or []))
        if not documents or not triggers:
            log.warning("Yo'naltirish sohasi '%s' to'liq emas — o'tkazib yuborildi", name)
            continue
        domains.append(
            Domain(
                name=str(name),
                documents=documents,
                triggers=triggers,
                weight=float(body.get("weight", 1.0)),  # type: ignore[arg-type]
            )
        )

    return RoutingConfig(
        domains=tuple(domains),
        boost=float(data.get("boost", 0.8)),  # type: ignore[arg-type]
        min_score=float(data.get("min_score", 1.0)),  # type: ignore[arg-type]
        term_weight=float(data.get("term_weight", 1.0)),  # type: ignore[arg-type]
        phrase_bonus=float(data.get("phrase_bonus", 0.5)),  # type: ignore[arg-type]
    )


@functools.lru_cache(maxsize=4)
def load_routing(path: Path = DEFAULT_ROUTING) -> RoutingConfig:
    """Sozlamani yuklaydi. Fayl yo'q bo'lsa — yo'naltirish o'chadi."""
    if not path.exists():
        log.debug("Yo'naltirish sozlamasi topilmadi: %s", path)
        return RoutingConfig(domains=())
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _parse_config(data)


class DocumentRouter:
    """Savolni huquq sohasiga va shu sohaning hujjatlariga bog'laydi."""

    def __init__(self, config: RoutingConfig | None = None) -> None:
        self.config = config if config is not None else load_routing()

    # ------------------------------------------------------------------ #

    def route(self, query: str) -> Route:
        """Savolni tahlil qilib, ko'tariladigan hujjatlarni belgilaydi.

        Bir nechta soha g'olib bo'lishi mumkin (masalan «mehnat» +
        «fuqarolik-protsessual»), chunki savol ikkalasiga ham tegishli —
        sudga mehnat nizosi bo'yicha murojaat.
        """
        if not self.config.domains:
            return Route()

        folded = fold(query)
        scores: dict[str, float] = {}

        for domain in self.config.domains:
            score = sum(
                self._term_score(term) for term in domain.triggers if term and term in folded
            )
            if score > 0:
                scores[domain.name] = round(score * domain.weight, 3)

        if not scores:
            return Route()

        best = max(scores.values())
        if best < self.config.min_score:
            log.debug("Yo'naltirish qo'llanilmadi: eng yuqori ball %.2f", best)
            return Route(scores=scores)

        # G'olibga yaqin sohalar ham qoladi — savol chegarada bo'lishi mumkin
        # («mehnat nizosi bo'yicha sudga murojaat» ikki sohaga tegishli).
        threshold = best * 0.6
        winners = [
            domain
            for domain in self.config.domains
            if scores.get(domain.name, 0.0) >= threshold
        ]
        winners.sort(key=lambda d: scores[d.name], reverse=True)

        documents: list[str] = []
        for domain in winners:
            for doc in domain.documents:
                if doc not in documents:
                    documents.append(doc)

        return Route(
            domains=[d.name for d in winners],
            documents=documents,
            scores=scores,
            confidence=self._confidence(best, scores),
        )

    def _term_score(self, term: str) -> float:
        """Ko'p so'zli ibora aniqroq signal — u ko'proq ball oladi."""
        words = term.count(" ") + 1
        return self.config.term_weight + self.config.phrase_bonus * (words - 1)

    @staticmethod
    def _confidence(best: float, scores: dict[str, float]) -> float:
        """G'olib qanchalik ajralib turadi — 0…1.

        Bitta soha aniq yetakchi bo'lsa ishonch yuqori; ikki soha teng
        bo'lsa past, ya'ni ko'tarish kuchi ham kamayadi.
        """
        total = sum(scores.values())
        if total <= 0:
            return 0.0
        return min(1.0, best / total)

    # ------------------------------------------------------------------ #

    def boost_factor(self, route: Route, doc_title: str) -> float:
        """Ushbu hujjat uchun ball ko'paytmasi.

        Yo'naltirilmagan yoki mos kelmagan hujjat uchun `1.0` — ya'ni
        hech narsa o'zgarmaydi. Bu muhim: ko'tarish faqat **qo'shadi**,
        boshqalarni jazolamaydi.
        """
        if not route.is_routed or not route.matches(doc_title):
            return 1.0
        return 1.0 + self.config.boost * route.confidence
