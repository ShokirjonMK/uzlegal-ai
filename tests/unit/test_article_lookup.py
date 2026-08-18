"""Modda raqami bo'yicha qidirish va BM25 teskari indeksi — docs/24.

Ikki talab bir faylda, chunki ikkalasi ham `index/store.py` ning bir
xil xossasiga tayanadi: **e'lon qilingan natija amaldagi natija
bo'lsin**.

* `chunks_for_article()` bitta moddani qaytarsin — bir hujjatda bir
  xil raqamli bir necha modda bo'lishi mumkin va ularni aralashtirish
  chaqiruvchiga bilinmaydi;
* BM25 teskari indeksga o'tdi — natija **bayt-bayt** eskisidek
  qolishi kerak, faqat tezroq.
"""

from __future__ import annotations

import math
import pickle
from collections import Counter
from pathlib import Path

from uzlegal.index.chunker import Chunk
from uzlegal.index.store import BM25Index, KnowledgeIndex, tokenize


def _chunk(
    chunk_id: str,
    *,
    article: str,
    element_id: str,
    hierarchy: list[str] | None = None,
    content: str = "Mulkdor talab qilishga haqli.",
    part: str | None = None,
    status: str = "in_force",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id="d-1",
        doc_title="Sinov nizomi",
        doc_type="boshqa",
        lang="uz",
        article=article,
        part=part,
        hierarchy=hierarchy or [],
        element_id=element_id,
        heading=f"[Sinov nizomi > {article}-modda]",
        content=content,
        token_count=8,
        status=status,
    )


def _index(tmp_path: Path, chunks: list[Chunk]) -> KnowledgeIndex:
    index = KnowledgeIndex(tmp_path)
    index.chunks_path.write_text("\n".join(c.model_dump_json() for c in chunks), encoding="utf-8")
    index.read_chunks()
    return index


# --------------------------------------------------------------------------- #
# chunks_for_article — ilovalar aralashmasin
# --------------------------------------------------------------------------- #


def test_bir_moddaning_bolaklari_qaytadi(tmp_path: Path) -> None:
    """Oddiy holat: bitta modda, bir necha qism."""
    index = _index(
        tmp_path,
        [
            _chunk("d-1:5:1", article="5", element_id="e5", part="1"),
            _chunk("d-1:5:2", article="5", element_id="e5", part="2"),
        ],
    )
    found = index.chunks_for_article("d-1", "5")
    assert [c.chunk_id for c in found] == ["d-1:5:1", "d-1:5:2"]


def test_boshqa_ilovadagi_modda_aralashmaydi(tmp_path: Path) -> None:
    """Bir hujjatda ikki ilova, ikkalasida ham 5-modda bor.

    Ilgari ikkalasi bitta moddaning bo'laklari sifatida qaytardi.
    Korpusda o'lchandi: 348 hujjatda 1 745 shunday holat (docs/23 § 2.2).
    """
    index = _index(
        tmp_path,
        [
            _chunk("d-1:5", article="5", element_id="e5", hierarchy=["1-ilova"], content="bir"),
            _chunk("d-1:5#2", article="5", element_id="e9", hierarchy=["2-ilova"], content="ikki"),
        ],
    )
    found = index.chunks_for_article("d-1", "5")

    assert len(found) == 1
    assert found[0].element_id == "e5"
    assert found[0].content == "bir"


def test_hujjatdagi_birinchi_modda_tanlanadi(tmp_path: Path) -> None:
    """Tanlov deterministik: fayl tartibi = hujjat tartibi."""
    index = _index(
        tmp_path,
        [
            _chunk("d-1:5", article="5", element_id="e5", content="birinchi"),
            _chunk("d-1:5#2", article="5", element_id="e9", content="ikkinchi"),
        ],
    )
    assert index.chunks_for_article("d-1", "5")[0].content == "birinchi"


def test_holat_boshqa_ilovadan_olinmaydi(tmp_path: Path) -> None:
    """`collisions.status()` birinchi bo'lakning holatini oladi.

    Aralashtirish davom etsa amaldagi modda boshqa ilovadagi bekor
    qilingan modda tufayli «bekor» deb belgilanardi.
    """
    index = _index(
        tmp_path,
        [
            _chunk("d-1:5", article="5", element_id="e5", status="in_force"),
            _chunk("d-1:5#2", article="5", element_id="e9", status="repealed"),
        ],
    )
    assert index.chunks_for_article("d-1", "5", limit=1)[0].status == "in_force"


def test_topilmasa_bosh_royxat(tmp_path: Path) -> None:
    index = _index(tmp_path, [_chunk("d-1:5", article="5", element_id="e5")])
    assert index.chunks_for_article("d-1", "404") == []


def test_article_variants_noaniqlikni_korsatadi(tmp_path: Path) -> None:
    """Tanlov borligi chaqiruvchiga ko'rinishi kerak."""
    index = _index(
        tmp_path,
        [
            _chunk("d-1:5", article="5", element_id="e5", hierarchy=["1-ilova"]),
            _chunk("d-1:5#2", article="5", element_id="e9", hierarchy=["2-ilova"]),
            _chunk("d-1:6", article="6", element_id="e6", hierarchy=["1-ilova"]),
        ],
    )
    assert index.article_variants("d-1", "5") == [["1-ilova"], ["2-ilova"]]
    assert index.article_variants("d-1", "6") == [["1-ilova"]]


def test_ambiguous_articles_hujjat_boyicha_sanaydi(tmp_path: Path) -> None:
    index = _index(
        tmp_path,
        [
            _chunk("d-1:5", article="5", element_id="e5"),
            _chunk("d-1:5#2", article="5", element_id="e9"),
            _chunk("d-1:6", article="6", element_id="e6"),
        ],
    )
    assert index.ambiguous_articles() == {"d-1": 1}


# --------------------------------------------------------------------------- #
# BM25 teskari indeksi — natija o'zgarmasin
# --------------------------------------------------------------------------- #


def _korpus() -> list[Chunk]:
    matnlar = [
        "Mulkdor o'z mulkini vijdonsiz oluvchidan talab qilishga haqli",
        "Vindikatsiya da'vosi mulk huquqini himoya qiladi",
        "Mehnat shartnomasi ish beruvchi va xodim o'rtasida tuziladi",
        "Ish haqi to'lash muddatlari mehnat kodeksida belgilanadi",
        "Jinoyat uchun javobgarlik faqat sud hukmi bilan belgilanadi",
    ]
    return [
        _chunk(f"d-1:{i}", article=str(i), element_id=f"e{i}", content=t)
        for i, t in enumerate(matnlar, start=1)
    ]


def _eski_usul(
    index: BM25Index, doc_freqs: list[Counter[str]], query: str
) -> list[tuple[str, float]]:
    """Teskari indeksdan oldingi hisoblash — taqqoslash uchun."""
    terms = tokenize(query)
    n = len(index.doc_ids)
    scores: dict[int, float] = {}
    for term in terms:
        df = index.df.get(term, 0)
        if df == 0:
            continue
        idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
        for i, freqs in enumerate(doc_freqs):
            tf = freqs.get(term, 0)
            if tf == 0:
                continue
            norm = 1 - index.b + index.b * (index.doc_lens[i] / (index.avg_len or 1))
            scores[i] = scores.get(i, 0.0) + idf * (tf * (index.k1 + 1)) / (tf + index.k1 * norm)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [(index.doc_ids[i], s) for i, s in ranked]


def test_teskari_indeks_ayni_natijani_beradi() -> None:
    """Tezlik uchun qilingan o'zgarish sifatga tegmasin."""
    chunks = _korpus()
    index = BM25Index()
    index.build(chunks)

    doc_freqs = [Counter(tokenize(c.indexed_text)) for c in chunks]

    for query in ("mulk talab qilish", "mehnat shartnomasi", "jinoyat javobgarlik", "vindikatsiya"):
        yangi = index.search(query)
        eski = _eski_usul(index, doc_freqs, query)
        assert [d for d, _ in yangi] == [d for d, _ in eski]
        for (_, a), (_, b) in zip(yangi, eski, strict=True):
            assert a == b


def test_df_postings_uzunligiga_teng() -> None:
    """`idf` endi `len(postings)` dan hisoblanadi — u `df` bilan bir xil bo'lsin."""
    index = BM25Index()
    index.build(_korpus())
    assert all(index.df[term] == len(plist) for term, plist in index.postings.items())


def test_bosh_indeks_yiqilmaydi() -> None:
    assert BM25Index().search("mulk") == []


def test_eski_formatdagi_pikel_oqiladi(tmp_path: Path) -> None:
    """Tuzatishdan oldingi `bm25.pkl` qayta qurilmasdan ishlasin.

    Format o'zgardi (`doc_freqs` → `postings`). Eski faylni rad etish
    foydalanuvchini sababsiz o'n besh daqiqalik qayta indekslashga
    majbur qilardi.
    """
    chunks = _korpus()
    yangi = BM25Index()
    yangi.build(chunks)

    eski_fayl = tmp_path / "bm25.pkl"
    with eski_fayl.open("wb") as fh:
        pickle.dump(
            {
                "k1": yangi.k1,
                "b": yangi.b,
                "doc_ids": yangi.doc_ids,
                "doc_freqs": [Counter(tokenize(c.indexed_text)) for c in chunks],
                "doc_lens": yangi.doc_lens,
                "df": yangi.df,
                "avg_len": yangi.avg_len,
            },
            fh,
        )

    yuklangan = BM25Index.load(eski_fayl)
    assert yuklangan.postings == yangi.postings
    assert yuklangan.search("mulk talab qilish") == yangi.search("mulk talab qilish")


def test_yangi_format_aylanib_qaytadi(tmp_path: Path) -> None:
    index = BM25Index()
    index.build(_korpus())
    path = tmp_path / "bm25.pkl"
    index.save(path)

    yuklangan = BM25Index.load(path)
    assert yuklangan.postings == index.postings
    assert yuklangan.norms == index.norms
    assert yuklangan.search("mehnat shartnomasi") == index.search("mehnat shartnomasi")
