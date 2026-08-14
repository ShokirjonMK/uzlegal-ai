"""Havola yaxlitligi nazorati — docs/22 § 2.

## Bu ziddiyat detektori EMAS

Dastlabki g'oya «zid normalarni topish» edi va u iqtibos grafi bilan
**bajarilmaydi**. Graf faqat «A hujjat B ga havola qiladi» deydi; u
«A B ga zid» degan ma'noni bermaydi. Ziddiyatni aniqlash semantik
tahlil, graf yurish emas (docs/22 § 2.1).

Determinstik yo'l bilan haqiqatan aniqlanadigan narsa — **havola
yaxlitligining buzilishi**. Bu kamtarona ko'rinadi, lekin qonun
matnidagi haqiqiy nuqson va uni qonunchilikni takomillashtirish organi
tuzatishi mumkin.

## Uch sinf

| Sinf | Ta'rif |
|---|---|
| `uzilgan` | `to_doc`/`to_article` bor, lekin korpusda bunday modda **yo'q** |
| `bekor` | Nishon modda mavjud, lekin holati `in_force` emas |
| `hal-qilinmagan` | `kind = "unresolved"` — havola matni tanildi, nishon topilmadi |

## Chiqish tili

Chiqadigan narsa — **nomzodlar ro'yxati**, uni professor agenti yoki
yurist baholaydi. Modul hech qachon «ziddiyat topildi» demaydi
(docs/22 § 5 B3): natija tekshirilishi kerak bo'lgan ishoradir,
xulosa emas.

## Nima uchun `index` qatlamida

Havola grafi `ingest` da quriladi, nishon moddaning mavjudligi esa
**indeksdan** bilinadi. Ikkalasi kesishadigan eng past qatlam — `index`
(u `ingest` dan yuqorida). Qatlam shartnomasiga o'zgartirish kerak emas.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from collections.abc import Iterable

    from uzlegal.index.chunker import Chunk
    from uzlegal.ingest.linking import Reference, ReferenceGraph

log = logging.getLogger(__name__)

IssueKind = Literal["uzilgan", "bekor", "hal-qilinmagan"]

#: Buyruq satridagi `--kind` qiymatlari — tartib hisobotda ham shu.
ISSUE_KINDS: tuple[IssueKind, ...] = ("uzilgan", "bekor", "hal-qilinmagan")

#: Har bir sinfning o'zbekcha izohi — hisobot sarlavhalari shundan olinadi.
KIND_LABELS: dict[IssueKind, str] = {
    "uzilgan": "uzilgan havola — nishon modda korpusda topilmadi",
    "bekor": "bekor qilinganga havola — nishon modda amalda emas",
    "hal-qilinmagan": "hal qilinmagan havola — nishon aniqlanmadi",
}

#: Amaldagi norma holati. Boshqa har qanday qiymat `bekor` sinfiga tushadi.
IN_FORCE = "in_force"

#: Birlashgan bo'lakning oraliq yorlig'i — «18-19», «111-113».
_RANGE = re.compile(r"(\d+)-(\d+)")


class ArticleSource(Protocol):
    """`collisions` ga kerak bo'lgan indeks yuzasi — shundan ortig'i emas.

    `KnowledgeIndex` bu protokolga mos keladi. Protokol sifatida yozilishi
    testni indekssiz yozish imkonini beradi: LanceDB va BM25 fayllarini
    qurmasdan ham nazoratni tekshirish mumkin.
    """

    def chunks_for_article(self, doc_id: str, article: str, *, limit: int = 4) -> list[Chunk]:
        """Berilgan hujjatning berilgan moddasiga tegishli bo'laklar."""
        ...  # pragma: no cover — protokol

    def article_labels(self, doc_id: str) -> list[str]:
        """Hujjatning indeksdagi modda yorliqlari."""
        ...  # pragma: no cover — protokol

    def reference_graph(self, *, rebuild: bool = False) -> ReferenceGraph | None:
        """Havola grafi; tayyorlanmasa `None`."""
        ...  # pragma: no cover — protokol


class TargetLookup:
    """Nishon moddaning korpusdagi holati, keshlangan.

    `chunks_for_article()` har chaqiruvda butun bo'lak lug'atini aylanib
    chiqadi. 47 388 havola uchun buni takrorlash kvadratik ish bo'lardi,
    holbuki **takrorlanuvchi nishonlar ko'p** (o'lchandi: nishoni
    aniqlangan 33 192 havolada atigi 8 962 xil nishon). Shuning uchun
    natija `(doc_id, modda)` bo'yicha keshlanadi va har nishon bir marta
    izlanadi — butun korpus nazorati shu bilan 23 s da tugaydi.
    """

    def __init__(self, source: ArticleSource) -> None:
        self._source = source
        self._cache: dict[tuple[str, str], str | None] = {}
        self._labels: dict[str, list[str]] = {}

    def status(self, doc_id: str, article: str) -> str | None:
        """Nishon moddaning holati; modda korpusda bo'lmasa `None`.

        Modda bir nechta bo'lakka bo'lingan bo'lishi mumkin va nazariy
        jihatdan ularning holati turlicha bo'ladi. Birinchi bo'lak
        moddaning boshi (`chunks_for_article` shunday tartiblaydi),
        shuning uchun holat o'shandan olinadi.
        """
        key = (doc_id, article)
        if key in self._cache:
            return self._cache[key]

        chunks = self._source.chunks_for_article(doc_id, article, limit=1)
        if not chunks:
            label = self._covering_label(doc_id, article)
            if label is not None:
                chunks = self._source.chunks_for_article(doc_id, label, limit=1)

        self._cache[key] = chunks[0].status if chunks else None
        return self._cache[key]

    def _covering_label(self, doc_id: str, article: str) -> str | None:
        """Moddani o'z ichiga olgan **birlashgan** bo'lak yorlig'i.

        `chunker._merge_tiny()` kichik moddalarni birlashtiradi va bo'lakka
        «18-19» kabi oraliq yorlig'ini beradi. Bunday holda 19-modda
        korpusda bor, lekin aniq nom bilan topilmaydi.

        Bu tekshiruvsiz nomzodlar ro'yxati o'z chunkerimiz artefakti bilan
        ifloslanardi — o'lchandi: 3 425 «uzilgan» nomzoddan **882 tasi
        (25.8%)** aynan shu sabab bilan chiqqan bo'lardi.

        Nishon raqamining o'zi tireli bo'lsa (`241-9`) bu yerda
        kengaytirilmaydi: o'zbek qonunchiligida `241⁹` kabi modda raqami
        haqiqiy va uni oraliqdan ajratib bo'lmaydi.
        """
        if not article.isdigit():
            return None
        number = int(article)
        for label in self._doc_labels(doc_id):
            found = _RANGE.fullmatch(label)
            if found and int(found.group(1)) <= number <= int(found.group(2)):
                return label
        return None

    def _doc_labels(self, doc_id: str) -> list[str]:
        if doc_id not in self._labels:
            self._labels[doc_id] = self._source.article_labels(doc_id)
        return self._labels[doc_id]

    @property
    def looked_up(self) -> int:
        """Nechta xil nishon izlangani — keshning foydasi shu bilan o'lchanadi."""
        return len(self._cache)


class RefIssue(BaseModel):
    """Bitta **nomzod** — tekshirilishi kerak bo'lgan havola.

    Bu «nuqson bor» degan xulosa emas: masalan `hal-qilinmagan` sinfida
    ayb ko'pincha havolada emas, korpus to'liq emasligida bo'ladi.
    """

    kind: IssueKind
    from_doc: str
    from_article: str | None = None
    to_doc: str | None = None
    to_article: str | None = None
    to_status: str | None = Field(
        default=None, description="Nishon moddaning holati; topilmasa `None`"
    )
    ref_kind: str = Field(default="", description="Grafdagi asl turi: internal · external · …")
    text: str = Field(default="", description="Havola matni — dalil satri")

    @property
    def from_node(self) -> str:
        return f"{self.from_doc}:{self.from_article}"

    @property
    def to_node(self) -> str | None:
        if self.to_doc is None or self.to_article is None:
            return None
        return f"{self.to_doc}:{self.to_article}"


class RefCheckReport(BaseModel):
    """`refcheck` natijasi — nomzodlar va ular olingan asos.

    `graph_ready = False` bo'lsa hisobot bo'sh, lekin bu **xato emas**:
    graf ixtiyoriy qatlam va usiz qidiruv to'liq ishlaydi (docs/22 § 5 B5).
    """

    references: int = Field(default=0, description="Grafdagi havolalar soni")
    resolvable: int = Field(default=0, description="Nishoni aniqlangan havolalar")
    targets: int = Field(default=0, description="Nechta xil nishon tekshirildi")
    ref_kinds: dict[str, int] = Field(
        default_factory=dict, description="Grafdagi tur taqsimoti — docs/22 § 5 B4"
    )
    issues: list[RefIssue] = Field(default_factory=list)
    graph_ready: bool = True
    note: str = ""

    @property
    def counts(self) -> dict[str, int]:
        """Sinf bo'yicha nomzodlar soni — bo'sh sinf ham ko'rinadi."""
        out: dict[str, int] = dict.fromkeys(ISSUE_KINDS, 0)
        for issue in self.issues:
            out[issue.kind] += 1
        return out

    @property
    def candidates(self) -> int:
        return len(self.issues)

    @property
    def share(self) -> float:
        """Nomzodlar ulushi barcha havolalarga nisbatan."""
        return self.candidates / self.references if self.references else 0.0

    def filtered(self, kind: str | None) -> list[RefIssue]:
        return [i for i in self.issues if kind is None or i.kind == kind]


def _classify(ref: Reference, lookup: TargetLookup) -> RefIssue | None:
    """Bitta havolani uch sinfga soladi; sog'lom havolada `None`.

    Tartib muhim: `unresolved` avval tekshiriladi, chunki bunday havolada
    nishon umuman yo'q va uni korpusda izlashning ma'nosi ham yo'q.
    """
    if ref.kind == "unresolved" or ref.to_doc is None or ref.to_article is None:
        return RefIssue(
            kind="hal-qilinmagan",
            from_doc=ref.from_doc,
            from_article=ref.from_article,
            to_doc=ref.to_doc,
            to_article=ref.to_article,
            ref_kind=ref.kind,
            text=ref.text,
        )

    status = lookup.status(ref.to_doc, ref.to_article)
    if status is None:
        return RefIssue(
            kind="uzilgan",
            from_doc=ref.from_doc,
            from_article=ref.from_article,
            to_doc=ref.to_doc,
            to_article=ref.to_article,
            ref_kind=ref.kind,
            text=ref.text,
        )
    if status != IN_FORCE:
        return RefIssue(
            kind="bekor",
            from_doc=ref.from_doc,
            from_article=ref.from_article,
            to_doc=ref.to_doc,
            to_article=ref.to_article,
            to_status=status,
            ref_kind=ref.kind,
            text=ref.text,
        )
    return None


def check_references(
    source: ArticleSource,
    *,
    graph: ReferenceGraph | None = None,
    rebuild: bool = False,
    kind: str | None = None,
) -> RefCheckReport:
    """Havola yaxlitligini tekshiradi va **nomzodlar** ro'yxatini qaytaradi.

    `graph` berilmasa indeksdan olinadi. Graf tayyorlanmasa (`refs.jsonl`
    yo'q, bo'sh yoki buzuq) `KnowledgeIndex.reference_graph()` `None`
    qaytaradi — bunda ish **to'xtamaydi**, bo'sh hisobot va sabab
    izohi qaytadi (docs/22 § 5 B5).

    `kind` — faqat shu sinf qaytsin (`uzilgan` · `bekor` ·
    `hal-qilinmagan`). Filtr hisoblashdan **keyin** qo'llaniladi, ya'ni
    `ref_kinds` taqsimoti filtrdan qat'i nazar to'liq qoladi.
    """
    if kind is not None and kind not in ISSUE_KINDS:
        raise ValueError(f"noma'lum sinf: {kind}. Mumkin: {', '.join(ISSUE_KINDS)}")

    if graph is None:
        graph = source.reference_graph(rebuild=rebuild)
    if graph is None:
        return RefCheckReport(
            graph_ready=False,
            note="Havola grafi tayyorlanmadi — refs.jsonl yo'q, bo'sh yoki buzuq.",
        )

    references: Iterable[Reference] = graph.references
    lookup = TargetLookup(source)
    ref_kinds: dict[str, int] = {}
    issues: list[RefIssue] = []
    resolvable = 0
    total = 0

    for ref in references:
        total += 1
        ref_kinds[ref.kind] = ref_kinds.get(ref.kind, 0) + 1
        if ref.to_doc is not None and ref.to_article is not None:
            resolvable += 1
        issue = _classify(ref, lookup)
        if issue is not None:
            issues.append(issue)

    report = RefCheckReport(
        references=total,
        resolvable=resolvable,
        targets=lookup.looked_up,
        ref_kinds=dict(sorted(ref_kinds.items())),
        issues=issues if kind is None else [i for i in issues if i.kind == kind],
    )
    log.debug("Havola nazorati: %s nomzod / %s havola", report.candidates, total)
    return report
