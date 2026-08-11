"""Validatsiya testlari — docs/03 § 3.8.

Har bir tekshiruv uchun ikki holat: buzilgan hujjat **aniqlanishi** va
to'g'ri hujjat **tinch qolishi** kerak. Ikkinchisi muhimroq — yolg'on
signal butun korpusni karantinga tiqib qo'yadi va tekshiruv o'chiriladi.
"""

from __future__ import annotations

from datetime import date

import pytest

from uzlegal.ingest.connectors.lex_uz import LexUzConnector
from uzlegal.ingest.parsers.lex_uz import LexUzParser
from uzlegal.ingest.types import Element, ParsedDocument
from uzlegal.ingest.validate import (
    AUTOFIX_CODES,
    DROP_CODES,
    QUARANTINE_CODES,
    validate_document,
    validate_documents,
)
from uzlegal.ingest.versioning import apply_versions

TODAY = date(2026, 8, 11)
MATN = "Mulkdor oʻzgalarning qonunsiz egaligidagi mulkni talab qilib olishga haqli."


def _doc(*elements: Element, lang: str = "uz") -> ParsedDocument:
    return ParsedDocument(
        doc_id="sinov",
        source="lex.uz",
        url="https://lex.uz/uz/docs/sinov",
        title="Sinov kodeksi",
        lang=lang,  # type: ignore[arg-type]
        elements=list(elements),
    )


def _article(number: str | None, body: str = MATN, **kwargs: object) -> Element:
    return Element(
        element_id=f"e{number}",
        level="article",
        title=f"{number}-modda. Sarlavha",
        body=body,
        article_number=number,
        **kwargs,  # type: ignore[arg-type]
    )


def _codes(doc: ParsedDocument) -> set[str]:
    return {i.code for i in validate_document(doc, today=TODAY)}


# --------------------------------------------------------------------------- #
# Toza hujjat
# --------------------------------------------------------------------------- #


def test_toza_hujjatda_muammo_yoq() -> None:
    assert validate_document(_doc(_article("234")), today=TODAY) == []


def test_ierarxiya_mos_kelsa_muammo_yoq() -> None:
    chapter = Element(element_id="b1", level="chapter", title="11-BOB. MULK HUQUQI")
    article = _article("234")
    article.path = ["11-BOB.  MULK HUQUQI"]  # xom shakl — bo'sh joylar boshqacha
    assert "ierarxiya_nomuvofiq" not in _codes(_doc(chapter, article))


# --------------------------------------------------------------------------- #
# Karantin
# --------------------------------------------------------------------------- #


def test_modda_raqami_yoq() -> None:
    assert "modda_raqami_yoq" in _codes(_doc(_article(None)))


def test_takrorlangan_modda() -> None:
    doc = _doc(_article("12"), _article("12"))
    doc.elements[1].element_id = "e12b"
    assert "modda_takrorlanadi" in _codes(doc)


def test_ierarxiya_nomuvofiq() -> None:
    article = _article("234")
    article.path = ["99-BOB. MAVJUD BO'LMAGAN BOB"]
    assert "ierarxiya_nomuvofiq" in _codes(_doc(article))


def test_kelajakdagi_sana_xato() -> None:
    """Modda amalda, lekin versiya filtri uni chiqarib yuboradi — jimgina nosozlik."""
    assert "sana_kelajakda" in _codes(_doc(_article("234", valid_from="2030-01-01")))


def test_sana_mantiqsiz() -> None:
    doc = _doc(_article("234", valid_from="2020-01-01", valid_to="2019-01-01"))
    assert "sana_mantiqsiz" in _codes(doc)


def test_pii_karantin() -> None:
    body = "Daʼvogar Karimov Alisher Baxtiyorovich, JSHSHIR 30101856120014, ariza berdi."
    assert "pii_topildi" in _codes(_doc(_article("5", body)))


def test_bekor_qilingan_modda_matnda_qolsa_karantin() -> None:
    note = (
        "(241-9-modda Oʻzbekiston Respublikasining 2018-yil 23-iyuldagi OʻRQ-486-sonli "
        "Qonuniga asosan oʻz kuchini yoʻqotgan - Qonun hujjatlari maʼlumotlari milliy "
        "bazasi, 24.07.2018-y., 03/18/486/1559-son)"
    )
    doc = apply_versions(_doc(_article("241-9", f"{MATN}\n{note}")), today=TODAY)
    assert "bekor_qilingan_matnda" in _codes(doc)


# --------------------------------------------------------------------------- #
# Tashlab yuborish va ogohlantirish
# --------------------------------------------------------------------------- #


def test_qisqa_matn() -> None:
    codes = _codes(_doc(_article("234", "Bekor.")))
    assert "matn_qisqa" in codes


def test_qisqa_matnda_boshqa_tekshiruv_otkaziladi() -> None:
    """20 belgidan qisqa matn baribir tashlanadi — ortiqcha shovqin kerak emas."""
    codes = _codes(_doc(_article("234", "Bekor.")))
    assert codes == {"matn_qisqa"}


def test_kirill_qoldigi_ogohlantirish() -> None:
    doc = _doc(_article("234", "Мулкдор ўзганинг мулкини талаб қилиб олишга ҳақли эмас."))
    issues = validate_document(doc, today=TODAY)
    assert any(i.code == "kirill_qoldigi" and i.severity == "warning" for i in issues)


def test_rus_hujjatida_kirill_ogohlantirish_yoq() -> None:
    doc = _doc(
        _article("234", "Собственник вправе истребовать имущество из чужого владения."),
        lang="ru",
    )
    assert "kirill_qoldigi" not in _codes(doc)


def test_apostrof_ogohlantirish() -> None:
    doc = _doc(_article("234", "Mulkdor o'zgalarning qonunsiz egaligidagi mulkni talab qiladi."))
    issues = validate_document(doc, today=TODAY)
    assert any(i.code == "apostrof_nokanonik" and i.severity == "warning" for i in issues)


# --------------------------------------------------------------------------- #
# Harakat to'plamlari va yig'ma hisobot
# --------------------------------------------------------------------------- #


def test_harakat_toplamlari_kesishmaydi() -> None:
    assert not (QUARANTINE_CODES & DROP_CODES)
    assert not (QUARANTINE_CODES & AUTOFIX_CODES)


def test_yigma_hisobot() -> None:
    summary = validate_documents([_doc(_article("1"), _article(None))], today=TODAY)
    assert summary.documents == 1
    assert summary.articles == 2
    assert summary.errors == 1
    assert len(summary.quarantined) == 1
    assert summary.by_code()["modda_raqami_yoq"] == 1


def test_pii_tekshiruvi_ochirilishi_mumkin() -> None:
    body = "Daʼvogar Karimov Alisher Baxtiyorovich ariza berdi va sud qaror qabul qildi."
    doc = _doc(_article("5", body))
    assert "pii_topildi" not in {
        i.code for i in validate_document(doc, today=TODAY, check_pii=False)
    }


# --------------------------------------------------------------------------- #
# Arxivdagi haqiqiy hujjat
# --------------------------------------------------------------------------- #

ARXIV_ID = "-111189"


def test_arxivdagi_kodeks_karantin_darajasi() -> None:
    """docs/03 § 5: karantin darajasi ≤ 5%."""
    raw = LexUzConnector().load_cached(ARXIV_ID)
    if raw is None:
        pytest.skip(f"Arxivda {ARXIV_ID} yo'q — `uzlegal kb sync --docs {ARXIV_ID}`")

    doc = apply_versions(LexUzParser().parse(raw), today=TODAY)
    summary = validate_documents([doc], today=TODAY)
    assert summary.quarantine_rate <= 0.05, summary.by_code()
