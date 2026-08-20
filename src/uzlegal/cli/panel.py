"""`uzlegal panel` — senior yurist kengashi buyruqlari (docs/26)."""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:  # pragma: no cover — faqat tip tekshiruvi uchun
    from uzlegal.agents.base import AgentContext
    from uzlegal.training.dataset import TrainingSample

panel_app = typer.Typer(help="Senior yurist kengashi — trening namunalarini saralash")
console = Console()


@panel_app.command("seniors")
def seniors() -> None:
    """Kengash tarkibi — o'nta senior va ularning mutaxassisligi."""
    from uzlegal.panel.seniors import SENIORS

    table = Table(show_header=True, header_style="bold")
    table.add_column("Kalit", style="cyan", no_wrap=True)
    table.add_column("Soha")
    table.add_column("Alohida e'tibor", style="dim")

    for senior in SENIORS:
        table.add_row(senior.key, senior.field_of_law, senior.lens)

    console.print(table)
    console.print(f"\n[dim]Har namunani {len(SENIORS)} tadan 3 tasi ko'radi.[/dim]")


@panel_app.command("route")
def route(
    text: str = typer.Argument(..., help="Savol yoki namuna matni"),
    size: int = typer.Option(3, "--size", help="Kengash tarkibi"),
) -> None:
    """Berilgan matn qaysi seniorlarga yuborilishini ko'rsatadi.

    Modelsiz ishlaydi — marshrutlashni tekshirish uchun.
    """
    from uzlegal.panel.seniors import select

    chosen = select(text, size=size)
    if not chosen:
        console.print("[yellow]Kengash tanlanmadi[/yellow]")
        raise typer.Exit(1)

    for i, senior in enumerate(chosen, start=1):
        marker = "[dim](tashqi ko'z)[/dim]" if i == len(chosen) and len(chosen) > 1 else ""
        console.print(f"  {i}. [cyan]{senior.key}[/cyan]  {senior.field_of_law} {marker}")


@panel_app.command("review")
def review(
    dataset: Path = typer.Option(..., "--dataset", help="Trening to'plami (JSONL)"),
    size: int = typer.Option(3, "--size", help="Har namunani nechta senior ko'radi"),
    limit: int = typer.Option(0, "--limit", help="Nechta namuna (0 — hammasi)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Faqat marshrutlash, modelsiz"),
    json_out: bool = typer.Option(False, "--json", help="Mashina uchun JSON"),
) -> None:
    """Namunalarni kengashdan o'tkazadi va natijani to'plamga yozadi.

    Kengash `verified` bayrog'iga **tegmaydi** — u faqat `panel`
    maydonini to'ldiradi. Yurist imzosi alohida qadam bo'lib qoladi
    (`uzlegal train verify`).
    """
    from uzlegal.config import get_registry
    from uzlegal.panel.review import SPOT_CHECK_RATE, review_sample
    from uzlegal.training.dataset import Dataset

    store = Dataset(dataset)
    try:
        samples = store.read()
    except Exception as exc:
        # `train seed` chiqishi TrainingSample emas — u hali javobsiz
        # savollar ro'yxati. Traceback o'rniga nima qilish kerakligini
        # aytamiz (loyihaning umumiy uslubi).
        console.print(
            f"[red]✕[/red] To'plam o'qilmadi: {dataset}\n"
            f"  [dim]{type(exc).__name__}: {str(exc).splitlines()[0]}[/dim]\n"
            "  Kengash **tayyor namunalar** ustida ishlaydi. Urug' savollardan\n"
            "  namuna yasash: [bold]uzlegal train seed[/bold] → generatsiya → shu buyruq."
        )
        raise typer.Exit(2) from exc

    if not samples:
        console.print(f"[red]✕[/red] To'plam bo'sh yoki topilmadi: {dataset}")
        raise typer.Exit(4)

    pending = [s for s in samples if not s.verified and not s.rejection_reason]
    if limit:
        pending = pending[:limit]

    console.print(
        f"To'plam: [bold]{dataset.name}[/bold] — {len(samples)} namuna, "
        f"{len(pending)} tasi kengashga tushadi\n"
    )

    if dry_run:
        _dry_run(pending, size)
        return

    ctx = _context(get_registry)
    if ctx is None:
        raise typer.Exit(4)

    counts: dict[str, int] = {}
    # Namunaviy tekshiruv **deterministik** tanlanadi: har `n` inchisi.
    # Tasodifiy tanlash bir xil to'plamda har safar boshqa natija berardi
    # va tekshiruvni takrorlab bo'lmasdi.
    step = max(1, round(1 / SPOT_CHECK_RATE))

    with console.status("kengash ishlamoqda…"):
        for i, sample in enumerate(pending):
            report = review_sample(sample, ctx, size=size, spot_check=(i % step == 0))
            sample.panel = report.model_dump(mode="json")
            if report.outcome == "rad":
                sample.rejection_reason = f"kengash: {report.reason}"
            counts[report.outcome] = counts.get(report.outcome, 0) + 1

    store.write(samples)
    _summary(counts, samples, json_out=json_out)


def _dry_run(pending: list[TrainingSample], size: int) -> None:
    """Modelsiz: faqat marshrutlash taqsimoti."""
    from uzlegal.panel.seniors import select

    spread: dict[str, int] = {}
    for sample in pending:
        text = f"{getattr(sample, 'question', '')}\n{getattr(sample, 'answer', '')}"
        for senior in select(text, size=size):
            spread[senior.key] = spread.get(senior.key, 0) + 1

    table = Table(show_header=True, header_style="bold")
    table.add_column("Senior", style="cyan")
    table.add_column("Namuna", justify="right")
    for key, count in sorted(spread.items(), key=lambda kv: -kv[1]):
        table.add_row(key, str(count))
    console.print(table)
    console.print("\n[dim]--dry-run: model chaqirilmadi, faqat marshrutlash.[/dim]")


def _context(get_registry: Any) -> AgentContext | None:
    from uzlegal.agents.base import SHARED_PREAMBLE, AgentContext, build_prefix

    try:
        registry = get_registry()
        backend = registry.backend()
    except Exception as exc:  # pragma: no cover — muhitga bog'liq
        console.print(
            f"[red]✕[/red] Model backendi tayyor emas: {exc}\n"
            "  Model tanlang: [bold]uzlegal models use <id>[/bold]\n"
            "  Yoki marshrutlashni modelsiz ko'ring: [bold]--dry-run[/bold]"
        )
        return None

    return AgentContext(
        question="",
        backend=backend,
        prefix=build_prefix(SHARED_PREAMBLE, ""),
        registry=registry,
    )


def _summary(counts: dict[str, int], samples: list[TrainingSample], *, json_out: bool) -> None:
    awaiting = sum(1 for s in samples if s.awaits_human)
    total = sum(counts.values()) or 1

    if json_out:
        console.print_json(
            _json.dumps({"natija": counts, "yurist_navbatida": awaiting}, ensure_ascii=False)
        )
        return

    labels = {
        "rad": ("[red]rad etildi[/red]", "yuristga ko'rsatilmaydi"),
        "noaniq": ("[yellow]noaniq[/yellow]", "yurist ko'radi"),
        "kengash-ma'qulladi": ("[green]ma'qullandi[/green]", "namunaviy tekshiruv"),
    }
    console.print()
    for key, (label, note) in labels.items():
        count = counts.get(key, 0)
        console.print(f"  {label:28}  {count:5}  ({count / total:4.0%})  [dim]{note}[/dim]")

    console.print(f"\n  [bold]Yurist navbatida: {awaiting}[/bold] / {total}")
    console.print(
        "  [dim]Kengash `verified` ga tegmadi — imzo `uzlegal train verify` da qoladi.[/dim]"
    )
