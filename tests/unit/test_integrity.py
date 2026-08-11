"""Pora va nomutanosiblik aniqlash testlari."""

from __future__ import annotations

import pytest

from uzlegal.court.parser import CourtDecision, Party, Penalty, PenaltyKind
from uzlegal.integrity.detector import (
    CHECKS,
    check_evidence_handling,
    check_procedural,
    check_sentencing,
    check_structural,
    check_timing,
    detect,
)
from uzlegal.integrity.patterns import FlagCategory, RedFlag, Severity, risk_label
from uzlegal.integrity.profile import build_profile

# ── Fiksturalar ──────────────────────────────────────────────────────────────


def _criminal_decision(
    *,
    penalty_years: float | None = None,
    suspended: bool = False,
    circumstances: str | None = None,
    conclusion: str | None = None,
    reasoning: str | None = None,
    parties: list[Party] | None = None,
    evidence: list[str] | None = None,
    law_refs: bool = True,
    judge: str = "A. Karimov",
    decided_at: str | None = "2026-03-15",
    hearing_at: str | None = "2026-03-10",
) -> CourtDecision:
    from uzlegal.court.parser import DecisionKind
    from uzlegal.types import Citation

    penalty = None
    if penalty_years is not None:
        penalty = Penalty(
            kind=PenaltyKind.OZODLIKDAN_MAHRUM,
            amount=penalty_years,
            unit="yil",
            suspended=suspended,
            raw=f"ozodlikdan mahrum qilish {penalty_years:.0f} yil",
        )

    refs = []
    if law_refs:
        refs = [
            Citation(
                tag="JK",
                doc_id="jinoyat-kodeksi",
                doc_title="Jinoyat kodeksi",
                doc_type="kodeks",
                article="169",
            )
        ]

    circ = circumstances if circumstances is not None else "Oʻgʻirlik hodisasi sodir boʻlgan"
    reas = reasoning if reasoning is not None else "Dalillar tekshirildi va baho berildi"
    conc = conclusion if conclusion is not None else "Sudlanuvchi aybdor deb topildi"

    return CourtDecision(
        kind=DecisionKind.HUKM,
        case_number="1-123/2026",
        court="Toshkent shahar jinoyat sudi",
        judge=judge,
        decided_at=decided_at,
        hearing_at=hearing_at,
        parties=parties or [
            Party(role="prokuror", name="Davlat"),
            Party(role="sudlanuvchi", name="Aliyev I.R."),
            Party(role="himoyachi", name="Ergashev D.K."),
            Party(role="jabrlanuvchi", name="Salimov D.K."),
        ],
        evidence=evidence or ["Guvoh koʻrsatmasi", "Ekspert xulosasi"],
        law_references=refs,
        circumstances=circ,
        reasoning=reas,
        conclusion=conc,
        penalty=penalty,
        raw=f"HUKM\n{circ}\n{reas}\n{conc}",
    )


# ── Jazo nomutanosiblegi ─────────────────────────────────────────────────────


class TestSentencing:
    def test_yengil_jazo_flag_beradi(self) -> None:
        decision = _criminal_decision(
            penalty_years=0.3,
            circumstances="Oʻgʻirlik hodisasi sodir boʻlgan",
        )
        flags = check_sentencing(decision)
        assert any(f.code == "SENT-001" for f in flags)
        assert any(f.severity is Severity.HIGH for f in flags)

    def test_normal_jazo_flag_bermaydi(self) -> None:
        decision = _criminal_decision(
            penalty_years=3,
            circumstances="Oʻgʻirlik hodisasi",
        )
        flags = check_sentencing(decision)
        assert not any(f.code == "SENT-001" for f in flags)

    def test_ogir_jazo_flag_beradi(self) -> None:
        decision = _criminal_decision(
            penalty_years=10,
            circumstances="Oʻgʻirlik hodisasi",
        )
        flags = check_sentencing(decision)
        assert any(f.code == "SENT-002" for f in flags)

    def test_shartli_jazo_belgi_beradi(self) -> None:
        decision = _criminal_decision(penalty_years=3, suspended=True)
        flags = check_sentencing(decision)
        assert any(f.code == "SENT-003" for f in flags)

    def test_jazosiz_qaror_flag_bermaydi(self) -> None:
        decision = _criminal_decision()
        flags = check_sentencing(decision)
        assert flags == []

    def test_noma_lum_jinoyat_flag_bermaydi(self) -> None:
        decision = _criminal_decision(
            penalty_years=1,
            circumstances="Nomaʼlum hodisa",
        )
        flags = check_sentencing(decision)
        assert not any(f.code in ("SENT-001", "SENT-002") for f in flags)


# ── Protsessual ──────────────────────────────────────────────────────────────


class TestProcedural:
    def test_himoyachisiz_sud(self) -> None:
        decision = _criminal_decision(
            parties=[
                Party(role="prokuror", name="Davlat"),
                Party(role="sudlanuvchi", name="Aliyev"),
            ],
        )
        flags = check_procedural(decision)
        assert any(f.code == "PROC-002" for f in flags)
        assert any(f.severity is Severity.HIGH for f in flags)

    def test_himoyachili_sud_toza(self) -> None:
        decision = _criminal_decision()
        flags = check_procedural(decision)
        assert not any(f.code == "PROC-002" for f in flags)

    def test_kelishuv_shartli_jazo(self) -> None:
        decision = _criminal_decision(
            penalty_years=2,
            suspended=True,
        )
        decision.raw = "yarashuv asosida shartli hukm " + decision.raw
        flags = check_procedural(decision)
        assert any(f.code == "PROC-003" for f in flags)


# ── Dalillar ─────────────────────────────────────────────────────────────────


class TestEvidence:
    def test_yagona_dalil_flag(self) -> None:
        decision = _criminal_decision(
            evidence=["Yagona dalil"],
            conclusion="Sudlanuvchi aybdor deb topildi",
        )
        flags = check_evidence_handling(decision)
        assert any(f.code == "EVID-003" for f in flags)

    def test_koplab_dalil_toza(self) -> None:
        decision = _criminal_decision(
            evidence=["Dalil 1", "Dalil 2", "Dalil 3"],
        )
        flags = check_evidence_handling(decision)
        assert not any(f.code == "EVID-003" for f in flags)


# ── Vaqt ─────────────────────────────────────────────────────────────────────


class TestTiming:
    def test_juda_tez_qaror(self) -> None:
        decision = _criminal_decision(
            decided_at="2026-03-11",
            hearing_at="2026-03-10",
        )
        flags = check_timing(decision)
        assert any(f.code == "TIME-001" for f in flags)

    def test_normal_muddat_toza(self) -> None:
        decision = _criminal_decision(
            decided_at="2026-03-25",
            hearing_at="2026-03-10",
        )
        flags = check_timing(decision)
        assert not any(f.code in ("TIME-001", "TIME-002") for f in flags)

    def test_sanasiz_qaror_toza(self) -> None:
        decision = _criminal_decision(decided_at=None, hearing_at=None)
        flags = check_timing(decision)
        assert flags == []


# ── Tuzilma ──────────────────────────────────────────────────────────────────


class TestStructural:
    def test_asossiz_qaror(self) -> None:
        decision = _criminal_decision(reasoning="", penalty_years=3)
        flags = check_structural(decision)
        assert any(f.code == "STRUC-001" for f in flags)

    def test_qonunsiz_jazo(self) -> None:
        decision = _criminal_decision(penalty_years=3, law_refs=False)
        flags = check_structural(decision)
        assert any(f.code == "STRUC-002" for f in flags)

    def test_yengillashtiruvchi_shartli(self) -> None:
        decision = _criminal_decision(
            penalty_years=2,
            suspended=True,
            reasoning="Yengillashtiruvchi holatlar mavjud",
            circumstances="Birinchi marta jinoyat sodir etgan",
        )
        flags = check_structural(decision)
        assert any(f.code == "STRUC-004" for f in flags)


# ── Umumiy detect ────────────────────────────────────────────────────────────


class TestDetect:
    def test_toza_qaror_past_risk(self) -> None:
        decision = _criminal_decision()
        profile = detect(decision)
        assert profile.risk_score < 0.3
        assert profile.judge == "A. Karimov"
        assert profile.case_count == 1

    def test_shubhali_qaror_yuqori_risk(self) -> None:
        decision = _criminal_decision(
            penalty_years=0.3,
            suspended=True,
            reasoning="",
            evidence=["Yagona dalil"],
            circumstances="Oʻgʻirlik",
            conclusion="Sudlanuvchi aybdor deb topildi",
            parties=[
                Party(role="prokuror", name="Davlat"),
                Party(role="sudlanuvchi", name="Aliyev"),
            ],
        )
        decision.raw = "yarashuv " + decision.raw
        profile = detect(decision)
        assert profile.risk_score > 0.5
        assert len(profile.serious_flags) >= 2

    def test_barcha_tekshiruvlar_bor(self) -> None:
        assert len(CHECKS) == 5
        names = {name for name, _ in CHECKS}
        assert "sentencing" in names
        assert "procedural" in names
        assert "evidence" in names
        assert "timing" in names
        assert "structural" in names


# ── Profil ───────────────────────────────────────────────────────────────────


class TestProfile:
    def test_bitta_qaror_profil(self) -> None:
        decision = _criminal_decision(penalty_years=3)
        profile = build_profile("A. Karimov", [decision])
        assert profile.case_count == 1
        assert profile.sentencing.custodial == 1
        assert profile.sentencing.average_term_years == 3.0
        assert "yetarli emas" in profile.caveats[0]

    def test_koplab_qaror_profil(self) -> None:
        decisions = [
            _criminal_decision(
                penalty_years=2, suspended=True, judge="B. Raximov"
            ),
            _criminal_decision(
                penalty_years=3, suspended=True, judge="B. Raximov"
            ),
            _criminal_decision(
                penalty_years=1, suspended=True, judge="B. Raximov"
            ),
        ]
        profile = build_profile("B. Raximov", decisions)
        assert profile.case_count == 3
        assert profile.sentencing.suspended == 3
        assert profile.sentencing.suspended_ratio == 1.0
        assert any("Shartli jazo ulushi yuqori" in c for c in profile.caveats)

    def test_bosh_profil_yiqilmaydi(self) -> None:
        profile = build_profile("Test", [])
        assert profile.case_count == 0
        assert profile.risk_score == 0.0

    def test_disclaimer_mavjud(self) -> None:
        decision = _criminal_decision()
        profile = build_profile("A. Karimov", [decision])
        assert "vakolatli organlar" in profile.disclaimer


# ── Patterns ─────────────────────────────────────────────────────────────────


class TestPatterns:
    def test_risk_label_yuqori(self) -> None:
        assert "yuqori" in risk_label(0.8)

    def test_risk_label_past(self) -> None:
        assert "past" in risk_label(0.2)

    def test_risk_label_nol(self) -> None:
        assert "topilmadi" in risk_label(0.0)

    def test_red_flag_weight_chegarasi(self) -> None:
        flag = RedFlag(
            code="T-001",
            category=FlagCategory.DISPROPORTIONATE,
            severity=Severity.HIGH,
            title="Test",
            description="Test",
            weight=0.5,
        )
        assert flag.is_serious
        with pytest.raises(ValueError):
            RedFlag(
                code="T-002",
                category=FlagCategory.DISPROPORTIONATE,
                severity=Severity.LOW,
                title="Test",
                description="Test",
                weight=1.5,
            )
