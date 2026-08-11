"""LoRA trening quvuri — Faza 4.

## Nima uchun LoRA va nima uchun rank 16

`ADR-003` da asoslangan: beshta rol beshta model emas, bitta baza + beshta
40 MB lik adapter. 24 GB xotirada beshta 14B model sig'maydi (40 GB kerak),
adapterlar esa 8.2 GB da hammasi joylashadi.

Rank 16 sabab: rol adapteri **yangi bilim o'rgatmaydi** — bilim RAG dan
keladi (`ADR-006`). Adapter faqat *qanday gapirishni* o'zgartiradi: uslub,
struktura, iqtibos odati. Buning uchun 16 yetarli; kattaroq rank
overfitting va keraksiz xotira sarfi.

## Xotira cheklovi

M4 24 GB da 14B modelni QLoRA bilan o'qitish chegarada ishlaydi.
`estimate_memory()` oldindan hisoblab, sig'masa aniq xato beradi —
trening yarim yo'lda OOM bilan yiqilgandan ko'ra yaxshiroq.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from uzlegal.training.dataset import Dataset, TrainingSample

log = logging.getLogger(__name__)

# docs/05 § 5 dagi konfiguratsiya
DEFAULT_RANK = 16
DEFAULT_ALPHA = 32
DEFAULT_EPOCHS = 2
DEFAULT_LR = 1e-4
DEFAULT_MAX_SEQ = 4096

# Adapter parametr hajmi: rank × 2 × (kirish + chiqish) × qatlamlar × fp16
# Amalda 14B da rank 16 ≈ 20M parametr ≈ 40 MB
BYTES_PER_PARAM = 2


@dataclass
class TrainingConfig:
    role: str
    base_model: str
    data_path: Path
    output_path: Path
    rank: int = DEFAULT_RANK
    alpha: int = DEFAULT_ALPHA
    epochs: int = DEFAULT_EPOCHS
    learning_rate: float = DEFAULT_LR
    max_seq_len: int = DEFAULT_MAX_SEQ
    batch_size: int = 1
    grad_accum: int = 8
    allow_unverified: bool = False

    @classmethod
    def from_yaml(cls, path: Path, **overrides: object) -> TrainingConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        lora = raw.get("lora", {})
        training = raw.get("training", {})
        merged: dict[str, object] = {
            "rank": lora.get("rank", DEFAULT_RANK),
            "alpha": lora.get("alpha", DEFAULT_ALPHA),
            "epochs": training.get("epochs", DEFAULT_EPOCHS),
            "learning_rate": training.get("learning_rate", DEFAULT_LR),
            "max_seq_len": training.get("max_seq_len", DEFAULT_MAX_SEQ),
            "batch_size": training.get("batch_size", 1),
            "grad_accum": training.get("grad_accum", 8),
        }
        merged.update(overrides)
        return cls(**merged)  # type: ignore[arg-type]


class UnverifiedDataError(RuntimeError):
    """Tekshirilmagan ma'lumot bilan o'qitishga urinish."""


class InsufficientMemoryError(RuntimeError):
    pass


def estimate_memory_gb(base_size_gb: float, rank: int, max_seq_len: int) -> float:
    """QLoRA trening uchun taxminiy xotira.

    Baza (muzlatilgan, 4-bit) + adapter gradientlari + optimizator holati +
    aktivatsiyalar. Aniq emas, lekin OOM ni oldindan aytish uchun yetarli.
    """
    adapter_gb = rank * 1.25 / 1000  # rank 16 ≈ 0.02 GB
    optimizer_gb = adapter_gb * 3  # Adam: momentum + variance
    activations_gb = (max_seq_len / 1024) * 0.55
    return base_size_gb + adapter_gb + optimizer_gb + activations_gb + 1.5


def prepare_mlx_data(samples: list[TrainingSample], out_dir: Path) -> dict[str, int]:
    """MLX kutadigan formatga o'giradi: `train.jsonl` va `valid.jsonl`.

    `mlx_lm.lora` har qatorda `{"text": "..."}` kutadi. Prompt va javob
    chat shabloni bilan birlashtiriladi — model aynan shu formatni
    inferencedа ham ko'radi.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    def render(sample: TrainingSample) -> str:
        context = "\n\n".join(f"=== [{c.tag}] ===\n{c.text}" for c in sample.context)
        return (
            f"<|im_start|>system\nSen {sample.role} rolidasan. Faqat berilgan "
            f"manbalarga tayanib javob ber va har da'voga iqtibos qo'y.<|im_end|>\n"
            f"<|im_start|>user\n{context}\n\nSavol: {sample.question}<|im_end|>\n"
            f"<|im_start|>assistant\n{sample.answer}<|im_end|>"
        )

    split = max(1, int(len(samples) * 0.05))
    valid, train = samples[:split], samples[split:]

    for name, rows in (("train", train), ("valid", valid)):
        (out_dir / f"{name}.jsonl").write_text(
            "\n".join(json.dumps({"text": render(s)}, ensure_ascii=False) for s in rows),
            encoding="utf-8",
        )

    return {"train": len(train), "valid": len(valid)}


def train_lora(config: TrainingConfig, *, dry_run: bool = False) -> dict[str, object]:
    """Rol adapterini o'qitadi.

    Tekshirilmagan ma'lumot bilan ishga tushirish **ataylab qiyinlashtirilgan**:
    `allow_unverified=True` kerak. Bu tasodifan sifatsiz adapter chiqarib
    qo'yishning oldini oladi.
    """
    dataset = Dataset(config.data_path)
    samples = dataset.trainable(allow_unverified=config.allow_unverified)

    if not samples:
        total = len(dataset.read())
        raise UnverifiedDataError(
            f"'{config.role}' uchun treningga yaroqli namuna yo'q "
            f"(jami {total} ta, tekshirilgan 0). "
            f"Yurist tekshiruvi kerak — yoki ataylab allow_unverified=True."
        )

    if config.allow_unverified:
        log.warning(
            "⚠ TEKSHIRILMAGAN ma'lumot bilan o'qitilmoqda (%d namuna). "
            "Natijaviy adapter ishlab chiqarishga yaroqsiz.",
            len(samples),
        )

    data_dir = config.output_path.parent / f"{config.role}-mlx-data"
    counts = prepare_mlx_data(samples, data_dir)

    iterations = max(
        1, (counts["train"] * config.epochs) // (config.batch_size * config.grad_accum)
    )
    command = [
        sys.executable,
        "-m",
        "mlx_lm.lora",
        "--model",
        config.base_model,
        "--train",
        "--data",
        str(data_dir),
        "--adapter-path",
        str(config.output_path),
        "--iters",
        str(iterations),
        "--batch-size",
        str(config.batch_size),
        "--num-layers",
        str(config.rank),
        "--learning-rate",
        str(config.learning_rate),
        "--max-seq-length",
        str(config.max_seq_len),
    ]

    if dry_run:
        return {"command": command, "samples": len(samples), "iterations": iterations}

    config.output_path.mkdir(parents=True, exist_ok=True)
    log.info("LoRA trening: %s, %d namuna, %d iteratsiya", config.role, len(samples), iterations)
    result = subprocess.run(command, check=False)

    return {
        "role": config.role,
        "samples": len(samples),
        "iterations": iterations,
        "returncode": result.returncode,
        "adapter_path": str(config.output_path),
        "verified_data": not config.allow_unverified,
    }
