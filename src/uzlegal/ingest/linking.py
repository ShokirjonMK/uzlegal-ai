"""Havolalarni bog'lash — docs/03 § 3.5.

Yuridik matn havolaga to'la: «ushbu Kodeksning 45-moddasida nazarda
tutilgan», «Mehnat kodeksining 78-moddasiga muvofiq». Retrieval bu grafni
kontekstni kengaytirish uchun ishlatadi: 234-modda topilsa, u havola qilgan
45-modda ham kontekstga qo'shiladi.

## Ikki manba, ikki xil ishonch

| Manba | Ishonch | Nima beradi |
|-------|---------|-------------|
| HTML `<a href>` | **Yuqori** | Nishon hujjat ID si va element ID si aniq |
| Matn shabloni | O'rta | Faqat matndan o'qilgani |

HTML manbasi ustun, chunki lex.uz havolani o'zi qo'yadi:

    <a href="/uz/docs/-97664#-338735">176-moddasi</a>

Bu yerda `-97664` — Maʼmuriy javobgarlik kodeksi, `-338735` — uning ichki
element ID si. Parser `clean_text()` da teglarni olib tashlaydi va bu
ma'lumot **yo'qoladi** — shuning uchun havolalar xom HTML dan alohida
o'qiladi (parser o'zgarmaydi: uning vazifasi matn, havola emas).

## Nishonni moddaga bog'lash

`#-338735` element ID si moddaning o'zi bo'lmasligi mumkin — u modda ichidagi
xatboshi bo'lishi ham mumkin. Shuning uchun har bir hujjat uchun
`element_id → modda raqami` xaritasi quriladi: hujjat tartibida yurib,
har bir elementni oxirgi ko'rilgan moddaga bog'laymiz.

## Filtrlanadigan havolalar

* `javascript:scrollText(...)` — sahifa ichidagi TOC harakati
* `?ONDATE=…` — **hujjatning eski tahririga** havola («Oldingi»), norma
  havolasi emas; grafga tushsa retrieval eskirgan matnni tortadi
* Ijtimoiy tarmoq va ulashish havolalari
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping
from pathlib import Path

from pydantic import BaseModel, Field

from uzlegal.ingest.normalize import expand_article_run, fold
from uzlegal.ingest.types import ParsedDocument

log = logging.getLogger(__name__)

RefKind = str  # "internal" | "external" | "unresolved"


class Reference(BaseModel):
    """Bitta havola: qaysi moddadan qaysi moddaga."""

    from_doc: str
    from_article: str | None
    to_doc: str | None
    to_article: str | None
    kind: RefKind
    origin: str = Field(default="matn", description="havola manbai: `matn` yoki `html`")
    text: str = ""

    @property
    def from_node(self) -> str:
        return f"{self.from_doc}:{self.from_article}"

    @property
    def to_node(self) -> str | None:
        if self.to_doc is None or self.to_article is None:
            return None
        return f"{self.to_doc}:{self.to_article}"


# --------------------------------------------------------------------------- #
# HTML havolalari
# --------------------------------------------------------------------------- #

# Parserdagi bilan bir xil struktura, lekin bu yerda teglar **saqlanadi**.
_CONTENT_DIV = re.compile(r'<div name="(-?\d+)" id="\1">(.*?)</div>', re.DOTALL)
_ANCHOR = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
_DOC_HREF = re.compile(r"^(?:https?://lex\.uz)?/(?:uz|ru)/docs/(-?\d+)(?:#(-?\d+))?$")
_TAGS = re.compile(r"<[^>]+>")


def element_article_map(raw_html: str, doc: ParsedDocument) -> dict[str, str]:
    """`element_id → modda raqami` xaritasi.

    Modda sarlavhasi va undan keyingi barcha matn bloklari shu moddaga
    tegishli — hujjat HTML da tartib bo'yicha keladi, shuning uchun oddiy
    holat mashinasi yetarli.
    """
    articles = {a.element_id: a.article_number for a in doc.articles if a.article_number}
    mapping: dict[str, str] = {}
    current: str | None = None

    for m in _CONTENT_DIV.finditer(raw_html):
        element_id = m.group(1)
        if element_id in articles:
            current = articles[element_id]
        if current:
            mapping[element_id] = current
    return mapping


def _anchor_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _TAGS.sub(" ", fragment)).strip()


def html_references(
    raw_html: str,
    doc: ParsedDocument,
    element_maps: Mapping[str, Mapping[str, str]] | None = None,
) -> list[Reference]:
    """Xom HTML dagi `<a href>` havolalarini ajratadi.

    `element_maps` — `{doc_id: {element_id: modda}}`. Boshqa hujjatga
    ko'rsatgan havolani moddagacha aniqlash uchun kerak; berilmasa nishon
    modda faqat havola matnidan o'qiladi.
    """
    maps = dict(element_maps or {})
    maps.setdefault(doc.doc_id, element_article_map(raw_html, doc))
    own = maps[doc.doc_id]

    out: list[Reference] = []
    current: str | None = None
    articles = {a.element_id: a.article_number for a in doc.articles if a.article_number}

    for block in _CONTENT_DIV.finditer(raw_html):
        if block.group(1) in articles:
            current = articles[block.group(1)]
        if current is None:
            continue

        for anchor in _ANCHOR.finditer(block.group(2)):
            href = anchor.group(1).strip()
            if "ONDATE" in href:  # «Oldingi» — eski tahrir, norma havolasi emas
                continue
            m = _DOC_HREF.match(href)
            if not m:
                continue

            to_doc, to_eid = m.group(1), m.group(2)
            label = _anchor_text(anchor.group(2))
            target_map = own if to_doc == doc.doc_id else maps.get(to_doc, {})
            to_article = target_map.get(to_eid or "") or _label_article(label)

            if to_doc == doc.doc_id and to_article == current:
                continue  # o'ziga havola — grafda foydasiz

            out.append(
                Reference(
                    from_doc=doc.doc_id,
                    from_article=current,
                    to_doc=to_doc,
                    to_article=to_article,
                    kind=_kind(doc.doc_id, to_doc, to_article),
                    origin="html",
                    text=label[:80],
                )
            )
    return out


def _kind(from_doc: str, to_doc: str | None, to_article: str | None) -> RefKind:
    if to_doc is None or to_article is None:
        return "unresolved"
    return "internal" if to_doc == from_doc else "external"


# --------------------------------------------------------------------------- #
# Matn shablonlari
# --------------------------------------------------------------------------- #

_RUN = r"((?:\d+(?:-\d+)?\s*(?:,|\bva\b|\bhamda\b|—|–|(?<=\s)-(?=\s))\s*)*\d+(?:-\d+)?)"

# «ushbu Kodeksning 45-moddasida», «mazkur Kodeks 324 - 326-moddalarida»
_INTERNAL = re.compile(rf"\b(?:ushbu|mazkur)\s+(?:kodeks|qonun)\w*\s+{_RUN}\s*-\s*moddas?\w*")

# «Mehnat kodeksining 78-moddasiga», «Fuqarolik protsessual kodeksi 324-moddasi»
_EXTERNAL = re.compile(
    rf"\b((?:[\w'-]+\s+){{0,3}}?[\w'-]+)\s+kodeksi(?:ning)?\s+{_RUN}\s*-\s*moddas?\w*"
)

# Kodeks nomini hujjat sarlavhasi bilan solishtirishda ortiqcha so'zlar
_TITLE_NOISE = re.compile(r"o'zbekiston|respublikasi\w*|ning\b|kodeksi\w*|\(.*?\)")


def _label_article(label: str) -> str | None:
    """Havola matnidan modda raqami.

    Faqat matnda «modda» so'zi bo'lsa ishonamiz. Aks holda raqam band yoki
    qism raqami bo'lishi mumkin («17-bandi») va uni modda deb olish grafda
    mavjud bo'lmagan qirra yaratadi.
    """
    folded = fold(label)
    if "modda" not in folded:
        return None
    m = re.search(r"\b(\d+(?:-\d+)?)\s*-?\s*modda", folded)
    return m.group(1) if m else None


def _code_registry(docs: Iterable[ParsedDocument]) -> dict[str, str]:
    """`kodeks nomi (fold) → doc_id`. Havolani hujjatga bog'lash uchun."""
    registry: dict[str, str] = {}
    for doc in docs:
        name = _TITLE_NOISE.sub(" ", fold(doc.title))
        name = re.sub(r"\s+", " ", name).strip()
        if name:
            registry.setdefault(name, doc.doc_id)
    return registry


def text_references(
    doc: ParsedDocument, code_registry: Mapping[str, str] | None = None
) -> list[Reference]:
    """Modda matnidagi havola iboralarini ajratadi."""
    registry = code_registry or {}
    out: list[Reference] = []

    for article in doc.articles:
        if not article.article_number:
            continue
        body = fold(article.body)

        for m in _INTERNAL.finditer(body):
            for number in expand_article_run(m.group(1)):
                if number == article.article_number:
                    continue
                out.append(
                    Reference(
                        from_doc=doc.doc_id,
                        from_article=article.article_number,
                        to_doc=doc.doc_id,
                        to_article=number,
                        kind="internal",
                        text=m.group(0)[:80],
                    )
                )

        for m in _EXTERNAL.finditer(body):
            name = re.sub(r"\s+", " ", _TITLE_NOISE.sub(" ", m.group(1))).strip()
            to_doc = _resolve_code(name, registry)
            for number in expand_article_run(m.group(2)):
                out.append(
                    Reference(
                        from_doc=doc.doc_id,
                        from_article=article.article_number,
                        to_doc=to_doc,
                        to_article=number,
                        kind=_kind(doc.doc_id, to_doc, number),
                        text=m.group(0)[:80],
                    )
                )
    return out


def _resolve_code(name: str, registry: Mapping[str, str]) -> str | None:
    """Kodeks nomini hujjat ID siga bog'laydi.

    Nom matnda kelishik qo'shimchasi bilan keladi va sarlavhaning bir qismi
    bo'ladi («Uy-joy» ⊂ «Oʻzbekiston Respublikasining Uy-joy kodeksi»),
    shuning uchun aniq tenglik emas, ichma-ichlik tekshiriladi.
    """
    if not name:
        return None
    if name in registry:
        return registry[name]
    matches = {doc_id for key, doc_id in registry.items() if name in key or key in name}
    return matches.pop() if len(matches) == 1 else None


def extract_references(
    doc: ParsedDocument,
    raw_html: str | None = None,
    *,
    code_registry: Mapping[str, str] | None = None,
    element_maps: Mapping[str, Mapping[str, str]] | None = None,
) -> list[Reference]:
    """Hujjatdagi barcha havolalar — matn shablonlari va HTML havolalari."""
    refs = text_references(doc, code_registry)
    if raw_html:
        refs += html_references(raw_html, doc, element_maps)
    return refs


# --------------------------------------------------------------------------- #
# Graf
# --------------------------------------------------------------------------- #


class ReferenceGraph:
    """Modda havolalari grafi.

    Tugun kaliti — `doc_id:modda` (masalan `-111189:234`). Oddiy lug'at
    yetarli: 20 kodeksda ~100k qirra, bu xotirada bir necha megabayt.
    """

    def __init__(self) -> None:
        self.references: list[Reference] = []
        self._out: dict[str, set[str]] = defaultdict(set)
        self._in: dict[str, set[str]] = defaultdict(set)

    def add(self, ref: Reference) -> None:
        self.references.append(ref)
        target = ref.to_node
        if target is None:
            return
        self._out[ref.from_node].add(target)
        self._in[target].add(ref.from_node)

    def neighbors(self, article: str, depth: int = 1, direction: str = "out") -> list[str]:
        """`depth` daraja narigi tugunlar (o'zi kirmaydi).

        `direction`: `out` — havola qilinganlar · `in` — havola qilganlar ·
        `both` — ikkalasi. Retrieval standart holda `out` ni ishlatadi:
        234-modda 45-moddaga havola qilsa, 45-modda kontekstga qo'shiladi.
        """
        seen: set[str] = {article}
        frontier: deque[tuple[str, int]] = deque([(article, 0)])
        found: list[str] = []

        while frontier:
            node, level = frontier.popleft()
            if level >= depth:
                continue
            for nxt in self._edges(node, direction):
                if nxt in seen:
                    continue
                seen.add(nxt)
                found.append(nxt)
                frontier.append((nxt, level + 1))
        return found

    def _edges(self, node: str, direction: str) -> set[str]:
        if direction == "in":
            return self._in.get(node, set())
        if direction == "both":
            return self._out.get(node, set()) | self._in.get(node, set())
        return self._out.get(node, set())

    def stats(self) -> dict[str, int]:
        kinds: dict[str, int] = {}
        for ref in self.references:
            kinds[ref.kind] = kinds.get(ref.kind, 0) + 1
        return {
            "havolalar": len(self.references),
            "tugunlar": len(set(self._out) | set(self._in)),
            "qirralar": sum(len(v) for v in self._out.values()),
            **kinds,
        }

    # ------------------------------------------------------------------ #

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(r.model_dump_json() for r in self.references), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: Path) -> ReferenceGraph:
        graph = cls()
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                graph.add(Reference(**json.loads(line)))
        return graph


def build_graph(
    docs: Iterable[ParsedDocument], html: Mapping[str, str] | None = None
) -> ReferenceGraph:
    """Hujjatlar to'plamidan havola grafini quradi.

    `html` — `{doc_id: xom HTML}`. Berilsa HTML havolalari ham qo'shiladi
    va hujjatlararo havolalar modda darajasigacha aniqlanadi (element ID
    xaritalari **avval** hamma hujjat uchun quriladi, keyin havolalar
    ajratiladi — aks holda oldinga ishoralar hal qilinmay qolardi).
    """
    documents = list(docs)
    registry = _code_registry(documents)
    pages = dict(html or {})

    element_maps = {
        doc.doc_id: element_article_map(pages[doc.doc_id], doc)
        for doc in documents
        if doc.doc_id in pages
    }

    graph = ReferenceGraph()
    for doc in documents:
        refs = extract_references(
            doc,
            pages.get(doc.doc_id),
            code_registry=registry,
            element_maps=element_maps,
        )
        for ref in refs:
            graph.add(ref)

    log.debug("Havola grafi: %s", graph.stats())
    return graph
