"""Trening quvuri testlari (Faza 3–4).

Eng muhim tekshiruv: **tekshirilmagan ma'lumot treningga tushmasligi**.
Bu tasodifiy emas — tekshirilmagan yuridik data modelni ishonch bilan
xato qilishga o'rgatadi (docs/05 § 3).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from uzlegal.index.chunker import Chunk
from uzlegal.training.dataset import (
    ContextRef,
    Dataset,
    TrainingSample,
    check_sample,
    extract_topic,
    filter_samples,
    seed_questions,
)
from uzlegal.training.lora import (
    TrainingConfig,
    UnverifiedDataError,
    estimate_memory_gb,
    prepare_mlx_data,
    train_lora,
)


def sample(**kw: object) -> TrainingSample:
    base: dict[str, object] = {
        "id": "s1",
        "role": "jurist",
        "context": [ContextRef(tag="C1", chunk_id="fk:234", text="Majburiyat — huquqiy munosabat")],
        "question": "Majburiyat nima?",
        "answer": "Majburiyat huquqiy munosabat hisoblanadi [C1]. " * 4,
    }
    base.update(kw)
    return TrainingSample(**base)  # type: ignore[arg-type]


def make_chunk(article: str, title: str) -> Chunk:
    return Chunk(
        chunk_id=f"fk:{article}",
        doc_id="fk",
        doc_title="Fuqarolik kodeksi",
        doc_type="kodeks",
        lang="uz",
        article=article,
        heading=f"[Fuqarolik kodeksi > {article}-modda. {title}]",
        content="matn " * 40,
    )


# --------------------------------------------------------------------------- #
# Mavzu ajratish
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Majburiyat tushunchasi", "majburiyat tushunchasi"),
        ("Mulk huquqining vujudga kelishi", "mulk huquqining vujudga kelishi"),
    ],
)
def test_mavzu_ajratiladi(title: str, expected: str) -> None:
    assert extract_topic(make_chunk("234", title)) == expected


def test_qisqa_sarlavha_otkazib_yuboriladi() -> None:
    assert extract_topic(make_chunk("1", "Kirish")) is None


# --------------------------------------------------------------------------- #
# Urug' savollar
# --------------------------------------------------------------------------- #


def test_urug_savollar_yaratiladi() -> None:
    chunks = [make_chunk(str(i), f"Huquqiy institut raqam {i}") for i in range(1, 6)]
    seeds = list(seed_questions(chunks, "jurist"))
    assert len(seeds) == 5
    assert all(s["role"] == "jurist" for s in seeds)


def test_savollar_har_xil() -> None:
    """Bir xil shablon takrorlansa model unga moslashadi."""
    chunks = [make_chunk(str(i), f"Institut {i}") for i in range(1, 7)]
    questions = {s["question"] for s in seed_questions(chunks, "jurist")}
    assert len(questions) == 6


def test_limit_hurmat_qilinadi() -> None:
    chunks = [make_chunk(str(i), f"Institut {i}") for i in range(1, 20)]
    assert len(list(seed_questions(chunks, "advocate", limit=3))) == 3


@pytest.mark.parametrize("role", ["jurist", "advocate", "prosecutor", "professor", "judge"])
def test_barcha_rollar_uchun_shablon_bor(role: str) -> None:
    chunks = [make_chunk("1", "Mulk huquqi tushunchasi")]
    assert list(seed_questions(chunks, role))


# --------------------------------------------------------------------------- #
# Filtrlar
# --------------------------------------------------------------------------- #


def test_yaroqli_namuna_otadi() -> None:
    assert check_sample(sample()) is None


def test_iqtibossiz_rad_etiladi() -> None:
    assert check_sample(sample(answer="Javob iqtibossiz. " * 10)) == "iqtibos yo'q"


def test_yolgon_iqtibos_tutiladi() -> None:
    """Kontekstda [C5] yo'q — model uni o'ylab topgan."""
    reason = check_sample(sample(answer="Javob matni bu yerda [C5]. " * 5))
    assert reason and "mavjud bo'lmagan iqtibos" in reason


def test_juda_qisqa_javob() -> None:
    assert check_sample(sample(answer="Ha [C1].")) == "javob juda qisqa"


def test_juda_uzun_javob() -> None:
    assert check_sample(sample(answer="soz " * 700 + "[C1]")) == "javob juda uzun"


def test_advokat_zaif_tomonni_korsatishi_shart() -> None:
    """Rol qulflanishiga qarshi asosiy mexanizm (docs/05 § 6)."""
    reason = check_sample(sample(role="advocate", answer="Pozitsiya kuchli [C1]. " * 6))
    assert reason == "zaif tomonlar ko'rsatilmagan"


def test_advokat_zaif_tomon_bilan_otadi() -> None:
    answer = "Pozitsiya kuchli [C1]. " * 6 + " ZAIF TOMONLAR: kvitansiya yo'q."
    assert check_sample(sample(role="advocate", answer=answer)) is None


def test_javob_savolni_takrorlamasin() -> None:
    reason = check_sample(sample(answer="Majburiyat nima? " * 12 + "[C1]"))
    assert reason == "javob savolni takrorlaydi"


def test_filtr_sabablarni_sanaydi() -> None:
    samples = [
        sample(id="a"),
        sample(id="b", answer="Qisqa [C1]."),
        sample(id="c", answer="x " * 700),
    ]
    passed, reasons = filter_samples(samples)
    assert len(passed) == 1
    assert sum(reasons.values()) == 2


# --------------------------------------------------------------------------- #
# Saqlash va tekshiruv holati
# --------------------------------------------------------------------------- #


def test_yozish_va_oqish(tmp_path: Path) -> None:
    dataset = Dataset(tmp_path / "d.jsonl")
    dataset.write([sample(id="a"), sample(id="b")])
    assert len(dataset.read()) == 2


def test_tekshirilmagan_namuna_treningga_tushmaydi(tmp_path: Path) -> None:
    """ENG MUHIM TEKSHIRUV."""
    dataset = Dataset(tmp_path / "d.jsonl")
    dataset.write([sample(id="a", verified=False), sample(id="b", verified=True)])

    assert len(dataset.trainable()) == 1
    assert dataset.trainable()[0].id == "b"


def test_allow_unverified_bilan_hammasi(tmp_path: Path) -> None:
    dataset = Dataset(tmp_path / "d.jsonl")
    dataset.write([sample(id="a", verified=False), sample(id="b", verified=True)])
    assert len(dataset.trainable(allow_unverified=True)) == 2


def test_rad_etilgan_namuna_hech_qachon_tushmaydi(tmp_path: Path) -> None:
    dataset = Dataset(tmp_path / "d.jsonl")
    dataset.write([sample(id="a", verified=True, rejection_reason="iqtibos yo'q")])
    assert dataset.trainable() == []
    assert dataset.trainable(allow_unverified=True) == []


def test_tekshirilgan_deb_belgilash(tmp_path: Path) -> None:
    dataset = Dataset(tmp_path / "d.jsonl")
    dataset.write([sample(id="a")])

    assert dataset.mark_verified("a", "expert-01")

    marked = dataset.read()[0]
    assert marked.verified and marked.verified_by == "expert-01"
    assert marked.verified_at


def test_statistika(tmp_path: Path) -> None:
    dataset = Dataset(tmp_path / "d.jsonl")
    dataset.write([sample(id="a", verified=True), sample(id="b", role="judge")])
    stats = dataset.stats()
    assert stats["jami"] == 2
    assert stats["tekshirilgan"] == 1


# --------------------------------------------------------------------------- #
# LoRA trening
# --------------------------------------------------------------------------- #


def test_tekshirilmagan_data_bilan_trening_toxtaydi(tmp_path: Path) -> None:
    data = tmp_path / "d.jsonl"
    Dataset(data).write([sample(verified=False)])

    config = TrainingConfig(
        role="jurist", base_model="models/x", data_path=data, output_path=tmp_path / "out"
    )
    with pytest.raises(UnverifiedDataError, match="Yurist tekshiruvi"):
        train_lora(config)


def test_bosh_toplam_toxtatadi(tmp_path: Path) -> None:
    data = tmp_path / "d.jsonl"
    Dataset(data).write([])
    config = TrainingConfig(
        role="jurist", base_model="models/x", data_path=data, output_path=tmp_path / "out"
    )
    with pytest.raises(UnverifiedDataError):
        train_lora(config)


def test_dry_run_buyruq_quradi(tmp_path: Path) -> None:
    data = tmp_path / "d.jsonl"
    Dataset(data).write([sample(id=f"s{i}", verified=True) for i in range(40)])

    config = TrainingConfig(
        role="advocate", base_model="models/qwen", data_path=data, output_path=tmp_path / "out"
    )
    result = train_lora(config, dry_run=True)

    assert "mlx_lm.lora" in result["command"]
    assert result["samples"] == 40
    assert result["iterations"] > 0


def test_mlx_formati(tmp_path: Path) -> None:
    counts = prepare_mlx_data([sample(id=f"s{i}") for i in range(20)], tmp_path)

    assert (tmp_path / "train.jsonl").exists()
    assert (tmp_path / "valid.jsonl").exists()
    assert counts["train"] + counts["valid"] == 20
    assert counts["valid"] >= 1, "validatsiya to'plami bo'sh bo'lmasligi kerak"


def test_mlx_matnida_iqtibos_saqlanadi(tmp_path: Path) -> None:
    prepare_mlx_data([sample()], tmp_path)
    text = (tmp_path / "valid.jsonl").read_text(encoding="utf-8")
    assert "[C1]" in text


def test_xotira_bahosi_oshib_boradi() -> None:
    small = estimate_memory_gb(8.0, rank=16, max_seq_len=2048)
    large = estimate_memory_gb(8.0, rank=64, max_seq_len=8192)
    assert large > small > 8.0


def test_konfiguratsiya_yamldan(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text("lora:\n  rank: 32\n  alpha: 64\ntraining:\n  epochs: 3\n", encoding="utf-8")
    config = TrainingConfig.from_yaml(
        path, role="judge", base_model="m", data_path=tmp_path / "d", output_path=tmp_path / "o"
    )
    assert config.rank == 32
    assert config.epochs == 3
