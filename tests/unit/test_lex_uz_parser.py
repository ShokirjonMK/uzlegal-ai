"""lex.uz parseri testlari.

Fixture — **haqiqiy** lex.uz sahifasidan (Fuqarolik kodeksi, 2026-08-09)
kesib olingan bo'lak. Sintetik emas, shuning uchun sayt tuzilishi o'zgarsa
testlar buni darhol ko'rsatadi.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from uzlegal.ingest.parsers.lex_uz import (
    LexUzParser,
    detect_doc_type,
    detect_header_level,
    is_amendment_note,
    parse_amendment,
)
from uzlegal.ingest.types import ParsedDocument, RawDocument

FIXTURE = Path(__file__).parents[1] / "fixtures" / "lex_uz_sample.html"


@pytest.fixture(scope="module")
def parsed() -> ParsedDocument:
    content = FIXTURE.read_text(encoding="utf-8")
    raw = RawDocument(
        source="lex.uz",
        doc_id="111181",
        url="https://lex.uz/docs/111181",
        fetched_at=datetime.now(UTC),
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        http_status=200,
        content_type="text/html",
        content=content,
    )
    return LexUzParser().parse(raw)


# --------------------------------------------------------------------------- #
# Asosiy ajratish
# --------------------------------------------------------------------------- #


def test_hujjat_metamalumoti(parsed: ParsedDocument) -> None:
    assert parsed.doc_id == "111181"
    assert parsed.doc_type == "kodeks"
    assert parsed.lang == "ru"
    assert "КОДЕКС" in parsed.title.upper()


def test_moddalar_ajratiladi(parsed: ParsedDocument) -> None:
    articles = parsed.articles
    assert len(articles) >= 5, "fixture da kamida 5 modda bo'lishi kerak"
    assert all(a.article_number for a in articles), "har bir moddada raqam bo'lishi shart"


def test_modda_raqamlari_ketma_ket(parsed: ParsedDocument) -> None:
    numbers = [int(a.article_number) for a in parsed.articles if a.article_number.isdigit()]
    assert numbers == sorted(numbers), "moddalar hujjat tartibida bo'lishi kerak"


def test_modda_tanasi_bosh_emas(parsed: ParsedDocument) -> None:
    """Eng muhim tekshiruv: sarlavha bor, lekin matn yo'q — jimgina nosozlik."""
    empty = [a for a in parsed.articles if len(a.body) < 30]
    assert not empty, f"tanasi bo'sh moddalar: {[a.article_number for a in empty]}"


def test_tana_sarlavhani_takrorlamaydi(parsed: ParsedDocument) -> None:
    for a in parsed.articles:
        assert not a.body.startswith(a.title), (
            f"modda {a.article_number} tanasi sarlavha bilan boshlanmasin"
        )


def test_ierarxiya_yoli(parsed: ParsedDocument) -> None:
    with_path = [a for a in parsed.articles if a.path]
    assert with_path, "moddalarda ierarxiya yo'li bo'lishi kerak"
    assert any("ГЛАВА" in " ".join(a.path).upper() for a in with_path)


def test_ui_shovqini_tozalanadi(parsed: ParsedDocument) -> None:
    noise = ["Аудиони тинглаш", "Ҳужжатга таклиф юбориш", "Ҳужжат элементидан"]
    for a in parsed.articles:
        for n in noise:
            assert n not in a.body, f"UI shovqini tozalanmagan: {n}"


def test_html_teglari_qolmaydi(parsed: ParsedDocument) -> None:
    for element in parsed.elements:
        assert "<div" not in element.body
        assert "<span" not in element.body
        assert "&nbsp;" not in element.body


# --------------------------------------------------------------------------- #
# O'zgartirish eslatmalari — versiyalash signali
# --------------------------------------------------------------------------- #


def test_ozgartirish_eslatmasi_ajratiladi(parsed: ParsedDocument) -> None:
    assert parsed.amendments, "fixture da o'zgartirish eslatmasi bor"
    note = parsed.amendments[0]
    assert note.target_article == "53"
    assert note.effective_date == "2025-12-25"
    assert note.amending_doc


def test_eslatma_modda_deb_hisoblanmaydi(parsed: ParsedDocument) -> None:
    """Eslatma CLAUSE_DEFAULT bilan keladi, lekin u modda emas."""
    for a in parsed.articles:
        assert not is_amendment_note(a.title), f"eslatma modda deb olingan: {a.title[:50]}"


@pytest.mark.parametrize(
    "text",
    [
        "Обратите внимание: в статью 53 внесены изменения",
        "Эътибор беринг: ўзгартишлар киритилган",
        "Статья утратила силу",
    ],
)
def test_eslatma_aniqlanadi(text: str) -> None:
    assert is_amendment_note(text)


def test_oddiy_modda_eslatma_emas() -> None:
    assert not is_amendment_note("Статья 1. Основные начала гражданского законодательства")


def test_eslatmadan_metamalumot() -> None:
    note = parse_amendment(
        "999", "Обратите внимание: в статью 53 внесены изменения Законом от 25 декабря 2025 года"
    )
    assert note.target_article == "53"
    assert note.effective_date == "2025-12-25"


# --------------------------------------------------------------------------- #
# Yordamchi funksiyalar
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("Часть первая", "part"),
        ("РАЗДЕЛ I ОБЩИЕ ПОЛОЖЕНИЯ", "section"),
        ("Подраздел 1 ОСНОВНЫЕ ПОЛОЖЕНИЯ", "subsection"),
        ("ГЛАВА 1 ГРАЖДАНСКОЕ ЗАКОНОДАТЕЛЬСТВО", "chapter"),
        ("11-bob Mulk huquqi", "chapter"),
    ],
)
def test_sarlavha_darajasi(title: str, level: str) -> None:
    assert detect_header_level(title) == level


@pytest.mark.parametrize(
    ("title", "doc_type"),
    [
        ("Гражданский кодекс Республики Узбекистан", "kodeks"),
        ("Mehnat kodeksi", "kodeks"),
        ("Постановление Пленума Верховного суда", "plenum"),
        ("Vazirlar Mahkamasi qarori", "VMQ"),
        ("Закон о защите прав потребителей", "qonun"),
        ("Ariza namunasi", "boshqa"),
    ],
)
def test_hujjat_turi(title: str, doc_type: str) -> None:
    assert detect_doc_type(title) == doc_type


# --------------------------------------------------------------------------- #
# Chidamlilik
# --------------------------------------------------------------------------- #


def _raw(content: str) -> RawDocument:
    return RawDocument(
        source="lex.uz",
        doc_id="test",
        url="https://lex.uz/docs/test",
        fetched_at=datetime.now(UTC),
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        http_status=200,
        content_type="text/html",
        content=content,
    )


def test_bosh_sahifa_xato_bermaydi() -> None:
    doc = LexUzParser().parse(_raw("<html><body></body></html>"))
    assert doc.elements == []
    assert doc.warnings, "bo'sh sahifa ogohlantirish berishi kerak"


def test_notogri_html_xato_bermaydi() -> None:
    doc = LexUzParser().parse(_raw("<html><div class='ACT_TEXT lx_elem'>yopilmagan"))
    assert isinstance(doc, ParsedDocument)


def test_can_parse() -> None:
    parser = LexUzParser()
    assert parser.can_parse(_raw("<html></html>"))


# --------------------------------------------------------------------------- #
# «Prim» moddalar — 358¹, 26², 176³
# --------------------------------------------------------------------------- #


def test_yuqori_indeks_modda_raqami() -> None:
    """358<sup>1</sup>-modda → "358-1", "1" EMAS.

    Real xato: teglar bo'sh joyga aylantirilib «358 1 -modda» chiqardi va
    modda raqami «1» deb ajratildi — haqiqiy 1-modda bilan to'qnashardi.
    """
    from uzlegal.ingest.normalize import extract_article_number
    from uzlegal.ingest.parsers.lex_uz import clean_text

    text = clean_text("<strong>358<sup>1</sup>-modda. Korporativ shartnoma</strong>")
    assert text.startswith("358-1-modda")
    assert extract_article_number(text) == "358-1"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("26<sup>1</sup>-modda. Jismoniy shaxs", "26-1"),
        ("176<sup>2</sup>-moddasi", "176-2"),
        ("358<sup>1</sup>-modda", "358-1"),
        ("12-modda", "12"),
    ],
)
def test_prim_moddalar(html: str, expected: str) -> None:
    from uzlegal.ingest.normalize import extract_article_number
    from uzlegal.ingest.parsers.lex_uz import clean_text

    assert extract_article_number(clean_text(html)) == expected


def test_oddiy_sup_matnni_buzmaydi() -> None:
    from uzlegal.ingest.parsers.lex_uz import clean_text

    assert "m-2" in clean_text("m<sup>2</sup>")


# --------------------------------------------------------------------------- #
# Band segmentatsiyasi — farmon va qarorlar
#
# 863 hujjatlik korpusda o'lchandi: 631 tasi (73%) nol modda bilan qaytdi.
# Ular Prezident farmoni va qarorlari — ularda «N-modda» sarlavhasi
# umuman yo'q, tuzilma faqat «1.», «2.» raqamlarida.
# --------------------------------------------------------------------------- #


def _text(body: str, element_id: str = "1") -> "Element":
    from uzlegal.ingest.types import Element

    return Element(element_id=element_id, level="text", title="", body=body)


def test_bandlar_ajratiladi() -> None:
    from uzlegal.ingest.parsers.lex_uz import segment_points

    long_a = "Sud hokimiyatining mustaqilligini taʼminlash chora-tadbirlari. " * 3
    long_b = "Vazirlar Mahkamasi bir oy muddatda takliflar kiritsin. " * 3
    out = segment_points([_text(f"1. {long_a}", "a"), _text(f"2. {long_b}", "b")])

    articles = [e for e in out if e.level == "article"]
    assert [a.article_number for a in articles] == ["1", "2"]
    assert long_a.split(".")[0] in articles[0].body


def test_band_davomi_oldingi_bandga_qoshiladi() -> None:
    """Raqamsiz paragraf — oldingi bandning davomi."""
    from uzlegal.ingest.parsers.lex_uz import segment_points

    head = "Quyidagilar asosiy yoʻnalishlar deb belgilansin. " * 3
    tail = "inson huquqlarini himoya qilish sohasida faoliyatni kuchaytirish. " * 3
    out = segment_points([_text(f"1. {head}", "a"), _text(tail, "b")])

    articles = [e for e in out if e.level == "article"]
    assert len(articles) == 1
    assert "inson huquqlarini" in articles[0].body


def test_modda_bor_hujjatga_tegilmaydi() -> None:
    """Kodeks allaqachon tuzilgan — segmentatsiya ishlamasligi kerak."""
    from uzlegal.ingest.parsers.lex_uz import segment_points
    from uzlegal.ingest.types import Element

    elements = [
        Element(element_id="a", level="article", title="1-modda", article_number="1", body="Matn"),
        _text("1. Bu band emas, modda tanasidagi ro'yxat elementi.", "b"),
    ]
    assert segment_points(elements) == elements


def test_juda_qisqa_band_alohida_chiqmaydi() -> None:
    """Jadval katagi yoki ro'yxat elementi alohida band bo'lmasligi kerak."""
    from uzlegal.ingest.parsers.lex_uz import segment_points

    long_body = "Birinchi bandning yetarlicha uzun matni bu yerda keladi. " * 3
    out = segment_points([_text(f"1. {long_body}", "a"), _text("2. Qisqa.", "b")])

    articles = [e for e in out if e.level == "article"]
    assert len(articles) == 1
    assert "Qisqa" in articles[0].body


def test_raqamsiz_matn_saqlanadi() -> None:
    """Muqaddima yo'qolmasligi kerak."""
    from uzlegal.ingest.parsers.lex_uz import segment_points

    out = segment_points([_text("Farmoni", "a"), _text("Muqaddima matni.", "b")])
    assert len(out) == 2
    assert all(e.level == "text" for e in out)


# --------------------------------------------------------------------------- #
# Strukturaviy birlik nomi
# --------------------------------------------------------------------------- #


def test_hujjat_turiga_qarab_birlik_nomi() -> None:
    """Farmonda «modda» emas, «band» — yuridik jihatdan muhim farq."""
    from uzlegal.ingest.types import unit_label

    assert unit_label("kodeks") == "modda"
    assert unit_label("qonun") == "modda"
    assert unit_label("PF") == "band"
    assert unit_label("PQ") == "band"
    assert unit_label("VMQ") == "band"


def test_nomalum_tur_modda_deb_ataladi() -> None:
    """Kodeks hech qachon noto'g'ri nomlanmasligi kerak."""
    from uzlegal.ingest.types import unit_label

    assert unit_label(None) == "modda"
    assert unit_label("boshqa") == "modda"
