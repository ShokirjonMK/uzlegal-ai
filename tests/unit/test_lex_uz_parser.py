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
        assert not a.body.startswith(a.title), f"modda {a.article_number} tanasi sarlavha bilan boshlanmasin"


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
        source="lex.uz", doc_id="test", url="https://lex.uz/docs/test",
        fetched_at=datetime.now(UTC),
        content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        http_status=200, content_type="text/html", content=content,
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
