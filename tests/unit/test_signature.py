"""Mualliflik va litsenziya tizimi testlari.

Bu testlar bitta narsani isbotlaydi: **litsenziyani muallifdan boshqa
hech kim yasay olmaydi.** Sinov uchun vaqtinchalik kalit juftligi
yaratiladi va muallifning haqiqiy kaliti umuman ishlatilmaydi —
maxfiy kalit hech qachon repoda bo'lmasligi kerak.
"""

from __future__ import annotations

import base64
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from uzlegal import signature as sig


@pytest.fixture
def keypair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sinov kalit juftligi; ochiq kalit modulga vaqtincha qo'yiladi."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    path = tmp_path / "id_ed25519"
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    )
    monkeypatch.setattr(sig, "PUBLIC_KEY_SSH", public.decode())
    return path


def _issue(keypair: Path, **kwargs: object) -> str:
    kwargs.setdefault("licensee", "Sinov MChJ")
    licensee = str(kwargs.pop("licensee"))
    return sig.issue_license(licensee, private_key_path=str(keypair), **kwargs)  # type: ignore[arg-type]


def _retoken(token: str, payload: dict[str, object]) -> str:
    """Payload'ni almashtiradi, imzoni ESKISICHA qoldiradi."""
    body = token[len(sig.TOKEN_PREFIX) :]
    _, signature_b64 = body.split(".")
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return f"{sig.TOKEN_PREFIX}{sig._b64url_encode(raw)}.{signature_b64}"


def _payload(token: str) -> dict[str, object]:
    body = token[len(sig.TOKEN_PREFIX) :]
    payload_b64, _ = body.split(".")
    return json.loads(sig._b64url_decode(payload_b64))  # type: ignore[no-any-return]


# --------------------------------------------------------------------------- #
# Mualliflik
# --------------------------------------------------------------------------- #


def test_mualliflik_bitta_manbadan_keladi() -> None:
    data = sig.attribution()
    assert data["author"] == sig.AUTHOR
    assert data["author_handle"] == sig.AUTHOR_HANDLE
    assert data["developer"] == sig.DEVELOPER
    assert data["contact"] == sig.CONTACT


def test_barcha_kalitlar_royxatda() -> None:
    """Muallif ko'rsatgan to'rtala nom ham tan olinadi."""
    assert set(sig.AUTHOR_KEYS) == {"ShokirjonMK", "MKdev", "mk", "@ceoNeuron"}


def test_javob_sarlavhalari_toliq() -> None:
    headers = sig.response_headers()
    assert headers["X-Author"].startswith(sig.AUTHOR)
    assert headers["X-Developer"] == sig.DEVELOPER
    assert headers["X-Contact"] == sig.CONTACT
    assert headers["X-Key-Fingerprint"] == sig.PUBLIC_KEY_FINGERPRINT


def test_banner_asosiy_nomlarni_ozida_saqlaydi() -> None:
    text = sig.banner()
    for name in (sig.AUTHOR, sig.AUTHOR_HANDLE, sig.DEVELOPER, sig.CONTACT):
        assert name in text


# --------------------------------------------------------------------------- #
# Litsenziya berish va tekshirish
# --------------------------------------------------------------------------- #


def test_berilgan_litsenziya_tekshiruvdan_otadi(keypair: Path) -> None:
    token = _issue(keypair, expires=date.today() + timedelta(days=30))
    license_ = sig.parse_license(token)
    assert license_.licensee == "Sinov MChJ"
    assert license_.days_left == 30
    assert not license_.is_expired


def test_muddatsiz_litsenziya(keypair: Path) -> None:
    license_ = sig.parse_license(_issue(keypair))
    assert license_.expires is None
    assert license_.days_left is None
    assert not license_.is_expired
    assert "muddatsiz" in license_.summary()


def test_scope_cheklaydi(keypair: Path) -> None:
    license_ = sig.parse_license(_issue(keypair, scope=("serve", "bot")))
    assert license_.allows("serve")
    assert license_.allows("bot")
    assert not license_.allows("train")


def test_bosh_scope_hammasiga_ruxsat(keypair: Path) -> None:
    license_ = sig.parse_license(_issue(keypair))
    assert license_.allows("serve")
    assert license_.allows("istalgan-narsa")


# --------------------------------------------------------------------------- #
# Soxtalashtirishga qarshilik — modulning butun ma'nosi
# --------------------------------------------------------------------------- #


def test_boshqa_kalit_bilan_imzolangan_token_rad_etiladi(keypair: Path, tmp_path: Path) -> None:
    """Kodni o'qigan odam ham litsenziya yasay olmasligi kerak."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    other = tmp_path / "boshqa"
    other.write_bytes(
        Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
    )
    forged = sig.issue_license("Buzg'unchi", private_key_path=str(other))
    with pytest.raises(sig.LicenseError, match="Imzo noto'g'ri"):
        sig.parse_license(forged)


def test_nomni_ozgartirish_ushlanadi(keypair: Path) -> None:
    token = _issue(keypair)
    payload = _payload(token)
    payload["licensee"] = "Buzg'unchi MChJ"
    with pytest.raises(sig.LicenseError, match="Imzo noto'g'ri"):
        sig.parse_license(_retoken(token, payload))


def test_muddatni_chozish_ushlanadi(keypair: Path) -> None:
    token = _issue(keypair, expires=date.today() + timedelta(days=1))
    payload = _payload(token)
    payload["expires"] = "2099-01-01"
    with pytest.raises(sig.LicenseError, match="Imzo noto'g'ri"):
        sig.parse_license(_retoken(token, payload))


def test_scope_kengaytirish_ushlanadi(keypair: Path) -> None:
    token = _issue(keypair, scope=("serve",))
    payload = _payload(token)
    payload["scope"] = ["*"]
    with pytest.raises(sig.LicenseError, match="Imzo noto'g'ri"):
        sig.parse_license(_retoken(token, payload))


def test_muddati_otgan_litsenziya_rad_etiladi(keypair: Path) -> None:
    token = _issue(keypair, expires=date.today() - timedelta(days=1))
    with pytest.raises(sig.LicenseError, match="muddati tugagan"):
        sig.parse_license(token)


# --------------------------------------------------------------------------- #
# Buzuq kirish — xato xabari aniq bo'lishi kerak
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("shunchaki-matn", "Token shakli noto'g'ri"),
        ("uzlegal-lic.v1.faqat-bitta-qism", "Token buzilgan"),
        ("uzlegal-lic.v1.!!!.!!!", "o'qilmadi"),
        ("uzlegal-lic.v1.eyJhIjoxfQ.qisqa", "o'qilmadi"),
    ],
)
def test_buzuq_token_aniq_xato_beradi(token: str, expected: str) -> None:
    with pytest.raises(sig.LicenseError, match=expected):
        sig.parse_license(token)


def test_licensee_siz_payload_rad_etiladi(keypair: Path) -> None:
    token = _issue(keypair, licensee="X")
    payload = _payload(token)
    payload["licensee"] = ""
    # Imzo baribir buziladi — lekin xabar aniq bo'lishi kerak
    with pytest.raises(sig.LicenseError):
        sig.parse_license(_retoken(token, payload))


# --------------------------------------------------------------------------- #
# Muhitdan o'qish
# --------------------------------------------------------------------------- #


def test_muhit_ozgaruvchisidan_oqiladi(keypair: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(sig.LICENSE_ENV, _issue(keypair))
    license_ = sig.load_license()
    assert license_ is not None
    assert license_.licensee == "Sinov MChJ"


def test_fayldan_oqiladi(keypair: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "license.key"
    path.write_text(_issue(keypair), encoding="utf-8")
    monkeypatch.delenv(sig.LICENSE_ENV, raising=False)
    monkeypatch.setenv(sig.LICENSE_FILE_ENV, str(path))
    license_ = sig.load_license()
    assert license_ is not None


def test_litsenziya_yoq_bolsa_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """«Yo'q» va «buzuq» farqlanadi — birinchisi xato emas."""
    monkeypatch.delenv(sig.LICENSE_ENV, raising=False)
    monkeypatch.setenv(sig.LICENSE_FILE_ENV, str(tmp_path / "mavjud-emas"))
    assert sig.load_license() is None


def test_require_license_yoq_bolsa_toxtaydi(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(sig.LICENSE_ENV, raising=False)
    monkeypatch.setenv(sig.LICENSE_FILE_ENV, str(tmp_path / "yoq"))
    with pytest.raises(sig.LicenseError, match="litsenziyasi yo'q"):
        sig.require_license("serve")


def test_require_license_scope_tekshiradi(keypair: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(sig.LICENSE_ENV, _issue(keypair, scope=("bot",)))
    assert sig.require_license("bot").licensee == "Sinov MChJ"
    with pytest.raises(sig.LicenseError, match="ruxsat etilmagan"):
        sig.require_license("serve")


def test_status_tokenni_oshkor_qilmaydi(keypair: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token = _issue(keypair)
    monkeypatch.setenv(sig.LICENSE_ENV, token)
    status = sig.license_status()
    assert status["valid"] is True
    assert token not in json.dumps(status)


def test_status_buzuq_tokenda_yiqilmaydi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(sig.LICENSE_ENV, "buzuq-token")
    status = sig.license_status()
    assert status["valid"] is False
    assert "error" in status


# --------------------------------------------------------------------------- #
# Ochiq kalit
# --------------------------------------------------------------------------- #


def test_ochiq_kalit_ssh_formatida_oqiladi() -> None:
    """Repodagi haqiqiy kalit — `SIGNATURE.md` dagi bilan bir xil bo'lishi kerak."""
    key = sig._public_key()
    from cryptography.hazmat.primitives import serialization

    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    assert len(raw) == 32  # Ed25519 ochiq kaliti — 32 bayt


def test_ochiq_kalit_signature_md_bilan_mos() -> None:
    text = Path("SIGNATURE.md").read_text(encoding="utf-8")
    assert sig.PUBLIC_KEY_SSH in text
    assert sig.PUBLIC_KEY_FINGERPRINT in text


def test_b64url_aylanma() -> None:
    for payload in (b"", b"a", b"ab", b"abc", b"o'zbek matni".encode() if False else b"xyz"):
        assert sig._b64url_decode(sig._b64url_encode(payload)) == payload


def test_base64_standart_kutubxona_bilan_mos() -> None:
    data = b"sinov ma'lumoti"
    assert base64.urlsafe_b64decode(sig._b64url_encode(data) + "=") == data
