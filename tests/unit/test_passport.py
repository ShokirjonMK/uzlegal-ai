"""Javob pasporti testlari (`docs/21` § 4).

Bu testlar to'rtta narsani qo'riqlaydi:

1. Pasport **aylanma yo'ldan o'tadi**: berilgan token o'sha tizimda
   tekshiriladi va mazmuni o'zgarmaydi;
2. Buzilgan tokenning **uchala yo'li** ham rad etiladi — imzo, payload
   va prefiks (docs/21 § 5, B2);
3. Savol va javob **matni pasportga tushmaydi** — faqat xeshi;
4. Imzolash yiqilsa **so'rov yiqilmaydi**: pasport `None` bo'ladi,
   javobning o'zi baribir beriladi.

Har testda kalit vaqtinchalik katalogda yaratiladi: repodagi haqiqiy
joylashtirma kaliti hech qachon ishlatilmaydi va yaratilmaydi ham.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from conftest import ScriptedBackend, StubRetriever, make_chunk  # tests/unit sys.path da

from uzlegal import passport as pp
from uzlegal.config import PROJECT_ROOT
from uzlegal.core import ConsultRequest, consult

SAVOL = "Sinov muddati necha oy bo'lishi mumkin"
JAVOB = "Sinov muddati uch oydan oshmasligi kerak [C1]"


@pytest.fixture(autouse=True)
def _kalit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Har test o'z kaliti bilan ishlaydi."""
    path = tmp_path / "passport_ed25519"
    monkeypatch.delenv(pp.KEY_ENV, raising=False)
    monkeypatch.setenv(pp.KEY_FILE_ENV, str(path))
    return path


def _issue(**kwargs: Any) -> str:
    body: dict[str, Any] = {
        "trace_id": "cns_1",
        "question": SAVOL,
        "answer": JAVOB,
        "citations": ["mk:130"],
        "kb_version": "v2026.08.01",
        "model_version": "m1",
        "as_of": None,
        "gate": {"passed": 3, "dropped": 1},
    }
    body.update(kwargs)
    token = pp.issue_passport(**body)
    assert token is not None
    return token


def _payload(token: str) -> dict[str, Any]:
    """Tokendagi payloadni ochadi — imzoni tekshirmasdan."""
    raw = token[len(pp.TOKEN_PREFIX) :].split(".")[0]
    data = json.loads(pp._b64url_decode_strict(raw).decode("utf-8"))
    assert isinstance(data, dict)
    return data


def _retoken(token: str, payload: dict[str, Any]) -> str:
    """Payloadni almashtiradi, imzoni ESKISICHA qoldiradi."""
    signature = token[len(pp.TOKEN_PREFIX) :].split(".")[1]
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{pp.TOKEN_PREFIX}{pp._b64url_encode(body.encode('utf-8'))}.{signature}"


def _pem() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


# --------------------------------------------------------------------------- #
# B1 — aylanma yo'l
# --------------------------------------------------------------------------- #


def test_pasport_berildi_va_tekshirildi() -> None:
    result = pp.verify_passport(_issue())

    assert result.version == pp.VERSION
    assert result.trace_id == "cns_1"
    assert result.citations == ("mk:130",)
    assert result.kb_version == "v2026.08.01"
    assert result.model_version == "m1"
    assert result.gate == {"passed": 3, "dropped": 1}
    assert result.key_fingerprint.startswith("SHA256:")


def test_javob_matni_xesh_orqali_tasdiqlanadi() -> None:
    """Pasportning butun ma'nosi shu: «tizim aynan shuni aytganmi?»."""
    result = pp.verify_passport(_issue())

    assert result.matches_answer(JAVOB)
    assert result.matches_question(SAVOL)
    assert not result.matches_answer(JAVOB + " (o'zgartirilgan)")


def test_as_of_pasportda_saqlanadi() -> None:
    """Javob qaysi sanadagi qonunchilikka ko'ra berilgani — nizoda hal qiluvchi."""
    result = pp.verify_passport(_issue(as_of=date(2019, 5, 1)))
    assert result.as_of == "2019-05-01"


def test_bir_xil_mazmun_bir_xil_payload_beradi() -> None:
    """Kanonik shakl `sort_keys` bilan: kalitlar tartibi imzoni buzmasin."""
    first = _payload(_issue())
    second = _payload(_issue())
    first.pop("issued_at")
    second.pop("issued_at")
    assert list(first) == sorted(first)
    assert first == second


# --------------------------------------------------------------------------- #
# B2 — buzilishning uchala yo'li
# --------------------------------------------------------------------------- #


def test_buzilgan_imzo_xato_beradi() -> None:
    """Boshqa payloadning imzosi qo'yilgan — payloadning o'zi butun."""
    boshqa = _issue(trace_id="cns_2", answer="Butunlay boshqa javob")
    imzo = boshqa[len(pp.TOKEN_PREFIX) :].split(".")[1]
    token = _issue()
    soxta = f"{pp.TOKEN_PREFIX}{token[len(pp.TOKEN_PREFIX) :].split('.')[0]}.{imzo}"

    with pytest.raises(pp.PassportError, match="Imzo"):
        pp.verify_passport(soxta)


def test_ozgartirilgan_payload_xato_beradi() -> None:
    """Javob almashtirilgan, imzo eskisicha — eng xavfli holat."""
    token = _issue()
    payload = _payload(token)
    payload["answer_hash"] = "sha256:" + "0" * 64

    with pytest.raises(pp.PassportError, match="Imzo"):
        pp.verify_passport(_retoken(token, payload))


def test_notogri_prefiksli_token_xato_beradi() -> None:
    """Litsenziya tokeni pasport sifatida o'tib ketmasin."""
    token = _issue().replace(pp.TOKEN_PREFIX, "uzlegal-lic.v1.", 1)

    with pytest.raises(pp.PassportError, match="Token shakli"):
        pp.verify_passport(token)


def test_buzilgan_base64_aniq_xato_beradi() -> None:
    """«O'qilmadi» va «soxta» ATAYLAB farqlanadi — tashxis to'g'ri bo'lsin."""
    with pytest.raises(pp.PassportError, match="base64"):
        pp.verify_passport(f"{pp.TOKEN_PREFIX}!!!.!!!")


def test_qisqa_imzo_aniq_xato_beradi() -> None:
    token = _issue()
    payload_b64 = token[len(pp.TOKEN_PREFIX) :].split(".")[0]

    with pytest.raises(pp.PassportError, match="imzo uzunligi"):
        pp.verify_passport(f"{pp.TOKEN_PREFIX}{payload_b64}.{pp._b64url_encode(b'qisqa')}")


def test_qismlari_ajratilmagan_token_xato_beradi() -> None:
    with pytest.raises(pp.PassportError, match="ajratilmadi"):
        pp.verify_passport(f"{pp.TOKEN_PREFIX}faqat-bitta-qism")


def test_boshqa_ornatma_kaliti_aniq_aytiladi(monkeypatch: pytest.MonkeyPatch) -> None:
    """«Boshqa kalit» va «soxta» — ikki xil hodisa, ikki xil javob."""
    monkeypatch.setenv(pp.KEY_ENV, _pem())
    token = _issue()

    monkeypatch.setenv(pp.KEY_ENV, _pem())
    with pytest.raises(pp.PassportError, match="boshqa o'rnatma"):
        pp.verify_passport(token)


# --------------------------------------------------------------------------- #
# B4 — matn pasportga kirmaydi
# --------------------------------------------------------------------------- #


def test_savol_va_javob_matni_pasportda_yoq() -> None:
    """Pasport javob bilan birga tarqaydi — u maxfiy ma'lumot tashimasin."""
    token = _issue()
    payload = _payload(token)

    dumped = json.dumps(payload, ensure_ascii=False)
    assert SAVOL not in dumped
    assert JAVOB not in dumped
    assert "question" not in payload
    assert "answer" not in payload

    assert payload["question_hash"].startswith("sha256:")
    assert payload["answer_hash"].startswith("sha256:")


def test_pasport_maydonlari_shartnomaga_mos() -> None:
    """docs/21 § 4.4 — pasport tarkibi shartnoma bo'yicha belgilangan."""
    assert set(_payload(_issue())) == {
        "version",
        "trace_id",
        "issued_at",
        "question_hash",
        "answer_hash",
        "citations",
        "kb_version",
        "model_version",
        "as_of",
        "gate",
        "key_fingerprint",
    }


# --------------------------------------------------------------------------- #
# B3 — kalit boshqaruvi
# --------------------------------------------------------------------------- #


def test_kalit_yoq_bolsa_ozi_yaratiladi(_kalit: Path, caplog: pytest.LogCaptureFixture) -> None:
    assert not _kalit.exists()

    with caplog.at_level(logging.WARNING, logger="uzlegal.passport"):
        _issue()

    assert _kalit.exists()
    assert "PRIVATE KEY" in _kalit.read_text(encoding="utf-8")
    # Yangi kalit — yangi shaxs. U jimgina tug'ilmasligi kerak.
    assert "SHA256:" in caplog.text


def test_maxfiy_kalit_gitignore_da() -> None:
    """Kalit repoga tushsa har kim shu tizim nomidan pasport yasay olardi."""
    ignored = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "data/keys/" in ignored
    assert pp.DEFAULT_KEY_PATH.parent.name == "keys"


def test_muhitdagi_kalit_fayldan_ustun(_kalit: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Konteynerda kalit sirlar omboridan keladi — diskka yozilmasin."""
    monkeypatch.setenv(pp.KEY_ENV, _pem())

    assert pp.verify_passport(_issue()).trace_id == "cns_1"
    assert not _kalit.exists()


def test_openssh_formatidagi_kalit_ham_ishlaydi(_kalit: Path) -> None:
    """Kalitni odatda `ssh-keygen` bilan yasashadi."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _kalit.write_bytes(
        Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
    )

    assert pp.verify_passport(_issue()).trace_id == "cns_1"


def test_ochiq_kalit_barmoq_izi_bilan_qaytadi() -> None:
    public = pp.passport_public_key()

    assert public.startswith("ssh-ed25519 ")
    assert "SHA256:" in public
    # Ochiq kalitda maxfiy qism bo'lmasligi kerak.
    assert "PRIVATE" not in public


# --------------------------------------------------------------------------- #
# B8 — xato so'rovni yiqitmaydi
# --------------------------------------------------------------------------- #


def test_buzuq_kalit_bilan_pasport_none(_kalit: Path) -> None:
    """Javobsiz qolgandan ko'ra pasportsiz qolgan yaxshiroq."""
    _kalit.write_text("bu kalit emas", encoding="utf-8")

    assert (
        pp.issue_passport(
            trace_id="cns_1",
            question=SAVOL,
            answer=JAVOB,
            citations=[],
            kb_version="v1",
            model_version=None,
            as_of=None,
            gate=None,
        )
        is None
    )


def test_notogri_turdagi_kalit_pasport_none(_kalit: Path) -> None:
    """RSA kalit bilan token yasalardi, lekin hech qachon tekshiruvdan o'tmasdi."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    _kalit.write_bytes(
        rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    assert (
        pp.issue_passport(
            trace_id="cns_1",
            question=SAVOL,
            answer=JAVOB,
            citations=[],
            kb_version="v1",
            model_version=None,
            as_of=None,
            gate=None,
        )
        is None
    )


def test_kalitsiz_tekshiruv_kalit_yaratmaydi(
    _kalit: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Tekshiruvchi o'ziga kalit yasab olsa, tashxis butunlay noto'g'ri bo'lardi."""
    token = _issue()

    boshqa = tmp_path / "yoq" / "passport_ed25519"
    monkeypatch.setenv(pp.KEY_FILE_ENV, str(boshqa))

    with pytest.raises(pp.PassportError, match="topilmadi"):
        pp.verify_passport(token)
    assert not boshqa.exists()


# --------------------------------------------------------------------------- #
# B5 — `consult()` bilan bog'lanish
# --------------------------------------------------------------------------- #


FRAME_JSON = (
    '{"facts": ["Sinov muddati belgilangan"], "legal_questions": ["Necha oy"], '
    '"applicable_norms": ["C1"], "unknowns": []}'
)


class FakeRegistry:
    active_id = "fake"

    def restore_state(self) -> str:
        return "fake"


def test_consult_javobiga_pasport_qoshiladi() -> None:
    result = consult(
        ConsultRequest(question=SAVOL, mode="simple"),
        retriever=StubRetriever([make_chunk("mk-130", "Sinov muddati uch oydan oshmaydi")]),
        backend=ScriptedBackend([FRAME_JSON]),
        registry=FakeRegistry(),
    )

    assert result.passport is not None
    checked = pp.verify_passport(result.passport)
    assert checked.trace_id == result.trace_id
    assert checked.matches_answer(result.answer)
    assert checked.kb_version == result.kb_version
    # docs/21 § 4.4 — gate natijasi pasportda ko'rinadi.
    assert {"passed", "dropped"} <= set(checked.gate)


def test_pasport_berilmasa_javob_baribir_qaytadi(_kalit: Path) -> None:
    """B8 — imzolash yiqilishi so'rovni to'xtatmaydi."""
    _kalit.write_text("bu kalit emas", encoding="utf-8")

    result = consult(
        ConsultRequest(question=SAVOL, mode="simple"),
        retriever=StubRetriever([make_chunk("mk-130", "Sinov muddati uch oydan oshmaydi")]),
        backend=ScriptedBackend([FRAME_JSON]),
        registry=FakeRegistry(),
    )

    assert result.passport is None
    assert result.answer
    assert result.disclaimer


# --------------------------------------------------------------------------- #
# B6 — REST
# --------------------------------------------------------------------------- #


@pytest.fixture
def client() -> Any:
    from fastapi.testclient import TestClient

    from uzlegal.api.app import app

    return TestClient(app)


def test_verify_endpointi_kalitsiz_ochiq(client: Any) -> None:
    """Pasportni ko'rsatgan tomonda API kaliti yo'q va bo'lmaydi ham."""
    response = client.post("/v1/passport/verify", json={"token": _issue()})

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["passport"]["trace_id"] == "cns_1"


def test_verify_endpointi_matnni_oshkor_qilmaydi(client: Any) -> None:
    response = client.post("/v1/passport/verify", json={"token": _issue()})

    assert SAVOL not in response.text
    assert JAVOB not in response.text


def test_verify_endpointi_soxta_tokenni_rad_etadi(client: Any) -> None:
    """«Soxta» — so'rovga to'liq javob, so'rovdagi xato emas."""
    token = _issue()
    payload = _payload(token)
    payload["trace_id"] = "cns_soxta"

    response = client.post("/v1/passport/verify", json={"token": _retoken(token, payload)})

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["reason"]


# --------------------------------------------------------------------------- #
# B7 — CLI
# --------------------------------------------------------------------------- #


def _cli(*args: str) -> Any:
    from typer.testing import CliRunner

    from uzlegal.cli.main import app as cli_app

    return CliRunner().invoke(cli_app, list(args))


def test_cli_pasportni_tekshiradi() -> None:
    result = _cli("passport", "verify", _issue())

    assert result.exit_code == 0
    assert "cns_1" in result.output


def test_cli_buzilgan_pasportda_yiqiladi() -> None:
    result = _cli("passport", "verify", "uzlegal-pass.v1.xxx.yyy")

    assert result.exit_code == 1


def test_cli_javob_matnini_pasport_bilan_solishtiradi(tmp_path: Path) -> None:
    """Qo'lidagi javob pasportga tegishlimi — foydalanuvchining asosiy savoli."""
    matn = tmp_path / "javob.txt"
    matn.write_text(JAVOB, encoding="utf-8")

    result = _cli("passport", "verify", _issue(), "--answer-file", str(matn))
    assert result.exit_code == 0

    matn.write_text(JAVOB + " (o'zgartirilgan)", encoding="utf-8")
    buzilgan = _cli("passport", "verify", _issue(), "--answer-file", str(matn))
    assert buzilgan.exit_code == 2


def test_cli_ochiq_kalitni_korsatadi() -> None:
    result = _cli("passport", "key")

    assert result.exit_code == 0
    assert "ssh-ed25519" in result.output
