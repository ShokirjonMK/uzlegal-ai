"""Orkestratsiya testlari — gate, munozara, router, zanjir.

Gate testlari eng muhimi: u tizimning **yolg'on aytmaslik** kafolati.
Shuning uchun ular ikki tomonlama yozilgan — nima o'chirilishi kerakligi
ham, nima o'chirilmasligi kerakligi ham tekshiriladi. Ikkinchisi
birinchisidan muhimroq: hamma narsani o'chiradigan gate «xavfsiz», lekin
foydasiz.
"""

from __future__ import annotations

from uzlegal.orchestrator.debate import (
    citation_overlap,
    conclusion_distance,
    disagreement,
    needs_second_round,
)
from uzlegal.orchestrator.gate import (
    GroundednessGate,
    is_legal_claim,
    split_claims,
    support_score,
)
from uzlegal.orchestrator.router import roles_for, route
from uzlegal.types import Argument, Citation, ConsultMode, Position

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def citation(tag: str, article: str = "228", excerpt: str = "") -> Citation:
    return Citation(
        tag=tag,
        doc_id="fk",
        doc_title="Fuqarolik kodeksi",
        article=article,
        excerpt=excerpt or "Mulkdor oʻz mol-mulkini qonunsiz egalikdan talab qilib olishga haqli",
    )


def gate(*tags: str) -> GroundednessGate:
    return GroundednessGate([citation(t) for t in tags or ("C1", "C2")])


# --------------------------------------------------------------------------- #
# Da'volarga ajratish
# --------------------------------------------------------------------------- #


def test_satrlar_davolarga_ajraladi() -> None:
    claims = split_claims("XULOSA\nBirinchi daʼvo. Ikkinchi daʼvo.\n- Uchinchi daʼvo")
    assert "XULOSA" in claims
    assert "Uchinchi daʼvo" in claims
    assert len(claims) == 4


def test_sarlavha_davo_emas() -> None:
    from uzlegal.orchestrator.gate import is_heading

    assert is_heading("ASOSLAR")
    assert not is_heading("Mulkdor talab qilishga haqli")


def test_royxat_belgisi_olib_tashlanadi() -> None:
    assert split_claims("- Mulkni talab qilish mumkin") == ["Mulkni talab qilish mumkin"]


# --------------------------------------------------------------------------- #
# 1-bosqich: iqtibossiz huquqiy da'vo o'chiriladi
# --------------------------------------------------------------------------- #


def test_iqtibossiz_huquqiy_davo_ochiriladi() -> None:
    answer = "Mulkdor 228-moddaga koʻra talab qilishga haqli"
    cleaned, report = gate().check(answer)

    assert report.dropped == [answer]
    assert cleaned == ""
    assert report.is_empty


def test_iqtibossiz_umumiy_gap_qoladi() -> None:
    """Norma haqida daʼvo qilmaydigan gap iqtibossiz ham qolishi kerak.

    Aks holda gate javobning tushunarli qismini ham yeb qo'yadi.
    """
    answer = "Quyidagi hujjatlarni tayyorlab qoʻyish tavsiya etiladi"
    cleaned, report = gate().check(answer)

    assert report.dropped == []
    assert cleaned == answer


def test_huquqiy_davo_aniqlanadi() -> None:
    assert is_legal_claim("228-moddaga koʻra javobgarlik yuzaga keladi")
    assert is_legal_claim("Daʼvo muddati uch yil")
    assert not is_legal_claim("Bu vaziyatda ikki yoʻl bor")


# --------------------------------------------------------------------------- #
# 2-bosqich: o'ylab topilgan iqtibos
# --------------------------------------------------------------------------- #


def test_mavjud_bolmagan_iqtibos_bilan_davo_ochiriladi() -> None:
    cleaned, report = gate("C1").check("Mulkdor talab qilishga haqli [C9]")
    assert len(report.dropped) == 1
    assert "[C9]" not in cleaned


def test_qisman_notogri_iqtibosda_yolgon_belgi_olib_tashlanadi() -> None:
    """Bitta belgi to'g'ri bo'lsa da'vo qoladi, yolg'oni o'chadi.

    Butun da'voni o'chirish bu yerda ortiqcha: uning asosi bor.
    """
    cleaned, report = gate("C1").check("Mulkdor talab qilib olishga haqli [C1] [C9]")
    assert report.dropped == []
    assert "[C1]" in cleaned and "[C9]" not in cleaned


def test_haqiqiy_iqtibos_bilan_davo_qoladi() -> None:
    claim = "Mulkdor mol-mulkini qonunsiz egalikdan talab qilib olishga haqli [C1]"
    _, report = gate("C1").check(claim)

    assert report.kept == [claim]
    assert report.dropped == []
    assert [c.tag for c in report.citations] == ["C1"]


# --------------------------------------------------------------------------- #
# 3-bosqich: qo'llab-quvvatlash — o'chirmaydi, belgilaydi
# --------------------------------------------------------------------------- #


def test_qollab_quvvatlanmagan_davo_belgilanadi_ochirilmaydi() -> None:
    """Uchinchi bosqich xato qilishi mumkin — shuning uchun u o'chirmaydi."""
    claim = "Bojxona deklaratsiyasi tranzit tartibida rasmiylashtiriladi [C1]"
    cleaned, report = gate("C1").check(claim)

    assert report.dropped == []
    assert len(report.flagged) == 1
    assert cleaned.startswith("⚠")


def test_qoplama_hisoblanadi() -> None:
    source = [citation("C1", excerpt="Mulkdor mol-mulkini talab qilib olishga haqli")]
    assert support_score("Mulkdor mol-mulkini talab qilib olishi mumkin", source) > 0.5
    assert support_score("Bojxona tranzit deklaratsiyasi rasmiylashtiriladi", source) < 0.25


def test_iqtibos_matni_yoq_bolsa_belgilanmaydi() -> None:
    """Manba matni saqlanmagan bo'lsa bu bosqich o'tkazib yuboriladi."""
    empty = Citation(tag="C1", doc_id="fk", article="228", excerpt=None)
    _, report = GroundednessGate([empty]).check("Har qanday daʼvo mumkin [C1]")
    assert report.flagged == []


# --------------------------------------------------------------------------- #
# Javobni qayta yig'ish
# --------------------------------------------------------------------------- #


def test_bosh_qolgan_sarlavha_tashlanadi() -> None:
    """Sarlavha ostidagi barcha daʼvo o'chirilsa, sarlavha ham ketadi."""
    answer = "XULOSA\nMulkdor 228-moddaga koʻra haqli\n\nOGOHLANTIRISHLAR\nMaʼlumot yetarli emas"
    cleaned, _ = gate().check(answer)
    assert "XULOSA" not in cleaned


def test_gate_yangi_matn_qoshmaydi() -> None:
    """Gate faqat olib tashlaydi — bu uning asosiy shartnomasi."""
    claim = "Mulkdor mol-mulkini qonunsiz egalikdan talab qilib olishga haqli [C1]"
    cleaned, _ = gate("C1").check(claim)
    assert set(cleaned.split()) <= set(claim.split())


def test_ochirilgan_davoning_manbasi_royxatdan_chiqadi() -> None:
    answer = (
        "Mulkdor mol-mulkini qonunsiz egalikdan talab qilib olishga haqli [C1]\n"
        "Boshqa moddaga koʻra javobgarlik yuzaga keladi"
    )
    _, report = gate("C1", "C2").check(answer)
    assert [c.tag for c in report.citations] == ["C1"], "C2 javobda ishlatilmadi"


def test_gate_hisoboti_ulushni_beradi() -> None:
    answer = "Birinchi qonun talabi bajariladi\nMulkdor talab qilib olishga haqli [C1]"
    _, report = gate("C1").check(answer)
    assert report.total == 2
    assert 0.0 < report.drop_rate <= 1.0


# --------------------------------------------------------------------------- #
# Munozara — kelishmovchilik balli
# --------------------------------------------------------------------------- #


def position(role: str, stance: str, tags: list[str], confidence: float) -> Position:
    return Position(
        role=role,
        stance=stance,
        arguments=[Argument(claim="daʼvo", citations=tags)],
        weaknesses=["zaif joy"],
        confidence=confidence,
    )


def test_bir_xil_normalarga_tayangan_pozitsiyalar_yaqin() -> None:
    a = position("advocate", "Mijoz haqli", ["C1", "C2"], 0.7)
    b = position("prosecutor", "Mijoz haqli emas", ["C1", "C2"], 0.7)
    assert citation_overlap(a, b) == 1.0
    assert disagreement(a, b) < 0.4


def test_turli_normalarga_tayanish_kelishmovchilik() -> None:
    a = position("advocate", "Mijoz haqli", ["C1"], 0.9)
    b = position("prosecutor", "Mijoz javobgar", ["C5"], 0.3)
    assert citation_overlap(a, b) == 0.0
    assert disagreement(a, b) > 0.4


def test_ikkinchi_raund_kelishmovchilikda_ochiladi() -> None:
    positions = {
        "advocate": position("advocate", "Mijoz toʻliq haqli", ["C1"], 0.9),
        "prosecutor": position("prosecutor", "Mijoz javobgar boʻladi", ["C5"], 0.2),
    }
    needed, score = needs_second_round(positions)
    assert needed and score > 0.4


def test_ikkinchi_raund_rozilikda_otkazib_yuboriladi() -> None:
    """Agentlar rozi bo'lsa munozara vaqtni behuda sarflaydi."""
    shared = ["C1", "C2"]
    positions = {
        "advocate": position("advocate", "Mijoz haqli deb hisoblayman", shared, 0.7),
        "prosecutor": position("prosecutor", "Mijoz haqli deb hisoblayman", shared, 0.7),
    }
    needed, _ = needs_second_round(positions)
    assert not needed


def test_bir_tomon_yoq_bolsa_ikkinchi_raund_yoq() -> None:
    positions = {"advocate": position("advocate", "Mijoz haqli", ["C1"], 0.8)}
    assert needs_second_round(positions) == (False, 0.0)


def test_iqtibossiz_pozitsiyalar_farq_hisoblanmaydi() -> None:
    a = position("advocate", "bir xil", [], 0.5)
    b = position("prosecutor", "bir xil", [], 0.5)
    assert citation_overlap(a, b) == 1.0
    assert conclusion_distance(a, b) == 0.0


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #


def test_faktik_savol_simple() -> None:
    assert route("MMT stavkasi qancha") is ConsultMode.SIMPLE


def test_tahliliy_savol_standard() -> None:
    assert route("Bu shartnomani bekor qilish mumkinmi") is ConsultMode.STANDARD


def test_nizoli_savol_complex() -> None:
    assert route("Kim haq — ish beruvchimi yoki xodimmi") is ConsultMode.COMPLEX


def test_mijoz_bayoni_har_doim_complex() -> None:
    """Mijoz o'z holatini aytgan bo'lsa savol deyarli har doim nizoli."""
    assert route("Nima qilay", client_position="Meni ishdan boʻshatishdi") is ConsultMode.COMPLEX


def test_noaniq_savol_ortacha_yol() -> None:
    assert route("Fuqarolik kodeksi haqida") is ConsultMode.STANDARD


def test_rejim_rollarni_belgilaydi() -> None:
    assert roles_for(ConsultMode.SIMPLE) == ["jurist"]
    assert len(roles_for(ConsultMode.COMPLEX)) == 5
