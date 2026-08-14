"""`uzlegal nazorat` CLI testlari — docs/22 § 5 (C1..C6).

Bu buyruqlar **yangi mantiq qurmaydi**: ular `integrity/` moduliga
qadoqdir. Shuning uchun testlar aniqlash sifatini emas, qadoqning
o'zini qo'riqlaydi: fayl o'qish, chiqish kodlari, `--json` ning
`model_dump()` ga mosligi va o'chirib bo'lmaydigan yuridik izoh.

Eng muhimi C6: modul model chaqirmaydi va shuning uchun bir xil fayl
har doim bir xil hisobot beradi. Bu xususiyat yo'qolsa, hisobotni
nazorat organiga ko'rsatib bo'lmaydi.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# --------------------------------------------------------------------------- #
# Namuna qarorlar
# --------------------------------------------------------------------------- #

SHUBHALI = """OʻZBEKISTON RESPUBLIKASI NOMIDAN
HUKM

Ish № 1-2345/2024

Toshkent shahar Chilonzor tumanlararo sudi
Sudya: Karimov A.B.
2024-yil 15-mart kuni sud majlisida ochiq koʻrib chiqdi.

Sudlanuvchi: Toshmatov Alisher

ANIQLADI:

Toshmatov A.B. 2023-yil 10-dekabr kuni mol-mulkni oʻgʻirlagan.
Guvoh koʻrsatuvi bilan tasdiqlangan.

HUKM QILDI:

Toshmatovni Jinoyat kodeksining 169-moddasi bilan aybdor deb topib,
1 yil ozodlikdan mahrum qilish jazosi shartli ravishda tayinlansin.
"""

TOZA = """OʻZBEKISTON RESPUBLIKASI NOMIDAN
HUKM

Ish № 1-7788/2024

Samarqand viloyat sudi
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
Oliy sud Plenumi qarori hisobga olindi.
Sudlanuvchiga oxirgi soʻz berildi.

HUKM QILDI:

Toshmatov Alisher Baxtiyorovichni Jinoyat kodeksining 169-moddasi 2-qismi
bilan aybdor deb topib, 3 yil ozodlikdan mahrum qilish jazosi tayinlansin.
Hukm ustidan 10 kun ichida apellyatsiya shikoyati berilishi mumkin.
"""

BOSHQA_SUDYA = TOZA.replace("Sudya: Karimov A.B.", "Sudya: Sobirov D.E.")


# --------------------------------------------------------------------------- #
# Yordamchilar
# --------------------------------------------------------------------------- #


def _cli(*args: str) -> Any:
    from typer.testing import CliRunner

    from uzlegal.cli.main import app as cli_app

    return CliRunner().invoke(cli_app, list(args))


def _satrlar(result: Any) -> list[str]:
    return [s.rstrip() for s in str(result.output).splitlines()]


@pytest.fixture
def qaror(tmp_path: Path) -> Path:
    """Bitta shubhali qaror fayli."""
    path = tmp_path / "qaror-1.txt"
    path.write_text(SHUBHALI, encoding="utf-8")
    return path


@pytest.fixture
def katalog(tmp_path: Path) -> Path:
    """Uchta qarorli katalog: ikkitasi bir sudyaniki, biri boshqasiniki."""
    folder = tmp_path / "qarorlar"
    folder.mkdir()
    (folder / "qaror-1.txt").write_text(SHUBHALI, encoding="utf-8")
    (folder / "qaror-2.txt").write_text(TOZA, encoding="utf-8")
    (folder / "qaror-3.txt").write_text(BOSHQA_SUDYA, encoding="utf-8")
    return folder


# --------------------------------------------------------------------------- #
# C1 — nazorat check
# --------------------------------------------------------------------------- #


def test_check_buyrugi_ishlaydi(qaror: Path) -> None:
    result = _cli("nazorat", "check", str(qaror))

    assert result.exit_code == 0
    assert "Sud qarori: qaror-1.txt" in result.output
    assert "Karimov A.B." in result.output


def test_check_xavf_darajasi_va_yorligi_chiqadi(qaror: Path) -> None:
    result = _cli("nazorat", "check", str(qaror))

    assert "Xavf darajasi: 1.00 — yuqori xavf" in result.output


def test_check_belgilar_toifa_boyicha_guruhlanadi(qaror: Path) -> None:
    result = _cli("nazorat", "check", str(qaror))

    assert "protsessual tartib (" in result.output
    assert "qaror tuzilmasi (" in result.output


def test_check_har_belgiga_dalil_satri_bor(qaror: Path) -> None:
    """§ 3.3 — har bir belgi qarorning qayeridan kelganini ko'rsatsin."""
    from uzlegal.integrity.detector import detect_from_text

    profile = detect_from_text(SHUBHALI)
    lines = [s for s in _satrlar(_cli("nazorat", "check", str(qaror))) if "dalil: " in s]

    assert profile.flags, "namuna qaror belgisiz qolib ketmasin"
    assert len(lines) == len(profile.flags)


def test_check_belgisiz_qaror_hisobotni_buzmaydi(tmp_path: Path) -> None:
    path = tmp_path / "toza.txt"
    path.write_text(TOZA, encoding="utf-8")

    result = _cli("nazorat", "check", str(path))

    assert result.exit_code == 0
    assert "Xavf darajasi:" in result.output


def test_check_out_faylga_yozadi(qaror: Path, tmp_path: Path) -> None:
    out = tmp_path / "hisobot.txt"

    result = _cli("nazorat", "check", str(qaror), "--out", str(out))

    assert result.exit_code == 0
    assert "Saqlandi" in result.output
    assert "Sud qarori: qaror-1.txt" in out.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# C2 — nazorat profile
# --------------------------------------------------------------------------- #


def test_profile_buyrugi_ishlaydi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog))

    assert result.exit_code == 0
    assert "Sudya profili:" in result.output
    assert "Qarorlar  3" in result.output


def test_profile_jazo_statistikasini_beradi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog))

    assert "Jazo statistikasi" in result.output
    assert "Ozodlikdan mahrum  3" in result.output


def test_profile_judge_bilan_toraytiriladi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog), "--judge", "Karimov A.B.")

    assert result.exit_code == 0
    assert "Sudya profili: Karimov A.B." in result.output
    assert "Qarorlar  2" in result.output
    assert "qaror-3.txt" not in result.output


def test_profile_aralash_katalogda_ogohlantiradi(katalog: Path) -> None:
    """Ikki sudyaning qarorini bitta profilga qo'shish — jimgina yolg'on."""
    result = _cli("nazorat", "profile", str(katalog))

    assert "xil sudya nomi bor" in result.output


def test_profile_bitta_sudyada_ogohlantirmaydi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog), "--judge", "Sobirov")

    assert "xil sudya nomi bor" not in result.output


def test_profile_bosh_faylni_otkazib_yuboradi(katalog: Path) -> None:
    (katalog / "qaror-4.txt").write_text("   \n", encoding="utf-8")

    result = _cli("nazorat", "profile", str(katalog))

    assert result.exit_code == 0
    assert "Bo'sh fayl o'tkazildi" in result.output
    assert "Qarorlar  3" in result.output


def test_profile_limit_ishlarni_qisqartiradi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog), "--limit", "1")

    assert "qaror-1.txt" in result.output
    assert "yana 2 ish" in result.output


def test_profile_limit_nol_hammasini_beradi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog), "--limit", "0")

    assert "qaror-3.txt" in result.output
    assert "ish (hammasi uchun" not in result.output


def test_profile_naqsh_bilan_faylni_tanlaydi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog), "--pattern", "qaror-1.txt")

    assert result.exit_code == 0
    assert "Qarorlar  1" in result.output


def test_profile_out_faylga_yozadi(katalog: Path, tmp_path: Path) -> None:
    out = tmp_path / "profil.txt"

    result = _cli("nazorat", "profile", str(katalog), "--out", str(out))

    assert result.exit_code == 0
    assert "Sudya profili:" in out.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# C3 — --json chiqishi model_dump() ga mos
# --------------------------------------------------------------------------- #


def test_check_json_model_dump_ga_mos(qaror: Path) -> None:
    from uzlegal.cli.nazorat import DISCLAIMER
    from uzlegal.integrity.detector import detect_from_text

    result = _cli("nazorat", "check", str(qaror), "--json")

    kutilgan = detect_from_text(SHUBHALI).model_dump()
    kutilgan["disclaimer"] = DISCLAIMER
    assert json.loads(result.output) == kutilgan


def test_profile_json_model_dump_ga_mos(katalog: Path) -> None:
    from uzlegal.court.parser import parse
    from uzlegal.integrity.profile import build_profile

    result = _cli("nazorat", "profile", str(katalog), "--judge", "Karimov A.B.", "--json")

    kutilgan = build_profile("Karimov A.B.", [parse(SHUBHALI), parse(TOZA)]).model_dump()
    assert json.loads(result.output) == kutilgan


def test_json_out_bilan_faylga_ham_yoziladi(qaror: Path, tmp_path: Path) -> None:
    out = tmp_path / "hisobot.json"

    result = _cli("nazorat", "check", str(qaror), "--json", "--out", str(out))

    assert result.exit_code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["risk_label"]


# --------------------------------------------------------------------------- #
# C4 — xato yo'llari: typer.Exit(4) va o'zbekcha matn
# --------------------------------------------------------------------------- #


def test_check_fayl_topilmasa_toxtaydi(tmp_path: Path) -> None:
    result = _cli("nazorat", "check", str(tmp_path / "yoq.txt"))

    assert result.exit_code == 4
    assert "Fayl topilmadi" in result.output


def test_check_katalog_berilsa_rad_etiladi(katalog: Path) -> None:
    result = _cli("nazorat", "check", str(katalog))

    assert result.exit_code == 4
    assert "Bu katalog, fayl kutilgan edi" in result.output


def test_check_bosh_fayl_rad_etiladi(tmp_path: Path) -> None:
    path = tmp_path / "bosh.txt"
    path.write_text("\n \n", encoding="utf-8")

    result = _cli("nazorat", "check", str(path))

    assert result.exit_code == 2
    assert "Fayl bo'sh" in result.output


def test_profile_katalog_topilmasa_toxtaydi(tmp_path: Path) -> None:
    result = _cli("nazorat", "profile", str(tmp_path / "yoq"))

    assert result.exit_code == 4
    assert "Katalog topilmadi" in result.output


def test_profile_fayl_berilsa_rad_etiladi(qaror: Path) -> None:
    result = _cli("nazorat", "profile", str(qaror))

    assert result.exit_code == 4
    assert "Bu fayl, katalog kutilgan edi" in result.output


def test_profile_bosh_katalogda_toxtaydi(tmp_path: Path) -> None:
    folder = tmp_path / "bosh"
    folder.mkdir()

    result = _cli("nazorat", "profile", str(folder))

    assert result.exit_code == 4
    assert "naqshiga mos fayl yo'q" in result.output


def test_profile_barcha_fayl_bosh_bolsa_toxtaydi(tmp_path: Path) -> None:
    folder = tmp_path / "bosh-fayllar"
    folder.mkdir()
    (folder / "a.txt").write_text("  ", encoding="utf-8")

    result = _cli("nazorat", "profile", str(folder))

    assert result.exit_code == 4
    assert "O'qiladigan qaror topilmadi" in result.output


def test_profile_notanish_sudyada_toxtaydi(katalog: Path) -> None:
    result = _cli("nazorat", "profile", str(katalog), "--judge", "Yo'qov Z.")

    assert result.exit_code == 4
    assert "sudyasining qarori topilmadi" in result.output


# --------------------------------------------------------------------------- #
# C5 — disclaimer har doim chiqadi
# --------------------------------------------------------------------------- #

_DISCLAIMER_BELGISI = "vakolatli organlar tomonidan aniqlanadi"


def test_check_disclaimer_chiqadi(qaror: Path) -> None:
    assert _DISCLAIMER_BELGISI in _cli("nazorat", "check", str(qaror)).output


def test_check_json_disclaimer_saqlanadi(qaror: Path) -> None:
    payload = json.loads(_cli("nazorat", "check", str(qaror), "--json").output)

    assert _DISCLAIMER_BELGISI in payload["disclaimer"]


def test_profile_disclaimer_chiqadi(katalog: Path) -> None:
    assert _DISCLAIMER_BELGISI in _cli("nazorat", "profile", str(katalog)).output


def test_profile_json_disclaimer_saqlanadi(katalog: Path) -> None:
    payload = json.loads(_cli("nazorat", "profile", str(katalog), "--json").output)

    assert _DISCLAIMER_BELGISI in payload["disclaimer"]


def test_belgisiz_qarorda_ham_disclaimer_chiqadi(tmp_path: Path) -> None:
    path = tmp_path / "toza.txt"
    path.write_text(TOZA, encoding="utf-8")

    assert _DISCLAIMER_BELGISI in _cli("nazorat", "check", str(path)).output


def test_out_bilan_disclaimer_ekranda_ham_faylda_ham_qoladi(qaror: Path, tmp_path: Path) -> None:
    """`--out` yuridik izohni chetlab o'tishning yo'li bo'lmasin."""
    out = tmp_path / "hisobot.txt"

    result = _cli("nazorat", "check", str(qaror), "--out", str(out))

    assert _DISCLAIMER_BELGISI in result.output
    assert _DISCLAIMER_BELGISI in out.read_text(encoding="utf-8")


def test_json_out_bilan_disclaimer_ekranda_qoladi(katalog: Path, tmp_path: Path) -> None:
    out = tmp_path / "profil.json"

    result = _cli("nazorat", "profile", str(katalog), "--json", "--out", str(out))

    assert _DISCLAIMER_BELGISI in result.output


def test_disclaimer_manbasi_judge_profile() -> None:
    """CLI matnni ko'chirib yozmaydi — u `JudgeProfile` dan olinadi."""
    from uzlegal.cli.nazorat import DISCLAIMER
    from uzlegal.integrity.profile import JudgeProfile

    assert JudgeProfile(judge="X").disclaimer == DISCLAIMER


# --------------------------------------------------------------------------- #
# C6 — model chaqirilmaydi, chiqish deterministik
# --------------------------------------------------------------------------- #


@pytest.fixture
def modelsiz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Har qanday model yuklashga urinish testni yiqitadi."""
    import uzlegal.inference.backend as backend

    def _taqiq(*args: object, **kwargs: object) -> object:
        raise AssertionError("nazorat modeli chaqirdi — bu taqiqlangan (docs/22 § 5 C6)")

    monkeypatch.setattr(backend, "create_backend", _taqiq)
    monkeypatch.setattr(backend, "load_builtin_backends", _taqiq)


def test_check_model_chaqirmaydi(qaror: Path, modelsiz: None) -> None:
    result = _cli("nazorat", "check", str(qaror))

    assert result.exit_code == 0
    assert _DISCLAIMER_BELGISI in result.output


def test_profile_model_chaqirmaydi(katalog: Path, modelsiz: None) -> None:
    result = _cli("nazorat", "profile", str(katalog))

    assert result.exit_code == 0
    assert _DISCLAIMER_BELGISI in result.output


def test_check_chiqishi_deterministik(qaror: Path) -> None:
    """Bir xil fayl → bir xil hisobot. Modelli tizimda bu kafolatlanmaydi."""
    birinchi = _cli("nazorat", "check", str(qaror)).output
    ikkinchi = _cli("nazorat", "check", str(qaror)).output

    assert birinchi == ikkinchi
    assert birinchi.strip()


def test_profile_chiqishi_deterministik(katalog: Path) -> None:
    birinchi = _cli("nazorat", "profile", str(katalog)).output
    ikkinchi = _cli("nazorat", "profile", str(katalog)).output

    assert birinchi == ikkinchi


def test_belgilar_tartibi_toifa_royxatidan_keladi() -> None:
    """Toifa tartibi qattiq belgilangan — aks holda hisobot suzib ketadi."""
    from uzlegal.cli.nazorat import _CATEGORY_LABELS
    from uzlegal.integrity.patterns import FlagCategory

    assert set(_CATEGORY_LABELS) == set(FlagCategory)


# --------------------------------------------------------------------------- #
# Ro'yxatga ulanish
# --------------------------------------------------------------------------- #


def test_nazorat_sub_app_royxatda() -> None:
    from uzlegal.cli.main import app as cli_app

    assert "nazorat" in {group.name for group in cli_app.registered_groups}
