"""Versiyalash testlari — docs/03 § 3.4.

Izoh matnlari **haqiqiy** lex.uz hujjatlaridan olingan (Fuqarolik kodeksi,
Jinoyat-protsessual kodeksi, Maʼmuriy javobgarlik kodeksi — 2026-08-11
arxivi). Sintetik misol emas: shakl o'zgarsa testlar buni darhol ko'rsatadi.

Arxivga tayanadigan testlar `data/raw` bo'lmasa o'tkazib yuboriladi —
testlar hech qachon tarmoqqa chiqmaydi.
"""

from __future__ import annotations

from datetime import date

import pytest

from uzlegal.ingest.connectors.lex_uz import LexUzConnector
from uzlegal.ingest.parsers.lex_uz import LexUzParser
from uzlegal.ingest.types import Element, ParsedDocument
from uzlegal.ingest.versioning import (
    amending_doc_id,
    apply_versions,
    build_versions,
    effective_date,
    note_targets,
    parse_note,
    split_citation,
)

TODAY = date(2026, 8, 11)

TAHRIR = (
    "(148-moddaning birinchi qismi dispozitsiyasi Oʻzbekiston Respublikasining "
    "2017-yil 6-sentabrdagi OʻRQ-442-sonli Qonuni tahririda - OʻR QHT, 2017-y., "
    "36-son, 943-modda)"
)
BEKOR = (
    "(Oʻzbekiston Respublikasining 2025-yil 7-fevraldagi OʻRQ-1025-sonli Qonuniga "
    "asosan 176-moddaning oʻz kuchini yoʻqotish sanasi - 2025-yil 8-may - "
    "Qonunchilik maʼlumotlari milliy bazasi, 07.02.2025-y., 03/25/1025/0116-son)"
)
KUCHGA_KIRISH = (
    "(2-moddaning beshinchi qismi Oʻzbekiston Respublikasining 2025-yil 23-iyundagi "
    "OʻRQ-1070-sonli Qonuni tahririda - Qonunchilik maʼlumotlari milliy bazasi, "
    "24.06.2025-y., 03/25/1070/0536-son. Kuchga kirish sanasi - 2025-yil 25-sentabr)"
)
BOB_BEKOR = (
    "(42-bob Oʻzbekiston Respublikasining 2017-yil 6-sentabrdagi OʻRQ-442-sonli "
    "Qonuniga asosan oʻz kuchini yoʻqotgan - OʻR QHT, 2017-y., 36-son, 943-modda)"
)
DIAPAZON = (
    "(173-1 - 173-7-moddalar Oʻzbekiston Respublikasining 2023-yil 23-oktabrdagi "
    "OʻRQ-871-sonli Qonuniga asosan kiritilgan - Qonunchilik maʼlumotlari milliy "
    "bazasi, 25.10.2023-y., 03/23/871/0797-son)"
)


def _doc(*articles: tuple[str, str]) -> ParsedDocument:
    return ParsedDocument(
        doc_id="sinov",
        source="lex.uz",
        url="https://lex.uz/uz/docs/sinov",
        title="Sinov kodeksi",
        elements=[
            Element(
                element_id=f"e{number}",
                level="article",
                title=f"{number}-modda. Sarlavha",
                body=body,
                article_number=number,
            )
            for number, body in articles
        ],
    )


# --------------------------------------------------------------------------- #
# Nishon modda
# --------------------------------------------------------------------------- #


def test_nashr_quyrugi_ajratiladi() -> None:
    """«OʻR QHT, 2017-y., 36-son, 943-modda» — byulleten, kodeks moddasi emas."""
    head, tail = split_citation(TAHRIR.lower().replace("ʻ", "'").replace("ʼ", "'"))
    assert "148" in head
    assert "943" in tail and "943" not in head


def test_nashr_quyrugidagi_modda_nishon_emas() -> None:
    signal = parse_note(TAHRIR)
    assert signal is not None
    assert signal.articles == ["148"], "943-modda nashr havolasi, nishon emas"


def test_diapazon_yoyiladi() -> None:
    signal = parse_note(DIAPAZON)
    assert signal is not None
    assert signal.articles == [f"173-{n}" for n in range(1, 8)]
    assert signal.kind == "added"


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        ("148-moddaning birinchi qismi", ["148"]),
        ("65 va 66-moddalar", ["65", "66"]),
        ("2 — 7-moddalari", ["2", "3", "4", "5", "6", "7"]),
        ("259-1-moddaning nomi", ["259-1"]),
        ("в статью 53 внесены изменения", ["53"]),
    ],
)
def test_nishon_ajratiladi(head: str, expected: list[str]) -> None:
    assert note_targets(head.lower()) == expected


# --------------------------------------------------------------------------- #
# Tur va sana
# --------------------------------------------------------------------------- #


def test_tahrir_sanasi_qonun_qabul_sanasi() -> None:
    signal = parse_note(TAHRIR)
    assert signal is not None
    assert signal.kind == "edition"
    assert signal.effective_date == "2017-09-06"
    assert signal.amending_doc == "OʻRQ-442"


def test_kuchga_kirish_sanasi_ustun() -> None:
    """Bir izohda uch sana bor — kuchga kirish sanasi g'olib."""
    signal = parse_note(KUCHGA_KIRISH)
    assert signal is not None
    assert signal.effective_date == "2025-09-25", "qabul (23.06) yoki nashr (24.06) emas"


def test_bekor_qilish_sanasi() -> None:
    signal = parse_note(BEKOR)
    assert signal is not None
    assert signal.kind == "repealed"
    assert signal.scope == "article"
    assert signal.effective_date == "2025-05-08", "qonun sanasi (07.02) emas"


def test_qism_bekor_qilinishi_moddani_bekor_qilmaydi() -> None:
    note = (
        "(85-moddaning toʻrtinchi qismi Oʻzbekiston Respublikasining 2003-yil "
        "30-avgustdagi 535-II-son Qonuniga muvofiq chiqarib tashlangan - "
        "Oliy Majlis Axborotnomasi, 2003-y., 9-10-son, 149-modda)"
    )
    signal = parse_note(note)
    assert signal is not None
    assert signal.scope == "part"
    assert signal.kind == "removed"

    report = build_versions(_doc(("85", f"Matn.\n{note}")), today=TODAY)
    assert report.versions["85"].status == "in_force"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("o'rq-683-sonli qonuni", "OʻRQ-683"),  # kirish `fold()` shaklida keladi
        ("535-ii-son qonuniga", "535-II"),
        ("зру-123 sonli", "OʻRQ-123"),
    ],
)
def test_ozgartiruvchi_hujjat(text: str, expected: str) -> None:
    assert amending_doc_id(text) == expected


def test_sana_topilmasa_none() -> None:
    """Taxmin qilinmaydi: noto'g'ri sana yo'q sanadan xavfliroq."""
    assert effective_date("qonuniga asosan tahririda", "edition") is None


# --------------------------------------------------------------------------- #
# Bob izohi — o'lchangan yolg'on «repealed» manbai
# --------------------------------------------------------------------------- #


def test_bob_izohi_moddaga_bogflanmaydi() -> None:
    """Bob bekor qilinsa, qo'shni modda bekor qilingan deb belgilanmasin."""
    signal = parse_note(BOB_BEKOR, fallback_article="338")
    assert signal is None


def test_bob_izohi_hujjatda_moddani_ozgartirmaydi() -> None:
    report = build_versions(_doc(("338", f"Modda matni.\n{BOB_BEKOR}")), today=TODAY)
    assert "338" not in report.versions or report.versions["338"].status == "in_force"


# --------------------------------------------------------------------------- #
# Hujjat darajasida
# --------------------------------------------------------------------------- #


def test_bir_necha_izohda_eng_oxirgi_sana() -> None:
    body = (
        "Modda matni.\n"
        "(15-moddaning matni Oʻzbekiston Respublikasining 2020-yil 22-yanvardagi "
        "OʻRQ-603-sonli Qonuni tahririda - Qonun hujjatlari maʼlumotlari milliy "
        "bazasi, 23.01.2020-y., 03/20/603/0071-son)\n"
        "(15-moddaning birinchi qismi Oʻzbekiston Respublikasining 2021-yil "
        "21-apreldagi OʻRQ-683-sonli Qonuni tahririda - Qonunchilik maʼlumotlari "
        "milliy bazasi, 21.04.2021-y., 03/21/683/0375-son)"
    )
    version = build_versions(_doc(("15", body)), today=TODAY).versions["15"]
    assert version.valid_from == "2021-04-21"
    assert version.note_count == 2
    assert set(version.amended_by) == {"OʻRQ-603", "OʻRQ-683"}


def test_kelajakdagi_sana_valid_from_ga_tushmaydi() -> None:
    """Kuchga kirmagan tahrir — matndagi versiya hali eskisi.

    Bunday sana `valid_from` ga yozilsa, `version_filter` bugungi so'rovda
    amaldagi moddani chiqarib yuborardi.
    """
    body = f"Modda matni.\n{KUCHGA_KIRISH}"
    version = build_versions(_doc(("2", body)), today=date(2025, 7, 1)).versions["2"]
    assert version.valid_from is None
    assert version.pending_from == "2025-09-25"


def test_bekor_qilingan_modda_statusi() -> None:
    report = build_versions(_doc(("176", f"Matn.\n{BEKOR}")), today=TODAY)
    version = report.versions["176"]
    assert version.status == "repealed"
    assert version.valid_to == "2025-05-08"


def test_kelajakda_bekor_qilinadigan_modda_hozir_amalda() -> None:
    report = build_versions(_doc(("176", f"Matn.\n{BEKOR}")), today=date(2025, 1, 1))
    version = report.versions["176"]
    assert version.status == "in_force", "bekor qilish sanasi hali kelmagan"
    assert version.valid_to == "2025-05-08"


def test_matnda_yoq_bekor_modda_qayd_etiladi() -> None:
    report = build_versions(_doc(("175", f"Matn.\n{BEKOR}")), today=TODAY)
    assert report.repealed_absent == ["176"]


def test_apply_versions_elementlarga_yozadi() -> None:
    doc = _doc(("148", f"Matn.\n{TAHRIR}"))
    apply_versions(doc, today=TODAY)
    element = doc.articles[0]
    assert element.valid_from == "2017-09-06"
    assert element.status == "in_force"
    assert element.amended_by == ["OʻRQ-442"]


def test_izohsiz_modda_versiyasiz_qoladi() -> None:
    doc = _doc(("1", "Oddiy modda matni, hech qanday tahrir izohisiz."))
    apply_versions(doc, today=TODAY)
    assert doc.articles[0].valid_from is None
    assert doc.articles[0].status == "in_force"


# --------------------------------------------------------------------------- #
# Arxivdagi haqiqiy hujjat
# --------------------------------------------------------------------------- #

ARXIV_ID = "-111189"  # Fuqarolik kodeksi (birinchi qism)


@pytest.fixture(scope="module")
def fuqarolik_kodeksi() -> ParsedDocument:
    raw = LexUzConnector().load_cached(ARXIV_ID)
    if raw is None:
        pytest.skip(f"Arxivda {ARXIV_ID} yo'q — `uzlegal kb sync --docs {ARXIV_ID}`")
    return LexUzParser().parse(raw)


def test_arxivdagi_kodeksda_moddalar_versiya_oladi(fuqarolik_kodeksi: ParsedDocument) -> None:
    report = build_versions(fuqarolik_kodeksi, today=TODAY)
    present = {a.article_number for a in fuqarolik_kodeksi.articles}
    dated = [n for n, v in report.versions.items() if n in present and v.valid_from]

    assert len(dated) > 150, f"kutilgan >150, olindi {len(dated)}"
    assert report.notes_parsed / report.notes_seen > 0.9


def test_arxivda_yolgon_bekor_qilish_yoq(fuqarolik_kodeksi: ParsedDocument) -> None:
    """FK birinchi qismida bekor qilingan moddalar matndan olib tashlangan."""
    report = build_versions(fuqarolik_kodeksi, today=TODAY)
    present = {a.article_number for a in fuqarolik_kodeksi.articles}
    still_present = [n for n, v in report.versions.items() if n in present and v.status == "repealed"]
    assert still_present == []
    assert "176" in report.repealed_absent
