"""Senior yurist kengashi — docs/26.

Eng muhim test faylning eng oxirida: **kengash `verified` ga tegmaydi**.
Qolgan hamma narsa tezlik uchun, o'sha bitta test esa kafolat uchun.
"""

from __future__ import annotations

import pytest

from uzlegal.panel.review import (
    MIN_CONFIDENCE,
    PanelReport,
    SeniorVerdict,
    decide,
)
from uzlegal.panel.seniors import BY_KEY, PANEL_SIZE, SENIORS, select
from uzlegal.training.dataset import ContextRef, TrainingSample


def _verdict(
    senior: str,
    verdict: str = "to'g'ri",
    confidence: float = 0.9,
    issues: list[str] | None = None,
) -> SeniorVerdict:
    return SeniorVerdict(
        senior=senior,
        verdict=verdict,  # type: ignore[arg-type]
        confidence=confidence,
        issues=issues or ([] if verdict == "to'g'ri" else ["sabab"]),
    )


def _sample(**kwargs: object) -> TrainingSample:
    base: dict[str, object] = {
        "id": "adv-001",
        "role": "advocate",
        "context": [ContextRef(tag="C1", chunk_id="d-1:228", text="Mulkdor talab qilishga haqli.")],
        "question": "Mulkni qaytarib olish mumkinmi?",
        "answer": "Vindikatsiya da'vosi qo'llaniladi [C1]. ZAIF tomoni — muddat.",
    }
    base.update(kwargs)
    return TrainingSample(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Kengash tarkibi
# --------------------------------------------------------------------------- #


def test_onta_senior_bor() -> None:
    assert len(SENIORS) == 10
    assert len({s.key for s in SENIORS}) == 10


def test_har_seniorda_linza_bor() -> None:
    """Linza — nuqtai nazar xilma-xilligining manbai. Bo'sh bo'lmasin."""
    for senior in SENIORS:
        assert senior.lens.strip(), senior.key
        assert senior.keywords, senior.key


# --------------------------------------------------------------------------- #
# Marshrutlash
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "kutilgan"),
    [
        ("Mehnat shartnomasini ish beruvchi bekor qildi, xodim nima qiladi", "mehnat"),
        ("Jinoyat uchun jazo qanday belgilanadi", "jinoyat"),
        ("Nikohdan ajrashishda aliment qanday hisoblanadi", "oila"),
        ("Soliq bazasi va qqs stavkasi", "soliq"),
        ("Yer uchastkasiga qurilish ruxsati", "yer"),
    ],
)
def test_marshrutlash_sohaga_tushadi(text: str, kutilgan: str) -> None:
    keys = [s.key for s in select(text)]
    assert kutilgan in keys


def test_kengash_hajmi_saqlanadi() -> None:
    chosen = select("Mehnat shartnomasi bo'yicha nizo")
    assert len(chosen) == PANEL_SIZE
    assert len({s.key for s in chosen}) == PANEL_SIZE, "bir senior ikki marta chaqirilmasin"


def test_oxirgi_senior_boshqa_sohadan() -> None:
    """«Tashqi ko'z» — mavzuga eng uzoq senior.

    Ikkita mutaxassis bir xil narsani o'tkazib yuborishi mumkin; uchinchisi
    ataylab boshqa linza bilan qaraydi.
    """
    text = "Mehnat shartnomasi va xodimning ish haqi"
    chosen = select(text)
    outsider = chosen[-1]
    assert outsider.key not in ("mehnat",)


def test_notanish_matnda_zaxira_ishlaydi() -> None:
    """Hech bir kalit so'z topilmasa ham kengash bo'sh qaytmaydi."""
    chosen = select("qwerty zxcvb")
    assert chosen
    assert BY_KEY["konstitutsiyaviy"] in chosen


def test_nol_hajm_bosh_royxat() -> None:
    assert select("mehnat", size=0) == []


# --------------------------------------------------------------------------- #
# Kelishuv qoidalari
# --------------------------------------------------------------------------- #


def test_bir_ovozdan_maqullash() -> None:
    report = decide([_verdict("mehnat"), _verdict("fuqarolik"), _verdict("soliq")])
    assert report.outcome == "kengash-ma'qulladi"
    assert report.agreement == 1.0


def test_kopchilik_rad_etsa_tashlanadi() -> None:
    """Rad etishda xato qilish arzon — namuna qaytadan generatsiya qilinadi."""
    report = decide(
        [
            _verdict("mehnat", "noto'g'ri"),
            _verdict("fuqarolik", "noto'g'ri"),
            _verdict("soliq"),
        ]
    )
    assert report.outcome == "rad"
    assert report.reason == "sabab"


def test_yarmi_rad_etsa_ham_tashlanadi() -> None:
    report = decide([_verdict("mehnat", "noto'g'ri"), _verdict("fuqarolik")])
    assert report.outcome == "rad"


def test_bitta_shubha_odamga_yuboradi() -> None:
    """Ma'qullash bir ovozdan bo'ladi — aks holda odam ko'radi."""
    report = decide(
        [_verdict("mehnat"), _verdict("fuqarolik", "tuzatish-kerak"), _verdict("soliq")]
    )
    assert report.outcome == "noaniq"
    assert report.needs_human


def test_past_ishonchli_kelishuv_kelishuv_emas() -> None:
    low = MIN_CONFIDENCE - 0.1
    report = decide([_verdict("mehnat", confidence=low), _verdict("fuqarolik", confidence=0.95)])
    assert report.outcome == "noaniq"
    assert "ishonch past" in report.reason


def test_bosh_xulosa_odamga_yuboradi() -> None:
    """Model javob bermasa namuna jimgina o'tib ketmasin."""
    report = decide([])
    assert report.outcome == "noaniq"
    assert report.needs_human


def test_namunaviy_tekshiruv_maqullanganni_ham_odamga_yuboradi() -> None:
    report = decide([_verdict("mehnat"), _verdict("fuqarolik")], spot_check=True)
    assert report.outcome == "kengash-ma'qulladi"
    assert report.needs_human, "namunaviy tekshiruv nol bo'lmasligi kerak"


def test_issues_takrorlanmaydi() -> None:
    report = decide(
        [
            _verdict("mehnat", "noto'g'ri", issues=["muddat yo'q"]),
            _verdict("fuqarolik", "noto'g'ri", issues=["muddat yo'q", "iqtibos xato"]),
        ]
    )
    assert report.issues == ["muddat yo'q", "iqtibos xato"]


# --------------------------------------------------------------------------- #
# Chegara — eng muhim test
# --------------------------------------------------------------------------- #


def test_kengash_verified_ga_tegmaydi() -> None:
    """`docs/05 § 3` kafolati: imzo odamniki.

    Kengash ma'qullagan namuna **treningga tushmaydi**. Bu test buzilsa,
    mashina tekshiruvi odam tekshiruvi o'rniga o'tgan bo'ladi va
    loyihaning markaziy xavfsizlik qoidasi yo'qoladi.
    """
    report = PanelReport(outcome="kengash-ma'qulladi", agreement=1.0)
    sample = _sample(panel=report.model_dump(mode="json"))

    assert sample.verified is False
    assert sample.is_trainable is False
    assert sample.panel_outcome == "kengash-ma'qulladi"


def test_kengash_rad_etgani_yurist_navbatiga_tushmaydi() -> None:
    """Aynan shu odam vaqtini tejaydi."""
    report = PanelReport(outcome="rad", reason="manbada yo'q da'vo")
    sample = _sample(panel=report.model_dump(mode="json"), rejection_reason="kengash: ...")
    assert sample.awaits_human is False


def test_noaniq_yurist_navbatiga_tushadi() -> None:
    report = PanelReport(outcome="noaniq", reason="seniorlar kelisha olmadi")
    sample = _sample(panel=report.model_dump(mode="json"))
    assert sample.awaits_human is True


def test_kengashdan_otmagan_ham_navbatda() -> None:
    """Kengash ishlamagan namuna jimgina yo'qolmasin."""
    assert _sample().awaits_human is True


def test_tekshirilgan_namuna_navbatdan_chiqadi() -> None:
    sample = _sample(verified=True, verified_by="expert-01")
    assert sample.awaits_human is False
    assert sample.is_trainable is True
