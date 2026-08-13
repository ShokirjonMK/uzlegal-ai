"""Audit jurnali testlari (`docs/10` § 5).

Bu testlar uchta narsani qoʻriqlaydi:

1. Shaxsiy maʼlumot jurnalga **maskasiz tushmaydi**;
2. Javobning **oʻzi saqlanmaydi**, faqat xeshi;
3. Yozuvni oʻzgartirish yoki oʻchirish **sezilmay qolmaydi**.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from uzlegal import audit


@pytest.fixture(autouse=True)
def _journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "consult.jsonl"
    monkeypatch.setenv(audit.PATH_ENV, str(path))
    monkeypatch.delenv(audit.ENABLED_ENV, raising=False)
    return path


def _write(**kwargs: object) -> str | None:
    body: dict[str, object] = {
        "trace_id": "cns_1",
        "question": "Sinov muddati necha oy?",
        "answer": "Uch oy.",
        "mode": "simple",
        "confidence": 0.8,
        "citations": ["mk:130"],
        "kb_version": "v1",
        "model_version": "m1",
        "latency_ms": 100,
    }
    body.update(kwargs)
    return audit.record_consult(**body)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Yozish
# --------------------------------------------------------------------------- #


def test_yozuv_saqlanadi(_journal: Path) -> None:
    assert _write() is not None
    records = list(audit.read_all())
    assert len(records) == 1
    assert records[0]["trace_id"] == "cns_1"


def test_javobning_ozi_saqlanmaydi(_journal: Path) -> None:
    """Jurnal maxfiy maʼlumot omboriga aylanmasligi kerak."""
    _write(answer="Juda maxfiy javob matni")
    raw = _journal.read_text(encoding="utf-8")

    assert "Juda maxfiy javob matni" not in raw
    assert "answer_hash" in raw
    assert next(iter(audit.read_all()))["answer_hash"].startswith("sha256:")


def test_javob_xeshi_isbotlash_uchun_yetarli(_journal: Path) -> None:
    """Foydalanuvchida javob nusxasi boʻlsa — uni tekshirib koʻrish mumkin."""
    import hashlib

    answer = "Uch oydan oshmasligi kerak."
    _write(answer=answer)

    expected = "sha256:" + hashlib.sha256(answer.encode()).hexdigest()
    assert next(iter(audit.read_all()))["answer_hash"] == expected


def test_shaxsiy_malumot_maskalanadi(_journal: Path) -> None:
    _write(question="Alisher Karimovni ishdan boʻshatish mumkinmi?")
    masked = next(iter(audit.read_all()))["question_masked"]
    assert "Alisher" not in masked
    assert "Karimov" not in masked


def test_ochirilgan_audit_yozmaydi(_journal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(audit.ENABLED_ENV, "0")
    assert _write() is None
    assert not _journal.exists()


def test_audit_standart_holda_yoqilgan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit majburiyat — uning yoʻqligi tasodifiy boʻlmasligi kerak."""
    monkeypatch.delenv(audit.ENABLED_ENV, raising=False)
    assert audit.is_enabled()


# --------------------------------------------------------------------------- #
# Hash zanjiri
# --------------------------------------------------------------------------- #


def test_birinchi_yozuv_genezisdan_boshlanadi(_journal: Path) -> None:
    _write()
    assert next(iter(audit.read_all()))["prev"] == audit.GENESIS


def test_zanjir_boglanadi(_journal: Path) -> None:
    _write(trace_id="a")
    _write(trace_id="b")
    records = list(audit.read_all())
    assert records[1]["prev"] == records[0]["hash"]


def test_toza_zanjir_tekshiruvdan_otadi(_journal: Path) -> None:
    for i in range(5):
        _write(trace_id=f"cns_{i}")
    result = audit.verify_chain()
    assert result["ok"] is True
    assert result["records"] == 5


def test_ozgartirilgan_yozuv_ushlanadi(_journal: Path) -> None:
    """Yozuvni tahrirlash sezilmay qolmasligi kerak."""
    _write(trace_id="a")
    _write(trace_id="b")

    lines = _journal.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["confidence"] = 0.99
    lines[0] = json.dumps(tampered, ensure_ascii=False)
    _journal.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = audit.verify_chain()
    assert result["ok"] is False
    assert result["broken_at"] == 1
    assert "zgartirilgan" in result["reason"]


def test_ochirilgan_yozuv_ushlanadi(_journal: Path) -> None:
    for i in range(3):
        _write(trace_id=f"cns_{i}")

    lines = _journal.read_text(encoding="utf-8").splitlines()
    del lines[1]
    _journal.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = audit.verify_chain()
    assert result["ok"] is False
    assert result["broken_at"] == 2
    assert "uzilgan" in result["reason"]


def test_birinchi_buzilish_qaytariladi(_journal: Path) -> None:
    """Undan keyingi hamma narsa baribir shubhali."""
    for i in range(5):
        _write(trace_id=f"cns_{i}")

    lines = _journal.read_text(encoding="utf-8").splitlines()
    for index in (1, 3):
        body = json.loads(lines[index])
        body["confidence"] = 0.5
        lines[index] = json.dumps(body, ensure_ascii=False)
    _journal.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert audit.verify_chain()["broken_at"] == 2


def test_bosh_jurnal_toza_hisoblanadi(_journal: Path) -> None:
    result = audit.verify_chain()
    assert result["ok"] is True
    assert result["records"] == 0


# --------------------------------------------------------------------------- #
# Qidirish va holat
# --------------------------------------------------------------------------- #


def test_trace_id_boyicha_topiladi(_journal: Path) -> None:
    _write(trace_id="a")
    _write(trace_id="kerakli")
    assert audit.find("kerakli") is not None
    assert audit.find("yoq") is None


def test_holat_korsatiladi(_journal: Path) -> None:
    _write(trace_id="a")
    _write(trace_id="b")
    info = audit.stats()
    assert info["records"] == 2
    assert info["enabled"] is True
    assert info["size_bytes"] > 0
    assert info["first"] and info["last"]


def test_yozib_bolmasa_sorov_yiqilmaydi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Foydalanuvchi javobsiz qolgandan koʻra jurnalda boʻshliq boʻlgani yaxshiroq.

    Yozib boʻlmaydigan holat: yoʻlda FAYL turibdi, papka emas — shunda
    `mkdir` ham, `open` ham muvaffaqiyatsiz boʻladi.
    """
    blocker = tmp_path / "band"
    blocker.write_text("men fayl man", encoding="utf-8")
    monkeypatch.setenv(audit.PATH_ENV, str(blocker / "consult.jsonl"))
    assert _write() is None
