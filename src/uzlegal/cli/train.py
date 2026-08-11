"""Trening buyruqlari — trening ma'lumoti va LoRA adapterlari.

Sub-app sifatida yozilgan va `cli/main.py` da ulanadi (docs/13 § 3.1).

## Ogohlantirish

Bu buyruqlar **tekshirilmagan** sintetik ma'lumot bilan ishlashi mumkin.
Tekshirilmagan yuridik trening ma'lumoti modelni ishonch bilan xato
qilishga o'rgatadi — bu tekshirilmagan modeldan yomonroq (docs/05 § 3).

Shuning uchun `train lora` standart holda **faqat tekshirilgan**
namunalarni oladi va `--allow-unverified` bayrog'i ataylab noqulay
nomlangan.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

train_app = typer.Typer(help="Trening ma'lumoti va LoRA adapterlari", no_args_is_help=True)
console = Console()

DEFAULT_DATA = Path("data/sft")
DEFAULT_CONFIG = Path("configs/training/role-lora.yaml")


@train_app.command("seed")
def seed(
    role: str = typer.Option(
        ..., "--role", help="jurist · advocate · prosecutor · professor · judge"
    ),
    limit: int = typer.Option(200, "--limit", help="Nechta urug' savol yaratilsin"),
    out: Path = typer.Option(None, "--out", help="Standart: data/sft/<role>/seeds.jsonl"),
) -> None:
    """Korpusdan urug' savollar yaratadi (sintetik quvurning birinchi qadami).

    Savollar korpus moddalaridan olinadi, javob esa **yozilmaydi** — u
    keyingi qadamda model bilan generatsiya qilinadi va undan keyin
    yurist tomonidan tekshiriladi.
    """
    import json

    from uzlegal.index.store import IndexNotBuiltError, KnowledgeIndex
    from uzlegal.training.dataset import seed_questions

    index = KnowledgeIndex()
    try:
        index.load()
    except IndexNotBuiltError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(4) from exc

    chunks = list(index._chunks.values())
    seeds = list(seed_questions(chunks, role, limit))

    destination = out or DEFAULT_DATA / role / "seeds.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in seeds), encoding="utf-8"
    )

    console.print(f"[green]✓[/green] {len(seeds)} urug' savol → {destination}")
    console.print(
        "[yellow]⚠ Bu tekshirilmagan sintetik material. "
        "Yurist tekshiruvisiz treningga ishlatilmaydi.[/yellow]"
    )


@train_app.command("stats")
def stats(
    role: str = typer.Option(None, "--role", help="Faqat shu rol"),
    data: Path = typer.Option(None, "--data", help="Standart: data/sft/<role>/samples.jsonl"),
) -> None:
    """Trening to'plami statistikasi — nechtasi tekshirilgan."""
    from uzlegal.training.dataset import Dataset

    path = data or (DEFAULT_DATA / (role or "") / "samples.jsonl")
    if not path.exists():
        console.print(f"[yellow]To'plam yo'q: {path}[/yellow]")
        raise typer.Exit(4)

    info = Dataset(path).stats()
    for key, value in info.items():
        console.print(f"  {key:14} {value}")

    verified = int(str(info.get("tekshirilgan") or 0))
    total = int(str(info.get("jami") or 0))
    if total and verified < total:
        console.print(
            f"\n[yellow]⚠ {total - verified} namuna tekshirilmagan — "
            f"ular treningga tushmaydi.[/yellow]"
        )


@train_app.command("verify")
def verify(
    sample_id: str = typer.Argument(..., help="Namuna ID"),
    expert: str = typer.Option(..., "--expert", help="Tekshirgan yurist"),
    data: Path = typer.Option(..., "--data", help="Namunalar fayli"),
) -> None:
    """Namunani tekshirilgan deb belgilaydi (tekshirish interfeysining CLI qismi).

    Bu qadamni avtomatlashtirib bo'lmaydi: yuridik to'g'rilikni faqat
    malakali yurist tasdiqlay oladi (docs/13 § 1).
    """
    from uzlegal.training.dataset import Dataset

    if not Dataset(data).mark_verified(sample_id, expert):
        console.print(f"[red]✕[/red] Namuna topilmadi: {sample_id}")
        raise typer.Exit(4)
    console.print(f"[green]✓[/green] {sample_id} — {expert} tomonidan tasdiqlandi")


@train_app.command("lora")
def lora(
    role: str = typer.Option(..., "--role"),
    base: str = typer.Option("gemma3-12b", "--base", help="Baza model ID"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config"),
    data: Path = typer.Option(None, "--data", help="Standart: data/sft/<role>/samples.jsonl"),
    out: Path = typer.Option(None, "--out", help="Standart: adapters/<role>/current"),
    epochs: int = typer.Option(None, "--epochs"),
    rank: int = typer.Option(None, "--rank"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Tekshiruvlar, treningsiz"),
    allow_unverified: bool = typer.Option(
        False,
        "--allow-unverified",
        help="TEKSHIRILMAGAN ma'lumot bilan o'qitish — ishlab chiqarishga chiqmaydi",
    ),
) -> None:
    """Rol adapterini o'qitadi (MLX LoRA).

    Standart holda faqat **tekshirilgan** namunalar ishlatiladi.
    """
    from uzlegal.config import get_registry
    from uzlegal.training.lora import (
        InsufficientMemoryError,
        TrainingConfig,
        UnverifiedDataError,
        estimate_memory_gb,
        train_lora,
    )

    data_path = data or DEFAULT_DATA / role / "samples.jsonl"
    out_path = out or Path("adapters") / role / "current"

    overrides: dict[str, object] = {
        "role": role,
        "base_model": base,
        "data_path": data_path,
        "output_path": out_path,
        "allow_unverified": allow_unverified,
    }
    if epochs is not None:
        overrides["epochs"] = epochs
    if rank is not None:
        overrides["rank"] = rank

    if config.exists():
        cfg = TrainingConfig.from_yaml(config, **overrides)
    else:
        console.print(f"[dim]Sozlama yo'q ({config}) — standart qiymatlar[/dim]")
        cfg = TrainingConfig(**overrides)  # type: ignore[arg-type]

    registry = get_registry()
    try:
        size_gb = registry.get_spec(base).size_gb or 8.0
    except KeyError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(2) from exc

    needed = estimate_memory_gb(size_gb, cfg.rank, cfg.max_seq_len)
    console.print(f"Rol: [bold]{role}[/bold] · baza {base} · rank {cfg.rank} · {cfg.epochs} epoch")
    console.print(f"Ma'lumot: {data_path}")
    console.print(f"Taxminiy xotira: {needed:.1f} GB / {registry.total_memory_gb:.0f} GB\n")

    if allow_unverified:
        console.print(
            "[yellow]⚠ TEKSHIRILMAGAN ma'lumot bilan o'qitilmoqda. "
            "Natija ishlab chiqarishga chiqarilmaydi.[/yellow]\n"
        )

    try:
        result = train_lora(cfg, dry_run=dry_run)
    except UnverifiedDataError as exc:
        console.print(f"[red]✕[/red] {exc}")
        console.print(
            "[dim]Tekshirilgan namuna yo'q. Yurist tekshiruvidan keyin qayta urinib ko'ring "
            "yoki --allow-unverified bilan majburlang (tavsiya etilmaydi).[/dim]"
        )
        raise typer.Exit(1) from exc
    except InsufficientMemoryError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(1) from exc
    except FileNotFoundError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(4) from exc

    for key, value in result.items():
        console.print(f"  {key:16} {value}")

    if dry_run:
        console.print("\n[dim]--dry-run: trening bajarilmadi[/dim]")
    else:
        console.print(f"\n[green]✓[/green] Adapter: {out_path}")
        console.print(
            "[dim]Ro'yxatdan o'tkazish: configs/models.yaml → adapters bo'limiga qo'shing[/dim]"
        )


if __name__ == "__main__":
    train_app()
