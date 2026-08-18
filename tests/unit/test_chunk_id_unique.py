"""`chunk_id` noyobligi — docs/23.

Nima uchun alohida fayl: to'qnashuv chunkerning **bitta** joyida emas,
oltita yo'lida tug'iladi va oqibati `index/store.py` da ko'rinadi.
Testlar shu ikkalasini bir joyda ushlab turadi.

Talab bitta: `chunk_document()` chiqishida ikkita bo'lak bir xil
`chunk_id` **hech qachon** olmasin. Aks holda `store.read_chunks()`
lug'atida biri ikkinchisini bosadi, qidiruv esa yutilgan bo'lakning
ballini g'olib bo'lakning matni bilan ko'rsatadi — haqiqiy
`source_url` bilan noto'g'ri norma.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from uzlegal.index.chunker import (
    MERGE_BELOW_TOKENS,
    SPLIT_TO_ITEMS_ABOVE,
    SPLIT_TO_PARTS_ABOVE,
    Chunk,
    Chunker,
    estimate_tokens,
)
from uzlegal.index.store import KnowledgeIndex, duplicate_ids
from uzlegal.ingest.types import Element, ParsedDocument


def make_doc(*articles: tuple[str, str]) -> ParsedDocument:
    """Har bir modda o'z `element_id` sini oladi, raqami esa takrorlanishi mumkin."""
    return ParsedDocument(
        doc_id="d-1",
        source="lex.uz",
        url="https://lex.uz/docs/d-1",
        title="Sinov kodeksi",
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


def ids(chunks: list[Chunk]) -> list[str]:
    return [c.chunk_id for c in chunks]


def gap(n_words: int, seed: str = "matn") -> str:
    """`n_words` so'zdan iborat gap — token bahosi so'z × 2."""
    return " ".join([seed] * n_words) + "."


# --------------------------------------------------------------------------- #
# Asosiy talab
# --------------------------------------------------------------------------- #


def test_bir_xil_modda_raqami_toqnashmaydi() -> None:
    """Yo'l 1 — `{doc}:{num}`.

    Amalda: parser «244-3-modda» dan `3` ni ajratadi va u haqiqiy
    3-modda bilan urishadi. Korpusda 3 794 satr shu sababdan yutilgan.
    """
    doc = make_doc(("3", gap(80, "birinchi")), ("3", gap(80, "ikkinchi")))
    chunks = Chunker().chunk_document(doc)

    assert len(chunks) == 2
    assert len(set(ids(chunks))) == 2
    assert ids(chunks) == ["d-1:3", "d-1:3#2"]
    # Mazmun almashib ketmagan — faqat identifikator o'zgardi.
    assert chunks[0].content.startswith("birinchi")
    assert chunks[1].content.startswith("ikkinchi")


def test_takroriy_qism_belgisi_toqnashmaydi() -> None:
    """Yo'l 2 — `{doc}:{num}:{mark}`.

    Davlat dasturlarida `1.` `2.` raqamlash bo'lim boshida qaytadan
    boshlanadi. Korpusda `-6811936:35:2` **187 marta** uchragan.
    """
    body = "".join(f"{n}. {gap(120)}\n" for n in (1, 2, 1, 2))
    assert estimate_tokens(body) > SPLIT_TO_PARTS_ABOVE

    chunks = Chunker().chunk_document(make_doc(("35", body)))
    assert [c.part for c in chunks] == ["1", "2", "1", "2"]
    assert ids(chunks) == ["d-1:35:1", "d-1:35:2", "d-1:35:1#2", "d-1:35:2#2"]


def test_takroriy_band_belgisi_toqnashmaydi() -> None:
    """Yo'l 3 — `{doc}:{num}:{mark}:{item}`.

    Bir qism ichida `a) b) … a)` ro'yxati qaytadan boshlanadi.
    """
    # Har bir band satr boshida turishi shart — `_ITEM_RE` shunday izlaydi.
    part = "1. Kirish matni.\n" + "".join(f"{m}) {gap(350)}\n" for m in ("a", "b", "a"))
    body = part + f"2. {gap(60)}\n"
    assert estimate_tokens(body) > SPLIT_TO_ITEMS_ABOVE

    chunks = Chunker().chunk_document(make_doc(("50", body)))
    items = [c.chunk_id for c in chunks if c.kind == "item"]
    assert len(items) == len(set(items))
    assert "d-1:50:1:a" in items and "d-1:50:1:a#2" in items


def test_bolingan_bolaklar_ham_qamrab_olinadi() -> None:
    """Yo'l 4 va 6 — `_split_oversized` va `_enforce_limit` ham `:{n}` qo'shadi.

    Shuning uchun kafolat `_enforce_limit()` dan **keyin** turadi: undan
    keyin identifikatorga hech kim tegmaydi. Kafolat oldin qo'yilsa
    bo'linishdan chiqqan identifikatorlar tekshiruvdan tashqarida
    qolardi.
    """
    # Ko'p gapli ulkan matn — bitta uzun gap kesilmaydi (`_split_oversized`).
    ulkan = " ".join(gap(50) for _ in range(200))
    chunks = Chunker().chunk_document(make_doc(("7", ulkan), ("7", ulkan)))

    assert len(chunks) > 2, "matn bo'linmagan — test o'z holatini tekshirmayapti"
    assert len(set(ids(chunks))) == len(chunks)
    assert sum(c.chunk_id.endswith("#2") for c in chunks) == len(chunks) // 2


def test_birlashtirilgan_bolak_toqnashmaydi() -> None:
    """Yo'l 5 — `_merge_tiny()` `{first}+{n}` ni birinchi bo'lakdan meros oladi."""
    kichik = gap(10)
    assert estimate_tokens(kichik) < MERGE_BELOW_TOKENS
    katta = gap(200)

    doc = make_doc(("7", kichik), ("8", kichik), ("9", katta), ("7", kichik), ("8", kichik))
    chunks = Chunker().chunk_document(doc)

    merged = [c.chunk_id for c in chunks if c.kind == "merged"]
    assert merged == ["d-1:7+2", "d-1:7+2#2"]


# --------------------------------------------------------------------------- #
# Kafolatning xossalari
# --------------------------------------------------------------------------- #


def test_toqnashmagan_identifikator_ozgarmaydi() -> None:
    """Eski havolalar buzilmasin.

    Korpusning 92% i (35 708 identifikator) to'qnashmagan. Ular o'z
    qiymatida qolsa audit jurnalidagi va imzolangan pasportlardagi
    havolalar qayta indekslashdan keyin ham ishlaydi.
    """
    doc = make_doc(("1", gap(80)), ("2", gap(80)), ("3", gap(80)))
    assert ids(Chunker().chunk_document(doc)) == ["d-1:1", "d-1:2", "d-1:3"]


def test_tartib_deterministik() -> None:
    """Bir xil kirishdan bir xil identifikator — ikki marta qurish farq qilmasin."""
    doc = make_doc(("3", gap(80, "bir")), ("3", gap(80, "ikki")), ("3", gap(80, "uch")))
    assert ids(Chunker().chunk_document(doc)) == ids(Chunker().chunk_document(doc))
    assert ids(Chunker().chunk_document(doc)) == ["d-1:3", "d-1:3#2", "d-1:3#3"]


def test_faqat_identifikator_ozgaradi() -> None:
    """Qo'shimcha mazmunga, sanaga yoki turga tegmasin."""
    doc = make_doc(("3", gap(80, "bir")), ("3", gap(80, "ikki")))
    ikkinchi = Chunker().chunk_document(doc)[1]

    assert ikkinchi.chunk_id.endswith("#2")
    assert ikkinchi.article == "3"
    assert ikkinchi.kind == "article"
    assert ikkinchi.content.startswith("ikki")
    assert ikkinchi.token_count == estimate_tokens(ikkinchi.content)


# --------------------------------------------------------------------------- #
# Indeks tomoni — jimgina yutish tugadi
# --------------------------------------------------------------------------- #


def _chunk(chunk_id: str, content: str = "Mulkdor talab qilishga haqli.") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id="d-1",
        doc_title="Sinov kodeksi",
        doc_type="kodeks",
        lang="uz",
        article="3",
        heading="[Sinov kodeksi > 3-modda]",
        content=content,
        token_count=8,
    )


def test_duplicate_ids_kamayish_tartibida() -> None:
    found = duplicate_ids([_chunk("a"), _chunk("b"), _chunk("b")] + [_chunk("c")] * 3)
    assert found == [("c", 3), ("b", 2)]


def test_takror_bilan_indeks_qurilmaydi(tmp_path: Path) -> None:
    """Embedding tayyor bo'lsa ham — buzuq indeks yozilmasin."""
    import numpy as np

    chunks = [_chunk("d-1:3"), _chunk("d-1:3")]
    with pytest.raises(ValueError, match="takrorlangan chunk_id"):
        KnowledgeIndex(tmp_path).build(chunks, np.zeros((2, 4)))


def test_read_chunks_takrorni_sanaydi(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Eski (tuzatishdan oldingi) indeks ochilsa — jimgina emas, ovoz bilan."""
    index = KnowledgeIndex(tmp_path)
    index.chunks_path.write_text(
        "\n".join(c.model_dump_json() for c in [_chunk("d-1:3", "bir"), _chunk("d-1:3", "ikki")]),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        index.read_chunks()

    assert index.duplicate_rows == 1
    assert len(index._chunks) == 1
    assert "takrorlangan chunk_id" in caplog.text
    # G'olib — oxirgisi. Aynan shu tufayli qidiruv boshqa matnni ko'rsatardi.
    assert index._chunks["d-1:3"].content == "ikki"


def test_tuzatilgan_indeksda_takror_yoq(tmp_path: Path) -> None:
    index = KnowledgeIndex(tmp_path)
    index.chunks_path.write_text(
        "\n".join(c.model_dump_json() for c in [_chunk("d-1:3"), _chunk("d-1:3#2")]),
        encoding="utf-8",
    )
    index.read_chunks()
    assert index.duplicate_rows == 0
    assert len(index._chunks) == 2
