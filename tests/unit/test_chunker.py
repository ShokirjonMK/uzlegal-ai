"""Chunking testlari.

Asosiy talab: **modda o'rtasidan hech qachon kesilmaydi.** Yuridik matnda
kesilgan chunk normani teskari talqin qilishga olib keladi.
"""

from __future__ import annotations

import pytest

from uzlegal.index.chunker import _ITEM_RE, _PART_RE, Chunker, estimate_tokens, split_by
from uzlegal.ingest.types import Element, ParsedDocument


def make_doc(*articles: tuple[str, str], title: str = "Test kodeksi") -> ParsedDocument:
    return ParsedDocument(
        doc_id="test-1",
        source="lex.uz",
        url="https://lex.uz/docs/test-1",
        title=title,
        doc_type="kodeks",
        lang="uz",
        elements=[
            Element(
                element_id=f"e{i}",
                level="article",
                title=f"{num}-modda. Sarlavha",
                body=body,
                article_number=num,
                path=["I bo'lim", "1-bob"],
            )
            for i, (num, body) in enumerate(articles)
        ],
    )


# --------------------------------------------------------------------------- #
# Asosiy hulq
# --------------------------------------------------------------------------- #


def test_kichik_modda_bitta_chunk() -> None:
    doc = make_doc(("1", "Qisqa modda matni. " * 20))
    chunks = Chunker().chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].kind == "article"
    assert chunks[0].article == "1"


def test_juda_qisqa_modda_tashlanadi() -> None:
    doc = make_doc(("1", "Yo'q."))
    assert Chunker().chunk_document(doc) == []


def test_uzun_modda_qismlarga_bolinadi() -> None:
    body = "\n".join(f"{i}. " + "Qism matni juda uzun. " * 40 for i in range(1, 4))
    chunks = Chunker().chunk_document(make_doc(("5", body)))
    assert len(chunks) == 3
    assert [c.part for c in chunks] == ["1", "2", "3"]
    assert all(c.kind == "part" for c in chunks)


def test_chunk_matni_yoqolmaydi() -> None:
    """Bo'lishda hech qanday jumla yo'qolmasligi kerak."""
    body = "\n".join(f"{i}. Noyob{i} jumla. " + "matn " * 40 for i in range(1, 4))
    chunks = Chunker().chunk_document(make_doc(("7", body)))
    joined = " ".join(c.content for c in chunks)
    for i in range(1, 4):
        assert f"Noyob{i}" in joined


def test_kichik_moddalar_birlashtiriladi() -> None:
    doc = make_doc(("1", "Juda qisqa matn shu." * 2), ("2", "Yana qisqa matn bu." * 2))
    chunks = Chunker().chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].kind == "merged"
    assert chunks[0].article == "1-2"


def test_turli_bobdagi_moddalar_birlashmaydi() -> None:
    doc = make_doc(("1", "Qisqa matn shu." * 2), ("2", "Yana qisqa matn." * 2))
    doc.elements[1].path = ["I bo'lim", "2-bob"]
    chunks = Chunker().chunk_document(doc)
    assert len(chunks) == 2, "bob chegarasidan oshib birlashtirmaslik kerak"


def test_katta_modda_birlashmaydi() -> None:
    doc = make_doc(("1", "Qisqa." * 3), ("2", "Uzun matn. " * 200))
    chunks = Chunker().chunk_document(doc)
    assert any(c.kind == "article" and c.article == "2" for c in chunks)


# --------------------------------------------------------------------------- #
# Metama'lumot va iqtibos
# --------------------------------------------------------------------------- #


def test_kontekstual_sarlavha() -> None:
    chunks = Chunker().chunk_document(make_doc(("42", "Matn. " * 30)))
    heading = chunks[0].heading
    assert "Test kodeksi" in heading
    assert "1-bob" in heading
    assert "42-modda" in heading


def test_indekslanadigan_matn_sarlavhani_oz_ichiga_oladi() -> None:
    """«234-modda» so'rovi chunk matnida yo'q, lekin sarlavhada bor."""
    chunks = Chunker().chunk_document(make_doc(("234", "Mulk huquqi. " * 30)))
    assert "234-modda" in chunks[0].indexed_text


def test_iqtibos_yorligi_modda() -> None:
    chunks = Chunker().chunk_document(make_doc(("234", "Mulk huquqi. " * 30)))
    assert chunks[0].citation_label == "Test kodeksi, 234-modda"


def test_iqtibos_yorligi_qism() -> None:
    # Qismlarga bo'linishi uchun 800 tokendan oshishi kerak
    body = "\n".join(f"{i}. " + "matn " * 250 for i in range(1, 3))
    chunks = Chunker().chunk_document(make_doc(("234", body)))
    assert chunks[0].kind == "part"
    assert chunks[0].citation_label == "Test kodeksi, 234-modda, 1-qism"


def test_chunk_id_unikal() -> None:
    body = "\n".join(f"{i}. " + "matn " * 50 for i in range(1, 4))
    doc = make_doc(("10", body), ("11", "Boshqa matn. " * 30))
    ids = [c.chunk_id for c in Chunker().chunk_document(doc)]
    assert len(ids) == len(set(ids))


def test_manba_havolasi() -> None:
    chunks = Chunker().chunk_document(make_doc(("1", "Matn. " * 30)))
    assert chunks[0].source_url == "https://lex.uz/docs/test-1#e0"


def test_search_text_normallashtirilgan() -> None:
    doc = make_doc(("1", "Oʻzgartirish kiritilgan. " * 20))
    chunk = Chunker().chunk_document(doc)[0]
    assert "o'zgartirish" in chunk.search_text
    assert chunk.search_text == chunk.search_text.lower()


# --------------------------------------------------------------------------- #
# Bo'luvchi
# --------------------------------------------------------------------------- #


def test_qismlarga_bolish() -> None:
    parts = split_by(_PART_RE, "1. Birinchi\n2. Ikkinchi\n3. Uchinchi")
    assert [p[0] for p in parts] == ["1", "2", "3"]


def test_kirish_matni_saqlanadi() -> None:
    parts = split_by(_PART_RE, "Kirish jumlasi.\n1. Birinchi\n2. Ikkinchi")
    assert parts[0][0] is None
    assert "Kirish" in parts[0][1]


def test_bandlarga_bolish() -> None:
    items = split_by(_ITEM_RE, "a) birinchi\nb) ikkinchi")
    assert [i[0] for i in items] == ["a", "b"]


def test_raqamlashsiz_matn_butun_qoladi() -> None:
    parts = split_by(_PART_RE, "Raqamlashsiz oddiy matn.")
    assert len(parts) == 1
    assert parts[0][0] is None


@pytest.mark.parametrize(("text", "minimum"), [("bir ikki uch", 6), ("", 0)])
def test_token_bahosi(text: str, minimum: int) -> None:
    assert estimate_tokens(text) == minimum
