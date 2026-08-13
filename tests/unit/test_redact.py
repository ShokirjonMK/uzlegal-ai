"""PII anonimizatsiya testlari — docs/03 § 3.7.

Matnlar sud qarori uslubida yozilgan, lekin **haqiqiy shaxs ma'lumoti emas**:
ismlar, raqamlar va manzillar o'ylab topilgan. Korpusda hali sud qarorlari
yo'q, shuning uchun bu yerda fixture ishlatiladi.

Testlarning yarmi «o'chirilsin» ni, yarmi **«qolsin»** ni tekshiradi —
ortiqcha o'chirish ham xato: sudya ismi yoki yuridik shaxs nomi yo'qolsa
qaror yuridik ma'nosini yo'qotadi.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from uzlegal.ingest.redact import Redactor, detect_pii, redact_text

QAROR = """Toshkent shahar Chilonzor tumani sudi. Sudya Rahimov Bahodir Anvarovich.
Daʼvogar Karimov Alisher Baxtiyorovich, passport AA 1234567, JSHSHIR 30101856120014,
tel: +998 90 123 45 67, elektron pochta alisher.k@mail.uz, Toshkent shahri,
Amir Temur koʻchasi, 12-uy, 15-xonadon manzilida yashovchi, 1985-yil 12-mayda tugʻilgan.
Javobgar «Oltin Vodiy» MChJ. Karimov A.B. ning hisob raqami 20208000900123456789."""


@pytest.fixture(scope="module")
def natija():  # type: ignore[no-untyped-def]
    return Redactor().redact(QAROR)


# --------------------------------------------------------------------------- #
# O'chiriladi
# --------------------------------------------------------------------------- #


def test_fish_almashtiriladi(natija) -> None:  # type: ignore[no-untyped-def]
    assert "Karimov Alisher Baxtiyorovich" not in natija.text
    assert "[SHAXS-1]" in natija.text


def test_izchil_almashtirish(natija) -> None:  # type: ignore[no-untyped-def]
    """«Karimov Alisher Baxtiyorovich» va «Karimov A.B.» — bitta shaxs."""
    assert natija.text.count("[SHAXS-1]") == 2
    assert len(natija.persons) == 1


def test_turli_shaxslar_turli_raqam() -> None:
    text = "Daʼvogar Karimov Alisher Baxtiyorovich, javobgar Yusupova Nodira Anvarovna."
    result = redact_text(text)
    assert "[SHAXS-1]" in result.text and "[SHAXS-2]" in result.text


def test_hujjat_raqamlari(natija) -> None:  # type: ignore[no-untyped-def]
    assert "AA 1234567" not in natija.text
    assert "30101856120014" not in natija.text
    assert natija.text.count("[HUJJAT]") == 2


def test_aloqa_malumotlari(natija) -> None:  # type: ignore[no-untyped-def]
    assert "+998 90 123 45 67" not in natija.text
    assert "alisher.k@mail.uz" not in natija.text
    assert natija.text.count("[ALOQA]") == 2


def test_bank_hisobi(natija) -> None:  # type: ignore[no-untyped-def]
    assert "20208000900123456789" not in natija.text
    assert "[HISOB]" in natija.text


def test_tugilgan_sana(natija) -> None:  # type: ignore[no-untyped-def]
    assert "1985-yil 12-may" not in natija.text
    assert "[SANA]" in natija.text


def test_manzil_ochiriladi_shahar_qoladi(natija) -> None:  # type: ignore[no-untyped-def]
    """Ko'cha va uy ketadi, shahar qoladi — yurisdiksiya huquqiy ahamiyatga ega."""
    assert "Amir Temur koʻchasi" not in natija.text
    assert "[MANZIL]" in natija.text
    assert "Toshkent shahri" in natija.text


# --------------------------------------------------------------------------- #
# Qoladi
# --------------------------------------------------------------------------- #


def test_sudya_ismi_qoladi(natija) -> None:  # type: ignore[no-untyped-def]
    assert "Rahimov Bahodir Anvarovich" in natija.text


@pytest.mark.parametrize("rol", ["Sudya", "Prokuror", "Tergovchi", "Raislik qiluvchi"])
def test_rasmiy_rol_ismi_qoladi(rol: str) -> None:
    text = f"{rol} Ergashev Sanjar Alisherovich ishtirok etdi."
    assert "Ergashev Sanjar Alisherovich" in redact_text(text).text


def test_yuridik_shaxs_qoladi(natija) -> None:  # type: ignore[no-untyped-def]
    assert "«Oltin Vodiy» MChJ" in natija.text


def test_davlat_organi_qoladi() -> None:
    """«Oʻzbekiston Respublikasi» ikki so'zli ism shabloniga mos keladi."""
    text = "Chet el fuqarosi Oʻzbekiston Respublikasi Vazirlar Mahkamasiga murojaat qildi."
    assert "Oʻzbekiston Respublikasi" in redact_text(text).text


def test_oddiy_yuridik_matn_ozgarmaydi() -> None:
    text = (
        "Mulkdor oʻzgalarning qonunsiz egaligidagi mulkni talab qilib olishga haqli. "
        "Ushbu Kodeksning 45-moddasida nazarda tutilgan hollarda 30 kunlik muddat qoʻllaniladi."
    )
    assert redact_text(text).text == text


# --------------------------------------------------------------------------- #
# Ishonch va karantin
# --------------------------------------------------------------------------- #


def test_past_ishonchli_topilma_karantin() -> None:
    """Familiya belgisi YOʻQ ikki soʻz — tartib noaniq, qoʻlda koʻrilsin.

    Ilgari bu yerda «Nodira Yusupova» turardi va u past ishonch bilan
    topilardi. Endi `-ova` qoʻshimchasi familiyani ANIQ koʻrsatadi, yaʼni
    tartibda noaniqlik qolmaydi va karantin kerak emas — bu yaxshilanish.

    Karantin hamon kerak boʻlgan holat: ikkala soʻz ham familiya belgisiz.
    «Nodira Anvar» — qaysi biri ism, qaysi biri familiya, bilib boʻlmaydi.
    """
    result = redact_text("Guvoh Nodira Anvar koʻrsatma berdi.")
    assert "[SHAXS-1]" in result.text
    assert result.quarantine
    assert result.confidence < 0.75


def test_familiya_qoshimchasi_noaniqlikni_yoqotadi() -> None:
    """`-ova` familiyani aniq koʻrsatadi — karantin shart emas."""
    result = redact_text("Guvoh Nodira Yusupova koʻrsatma berdi.")
    assert "[SHAXS-1]" in result.text
    assert not result.quarantine
    assert result.confidence >= 0.75


def test_toza_matn_karantinsiz(natija) -> None:  # type: ignore[no-untyped-def]
    assert not natija.quarantine, natija.reasons


def test_qolib_ketgan_uzun_raqam_karantin() -> None:
    result = redact_text("Ish raqami 123456789012 boʻyicha qaror.")
    assert result.quarantine
    assert any("uzun raqam" in r for r in result.reasons)


def test_detect_matnni_ozgartirmaydi() -> None:
    found = detect_pii(QAROR)
    assert found
    assert all(QAROR[f.start : f.end] == f.original for f in found)


def test_topilmalar_kesishmaydi() -> None:
    found = detect_pii(QAROR)
    for earlier, later in pairwise(found):
        assert earlier.end <= later.start


def test_redactor_qayta_ishlatilganda_raqamlar_saqlanadi() -> None:
    """Bir ish bo'yicha bir necha xatboshi — raqamlash uzilmasin."""
    redactor = Redactor()
    first = redactor.redact("Daʼvogar Karimov Alisher Baxtiyorovich ariza berdi.")
    second = redactor.redact("Karimov A.B. sud majlisiga keldi.")
    assert "[SHAXS-1]" in first.text
    assert "[SHAXS-1]" in second.text

    redactor.reset()
    third = redactor.redact("Javobgar Yusupov Sardor Anvarovich.")
    assert "[SHAXS-1]" in third.text
