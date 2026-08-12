"""lex.uz kashfiyot API si testlari.

Tarmoqqa chiqmaydi — URL qurish va natijalarni ajratish tekshiriladi.
Fixture haqiqiy qidiruv sahifasidan olingan markup namunasi.
"""

from __future__ import annotations

import pytest

from uzlegal.ingest.discover import (
    FORM_CODE,
    FORM_LAW,
    LANG_RU,
    LANG_UZ_LATIN,
    STATUS_IN_FORCE,
    DiscoveryQuery,
    parse_results,
    parse_total,
)

# Haqiqiy lex.uz qidiruv natijasi markupi (soddalashtirilgan)
SEARCH_HTML = """
<div class="searchPanelExt__body">
  <span>20 hujjat</span>
  <a class="lx_link" href="/uz/docs/-111189?query=kodeks#sr-1" target="_blank">
     Oʻzbekiston Respublikasining Fuqarolik kodeksi (birinchi qism)</a>
  <a class="lx_link" href="/uz/pdfs/-111189" title="PDF">pdf</a>
  <a class="lx_link" href="/uz/docs/-111189?type=doc" title="Word">doc</a>
  <a class="lx_link" href="/uz/docs/-6257288?query=kodeks#sr-2" target="_blank">
     Oʻzbekiston Respublikasining Mehnat kodeksi</a>
  <a class="lx_link" href="/uz/docs/111181?query=kodeks#sr-3" target="_blank">
     Гражданский кодекс Республики Узбекистан</a>
</div>
"""


# --------------------------------------------------------------------------- #
# URL qurish
# --------------------------------------------------------------------------- #


def test_url_barcha_parametrlarni_qoyadi() -> None:
    url = DiscoveryQuery(query="kodeks").url()
    assert "query=kodeks" in url
    assert f"lang={LANG_UZ_LATIN}" in url
    assert f"form_id={FORM_CODE}" in url
    assert f"status={STATUS_IN_FORCE}" in url


def test_url_ozbek_sorovni_kodlaydi() -> None:
    url = DiscoveryQuery(query="mehnat shartnomasi").url()
    assert "mehnat%20shartnomasi" in url


def test_form_id_ixtiyoriy() -> None:
    assert "form_id" not in DiscoveryQuery(query="x", form_id=None).url()


def test_boshqa_til() -> None:
    assert f"lang={LANG_RU}" in DiscoveryQuery(query="x", lang=LANG_RU).url()


def test_qonun_shakli() -> None:
    assert f"form_id={FORM_LAW}" in DiscoveryQuery(query="x", form_id=FORM_LAW).url()


# --------------------------------------------------------------------------- #
# Natijalarni ajratish
# --------------------------------------------------------------------------- #


def test_manfiy_id_ajratiladi() -> None:
    """O'zbek lotin nashrlari manfiy ID bilan keladi — asosiy holat."""
    refs = parse_results(SEARCH_HTML, FORM_CODE)
    ids = [r.doc_id for r in refs]
    assert "-111189" in ids
    assert "-6257288" in ids


def test_musbat_id_ham_ajratiladi() -> None:
    assert "111181" in [r.doc_id for r in parse_results(SEARCH_HTML, FORM_CODE)]


def test_pdf_va_word_havolalari_qoshilmaydi() -> None:
    """Har natija uchun 3 ta havola bor: hujjat, PDF, Word — faqat birinchisi."""
    refs = parse_results(SEARCH_HTML, FORM_CODE)
    assert len(refs) == 3, f"3 ta unikal hujjat kutilgan, olindi: {[r.doc_id for r in refs]}"


def test_sarlavha_tozalanadi() -> None:
    ref = next(r for r in parse_results(SEARCH_HTML, FORM_CODE) if r.doc_id == "-111189")
    assert ref.title == "Oʻzbekiston Respublikasining Fuqarolik kodeksi (birinchi qism)"


def test_hujjat_turi_form_id_dan() -> None:
    assert all(r.doc_type == "kodeks" for r in parse_results(SEARCH_HTML, FORM_CODE))
    assert all(r.doc_type == "qonun" for r in parse_results(SEARCH_HTML, FORM_LAW))


def test_url_quriladi() -> None:
    ref = next(r for r in parse_results(SEARCH_HTML, FORM_CODE) if r.doc_id == "-111189")
    assert ref.url == "https://lex.uz/uz/docs/-111189"


def test_bosh_sahifa() -> None:
    assert parse_results("<html></html>", FORM_CODE) == []


def test_jami_soni() -> None:
    assert parse_total(SEARCH_HTML) == 20


def test_jami_topilmasa_none() -> None:
    assert parse_total("<html>hech narsa</html>") is None


# --------------------------------------------------------------------------- #
# Tekshirilgan ID lar ro'yxati
# --------------------------------------------------------------------------- #


def test_ustuvor_hujjatlar_ozbek_nashri() -> None:
    """PRIORITY_DOCS dagi barcha kodekslar o'zbek (manfiy ID) nashri bo'lishi kerak."""
    from uzlegal.ingest.connectors.lex_uz import PRIORITY_DOCS

    assert len(PRIORITY_DOCS) == 20
    non_uzbek = [d.doc_id for d in PRIORITY_DOCS if not d.doc_id.startswith("-")]
    assert not non_uzbek, f"rus nashri qolib ketgan: {non_uzbek}"


@pytest.mark.parametrize("doc_id", ["-111189", "-6257288", "-111453"])
def test_muhim_kodekslar_royxatda(doc_id: str) -> None:
    from uzlegal.ingest.connectors.lex_uz import PRIORITY_DOCS

    assert doc_id in {d.doc_id for d in PRIORITY_DOCS}


def test_manfiy_id_fayl_nomi() -> None:
    """Manfiy ID fayl tizimida muammo tug'dirmasligi kerak."""
    from uzlegal.ingest.connectors.lex_uz import LexUzConnector

    conn = LexUzConnector()
    assert conn.raw_path("-111189").name == "neg111189.html"
    assert conn._from_safe_name("neg111189") == "-111189"
    assert conn._from_safe_name("111181") == "111181"


# --------------------------------------------------------------------------- #
# Keng kashfiyot — til va lug'at mosligi
#
# Birinchi urinishda rus qidiruviga O'ZBEKCHA atamalar yuborilgan edi
# (`majburiyat`, `ijara`) va lex.uz har safar 0 ta natija qaytardi:
# u matn bo'yicha qidiradi, tarjima qilmaydi. 95 daqiqa behuda ketdi.
# --------------------------------------------------------------------------- #


def test_har_til_oz_lugatini_oladi() -> None:
    from uzlegal.ingest.discover import (
        LANG_RU,
        LANG_UZ_LATIN,
        SEARCH_VOCABULARY,
        SEARCH_VOCABULARY_RU,
        broad_queries,
    )

    queries = broad_queries(langs=(LANG_UZ_LATIN, LANG_RU), forms=(None,))
    uz = {q.query for q in queries if q.lang == LANG_UZ_LATIN}
    ru = {q.query for q in queries if q.lang == LANG_RU}

    assert uz == set(SEARCH_VOCABULARY)
    assert ru == set(SEARCH_VOCABULARY_RU)
    assert not (uz & ru), "O'zbek va rus lug'atlari ustma-ust tushmasligi kerak"


def test_rus_lugatida_kirill_harflari_bor() -> None:
    """Rus so'rovi lotin harflarda bo'lsa, rus hujjatida uchramaydi."""
    from uzlegal.ingest.discover import SEARCH_VOCABULARY_RU

    for term in SEARCH_VOCABULARY_RU:
        assert any("Ѐ" <= ch <= "ӿ" for ch in term), f"kirill emas: {term}"


def test_ozbek_lugatida_kirill_yoq() -> None:
    from uzlegal.ingest.discover import SEARCH_VOCABULARY

    for term in SEARCH_VOCABULARY:
        assert not any("Ѐ" <= ch <= "ӿ" for ch in term), f"kirill bor: {term}"


def test_ikki_lugat_bir_xil_sohalarni_qoplaydi() -> None:
    """Qamrov nomutanosib bo'lmasligi kerak."""
    from uzlegal.ingest.discover import SEARCH_VOCABULARY, SEARCH_VOCABULARY_RU

    assert abs(len(SEARCH_VOCABULARY) - len(SEARCH_VOCABULARY_RU)) <= 3


def test_sorovlar_soni_kutilganday() -> None:
    from uzlegal.ingest.discover import LANG_UZ_LATIN, SEARCH_VOCABULARY, broad_queries

    queries = broad_queries(langs=(LANG_UZ_LATIN,), forms=(None, "3964"))
    assert len(queries) == len(SEARCH_VOCABULARY) * 2
