"""Sifat hisoboti testlari.

Bu hisobot panelda **qaror qabul qilish uchun** koʻrsatiladi, shuning
uchun uning notoʻgʻri boʻlishi oddiy nuqsondan yomonroq: u ishonch
uygʻotadigan yolgʻon raqam beradi.

Shu sababli testlar aynan chalgʻitishi mumkin boʻlgan joylarni bosadi:
nolga boʻlish, boʻsh jurnal, eski formatdagi yozuv, oyna chegarasi.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from uzlegal.api import quality


def _yozuv(**kwargs: Any) -> dict[str, Any]:
    """Audit yozuvining eng kichik shakli."""
    base: dict[str, Any] = {
        "trace_id": "cns_test",
        "timestamp": "2026-08-25T10:00:00+00:00",
        "user_hash": None,
        "question_masked": "Sinov savoli",
        "mode": "standard",
        "kb_version": "v2026.08.20",
        "retrieval": {"chunks": 5, "citations": 2},
        "gate": {"claims": 4, "kept": 3, "dropped": 1},
        "answer_chars": 500,
        "citations": ["x:1"],
        "confidence": 0.5,
        "latency_ms": 2000,
    }
    base.update(kwargs)
    return base


@pytest.fixture
def jurnal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Vaqtinchalik audit jurnali."""
    path = tmp_path / "consult.jsonl"
    monkeypatch.setattr(quality.audit, "audit_path", lambda: path)
    return path


def _yoz(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# Boʻsh va buzuq jurnal
# --------------------------------------------------------------------------- #


def test_bosh_jurnal_yiqilmaydi(jurnal: Path) -> None:
    """Panel jurnal boʻlmaganda ham ochilishi kerak."""
    natija = quality.summary()
    assert natija["records"] == 0
    assert "note" in natija


def test_buzuq_satr_panelni_yiqitmaydi(jurnal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Jurnal oʻqilmasa boʻsh hisobot qaytadi, istisno emas.

    Sabab: buzuq bitta satr tufayli butun panel yopilishi mumkin
    emas — aynan oʻsha paytda holatni koʻrish kerak boʻladi."""

    def yiqiladi() -> Any:
        raise ValueError("buzuq satr")

    monkeypatch.setattr(quality.audit, "read_all", yiqiladi)
    assert quality.summary()["records"] == 0
    assert quality.records()["yozuvlar"] == []


# --------------------------------------------------------------------------- #
# Nolga boʻlish
# --------------------------------------------------------------------------- #


def test_dalvosiz_yozuvlar_nolga_bolinmaydi(jurnal: Path) -> None:
    """Darvoza hech qanday daʼvo topmasa ulush 0 boʻlsin, xato emas."""
    _yoz(jurnal, [_yozuv(gate={"claims": 0, "kept": 0, "dropped": 0})])
    natija = quality.summary()
    assert natija["darvoza"]["drop_ulush"] == 0.0
    assert natija["rejimlar"][0]["drop_ulush"] == 0.0


def test_kechikishsiz_yozuv_persentilni_buzmaydi(jurnal: Path) -> None:
    _yoz(jurnal, [_yozuv(latency_ms=None)])
    kechikish = quality.summary()["rejimlar"][0]["kechikish"]
    assert kechikish["p50"] == 0
    assert kechikish["max"] == 0


# --------------------------------------------------------------------------- #
# Hisob-kitob
# --------------------------------------------------------------------------- #


def test_rejimlar_alohida_hisoblanadi(jurnal: Path) -> None:
    """Umumiy oʻrtacha muammoning qayerdaligini yashiradi.

    `simple` 0% va `standard` 50% — umumiysi 25%, lekin tuzatish
    kerak boʻlgan joy faqat ikkinchisi."""
    _yoz(
        jurnal,
        [
            _yozuv(mode="simple", gate={"claims": 4, "kept": 4, "dropped": 0}),
            _yozuv(mode="standard", gate={"claims": 4, "kept": 2, "dropped": 2}),
        ],
    )
    rejimlar = {m["mode"]: m for m in quality.summary()["rejimlar"]}
    assert rejimlar["simple"]["drop_ulush"] == 0.0
    assert rejimlar["standard"]["drop_ulush"] == 50.0


def test_sabablar_yigiladi(jurnal: Path) -> None:
    _yoz(
        jurnal,
        [
            _yozuv(gate={"claims": 2, "dropped": 2, "reasons": {"iqtibossiz huquqiy da'vo": 2}}),
            _yozuv(gate={"claims": 1, "dropped": 1, "reasons": {"iqtibossiz huquqiy da'vo": 1}}),
        ],
    )
    darvoza = quality.summary()["darvoza"]
    assert darvoza["reasons"]["iqtibossiz huquqiy da'vo"] == 3
    assert darvoza["reasons_available"] is True


def test_eski_yozuvda_sabab_yoq_deb_belgilanadi(jurnal: Path) -> None:
    """Eski yozuvlarda `reasons` maydoni yoʻq.

    Boʻsh roʻyxat «sabab yoʻq» deb oʻqilmasligi kerak — «maʼlumot
    yoʻq» deb oʻqilishi kerak. Panel shu bayroqqa qarab yozadi."""
    _yoz(jurnal, [_yozuv()])
    assert quality.summary()["darvoza"]["reasons_available"] is False


def test_haqiqiy_foydalanuvchilar_sanaladi(jurnal: Path) -> None:
    """Mahsulotning eng muhim koʻrsatkichi."""
    _yoz(jurnal, [_yozuv(user_hash=None), _yozuv(user_hash="a"), _yozuv(user_hash="a")])
    assert quality.summary()["foydalanuvchilar"] == 1


# --------------------------------------------------------------------------- #
# Savollar roʻyxati
# --------------------------------------------------------------------------- #


def test_yangi_yozuvlar_tepada(jurnal: Path) -> None:
    _yoz(
        jurnal,
        [
            _yozuv(trace_id="birinchi", timestamp="2026-08-01T10:00:00+00:00"),
            _yozuv(trace_id="ikkinchi", timestamp="2026-08-02T10:00:00+00:00"),
        ],
    )
    assert quality.records()["yozuvlar"][0]["trace_id"] == "ikkinchi"


def test_filtr_dropped(jurnal: Path) -> None:
    _yoz(
        jurnal,
        [
            _yozuv(trace_id="toza", gate={"claims": 2, "dropped": 0}),
            _yozuv(trace_id="muammoli", gate={"claims": 2, "dropped": 1}),
        ],
    )
    natija = quality.records(filtr="dropped")
    assert natija["jami"] == 1
    assert natija["yozuvlar"][0]["trace_id"] == "muammoli"


def test_filtr_iqtibossiz(jurnal: Path) -> None:
    _yoz(
        jurnal,
        [
            _yozuv(trace_id="bor", retrieval={"chunks": 3, "citations": 2}),
            _yozuv(trace_id="yoq", retrieval={"chunks": 3, "citations": 0}),
        ],
    )
    assert quality.records(filtr="no_citations")["yozuvlar"][0]["trace_id"] == "yoq"


def test_filtr_sekin(jurnal: Path) -> None:
    _yoz(
        jurnal,
        [_yozuv(trace_id="tez", latency_ms=1000), _yozuv(trace_id="sekin", latency_ms=90_000)],
    )
    assert quality.records(filtr="slow")["yozuvlar"][0]["trace_id"] == "sekin"


def test_sahifalash(jurnal: Path) -> None:
    _yoz(jurnal, [_yozuv(trace_id=f"n{i}") for i in range(10)])
    natija = quality.records(limit=3, offset=3)
    assert natija["jami"] == 10
    assert len(natija["yozuvlar"]) == 3


def test_javob_matni_qaytarilmaydi(jurnal: Path) -> None:
    """Jurnalda javob matni yoʻq, lekin buni test ham kafolatlasin.

    Panel orqali javob matnini oshkor qilish maxfiylik siyosatiga
    zid boʻlardi — u yerda «javob matni saqlanmaydi» deb yozilgan."""
    _yoz(jurnal, [_yozuv()])
    yozuv = quality.records()["yozuvlar"][0]
    assert "answer" not in yozuv
    assert "answer_hash" not in yozuv


def test_eksport_jsonl(jurnal: Path) -> None:
    _yoz(jurnal, [_yozuv(trace_id="a"), _yozuv(trace_id="b")])
    satrlar = quality.export_jsonl().splitlines()
    assert len(satrlar) == 2
    assert json.loads(satrlar[0])["trace_id"] in {"a", "b"}
