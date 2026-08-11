"""Havola grafi testlari — docs/03 § 3.5.

HTML bo'lagi lex.uz ning haqiqiy tuzilishini takrorlaydi (`lx_elem` o'rovchi
+ `<div name="ID" id="ID">`), chunki havolalar aynan shu tuzilma ichidan
o'qiladi. Arxivga tayanadigan testlar `data/raw` bo'lmasa o'tkazib
yuboriladi — tarmoqqa chiqilmaydi.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from uzlegal.ingest.connectors.lex_uz import LexUzConnector
from uzlegal.ingest.linking import (
    Reference,
    ReferenceGraph,
    build_graph,
    element_article_map,
    extract_references,
    html_references,
    text_references,
)
from uzlegal.ingest.parsers.lex_uz import LexUzParser
from uzlegal.ingest.types import ParsedDocument, RawDocument


def _block(cls: str, element_id: str, inner: str) -> str:
    return (
        f'<div class="{cls} lx_elem" onmousemove="lx_mo(event,1)">'
        f'<div name="{element_id}" id="{element_id}">{inner}</div></div>'
    )


HTML = "".join(
    [
        _block("ACT_TITLE", "-1", "Oʻzbekiston Respublikasining Sinov kodeksi"),
        _block("TEXT_HEADER_DEFAULT", "-2", "1-BOB. UMUMIY QOIDALAR"),
        _block("CLAUSE_DEFAULT", "-10", "45-modda. Mulk huquqi"),
        _block(
            "ACT_TEXT",
            "-11",
            'Ushbu Kodeksning <a href="/uz/docs/-500#-20">46-moddasida</a> nazarda '
            'tutilgan hollarda Mehnat kodeksining '
            '<a href="/uz/docs/-600#-338735">176-moddasi</a> qoʻllaniladi. '
            '<a href="/uz/docs/-500?ONDATE=01.03.1997 00#-11">Oldingi</a> '
            '<a href="javascript:scrollText(\'-20\');">46</a> '
            '<a href="/uz/docs/-700#-900">17-bandi</a>',
        ),
        _block("CLAUSE_DEFAULT", "-20", "46-modda. Egalik huquqi"),
        _block(
            "ACT_TEXT",
            "-21",
            "Mulkdor ushbu Kodeksning 45 va 47-moddalarida belgilangan tartibda "
            "hamda Mehnat kodeksining 78-moddasiga muvofiq ish koʻradi.",
        ),
        _block("CLAUSE_DEFAULT", "-30", "47-modda. Foydalanish"),
        _block("ACT_TEXT", "-31", "Ushbu Kodeksning 46-moddasi qoidalari qoʻllaniladi."),
    ]
)


def _raw(content: str, doc_id: str) -> RawDocument:
    return RawDocument(
        source="lex.uz",
        doc_id=doc_id,
        url=f"https://lex.uz/uz/docs/{doc_id}",
        fetched_at=datetime.now(UTC),
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        http_status=200,
        content_type="text/html",
        content=content,
    )


@pytest.fixture(scope="module")
def doc() -> ParsedDocument:
    return LexUzParser().parse(_raw(HTML, "-500"))


# --------------------------------------------------------------------------- #
# Matn shablonlari
# --------------------------------------------------------------------------- #


def test_ushbu_kodeks_ichki_havola(doc: ParsedDocument) -> None:
    refs = [r for r in text_references(doc) if r.from_article == "46"]
    internal = {r.to_article for r in refs if r.kind == "internal"}
    assert internal == {"45", "47"}
    assert all(r.to_doc == doc.doc_id for r in refs if r.kind == "internal")


def test_boshqa_kodeksga_havola(doc: ParsedDocument) -> None:
    """Registrsiz nishon hujjat noma'lum, lekin modda raqami saqlanadi."""
    external = [r for r in text_references(doc) if r.to_article == "78"]
    assert external and external[0].kind == "unresolved"


def test_nomli_kodeks_registr_orqali_bogflanadi(doc: ParsedDocument) -> None:
    registry = {"mehnat": "-600"}
    refs = [r for r in text_references(doc, registry) if r.to_article == "78"]
    assert refs[0].to_doc == "-600"
    assert refs[0].kind == "external"


def test_ozini_ozi_havola_qilmaydi(doc: ParsedDocument) -> None:
    for ref in extract_references(doc, HTML):
        assert not (ref.to_doc == ref.from_doc and ref.to_article == ref.from_article)


# --------------------------------------------------------------------------- #
# HTML havolalari — parser ularni yo'qotadi, shuning uchun alohida o'qiladi
# --------------------------------------------------------------------------- #


def test_element_xaritasi_matn_bloklarini_moddaga_bogflaydi(doc: ParsedDocument) -> None:
    mapping = element_article_map(HTML, doc)
    assert mapping["-10"] == "45"
    assert mapping["-11"] == "45", "modda tanasi ham o'sha moddaga tegishli"
    assert mapping["-21"] == "46"


def test_html_havolasi_yoqolmaydi(doc: ParsedDocument) -> None:
    """`<a href="/uz/docs/-600#-338735">176-moddasi</a>` grafda qolishi shart."""
    refs = html_references(HTML, doc)
    target = [r for r in refs if r.to_doc == "-600"]
    assert target, "boshqa hujjatga HTML havolasi topilmadi"
    assert target[0].to_article == "176"
    assert target[0].from_article == "45"
    assert target[0].origin == "html"


def test_ichki_html_havolasi_element_id_orqali_hal_qilinadi(doc: ParsedDocument) -> None:
    refs = html_references(HTML, doc)
    internal = [r for r in refs if r.to_doc == doc.doc_id and r.from_article == "45"]
    assert internal and internal[0].to_article == "46", "#-20 → 46-modda"


def test_eski_tahrir_havolasi_otkazib_yuboriladi(doc: ParsedDocument) -> None:
    """`?ONDATE=` — hujjatning eski nusxasi; grafga tushsa eskirgan matn tortiladi."""
    assert all("ONDATE" not in r.text for r in html_references(HTML, doc))
    assert not [r for r in html_references(HTML, doc) if r.to_article == "Oldingi"]


def test_band_raqami_modda_deb_olinmaydi(doc: ParsedDocument) -> None:
    """«17-bandi» — band, modda emas: yolg'on qirra yaratmasin."""
    refs = [r for r in html_references(HTML, doc) if r.to_doc == "-700"]
    assert refs and refs[0].to_article is None
    assert refs[0].kind == "unresolved"


def test_javascript_havolasi_hisobga_olinmaydi(doc: ParsedDocument) -> None:
    assert all("javascript" not in (r.text or "") for r in html_references(HTML, doc))


# --------------------------------------------------------------------------- #
# Graf
# --------------------------------------------------------------------------- #


def test_graf_qoshnilari(doc: ParsedDocument) -> None:
    graph = build_graph([doc], {doc.doc_id: HTML})
    assert "-500:46" in graph.neighbors("-500:45")
    assert "-500:47" in graph.neighbors("-500:46")


def test_graf_ikkinchi_daraja(doc: ParsedDocument) -> None:
    graph = build_graph([doc], {doc.doc_id: HTML})
    first = set(graph.neighbors("-500:45", depth=1))
    second = set(graph.neighbors("-500:45", depth=2))
    assert first < second, "ikkinchi daraja kengroq bo'lishi kerak"
    assert "-500:45" not in second, "o'zi qo'shni emas"


def test_graf_teskari_yonalish(doc: ParsedDocument) -> None:
    graph = build_graph([doc], {doc.doc_id: HTML})
    assert "-500:46" in graph.neighbors("-500:47", direction="in")


def test_hal_qilinmagan_havola_qirra_yaratmaydi() -> None:
    graph = ReferenceGraph()
    graph.add(
        Reference(
            from_doc="-500", from_article="1", to_doc=None, to_article=None, kind="unresolved"
        )
    )
    assert graph.neighbors("-500:1") == []
    assert graph.stats()["qirralar"] == 0


def test_graf_saqlanadi_va_oqiladi(doc: ParsedDocument, tmp_path: Path) -> None:
    graph = build_graph([doc], {doc.doc_id: HTML})
    loaded = ReferenceGraph.load(graph.save(tmp_path / "graf.jsonl"))
    assert loaded.stats() == graph.stats()


# --------------------------------------------------------------------------- #
# Arxivdagi haqiqiy hujjat
# --------------------------------------------------------------------------- #

ARXIV_ID = "-111189"


def test_arxivda_havolalar_topiladi() -> None:
    connector = LexUzConnector()
    raw = connector.load_cached(ARXIV_ID)
    if raw is None:
        pytest.skip(f"Arxivda {ARXIV_ID} yo'q — `uzlegal kb sync --docs {ARXIV_ID}`")

    parsed = LexUzParser().parse(raw)
    graph = build_graph([parsed], {parsed.doc_id: raw.content})
    stats = graph.stats()

    assert stats["havolalar"] > 1000, f"kutilgan >1000, olindi {stats['havolalar']}"
    assert stats["internal"] > stats["external"], "kodeks ko'proq o'ziga havola qiladi"
    assert graph.neighbors(f"{parsed.doc_id}:234"), "234-moddada havola bo'lishi kerak"
