"""Iqtibos yorlig'ining aniqligi — docs/25.

Yorliq `hybrid.py` da **modelga beriladigan** kontekst blokini
belgilaydi va model iqtibosni aynan shu ko'rinishda qaytaradi. Ya'ni
yorliq noaniq bo'lsa iqtibos ham noaniq bo'ladi.

Ikki aniqlik shu yerda qo'riqlanadi:

* **birlik** — farmonning `1.` bandi «1-modda» deb atalmasin;
* **tartib raqami** — bir yorliqqa bir nechta bo'lak tushganda ular
  farqlansin.
"""

from __future__ import annotations

import pytest

from uzlegal.index.chunker import Chunk, Chunker, unit_for
from uzlegal.ingest.types import Element, ParsedDocument


def make_doc(
    *articles: tuple[str | None, str, str],
    doc_type: str = "kodeks",
) -> ParsedDocument:
    """`(article_number, element_title, body)` uchligidan hujjat yasaydi."""
    return ParsedDocument(
        doc_id="d-1",
        source="lex.uz",
        url="https://lex.uz/docs/d-1",
        title="Sinov hujjati",
        doc_type=doc_type,
        lang="uz",
        elements=[
            Element(
                element_id=f"e{i}",
                level="article",
                title=title,
                body=body,
                article_number=num,
                path=[],
            )
            for i, (num, title, body) in enumerate(articles)
        ],
    )


def gap(n_words: int, seed: str = "matn") -> str:
    return " ".join([seed] * n_words) + "."


# --------------------------------------------------------------------------- #
# P7 — birlik element sarlavhasidan aniqlanadi
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("doc_type", "title", "expected"),
    [
        # Sarlavha faqat raqam — bu band, hujjat turi qanday bo'lishidan qat'i nazar
        ("boshqa", "1.", "band"),
        ("boshqa", "12)", "band"),
        ("qonun", "7.", "band"),
        ("kodeks", "3.", "band"),
        ("boshqa", "7-1.", "band"),
        # Sarlavhada «modda» bor — bu modda, hujjat turi «band» desa ham
        ("VMQ", "244-modda. Diniy materiallar", "modda"),
        ("boshqa", "3-modda. Kodeksning prinsiplari", "modda"),
        ("PF", "5-модда. Умумий қоидалар", "modda"),
        # Ikkalasi ham emas — hujjat turiga tushiladi
        ("kodeks", "Umumiy qoidalar", "modda"),
        ("PF", "Umumiy qoidalar", "band"),
        ("boshqa", "", "modda"),
        ("boshqa", None, "modda"),
    ],
)
def test_birlik_sarlavhadan(doc_type: str, title: str | None, expected: str) -> None:
    assert unit_for(doc_type, title) == expected


def test_farmon_bandi_modda_deb_atalmaydi() -> None:
    """P7 ning o'zagi.

    Korpusda 16 877 bo'lak (34.8%) shu sababdan noto'g'ri iqtibos
    olardi — asosan `doc_type = "boshqa"` bo'lgan nizom va tartiblar.
    """
    doc = make_doc(("1", "1.", gap(80)), doc_type="boshqa")
    chunk = Chunker().chunk_document(doc)[0]

    assert chunk.unit == "band"
    assert chunk.citation_label == "Sinov hujjati, 1-band"


def test_kodeks_moddasi_modda_boligicha_qoladi() -> None:
    doc = make_doc(("3", "3-modda. Prinsiplar", gap(80)), doc_type="kodeks")
    chunk = Chunker().chunk_document(doc)[0]

    assert chunk.unit == "modda"
    assert chunk.citation_label == "Sinov hujjati, 3-modda"


def test_birlashgan_bolak_birlikni_meros_oladi() -> None:
    """`_merge_tiny()` yangi Chunk yasaydi — maydon yo'qolib qolmasin."""
    kichik = gap(10)
    doc = make_doc(("1", "1.", kichik), ("2", "2.", kichik), doc_type="boshqa")
    merged = [c for c in Chunker().chunk_document(doc) if c.kind == "merged"]

    assert merged and merged[0].unit == "band"
    assert merged[0].citation_label == "Sinov hujjati, 1-2-band"


# --------------------------------------------------------------------------- #
# P3 — bir yorliqqa tushgan bo'laklar raqamlanadi
# --------------------------------------------------------------------------- #


def test_takroriy_qism_yorligi_raqamlanadi() -> None:
    """Bir modda ichida `2.` qismi ikki marta uchraydi."""
    body = "".join(f"{n}. {gap(120)}\n" for n in (1, 2, 1, 2))
    doc = make_doc(("35", "35-modda. Dastur", body))
    chunks = Chunker().chunk_document(doc)

    yorliqlar = [c.citation_label for c in chunks]
    assert yorliqlar == [
        "Sinov hujjati, 35-modda, 1-qism",
        "Sinov hujjati, 35-modda, 2-qism",
        "Sinov hujjati, 35-modda, 1-qism (2-bo'lak)",
        "Sinov hujjati, 35-modda, 2-qism (2-bo'lak)",
    ]
    assert len(set(yorliqlar)) == len(yorliqlar)


def test_olchamga_kora_bolinish_ham_raqamlanadi() -> None:
    """`chunk_id` har xil, yorliq esa bir xil bo'lardi.

    Bu `#` tartib raqami qamramaydigan ikkinchi sabab: matn uzunligi
    tufayli bo'lingan bo'laklarda modda, qism va band bir xil qoladi.
    """
    ulkan = " ".join(gap(50) for _ in range(200))
    chunks = Chunker().chunk_document(make_doc(("7", "7-modda. Uzun", ulkan)))

    assert len(chunks) > 1
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert not any("#" in c.chunk_id for c in chunks), "bu yerda # emas, :N bo'linishi"
    assert len({c.citation_label for c in chunks}) == len(chunks)


def test_birinchi_bolak_yorligi_ozgarmaydi() -> None:
    """Takrorlanmagan yorliqqa hech nima qo'shilmaydi."""
    doc = make_doc(("1", "1-modda. Bir", gap(80)), ("2", "2-modda. Ikki", gap(80)))
    chunks = Chunker().chunk_document(doc)

    assert [c.occurrence for c in chunks] == [1, 1]
    assert [c.citation_label for c in chunks] == [
        "Sinov hujjati, 1-modda",
        "Sinov hujjati, 2-modda",
    ]


def test_hisob_hujjat_ichida_yuritiladi() -> None:
    """Yorliq kaliti `doc_id` ni ham o'z ichiga oladi."""
    a = Chunk(
        chunk_id="d-1:5",
        doc_id="d-1",
        doc_title="Birinchi",
        doc_type="kodeks",
        lang="uz",
        article="5",
        heading="[Birinchi > 5-modda]",
        content="matn",
    )
    b = a.model_copy(update={"chunk_id": "d-2:5", "doc_id": "d-2", "doc_title": "Ikkinchi"})
    assert a.citation_key != b.citation_key


def test_tartib_deterministik() -> None:
    body = "".join(f"{n}. {gap(120)}\n" for n in (1, 2, 1, 2))
    doc = make_doc(("35", "35-modda. Dastur", body))
    birinchi = [c.citation_label for c in Chunker().chunk_document(doc)]
    ikkinchi = [c.citation_label for c in Chunker().chunk_document(doc)]
    assert birinchi == ikkinchi


def test_eski_chunks_jsonl_oqiladi() -> None:
    """Maydonsiz yozilgan eski fayl standart qiymatlar bilan yuklansin."""
    chunk = Chunk.model_validate(
        {
            "chunk_id": "d-1:5",
            "doc_id": "d-1",
            "doc_title": "Eski",
            "doc_type": "kodeks",
            "lang": "uz",
            "article": "5",
            "heading": "[Eski > 5-modda]",
            "content": "matn",
        }
    )
    assert chunk.unit == "modda"
    assert chunk.occurrence == 1
    assert chunk.citation_label == "Eski, 5-modda"
