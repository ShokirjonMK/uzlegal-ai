"""`uzlegal pipeline dates` testlari — docs/22 § 5 (A5, A6).

Eng katta risk shu buyruqda: u `chunks.jsonl` ga — butun qidiruvning
ma'lumot bazasiga — yozadi. Shuning uchun testlar ikki narsani
qattiq ushlab turadi: `--apply` siz **hech narsa** yozilmaydi va
`--apply` bilan matn maydonlari (`chunk_id`, `heading`, `content`)
tegilmaydi.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from uzlegal.index.chunker import Chunk

BUGUN = "2026-08-14"

ARXIV_SANALARI = {
    "d-eski": "2020-03-15",
    "d-kelajak": "2027-01-01",
    "d-sanali": "2019-01-01",
}


def _chunk(chunk_id: str, doc_id: str, valid_from: str | None = None) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        doc_title="Test kodeksi",
        doc_type="kodeks",
        lang="uz",
        article="1",
        heading="[Test kodeksi > 1-modda]",
        content="Mulkdor talab qilishga haqli.",
        token_count=8,
        valid_from=valid_from,
    )


@pytest.fixture
def indeks(tmp_path: Path) -> Path:
    """Uchta hujjatli kichik `chunks.jsonl`."""
    chunks = [
        _chunk("d-eski:1", "d-eski"),
        _chunk("d-eski:2", "d-eski"),
        _chunk("d-kelajak:1", "d-kelajak"),
        _chunk("d-sanali:1", "d-sanali", valid_from="2021-05-05"),
        _chunk("d-arxivsiz:1", "d-arxivsiz"),
    ]
    path = tmp_path / "chunks.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in chunks), encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def soxta_arxiv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Arxivga chiqmaymiz — sanalar to'g'ridan-to'g'ri beriladi."""
    monkeypatch.setattr(
        "uzlegal.cli.pipeline._archive_dates", lambda: dict(ARXIV_SANALARI), raising=True
    )


def _cli(*args: str) -> Any:
    from typer.testing import CliRunner

    from uzlegal.cli.main import app as cli_app

    return CliRunner().invoke(cli_app, list(args))


def _satrlar(path: Path) -> list[dict[str, Any]]:
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


# --------------------------------------------------------------------------- #
# A5 — o'lchov va yozish
# --------------------------------------------------------------------------- #


def test_quruq_yugurish_faylni_ozgartirmaydi(indeks: Path) -> None:
    oldin = (indeks / "chunks.jsonl").read_bytes()

    result = _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN)

    assert result.exit_code == 0
    assert (indeks / "chunks.jsonl").read_bytes() == oldin
    assert not list(indeks.glob("*.bak"))


def test_olchov_oldin_va_keyin_sonini_beradi(indeks: Path) -> None:
    result = _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN)

    assert result.exit_code == 0
    assert "To'ldiriladi 2" in result.output
    assert "kelajak sana tufayli o'tkazildi 1" in result.output
    assert "arxivda sana yo'q 1" in result.output


def test_apply_bosh_sanalarni_toldiradi(indeks: Path) -> None:
    result = _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN, "--apply")

    assert result.exit_code == 0
    sanalar = {r["chunk_id"]: r["valid_from"] for r in _satrlar(indeks / "chunks.jsonl")}
    assert sanalar["d-eski:1"] == "2020-03-15"
    assert sanalar["d-eski:2"] == "2020-03-15"


def test_apply_mavjud_sanani_bosmaydi(indeks: Path) -> None:
    _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN, "--apply")

    sanalar = {r["chunk_id"]: r["valid_from"] for r in _satrlar(indeks / "chunks.jsonl")}
    assert sanalar["d-sanali:1"] == "2021-05-05"


def test_arxivda_sanasiz_hujjat_bosh_qoladi(indeks: Path) -> None:
    _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN, "--apply")

    sanalar = {r["chunk_id"]: r["valid_from"] for r in _satrlar(indeks / "chunks.jsonl")}
    assert sanalar["d-arxivsiz:1"] is None


def test_apply_zaxira_nusxa_qoldiradi(indeks: Path) -> None:
    oldin = (indeks / "chunks.jsonl").read_bytes()

    _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN, "--apply")

    zaxira = list(indeks.glob("chunks.jsonl.*.bak"))
    assert len(zaxira) == 1
    assert zaxira[0].read_bytes() == oldin
    assert not list(indeks.glob("*.tmp"))


def test_indeks_topilmasa_toxtaydi(tmp_path: Path) -> None:
    result = _cli("pipeline", "dates", "--index", str(tmp_path / "yoq"))

    assert result.exit_code == 4


# --------------------------------------------------------------------------- #
# A6 — matn maydonlari tegilmaydi
# --------------------------------------------------------------------------- #


def test_apply_chunk_id_heading_content_ni_ozgartirmaydi(indeks: Path) -> None:
    """Bu buzilsa BM25 va LanceDB qatorlari `chunks.jsonl` dan uziladi."""
    oldin = {r["chunk_id"]: (r["heading"], r["content"]) for r in _satrlar(indeks / "chunks.jsonl")}

    _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN, "--apply")

    keyin = {r["chunk_id"]: (r["heading"], r["content"]) for r in _satrlar(indeks / "chunks.jsonl")}
    assert keyin == oldin


def test_apply_bolaklar_sonini_saqlaydi(indeks: Path) -> None:
    oldin = len(_satrlar(indeks / "chunks.jsonl"))

    _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN, "--apply")

    assert len(_satrlar(indeks / "chunks.jsonl")) == oldin


# --------------------------------------------------------------------------- #
# A4 — kelajak sana
# --------------------------------------------------------------------------- #


def test_kelajak_sanali_hujjat_valid_from_olmaydi(indeks: Path) -> None:
    """`version_filter` bunday bo'lakni barcha so'rovlardan yashirardi."""
    _cli("pipeline", "dates", "--index", str(indeks), "--as-of", BUGUN, "--apply")

    sanalar = {r["chunk_id"]: r["valid_from"] for r in _satrlar(indeks / "chunks.jsonl")}
    assert sanalar["d-kelajak:1"] is None


def test_kelajak_sana_bugun_kelganda_yoziladi(indeks: Path) -> None:
    """Chegara bugungi kunga bog'liq, hujjatga emas."""
    _cli("pipeline", "dates", "--index", str(indeks), "--as-of", "2027-06-01", "--apply")

    sanalar = {r["chunk_id"]: r["valid_from"] for r in _satrlar(indeks / "chunks.jsonl")}
    assert sanalar["d-kelajak:1"] == "2027-01-01"


# --------------------------------------------------------------------------- #
# Buzuq kirish
# --------------------------------------------------------------------------- #


def test_buzuq_chunks_faylida_yiqilmaydi(tmp_path: Path) -> None:
    """Buzuq satrda traceback emas, tushunarli xato va 4-kod."""
    (tmp_path / "chunks.jsonl").write_text('{"chunk_id": "a"\n', encoding="utf-8")

    result = _cli("pipeline", "dates", "--index", str(tmp_path), "--apply")

    assert result.exit_code == 4
    assert not list(tmp_path.glob("*.tmp"))
