"""Groundedness gate testlari — docs/01 § 6.

Bu tizimning eng muhim xavfsizlik chegarasi: gate ishlamasa, model o'ylab
topgan modda foydalanuvchiga **ishonchli javob sifatida** yetib boradi.
Shuning uchun bu yerda "asosiy holat ishlaydi" yetarli emas — har bir
chiqarish sababi alohida tekshiriladi.
"""

from __future__ import annotations

from uzlegal.orchestrator.gate import (
    REFUSAL,
    UNCERTAIN_MARK,
    ClaimKind,
    ClaimStatus,
    DropReason,
    article_numbers,
    groundedness_gate,
    is_legal_claim,
    split_claims,
    support_score,
)
from uzlegal.types import Citation

MK_106 = Citation(
    tag="C1",
    doc_id="uz-mk-2022",
    doc_title="Mehnat kodeksi",
    doc_type="kodeks",
    article="106",
    url="https://lex.uz/docs/142859#106",
    excerpt=(
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinishi mumkin. "
        "Xodim o'z tashabbusi bilan mehnat shartnomasini bekor qilishga haqli."
    ),
)
FK_234 = Citation(
    tag="C2",
    doc_id="uz-fk-1996",
    doc_title="Fuqarolik kodeksi",
    doc_type="kodeks",
    article="234",
    url="https://lex.uz/docs/111189#234",
    excerpt="Mulkdor o'z mulkini boshqa shaxsning qonunsiz egaligidan talab qilishga haqli.",
)
SOURCES = [MK_106, FK_234]


# --------------------------------------------------------------------------- #
# Da'volarga ajratish
# --------------------------------------------------------------------------- #


def test_royxat_elementi_bitta_davo_boladi() -> None:
    segments = split_claims("ASOSLAR\n- Birinchi asos [C1]\n- Ikkinchi asos [C2]")
    claims = [s for s in segments if s.is_claim]
    assert [c.text for c in claims] == ["Birinchi asos [C1]", "Ikkinchi asos [C2]"]


def test_abzats_gaplarga_bolinadi() -> None:
    segments = split_claims("Birinchi gap [C1]. Ikkinchi gap [C2].")
    assert len([s for s in segments if s.is_claim]) == 2


def test_ondagi_nuqta_gapni_bolmaydi() -> None:
    """«0.84» yoki «106.» dagi nuqta gap chegarasi emas — yuridik matnda raqam ko'p."""
    segments = split_claims("Ishonch 0.84 va muddat 3 yil.")
    assert len([s for s in segments if s.is_claim]) == 1


def test_sarlavha_davo_hisoblanmaydi() -> None:
    segments = split_claims("XULOSA\nJavob matni.")
    assert [s.is_heading for s in segments] == [True, False]


# --------------------------------------------------------------------------- #
# Da'vo turini aniqlash
# --------------------------------------------------------------------------- #


def test_norma_haqidagi_gap_huquqiy_davo() -> None:
    assert is_legal_claim("Mehnat shartnomasi 106-moddaga ko'ra bekor qilinadi")
    assert is_legal_claim("Da'vo muddati uch yil qilib belgilangan")


def test_iqtibos_belgisining_ozi_huquqiy_davo_alomati() -> None:
    """Model normaga havola qilgan bo'lsa, u huquqiy da'vo qilmoqda."""
    assert is_legal_claim("Bu holat boshqacha ko'rinadi [C1]")


def test_mantiqiy_gap_huquqiy_davo_emas() -> None:
    assert not is_legal_claim("Quyidagi savolga aniq javob berish kerak")
    assert not is_legal_claim("Vaziyat yetarlicha aniq emas")


# --------------------------------------------------------------------------- #
# Asosiy qoidalar
# --------------------------------------------------------------------------- #


def test_iqtibossiz_huquqiy_davo_ochiriladi() -> None:
    answer = (
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "Ishdan bo'shatishda ikki oylik nafaqa to'lanadi."
    )
    report = groundedness_gate(answer, SOURCES)

    assert not report.refused
    assert report.dropped == 1
    assert "ikki oylik nafaqa" not in report.answer
    assert "kelishuviga binoan" in report.answer
    dropped = next(c for c in report.checks if c.status is ClaimStatus.DROPPED)
    assert dropped.reason is DropReason.NO_CITATION


def test_yolgon_iqtibos_tutiladi() -> None:
    """Mavjud bo'lmagan belgi — eng xavfli holat: javob ishonchliroq ko'rinadi."""
    answer = (
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "Ishdan bo'shatish uchun sud qarori talab qilinadi [C9]."
    )
    report = groundedness_gate(answer, SOURCES)

    assert report.dropped == 1
    assert "[C9]" not in report.answer
    dropped = next(c for c in report.checks if c.status is ClaimStatus.DROPPED)
    assert dropped.reason is DropReason.UNKNOWN_CITATION
    assert dropped.tags == ["C9"]


def test_umumiy_davo_iqtibossiz_qoladi() -> None:
    answer = (
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "Quyidagi savolga aniq javob berish kerak."
    )
    report = groundedness_gate(answer, SOURCES)

    assert report.dropped == 0
    assert "aniq javob berish kerak" in report.answer
    general = next(c for c in report.checks if c.kind is ClaimKind.GENERAL)
    assert general.status is ClaimStatus.KEPT


def test_qollab_quvvatlanmagan_iqtibos_noaniq_deb_belgilanadi() -> None:
    """Belgi haqiqiy, lekin manba matni butunlay boshqa mavzuda."""
    answer = (
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "Avtomobil savdosida notarial tasdiqlash majburiy hisoblanadi [C1]."
    )
    report = groundedness_gate(answer, SOURCES)

    assert report.flagged == 1
    assert report.dropped == 0
    assert UNCERTAIN_MARK in report.answer
    flagged = next(c for c in report.checks if c.status is ClaimStatus.FLAGGED)
    assert flagged.reason is DropReason.UNSUPPORTED


def test_qollab_quvvatlash_tekshiruvini_ochirish_mumkin() -> None:
    answer = "Avtomobil savdosida notarial tasdiqlash majburiy hisoblanadi [C1]."
    report = groundedness_gate(answer, SOURCES, verify_support=False)
    assert report.flagged == 0
    assert report.kept == 1


def test_hamma_huquqiy_davo_ochirilsa_rad_etiladi() -> None:
    answer = (
        "Mehnat shartnomasi istalgan vaqtda bekor qilinadi.\n"
        "Ishdan bo'shatish uchun sud qarori kerak [C9]."
    )
    report = groundedness_gate(answer, SOURCES)

    assert report.refused
    assert report.answer.startswith(REFUSAL)
    assert report.kept_legal == 0
    # Rad etilganda ham foydalanuvchi qayerga qarashni bilishi kerak
    assert "Mehnat kodeksi" in report.answer
    assert report.citations == SOURCES


def test_manba_umuman_bolmasa_rad_etiladi() -> None:
    report = groundedness_gate("Har qanday javob [C1].", [])
    assert report.refused
    assert report.answer.startswith(REFUSAL)


def test_bosh_javob_rad_etiladi() -> None:
    report = groundedness_gate("", SOURCES)
    assert report.refused


# --------------------------------------------------------------------------- #
# Gate hech qachon yangi matn yozmaydi
# --------------------------------------------------------------------------- #


def test_gate_yangi_matn_generatsiya_qilmaydi() -> None:
    """Chiqishdagi har bir satr kirishda bo'lgan bo'lishi shart.

    Bu gate ning eng muhim invarianti: u javobni yaxshilashga urinsa, o'zi
    hallucination manbaiga aylanadi (docs/01 § 10).
    """
    answer = (
        "XULOSA\n"
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "ASOSLAR\n"
        "- Mulkdor mulkini qonunsiz egalikdan talab qilishga haqli [C2]\n"
        "- Bu da'vo hech qanday normaga tayanmaydi\n"
    )
    report = groundedness_gate(answer, SOURCES)

    for line in report.answer.splitlines():
        cleaned = line.replace(f" [{UNCERTAIN_MARK}]", "").lstrip("- ").strip()
        assert cleaned in answer, f"gate yangi matn qo'shdi: {line!r}"


def test_bosh_qolgan_sarlavha_olib_tashlanadi() -> None:
    answer = (
        "XULOSA\n"
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "ASOSLAR\n"
        "- Ishdan bo'shatishda ikki oylik nafaqa to'lanadi\n"
    )
    report = groundedness_gate(answer, SOURCES)
    assert "XULOSA" in report.answer
    assert "ASOSLAR" not in report.answer


def test_tuzilma_saqlanadi() -> None:
    answer = (
        "XULOSA\n"
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "ASOSLAR\n"
        "- Mulkdor mulkini qonunsiz egalikdan talab qilishga haqli [C2]\n"
    )
    report = groundedness_gate(answer, SOURCES)
    lines = report.answer.splitlines()
    assert lines[0] == "XULOSA"
    assert "ASOSLAR" in lines
    assert lines.index("ASOSLAR") > 0


# --------------------------------------------------------------------------- #
# Hisobot va audit
# --------------------------------------------------------------------------- #


def test_faqat_ishlatilgan_manbalar_qaytariladi() -> None:
    answer = "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1]."
    report = groundedness_gate(answer, SOURCES)
    assert [c.tag for c in report.citations] == ["C1"]


def test_hisobot_trace_uchun_yetarli() -> None:
    answer = (
        "Mehnat shartnomasi tomonlarning kelishuviga binoan bekor qilinadi [C1].\n"
        "Ishdan bo'shatishda nafaqa to'lanadi.\n"
        "Sud qarori kerak [C9]."
    )
    report = groundedness_gate(answer, SOURCES)
    assert report.summary() == {"claims": 3, "kept": 1, "dropped": 2}
    assert set(report.drop_reasons) == {
        DropReason.NO_CITATION.value,
        DropReason.UNKNOWN_CITATION.value,
    }


def test_support_score_manba_matnisiz_none_qaytaradi() -> None:
    """Tekshirib bo'lmaydigan narsa «qo'llab-quvvatlanmagan» degani emas."""
    bare = Citation(tag="C3", doc_id="x", article="")
    assert support_score("Uzun va mazmunli huquqiy da'vo matni", bare) is None


# --------------------------------------------------------------------------- #
# Modda raqami mosligi
#
# Amalda kuzatilgan xato (gemma3-12b, 2026-08-12): javob to'g'ri normani
# keltirdi, lekin uni NOTO'G'RI modda raqamiga bog'ladi —
# «Mehnat kodeksining 106-moddasiga ko'ra…[C1]», holbuki C1 aslida
# 130-131-modda. Leksik qoplama buni tutmaydi: so'zlar mos keladi.
# --------------------------------------------------------------------------- #


def _mk_citation(article: str, excerpt: str = "", tag: str = "C1") -> Citation:
    return Citation(
        tag=tag,
        doc_id="mk",
        doc_title="Mehnat kodeksi",
        article=article,
        excerpt=excerpt,
    )


def test_modda_raqamlari_ajratiladi() -> None:
    assert article_numbers("106-moddasiga ko'ra") == {"106"}
    assert article_numbers("130-131-modda") == {"130", "131"}
    assert article_numbers("Статья 228 нормасига") == {"228"}
    assert article_numbers("hech qanday raqam yo'q") == set()


def test_oylab_topilgan_modda_ochiriladi() -> None:
    """Da'vodagi 106 manbada yo'q — havola boshqa normaga olib boradi."""
    citation = _mk_citation("130-131", "Dastlabki sinov muddati uch oydan oshmasligi kerak.")
    report = groundedness_gate(
        "Mehnat kodeksining 106-moddasiga ko'ra sinov muddati uch oydan oshmasligi kerak [C1].",
        [citation],
    )
    assert report.dropped == 1
    assert DropReason.WRONG_ARTICLE.value in report.drop_reasons


def test_togri_modda_qoladi() -> None:
    citation = _mk_citation("130-131", "Dastlabki sinov muddati uch oydan oshmasligi kerak.")
    report = groundedness_gate(
        "Mehnat kodeksining 130-moddasiga ko'ra sinov muddati uch oydan oshmasligi kerak [C1].",
        [citation],
    )
    assert report.dropped == 0


def test_diapazonning_ikkinchi_chekkasi_ham_togri() -> None:
    citation = _mk_citation("130-131", "Sinov muddati haqida.")
    report = groundedness_gate("131-moddaga ko'ra sinov muddati belgilanadi [C1].", [citation])
    assert report.dropped == 0


def test_parcha_ichidagi_krossreferens_qabul_qilinadi() -> None:
    """Normalar bir-biriga havola qiladi — bu o'ylab topish emas."""
    citation = _mk_citation(
        "130", "Sinov muddati 228-moddada nazarda tutilgan tartibda hisoblanadi."
    )
    report = groundedness_gate("228-moddadagi tartib qo'llaniladi [C1].", [citation])
    assert report.dropped == 0


def test_iqtibosda_modda_raqami_yoq_bolsa_jazolanmaydi() -> None:
    """Tekshirib bo'lmaydigan narsa «noto'g'ri» degani emas."""
    citation = Citation(tag="C1", doc_id="x", doc_title="Qaror", article="", excerpt="Umumiy matn.")
    report = groundedness_gate("55-moddaga ko'ra tartib belgilanadi [C1].", [citation])
    assert DropReason.WRONG_ARTICLE.value not in report.drop_reasons


def test_davoda_modda_raqami_yoq_bolsa_tekshirilmaydi() -> None:
    citation = _mk_citation("130", "Dastlabki sinov muddati uch oydan oshmasligi kerak.")
    report = groundedness_gate("Sinov muddati uch oydan oshmasligi kerak [C1].", [citation])
    assert DropReason.WRONG_ARTICLE.value not in report.drop_reasons
