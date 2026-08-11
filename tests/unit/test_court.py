"""Sud qarori tahlili testlari — parser, yettita tekshiruv, hisobot.

Barcha testlar **modelsiz**: modul butunlay deterministik va bir xil
matn har doim bir xil natija berishi kerak. Aynan shu xususiyat bu
yerda tekshiriladigan asosiy narsa — tahlil sudda ishlatilishi mumkin
bo'lsa, u takrorlanadigan bo'lishi shart.

Testlar ikki tomonlama: har bir tekshiruv **nimani topishi** ham,
**nimani topmasligi** ham qo'riqlanadi. Faqat birinchisi bo'lsa, hamma
narsadan shikoyat qiladigan analizator ham «o'tardi».
"""

from __future__ import annotations

from uzlegal.court import Severity, analyze, parse, review
from uzlegal.court.analyzer import (
    check_deadlines,
    check_evidence,
    check_law_application,
    check_precedent,
    check_procedural,
    check_proportionality,
    check_rights,
)
from uzlegal.court.parser import DecisionKind, PenaltyKind

# --------------------------------------------------------------------------- #
# Namuna qarorlar
# --------------------------------------------------------------------------- #

CLEAN_CRIMINAL = """OʻZBEKISTON RESPUBLIKASI NOMIDAN
HUKM

Ish № 1-2345/2024

Toshkent shahar Chilonzor tumanlararo sudi
Sudya: Karimov A.B.
2024-yil 15-mart kuni sud majlisida ochiq koʻrib chiqdi.

Prokuror: Rahimov S.T.
Himoyachi: Yoʻldoshev B.N.
Sudlanuvchi: Toshmatov Alisher Baxtiyorovich
Jabrlanuvchi: Sobirov Rustam

ANIQLADI:

Toshmatov A.B. 2023-yil 10-dekabr kuni mol-mulkni oʻgʻirlagan.
Guvoh koʻrsatuvlari bilan tasdiqlangan.
Ekspert xulosasiga koʻra zarar 5 000 000 soʻmni tashkil etadi.
Tekshiruv bayonnomasi ishga qoʻshilgan.

ASOSLAR:

Sud dalillarni tekshirib, sudlanuvchining aybi isbotlangan deb topdi.
Ogʻirlashtiruvchi holat sifatida jinoyat takroran sodir etilgani qayd etildi.
Oliy sud Plenumi qarori hisobga olindi.
Sudlanuvchiga oxirgi soʻz berildi.

HUKM QILDI:

Toshmatov Alisher Baxtiyorovichni Jinoyat kodeksining 169-moddasi 2-qismi
bilan aybdor deb topib, 3 yil ozodlikdan mahrum qilish jazosi tayinlansin.
Hukm ustidan 10 kun ichida apellyatsiya shikoyati berilishi mumkin.
"""

BARE = """HUKM

ANIQLADI:

Sudlanuvchining aybi isbotlangan deb topildi.

HUKM QILDI:

5 yil ozodlikdan mahrum qilish jazosi tayinlansin.
"""


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def test_hujjat_turi_aniqlanadi() -> None:
    assert parse(CLEAN_CRIMINAL).kind is DecisionKind.HUKM
    assert parse("QAROR\n\nQAROR QILDI:\nDaʼvo qanoatlantirilsin.").kind is DecisionKind.QAROR


def test_kirish_qismi_maydonlari() -> None:
    d = parse(CLEAN_CRIMINAL)
    assert d.case_number == "1-2345/2024"
    assert d.judge == "Karimov A.B."
    assert d.court is not None and "Chilonzor" in d.court
    assert d.decided_at == "2024-03-15"


def test_tomonlar_rollari_bilan_ajratiladi() -> None:
    d = parse(CLEAN_CRIMINAL)
    roles = {p.role: p.name for p in d.parties}

    assert roles["sudlanuvchi"] == "Toshmatov Alisher Baxtiyorovich"
    assert roles["himoyachi"] == "Yoʻldoshev B.N."
    assert roles["prokuror"] == "Rahimov S.T."


def test_ism_satr_chegarasidan_oshmaydi() -> None:
    """Keyingi qatordagi rol nomi ismga yopishib qolmasligi kerak."""
    d = parse("Jabrlanuvchi: Sobirov Rustam\nSudlanuvchi: Toshmatov Alisher")
    assert d.party("jabrlanuvchi") is not None
    assert d.party("jabrlanuvchi").name == "Sobirov Rustam"  # type: ignore[union-attr]


def test_umumiy_ibora_tomon_deb_olinmaydi() -> None:
    """«Guvoh koʻrsatuvlari bilan tasdiqlangan» — bu tomon emas, dalil."""
    d = parse("ANIQLADI:\nGuvoh koʻrsatuvlari bilan tasdiqlangan.")
    assert not d.has_role("guvoh")


def test_bolimlar_ajratiladi() -> None:
    d = parse(CLEAN_CRIMINAL)
    assert "oʻgʻirlagan" in d.circumstances
    assert "aybi isbotlangan" in d.reasoning
    assert "ozodlikdan mahrum" in d.conclusion


def test_qonun_havolalari_ajratiladi() -> None:
    d = parse(CLEAN_CRIMINAL)
    assert len(d.law_references) == 1
    ref = d.law_references[0]
    assert ref.doc_title == "jinoyat kodeksi"
    assert ref.article == "169"
    assert ref.part == "2"


def test_qisqartma_havola_ham_ajratiladi() -> None:
    d = parse("HUKM QILDI:\nJK 105-moddasi bilan aybdor deb topilsin.")
    assert d.law_references[0].doc_title == "jinoyat kodeksi"
    assert d.law_references[0].article == "105"


def test_protsessual_kodeks_moddiy_bilan_chalkashmaydi() -> None:
    """«jinoyat-protsessual» «jinoyat» dan oldin tekshirilishi kerak."""
    d = parse("HUKM QILDI:\nJinoyat-protsessual kodeksining 455-moddasiga asosan.")
    assert d.law_references[0].doc_title == "jinoyat-protsessual kodeksi"


def test_dalillar_ajratiladi() -> None:
    d = parse(CLEAN_CRIMINAL)
    assert len(d.evidence) >= 3
    assert any("guvoh" in e.lower() for e in d.evidence)


def test_jazo_ajratiladi() -> None:
    penalty = parse(CLEAN_CRIMINAL).penalty
    assert penalty is not None
    assert penalty.kind is PenaltyKind.OZODLIKDAN_MAHRUM
    assert penalty.amount == 3.0
    assert penalty.unit == "yil"
    assert not penalty.suspended


def test_shartli_hukm_belgilanadi() -> None:
    d = parse("HUKM QILDI:\n2 yil ozodlikdan mahrum qilib, shartli ravishda qoʻllansin.")
    assert d.penalty is not None and d.penalty.suspended


def test_jazosiz_qarorda_penalty_yoq() -> None:
    d = parse("QAROR\n\nQAROR QILDI:\nDaʼvo arizasi koʻrib chiqilmasdan qoldirilsin.")
    assert d.penalty is None


def test_topilmagan_maydon_ogohlantirishga_tushadi() -> None:
    """Topilmagan maydon xato emas — u ochiq qayd etiladi."""
    d = parse(BARE)
    assert d.case_number is None
    assert any("case_number" in w for w in d.warnings)


# --------------------------------------------------------------------------- #
# 1 — Protsessual
# --------------------------------------------------------------------------- #


def test_toliq_qarorda_protsessual_kamchilik_yoq() -> None:
    assert check_procedural(parse(CLEAN_CRIMINAL)) == []


def test_yetishmayotgan_rekvizitlar_topiladi() -> None:
    codes = {f.code for f in check_procedural(parse(BARE))}
    assert "PROC-001" in codes  # ish raqami, sud, sudya, sana
    assert "PROC-003" in codes  # tomonlar


def test_rezolyutiv_qismsiz_qaror_kritik() -> None:
    findings = check_procedural(parse("HUKM\n\nANIQLADI:\nBaʼzi holatlar."))
    assert any(f.code == "PROC-002" and f.severity is Severity.CRITICAL for f in findings)


# --------------------------------------------------------------------------- #
# 2 — Dalillar
# --------------------------------------------------------------------------- #


def test_dalilsiz_ayblov_kritik() -> None:
    findings = check_evidence(parse(BARE))
    assert any(f.code == "EVID-001" and f.severity is Severity.CRITICAL for f in findings)


def test_bitta_dalilga_tayangan_ayblov_belgilanadi() -> None:
    text = (
        "HUKM\nANIQLADI:\nYagona guvoh koʻrsatuvlari bilan tasdiqlangan holat.\n"
        "ASOSLAR:\nAybi isbotlangan deb topildi.\nHUKM QILDI:\nJK 105-modda."
    )
    findings = check_evidence(parse(text))
    assert any(f.code == "EVID-002" for f in findings)


def test_toliq_dalillarda_kamchilik_yoq() -> None:
    assert check_evidence(parse(CLEAN_CRIMINAL)) == []


# --------------------------------------------------------------------------- #
# 3 — Qonun qo'llanishi
# --------------------------------------------------------------------------- #


def test_havolasiz_qaror_kritik() -> None:
    findings = check_law_application(parse(BARE))
    assert any(f.code == "LAW-001" and f.severity is Severity.CRITICAL for f in findings)


def test_faqat_protsessual_havola_bilan_jazo_kritik() -> None:
    text = (
        "HUKM\nHUKM QILDI:\nJinoyat-protsessual kodeksining 455-moddasiga asosan "
        "3 yil ozodlikdan mahrum qilinsin."
    )
    codes = {f.code for f in check_law_application(parse(text))}
    assert "LAW-002" in codes


def test_mavjud_bolmagan_modda_raqami_belgilanadi() -> None:
    d = parse("HUKM QILDI:\nJinoyat kodeksining 9999-moddasi bilan aybdor deb topilsin.")
    assert any(f.code == "LAW-004" for f in check_law_application(d))


def test_togri_havolada_kamchilik_yoq() -> None:
    assert check_law_application(parse(CLEAN_CRIMINAL)) == []


# --------------------------------------------------------------------------- #
# 4 — Mutanosiblik
# --------------------------------------------------------------------------- #


def test_chegaradan_oshgan_muddat_kritik() -> None:
    text = "HUKM\nASOSLAR:\nAsoslar.\nHUKM QILDI:\nJK 97-modda, 30 yil ozodlikdan mahrum qilinsin."
    findings = check_proportionality(parse(text))
    assert any(f.code == "PROP-001" and f.severity is Severity.CRITICAL for f in findings)


def test_yengillashtiruvchi_holatda_ozodlikdan_mahrum_belgilanadi() -> None:
    text = (
        "HUKM\nASOSLAR:\nYengillashtiruvchi holat: birinchi marta sodir etgan, "
        "zararni qopladi.\nHUKM QILDI:\nJK 169-modda, 3 yil ozodlikdan mahrum qilinsin."
    )
    assert any(f.code == "PROP-002" for f in check_proportionality(parse(text)))


def test_ogirlashtiruvchi_holat_borligida_belgilanmaydi() -> None:
    """Ogʻirlashtiruvchi holat bo'lsa ozodlikdan mahrum qilish asoslangan."""
    codes = {f.code for f in check_proportionality(parse(CLEAN_CRIMINAL))}
    assert "PROP-002" not in codes


def test_asossiz_jazo_belgilanadi() -> None:
    text = "HUKM\nHUKM QILDI:\nJK 169-modda, 3 yil ozodlikdan mahrum qilinsin."
    assert any(f.code == "PROP-003" for f in check_proportionality(parse(text)))


def test_jazosiz_qarorda_mutanosiblik_tekshirilmaydi() -> None:
    assert check_proportionality(parse("QAROR\nQAROR QILDI:\nDaʼvo rad etilsin.")) == []


# --------------------------------------------------------------------------- #
# 5 — Huquqlar
# --------------------------------------------------------------------------- #


def test_himoyachisiz_jinoyat_ishi_kritik() -> None:
    findings = check_rights(parse(BARE))
    assert any(f.code == "RIGHT-001" and f.severity is Severity.CRITICAL for f in findings)


def test_oxirgi_soz_qayd_etilmagani_topiladi() -> None:
    assert any(f.code == "RIGHT-002" for f in check_rights(parse(BARE)))


def test_tarjimon_kerak_bolganda_talab_qilinadi() -> None:
    text = (
        "HUKM\nSudlanuvchi: Petrov Ivan\nHimoyachi: Aliyev B.N.\n"
        "ANIQLADI:\nSudlanuvchi oʻzbek tilini bilmaydi.\n"
        "ASOSLAR:\nOxirgi soʻz berildi.\nHUKM QILDI:\nJK 105-modda."
    )
    assert any(f.code == "RIGHT-003" for f in check_rights(parse(text)))


def test_shikoyat_tartibi_korsatilmagani_topiladi() -> None:
    assert any(f.code == "RIGHT-004" for f in check_rights(parse(BARE)))


def test_toliq_qarorda_huquq_kamchiligi_yoq() -> None:
    assert check_rights(parse(CLEAN_CRIMINAL)) == []


# --------------------------------------------------------------------------- #
# 6 — Muddatlar
# --------------------------------------------------------------------------- #


def test_qaror_majlisdan_oldin_bolsa_kritik() -> None:
    d = parse(CLEAN_CRIMINAL)
    d.decided_at, d.hearing_at = "2024-03-01", "2024-03-15"
    findings = check_deadlines(d)
    assert any(f.code == "TIME-001" and f.severity is Severity.CRITICAL for f in findings)


def test_uzoq_kechikish_belgilanadi() -> None:
    d = parse(CLEAN_CRIMINAL)
    d.decided_at, d.hearing_at = "2024-05-01", "2024-03-01"
    assert any(f.code == "TIME-002" for f in check_deadlines(d))


def test_notogri_shikoyat_muddati_topiladi() -> None:
    d = parse(CLEAN_CRIMINAL)
    d.appeal_note = "Hukm ustidan 90 kun ichida shikoyat berilishi mumkin."
    assert any(f.code == "TIME-003" for f in check_deadlines(d))


def test_odatdagi_shikoyat_muddati_belgilanmaydi() -> None:
    codes = {f.code for f in check_deadlines(parse(CLEAN_CRIMINAL))}
    assert "TIME-003" not in codes


def test_sanasiz_qaror_qayd_etiladi() -> None:
    assert any(f.code == "TIME-004" for f in check_deadlines(parse(BARE)))


# --------------------------------------------------------------------------- #
# 7 — Oldingi qarorlar
# --------------------------------------------------------------------------- #


def test_bahalanmagan_sudlanganlik_topiladi() -> None:
    text = (
        "HUKM\nASOSLAR:\nSudlanuvchida ilgari sudlangan holati mavjud.\n"
        "HUKM QILDI:\nJK 169-modda, 3 yil ozodlikdan mahrum qilinsin."
    )
    assert any(f.code == "PREC-001" for f in check_precedent(parse(text)))


def test_bahalangan_sudlanganlik_belgilanmaydi() -> None:
    text = (
        "HUKM\nASOSLAR:\nIlgari sudlangan, lekin sudlanganlik olib tashlangan.\n"
        "Oliy sud Plenumi qarori hisobga olindi.\n"
        "HUKM QILDI:\nJK 169-modda."
    )
    assert check_precedent(parse(text)) == []


def test_amaliyotga_havola_yoqligi_info() -> None:
    text = "HUKM\nASOSLAR:\nSud dalillarni tekshirdi.\nHUKM QILDI:\nJK 169-modda."
    findings = check_precedent(parse(text))
    assert any(f.code == "PREC-002" and f.severity is Severity.INFO for f in findings)


# --------------------------------------------------------------------------- #
# Tahlil va hisobot
# --------------------------------------------------------------------------- #


def test_yettala_tekshiruv_bajariladi() -> None:
    result = analyze(parse(CLEAN_CRIMINAL))
    assert len(result.checks_run) == 7
    assert result.checks_failed == {}


def test_topilmalar_jiddiylik_boyicha_tartiblanadi() -> None:
    findings = analyze(parse(BARE)).findings
    weights = [f.weight for f in findings]
    assert weights == sorted(weights, reverse=True)


def test_hisobot_yigiladi() -> None:
    report = review(BARE)

    assert report.severity is Severity.CRITICAL
    assert report.findings
    assert report.corrections
    assert report.appeal_prospect > 0
    assert "yuridik xulosa hisoblanmaydi" in report.disclaimer


def test_toza_qarorda_istiqbol_past() -> None:
    report = review(CLEAN_CRIMINAL)
    assert report.appeal_prospect <= 0.10
    assert "past" in report.appeal_label or "topilmadi" in report.appeal_label


def test_kamchilikli_qarorda_istiqbol_yuqori() -> None:
    assert review(BARE).appeal_prospect > review(CLEAN_CRIMINAL).appeal_prospect


def test_info_topilma_tavsiyaga_tushmaydi() -> None:
    """`info` — kamchilik emas, shuning uchun tuzatish talab qilmaydi.

    Namuna sud amaliyotiga havolasiz: bu `PREC-002` (info) ni beradi,
    lekin tuzatish ro'yxatiga tushmasligi kerak.
    """
    text = CLEAN_CRIMINAL.replace("Oliy sud Plenumi qarori hisobga olindi.\n", "")
    report = review(text)

    info = [f for f in report.findings if f.severity is Severity.INFO]
    assert info, "namunada kamida bitta info topilma bo'lishi kerak"
    assert all(f.recommendation not in report.corrections for f in info)


def test_hisobotda_qonun_havolalari_yigiladi() -> None:
    report = review(CLEAN_CRIMINAL)
    articles = {c.article for c in report.citations}
    assert "169" in articles, "qarorning o'z havolasi"


def test_matnli_hisobot_asosiy_qismlarni_beradi() -> None:
    text = review(BARE).as_text()
    assert "SUD QARORI TAHLILI" in text
    assert "TOPILMALAR" in text
    assert "Apellyatsiya istiqboli" in text


def test_bosh_matn_yiqilmaydi() -> None:
    """Notanish hujjat tahlilni buzmasligi kerak."""
    report = review("")
    assert report.findings
    assert report.caveats


def test_takrorlanadigan_natija() -> None:
    """Deterministik: bir xil matn → bir xil topilmalar."""
    first = [f.code for f in review(CLEAN_CRIMINAL).findings]
    second = [f.code for f in review(CLEAN_CRIMINAL).findings]
    assert first == second
