"""Uchidan-uchiga baholash dvigateli testlari.

Eng muhim xususiyat — **tashxis**: baholash nafaqat «yiqildi» deyishi,
balki nosozlik qaysi qatlamda ekanini ko'rsatishi kerak. Aks holda
hisobot keyingi qadamni aytmaydi.
"""

from __future__ import annotations

from typing import Any

from uzlegal.eval.suite import (
    CaseOutcome,
    SuiteCase,
    SuiteReport,
    check,
    check_citations,
    is_refusal,
    render_report,
    run_suite,
)
from uzlegal.types import Citation, ConsultResult, GateReport

# --------------------------------------------------------------------------- #
# Yordamchilar
# --------------------------------------------------------------------------- #


def result(
    answer: str = "", articles: list[str] | None = None, dropped: int = 0, kept: int = 1
) -> ConsultResult:
    return ConsultResult(
        question="savol",
        answer=answer,
        citations=[
            Citation(tag=f"C{i}", doc_id="fk", doc_title="Fuqarolik kodeksi", article=a)
            for i, a in enumerate(articles or [], start=1)
        ],
        gate=GateReport(kept=["k"] * kept, dropped=["d"] * dropped),
    )


def case(**kwargs: Any) -> SuiteCase:
    return SuiteCase(**{"id": "t1", "question": "savol", **kwargs})


# --------------------------------------------------------------------------- #
# Mazmun tekshiruvi
# --------------------------------------------------------------------------- #


def test_kutilgan_ibora_topilsa_otadi() -> None:
    outcome = check(case(expect_any=[["uch yil", "3 yil"]]), result("Daʼvo muddati uch yil"), 1.0)
    assert outcome.passed


def test_kutilgan_ibora_yoq_bolsa_yiqiladi() -> None:
    outcome = check(case(expect_any=[["uch yil"]]), result("Daʼvo muddati besh yil"), 1.0)
    assert not outcome.passed
    assert "kutilgan yo'q" in outcome.failures[0]


def test_taqiqlangan_ibora_yiqitadi() -> None:
    outcome = check(case(forbid=["kafolat beraman"]), result("Men kafolat beraman"), 1.0)
    assert not outcome.passed


def test_apostrof_shakli_ahamiyatsiz() -> None:
    """`boʻladi` va `bo'ladi` bir xil hisoblanishi kerak."""
    outcome = check(case(expect_any=[["boʻladi"]]), result("Shunday bo'ladi"), 1.0)
    assert outcome.passed


def test_bosh_javob_yiqiladi() -> None:
    assert not check(case(), result(""), 1.0).passed


def test_juda_uzun_javob_yiqiladi() -> None:
    outcome = check(case(max_words=5), result("bir ikki uch tort besh olti yetti"), 1.0)
    assert not outcome.passed_length


# --------------------------------------------------------------------------- #
# Iqtibos kutilmasi
# --------------------------------------------------------------------------- #


def test_kutilgan_modda_iqtibos_qilinsa_otadi() -> None:
    outcome = check(case(expect_articles=["228"]), result("javob", articles=["228", "229"]), 1.0)
    assert outcome.passed


def test_kutilgan_modda_iqtibos_qilinmasa_yiqiladi() -> None:
    outcome = check(case(expect_articles=["228"]), result("javob", articles=["999"]), 1.0)
    assert not outcome.passed_articles


# --------------------------------------------------------------------------- #
# Rad etish — tuzoq to'plamida to'g'ri javob
# --------------------------------------------------------------------------- #


def test_rad_etish_aniqlanadi() -> None:
    assert is_refusal("Berilgan savol boʻyicha ishonchli manba topilmadi")
    assert is_refusal("Maʼlumot yetarli emas")
    assert not is_refusal("Daʼvo muddati uch yil")


def test_rad_etish_kutilganda_javob_berish_yiqitadi() -> None:
    outcome = check(case(expect_refusal=True), result("9999-moddaga koʻra javobgarlik bor"), 1.0)
    assert not outcome.passed_refusal


def test_rad_etish_kutilganda_rad_etish_otadi() -> None:
    outcome = check(case(expect_refusal=True), result("Bunday modda topilmadi"), 1.0)
    assert outcome.passed


def test_rad_etilganda_ham_taqiqlangan_tekshiriladi() -> None:
    """«Topilmadi» deb aytib, keyin baribir toʻqib yozsa — yiqilishi kerak."""
    outcome = check(
        case(expect_refusal=True, forbid=["9999-moddaga koʻra"]),
        result("Manba topilmadi, lekin 9999-moddaga koʻra javobgarlik bor"),
        1.0,
    )
    assert not outcome.passed_forbid


# --------------------------------------------------------------------------- #
# Tashxis — nosozlik qaysi qatlamda
# --------------------------------------------------------------------------- #


def test_tashxis_retrieval() -> None:
    """Kutilgan modda umuman topilmadi — bu qidiruv muammosi."""
    outcome = check(case(expect_articles=["228"]), result("javob", articles=["999"]), 1.0)
    outcome.retrieved_articles = ["999"]
    assert outcome.diagnosis == "retrieval"


def test_tashxis_gate() -> None:
    """Modda topildi, lekin gate uni oʻchirdi — iqtibos intizomi muammosi."""
    outcome = check(
        case(expect_articles=["228"]), result("javob", articles=["999"], dropped=3), 1.0
    )
    outcome.retrieved_articles = ["228"]
    assert outcome.diagnosis == "gate"


def test_tashxis_model() -> None:
    """Modda topildi va iqtibos qilindi, lekin mazmun xato."""
    outcome = check(case(expect_any=[["uch yil"]]), result("besh yil", articles=["150"]), 1.0)
    assert outcome.diagnosis == "model"


def test_otgan_holatda_tashxis_yoq() -> None:
    assert check(case(), result("javob"), 1.0).diagnosis == "—"


# --------------------------------------------------------------------------- #
# To'plamni yurgizish
# --------------------------------------------------------------------------- #


def test_toplam_yurgiziladi() -> None:
    cases = [case(id="a", expect_any=[["ha"]]), case(id="b", expect_any=[["yoq"]])]
    report = run_suite(cases, lambda q, **kw: result("ha"), suite="sinov")

    assert report.pass_rate == 0.5
    assert [o.case.id for o in report.failures] == ["b"]


def test_bitta_holat_yiqilsa_toplam_toxtamaydi() -> None:
    """Xato javob sifatida yoziladi va baholash davom etadi."""
    calls: list[str] = []

    def flaky(question: str, **kwargs: Any) -> ConsultResult:
        calls.append(question)
        if len(calls) == 1:
            raise RuntimeError("model yoʻq")
        return result("javob")

    report = run_suite([case(id="a"), case(id="b")], flaky)
    assert len(report.outcomes) == 2
    assert not report.outcomes[0].passed
    assert report.outcomes[1].passed


def test_rejim_holatdan_olinadi() -> None:
    seen: list[str] = []

    def spy(question: str, **kwargs: Any) -> ConsultResult:
        seen.append(kwargs["mode"])
        return result("javob")

    run_suite([case(id="a", mode="complex"), case(id="b")], spy, default_mode="simple")
    assert seen == ["complex", "simple"]


def test_gate_ochirish_ulushi() -> None:
    report = run_suite([case()], lambda q, **kw: result("javob", dropped=1, kept=3))
    assert report.gate_drop_rate == 0.25


# --------------------------------------------------------------------------- #
# Iqtibos yaxlitligi
# --------------------------------------------------------------------------- #


class FakeIndex:
    def __init__(self, known: set[tuple[str, str]]) -> None:
        self.known = known

    def chunks_for_article(self, doc_id: str, article: str, *, limit: int = 4) -> list[object]:
        return [object()] if (doc_id, article) in self.known else []


def test_mavjud_bolmagan_modda_iqtibosi_tutiladi() -> None:
    issues = check_citations(result("javob [C1]", articles=["999"]), FakeIndex(set()), "t1")
    assert any(i.kind == "mavjud emas" for i in issues)


def test_haqiqiy_iqtibos_muammo_bermaydi() -> None:
    issues = check_citations(
        result("javob [C1]", articles=["228"]), FakeIndex({("fk", "228")}), "t1"
    )
    assert issues == []


def test_javobdagi_boglanmagan_belgi_tutiladi() -> None:
    """Model `[C7]` yozgan, lekin iqtiboslar roʻyxatida u yoʻq."""
    issues = check_citations(
        result("javob [C1] va [C7]", articles=["228"]), FakeIndex({("fk", "228")}), "t1"
    )
    assert any(i.kind == "bog'lanmagan" and "C7" in i.detail for i in issues)


def test_bekor_qilingan_norma_iqtibosi_tutiladi() -> None:
    res = result("javob [C1]", articles=["228"])
    res.citations[0].status = "repealed"
    issues = check_citations(res, FakeIndex({("fk", "228")}), "t1")
    assert any(i.kind == "bekor" for i in issues)


# --------------------------------------------------------------------------- #
# Hisobot
# --------------------------------------------------------------------------- #


def test_hisobot_tashxisni_korsatadi() -> None:
    outcome = check(case(id="x", expect_any=[["uch yil"]]), result("besh yil"), 1.0)
    text = render_report(SuiteReport(suite="sinov", outcomes=[outcome]), target=0.75)

    assert "sinov" in text
    assert "maqsad 75%" in text
    assert "`x`" in text
    assert "model" in text


def test_bosh_hisobot_yiqilmaydi() -> None:
    text = render_report(SuiteReport(suite="bosh", outcomes=[]))
    assert "bosh" in text


def test_kategoriya_boyicha_taqsimot() -> None:
    outcomes = [
        CaseOutcome(case=case(id="a", category="mulk"), answer="x", latency_s=1.0),
        CaseOutcome(case=case(id="b", category="mehnat"), answer="x", latency_s=1.0),
    ]
    outcomes[1].passed_expect = False
    report = SuiteReport(suite="s", outcomes=outcomes)
    assert report.by_category() == {"mehnat": 0.0, "mulk": 1.0}
