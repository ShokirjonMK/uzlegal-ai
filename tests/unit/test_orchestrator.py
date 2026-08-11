"""Orkestratsiya testlari — gate, munozara, router.

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
    needs_round_two,
)
from uzlegal.orchestrator.gate import (
    ClaimStatus,
    DropReason,
    groundedness_gate,
    is_legal_claim,
    split_claims,
)
from uzlegal.orchestrator.router import ROLES_BY_MODE, Mode, route
from uzlegal.types import Argument, Citation, Position

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


def gate(answer: str, *tags: str):  # type: ignore[no-untyped-def]
    return groundedness_gate(answer, [citation(t) for t in tags or ("C1", "C2")])


def statuses(report):  # type: ignore[no-untyped-def]
    return [c.status for c in report.checks]


# --------------------------------------------------------------------------- #
# Da'volarga ajratish
# --------------------------------------------------------------------------- #


def test_satrlar_davolarga_ajraladi() -> None:
    segments = split_claims("XULOSA\nBirinchi daʼvo. Ikkinchi daʼvo.\n- Uchinchi daʼvo")
    claims = [s.text for s in segments if s.is_claim]
    assert "Uchinchi daʼvo" in claims
    assert any(s.is_heading for s in segments)


def test_huquqiy_davo_aniqlanadi() -> None:
    assert is_legal_claim("228-moddaga koʻra javobgarlik yuzaga keladi")
    assert is_legal_claim("Daʼvo muddati uch yil")
    assert not is_legal_claim("Bu vaziyatda ikki yoʻl bor")


# --------------------------------------------------------------------------- #
# 1-bosqich: iqtibossiz huquqiy da'vo o'chiriladi
# --------------------------------------------------------------------------- #


def test_iqtibossiz_huquqiy_davo_ochiriladi() -> None:
    report = gate("Mulkdor 228-moddaga koʻra talab qilishga haqli")

    assert ClaimStatus.DROPPED in statuses(report)
    assert report.checks[0].reason is DropReason.NO_CITATION
    assert report.refused, "boshqa huquqiy daʼvo qolmadi"


def test_iqtibossiz_umumiy_gap_ochirilmaydi() -> None:
    """Norma haqida daʼvo qilmaydigan gap iqtibossiz ham o'chirilmaydi.

    Aks holda gate javobning tushunarli qismini ham yeb qo'yardi.

    Diqqat: «huquqiy daʼvo» chegarasi ataylab **keng** olingan —
    `hujjat`, `muddat`, `mulk` kabi so'zlar ham daʼvoni huquqiy deb
    belgilaydi. Bu ko'proq iqtibos talab qiladi va ba'zi foydali
    gaplarni ham o'chiradi; tanlov tizimning «tasdiqlanmagan javobni
    ishonchli qilib ko'rsatmaslik» tamoyilidan kelib chiqadi.
    """
    report = gate("Bu vaziyatda ikki yoʻl bor va ikkalasini ham koʻrib chiqish mumkin")
    assert report.dropped == 0
    assert report.checks[0].status is ClaimStatus.KEPT


def test_huquqiy_davo_qolmasa_rad_etiladi() -> None:
    """Faqat umumiy gap qolgan javob «huquqiy javob» emas."""
    report = gate("Bu vaziyatda ikki yoʻl bor va ikkalasini ham koʻrib chiqish mumkin")
    assert report.refused


# --------------------------------------------------------------------------- #
# 2-bosqich: o'ylab topilgan iqtibos
# --------------------------------------------------------------------------- #


def test_mavjud_bolmagan_iqtibos_tutiladi() -> None:
    report = gate("Mulkdor talab qilib olishga haqli [C9]", "C1")
    assert "[C9]" not in report.answer
    assert report.dropped == 1
    assert report.checks[0].reason is DropReason.UNKNOWN_CITATION


def test_haqiqiy_iqtibos_bilan_davo_qoladi() -> None:
    claim = "Mulkdor mol-mulkini qonunsiz egalikdan talab qilib olishga haqli [C1]"
    report = gate(claim, "C1")

    assert report.kept == 1
    assert report.dropped == 0
    assert [c.tag for c in report.citations] == ["C1"]


def test_ishlatilmagan_iqtibos_royxatga_tushmaydi() -> None:
    """Javobda ishlatilmagan manba ro'yxatda turishi foydalanuvchini chalg'itadi."""
    claim = "Mulkdor mol-mulkini qonunsiz egalikdan talab qilib olishga haqli [C1]"
    report = gate(claim, "C1", "C2")
    assert [c.tag for c in report.citations] == ["C1"]


# --------------------------------------------------------------------------- #
# 3-bosqich: qo'llab-quvvatlash — o'chirmaydi, belgilaydi
# --------------------------------------------------------------------------- #


def test_qollab_quvvatlanmagan_davo_belgilanadi_ochirilmaydi() -> None:
    """Uchinchi bosqich xato qilishi mumkin — shuning uchun u o'chirmaydi."""
    report = gate("Bojxona tranzit deklaratsiyasi rasmiylashtiriladi [C1]", "C1")
    assert report.dropped == 0
    assert report.flagged == 1


def test_ozbek_morfologiyasi_hisobga_olinadi() -> None:
    """«muddat» va «muddati» bir xil so'z — daʼvo noto'g'ri belgilanmasligi kerak.

    Sudya normani **qayta ifodalaydi**, nusxa ko'chirmaydi: o'zbek
    agglyutinativ til va qo'shimchalar o'zgaradi.
    """
    norm = [citation("C1", article="150", excerpt="Umumiy daʼvo muddati uch yil qilib belgilanadi")]
    report = groundedness_gate("Daʼvo uch yillik muddat ichida qoʻzgʻatilishi kerak [C1]", norm)
    assert report.flagged == 0


# --------------------------------------------------------------------------- #
# Javobni qayta yig'ish
# --------------------------------------------------------------------------- #


def test_gate_yangi_matn_qoshmaydi() -> None:
    """Gate faqat olib tashlaydi — bu uning asosiy shartnomasi."""
    claim = "Mulkdor mol-mulkini qonunsiz egalikdan talab qilib olishga haqli [C1]"
    report = gate(claim, "C1")
    assert set(report.answer.split()) <= set(claim.split())


def test_hamma_ochirilsa_rad_etiladi() -> None:
    report = gate("Jarima 10 barobar oshiriladi\nSud xarajatlari yutqazganga yuklanadi")
    assert report.refused
    assert report.drop_reasons


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
    b = position("prosecutor", "Mijoz haqli", ["C1", "C2"], 0.7)
    assert citation_overlap(a, b) == 1.0
    assert disagreement(a, b) < 0.4


def test_turli_normalarga_tayanish_kelishmovchilik() -> None:
    a = position("advocate", "Mijoz toʻliq haqli", ["C1"], 0.9)
    b = position("prosecutor", "Mijoz javobgar boʻladi", ["C5"], 0.2)
    assert citation_overlap(a, b) == 0.0
    assert disagreement(a, b) > 0.4


def test_ikkinchi_raund_kelishmovchilikda_ochiladi() -> None:
    positions = {
        "advocate": position("advocate", "Mijoz toʻliq haqli", ["C1"], 0.9),
        "prosecutor": position("prosecutor", "Mijoz javobgar boʻladi", ["C5"], 0.2),
    }
    assert needs_round_two(positions)


def test_ikkinchi_raund_rozilikda_otkazib_yuboriladi() -> None:
    """Agentlar rozi bo'lsa munozara vaqtni behuda sarflaydi."""
    shared = ["C1", "C2"]
    positions = {
        "advocate": position("advocate", "Mijoz haqli deb hisoblayman", shared, 0.7),
        "prosecutor": position("prosecutor", "Mijoz haqli deb hisoblayman", shared, 0.7),
    }
    assert not needs_round_two(positions)


def test_bir_tomon_yoq_bolsa_ikkinchi_raund_yoq() -> None:
    """Prokuror sxema xatosi tufayli tushib qolgan — tortishadigan kim yo'q."""
    assert not needs_round_two({"advocate": position("advocate", "Mijoz haqli", ["C1"], 0.8)})


def test_iqtibossiz_pozitsiyalar_farq_hisoblanmaydi() -> None:
    a = position("advocate", "bir xil", [], 0.5)
    b = position("prosecutor", "bir xil", [], 0.5)
    assert citation_overlap(a, b) == 1.0
    assert conclusion_distance(a, b) == 0.0


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #


def test_faktik_savol_simple() -> None:
    assert route("MMT stavkasi qancha").mode is Mode.SIMPLE


def test_tahliliy_savol_standard() -> None:
    assert route("Bu shartnomani bekor qilish mumkinmi").mode is Mode.STANDARD


def test_nizoli_savol_complex() -> None:
    assert route("Kim haq — ish beruvchimi yoki xodimmi").mode is Mode.COMPLEX


def test_mijoz_bayoni_har_doim_complex() -> None:
    decision = route("Nima qilay", has_client_position=True)
    assert decision.mode is Mode.COMPLEX


def test_foydalanuvchi_tanlovi_ustun() -> None:
    decision = route("MMT stavkasi qancha", forced="complex")
    assert decision.mode is Mode.COMPLEX
    assert decision.forced


def test_qaror_sababi_boladi() -> None:
    """«Nima uchun bu savolga 45 soniya sarflandi?» — javob bo'lishi kerak."""
    assert route("Kim haq — ish beruvchimi yoki xodimmi").reason


def test_rejim_rollarni_belgilaydi() -> None:
    assert ROLES_BY_MODE[Mode.SIMPLE] == ["jurist"]
    assert len(ROLES_BY_MODE[Mode.COMPLEX]) == 5
