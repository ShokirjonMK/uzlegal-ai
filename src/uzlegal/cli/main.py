"""UzLegal-AI CLI."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from uzlegal.config import get_registry, get_settings
from uzlegal.inference.backend import available_backends
from uzlegal.types import GenerationParams

app = typer.Typer(help="UzLegal-AI — O'zbekiston huquqiy AI platformasi", no_args_is_help=True)
models_app = typer.Typer(help="Model boshqaruvi", no_args_is_help=True)
app.add_typer(models_app, name="models")

console = Console()


@app.callback()
def _root(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


# --------------------------------------------------------------------------- #
# models
# --------------------------------------------------------------------------- #


@models_app.command("list")
def models_list() -> None:
    """Katalogdagi modellar va ularning holati."""
    reg = get_registry()
    table = Table(box=None, pad_edge=False)
    table.add_column("", width=2)
    table.add_column("ID", style="bold")
    table.add_column("Nomi")
    table.add_column("Backend")
    table.add_column("Hajm", justify="right")
    table.add_column("Holat")

    for m in reg.list_models():
        mark = "●" if m.is_active else " "
        status = m.status.value
        if not m.fits_in_memory:
            status = "[red]sig'maydi[/red]"
        elif m.memory_warning:
            status = f"[yellow]{status}[/yellow]"
        elif m.status.value == "available":
            status = f"[green]{status}[/green]"
        table.add_row(
            f"[cyan]{mark}[/cyan]",
            m.spec.id,
            m.spec.display_name,
            m.spec.backend,
            f"{m.spec.size_gb:.1f} GB" if m.spec.size_gb else "—",
            status,
        )

    console.print(table)
    console.print(
        f"\nXotira: {reg.total_memory_gb:.0f} GB · "
        f"Backendlar: {', '.join(available_backends())} · "
        f"Faol: {reg.active_id or '[dim]yo’q[/dim]'}"
    )


@models_app.command("use")
def models_use(
    model_id: str,
    force: bool = typer.Option(
        False, "--force", help="Xotira ogohlantirishini e'tiborsiz qoldirish"
    ),
) -> None:
    """Modelni faollashtirish (eskisi bo'shatiladi)."""
    reg = get_registry()
    with console.status(f"'{model_id}' yuklanmoqda…"):
        try:
            info = reg.activate(model_id, force=force)
        except Exception as exc:
            console.print(f"[red]✕[/red] {exc}")
            raise typer.Exit(3) from exc
    console.print(f"[green]✓[/green] Faol model: [bold]{info.spec.display_name}[/bold]")
    if info.memory_warning:
        console.print(f"[yellow]⚠ {info.memory_warning}[/yellow]")


@models_app.command("pull")
def models_pull(model_id: str) -> None:
    """Modelni HuggingFace dan yuklab olib, MLX formatiga o'tkazish."""
    reg = get_registry()
    try:
        spec = reg.get_spec(model_id)
    except KeyError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(2) from exc

    if not spec.hf_id:
        console.print(f"[red]✕[/red] '{model_id}' uchun hf_id ko'rsatilmagan")
        raise typer.Exit(2)

    dest = Path(spec.local_path or f"models/{model_id}")
    if dest.exists():
        console.print(f"[green]✓[/green] Allaqachon mavjud: {dest}")
        return

    console.print(f"Yuklanmoqda: [bold]{spec.hf_id}[/bold] → {dest}")
    console.print(f"[dim]Hajm ~{spec.size_gb or '?'} GB, bu bir necha daqiqa olishi mumkin[/dim]\n")
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        console.print("[red]✕[/red] huggingface_hub o'rnatilmagan: uv pip install huggingface_hub")
        raise typer.Exit(1) from exc

    try:
        snapshot_download(
            repo_id=spec.hf_id,
            local_dir=str(dest),
            # Faqat inference uchun keraklisi — .pth/.bin dublikatlari o'tkazib yuboriladi
            allow_patterns=["*.safetensors", "*.json", "*.txt", "*.model", "*.jinja"],
            max_workers=4,
        )
    except Exception as exc:
        console.print(f"[red]✕[/red] Yuklab olinmadi: {exc}")
        raise typer.Exit(1) from exc

    reg.reload_catalog()
    console.print(
        f"\n[green]✓[/green] Tayyor. Faollashtirish: [bold]uzlegal models use {model_id}[/bold]"
    )


@models_app.command("unload")
def models_unload() -> None:
    """Modelni xotiradan bo'shatish."""
    get_registry().unload()
    console.print("[green]✓[/green] Xotira bo'shatildi")


@models_app.command("bench")
def models_bench(
    candidates: str = typer.Option(..., "--candidates", help="Vergul bilan ajratilgan ID lar"),
    suite: str = typer.Option("bench-uz-legal-v0", "--suite"),
) -> None:
    """Nomzod modellarni o'zbek yuridik to'plamida solishtirish (Faza 0, ADR-001)."""
    console.print("[yellow]Baholash to'plami hali tayyorlanmagan.[/yellow]")
    console.print(f"Kerak: data/eval/{suite}.jsonl — 100 ta o'zbekcha yuridik savol")
    console.print(f"Nomzodlar: {candidates}")
    console.print("\nTo'plam tayyor bo'lgach shu buyruq ularni o'lchab, ADR-001 ni to'ldiradi.")
    raise typer.Exit(4)


# --------------------------------------------------------------------------- #
# Asosiy buyruqlar
# --------------------------------------------------------------------------- #


@app.command()
def ask(
    question: str,
    role: str = typer.Option(
        None, "--role", "-r", help="jurist · advocate · prosecutor · professor · judge"
    ),
    max_tokens: int = typer.Option(512, "--max-tokens"),
    temperature: float = typer.Option(0.3, "--temperature"),
) -> None:
    """Savol berish (Faza 0 — xom generatsiya, RAG va agentlar hali yo'q)."""
    reg = get_registry()
    if reg.active_id is None and not reg.restore_state():
        console.print("[red]✕[/red] Faol model yo'q. `uzlegal models use <id>` bilan tanlang.")
        raise typer.Exit(3)

    try:
        if role:
            reg.set_adapter(role)
        backend = reg.backend
    except Exception as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(3) from exc

    params = GenerationParams(max_tokens=max_tokens, temperature=temperature)
    for token in backend.stream(question, params):
        console.print(token, end="")
    console.print()


@app.command()
def serve(
    host: str = typer.Option(None, "--host"),
    port: int = typer.Option(None, "--port"),
    profile: str = typer.Option(None, "--profile"),
) -> None:
    """API va Web UI ni ishga tushirish."""
    import os

    if profile:
        os.environ["UZLEGAL_PROFILE"] = profile

    from uzlegal.api.app import serve as _serve

    settings = get_settings()
    url = f"http://{host or settings.api_host}:{port or settings.api_port}"
    console.print(f"[bold]UzLegal-AI[/bold] · profil: {settings.profile}")
    console.print(f"Web UI:  {url}")
    console.print(f"API doc: {url}/docs\n")
    _serve(host, port)


@app.command()
def doctor() -> None:
    """Muhit diagnostikasi."""
    settings = get_settings()
    ok = True

    console.print("[bold]Muhit[/bold]")
    console.print(f"  Python        {sys.version.split()[0]}")
    console.print(f"  Profil        {settings.profile}")

    try:
        import mlx.core as mx

        metal = mx.metal.is_available()
        console.print(
            f"  MLX           [green]o'rnatilgan[/green], Metal: {'ha' if metal else 'yo’q'}"
        )
        if not metal:
            ok = False
    except ImportError:
        console.print("  MLX           [yellow]o'rnatilmagan[/yellow] (uv pip install -e '.[mac]')")

    console.print(f"  Backendlar    {', '.join(available_backends())}")

    reg = get_registry()
    console.print(f"  Xotira        {reg.total_memory_gb:.0f} GB")

    wired = subprocess.run(["sysctl", "-n", "iogpu.wired_limit_mb"], capture_output=True, text=True)
    if wired.returncode == 0:
        mb = int(wired.stdout.strip() or 0)
        if mb == 0:
            console.print(
                "  GPU chegarasi [yellow]sozlanmagan[/yellow] (sudo sysctl iogpu.wired_limit_mb=20480)"
            )
        else:
            console.print(f"  GPU chegarasi {mb} MB")

    console.print("\n[bold]Katalog[/bold]")
    models = reg.list_models()
    ready = sum(1 for m in models if m.status.value in ("available", "active"))
    console.print(f"  Modellar      {len(models)} ta, {ready} tasi tayyor")
    console.print(f"  Faol          {reg.active_id or '[dim]yo’q[/dim]'}")

    console.print("\n[bold]Bilim bazasi[/bold]")
    console.print("  [dim]Faza 2 da quriladi[/dim]")

    console.print(
        f"\n{'[green]✓ Muhit tayyor[/green]' if ok else '[yellow]⚠ E’tibor talab qiladi[/yellow]'}"
    )


if __name__ == "__main__":
    app()
