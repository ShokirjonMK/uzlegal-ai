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
eval_app = typer.Typer(help="Baholash", no_args_is_help=True)
kb_app = typer.Typer(help="Bilim bazasi", no_args_is_help=True)
index_app = typer.Typer(help="Indeks", no_args_is_help=True)
app.add_typer(models_app, name="models")
app.add_typer(eval_app, name="eval")
app.add_typer(kb_app, name="kb")
app.add_typer(index_app, name="index")

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


@eval_app.command("bench")
def eval_bench(
    candidates: str = typer.Option(..., "--candidates", help="Vergul bilan ajratilgan model ID lari"),
    suite: str = typer.Option("bench-uz-legal-v0", "--suite"),
    limit: int = typer.Option(None, "--limit", help="Faqat birinchi N savol (tez sinov)"),
    out: Path = typer.Option(Path("reports/model-selection.md"), "--out"),
) -> None:
    """Nomzod modellarni o'zbek yuridik to'plamida solishtirish (Faza 0, ADR-001)."""
    from uzlegal.eval.bench import decide, load_items, render_report, run_model

    suite_dir = Path("data/eval") / suite
    if not (suite_dir / "items.jsonl").exists():
        console.print(f"[red]✕[/red] To'plam topilmadi: {suite_dir}/items.jsonl")
        raise typer.Exit(4)

    items = load_items(suite_dir, limit)
    ids = [c.strip() for c in candidates.split(",") if c.strip()]
    console.print(f"To'plam: [bold]{suite}[/bold] — {len(items)} savol")
    console.print(f"Nomzodlar: {', '.join(ids)}\n")

    reg = get_registry()
    scores = []
    for model_id in ids:
        console.print(f"[bold]{model_id}[/bold] baholanmoqda…")
        try:
            with console.status(f"{model_id}: {len(items)} savol"):
                score = run_model(reg, model_id, items)
        except Exception as exc:
            console.print(f"  [red]✕ o'tkazib yuborildi: {exc}[/red]")
            continue
        scores.append(score)
        console.print(
            f"  ball {score.weighted:.2f}/5 · o'zbek {score.uzbek_fluency * 5:.2f} · "
            f"mulohaza {score.context_reasoning:.0%} · {score.tokens_per_second:.1f} tok/s"
        )
        raw = out.parent / f"bench-{model_id}.jsonl"
        raw.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        raw.write_text(
            "\n".join(
                _json.dumps(
                    {"id": i.item_id, "category": i.category, "answer": i.answer,
                     "failures": i.failures, "lang": round(i.lang_score, 2)},
                    ensure_ascii=False,
                )
                for i in score.items
            ),
            encoding="utf-8",
        )

    if not scores:
        console.print("[red]✕[/red] Hech bir model baholanmadi")
        raise typer.Exit(1)

    winner, notes = decide(scores)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(scores, winner, notes), encoding="utf-8")

    console.print(f"\n[bold]Natija:[/bold] {out}")
    for n in notes:
        console.print(f"  {n}")
    if winner:
        console.print(f"\n[green]⭐ Tanlangan model: [bold]{winner}[/bold][/green]")


# --------------------------------------------------------------------------- #
# Bilim bazasi
# --------------------------------------------------------------------------- #


@kb_app.command("status")
def kb_status() -> None:
    """Bilim bazasi holati: oxirgi yangilash, muddat, tarix."""
    from uzlegal.ingest.sync import SyncManager

    info = SyncManager().info()
    console.print(f"Holat          {info['status']}")
    console.print(f"Versiya        {info['kb_version'] or '[dim]qurilmagan[/dim]'}")
    console.print(f"Oxirgi yangilash  {info['last_sync_at'] or '[dim]hech qachon[/dim]'}"
                  + (f" ({info['age_days']} kun)" if info['age_days'] is not None else ""))
    console.print(f"Keyingi muddat    {info['next_due_at'] or '—'}")
    console.print(f"Avtomatik      {'yoqilgan' if info['auto_enabled'] else 'o’chirilgan'}"
                  f", har {info['interval_days']} kunda")
    if info["is_stale"]:
        console.print("\n[yellow]⚠ Bilim bazasi eskirgan — bekor qilingan normalar xavfi bor.[/yellow]")
    elif info["is_due"]:
        console.print("\n[yellow]⏰ Yangilash muddati keldi.[/yellow]")


@kb_app.command("sync")
def kb_sync(
    docs: str = typer.Option(None, "--docs", help="Vergul bilan ajratilgan hujjat ID lari"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Tugashini kutish"),
) -> None:
    """Bilim bazasini yangilash.

    Diqqat: lex.uz `Crawl-delay: 20` talab qiladi — har hujjat kamida 20 soniya.
    """
    import time as _time

    from uzlegal.ingest.sync import SyncAlreadyRunningError, SyncManager, SyncStatus

    manager = SyncManager()
    doc_ids = [d.strip() for d in docs.split(",")] if docs else None
    try:
        report = manager.start(trigger="manual", doc_ids=doc_ids)
    except SyncAlreadyRunningError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"Boshlandi: {report.run_id} — {report.total} hujjat")
    console.print(f"[dim]Taxminiy vaqt: ~{report.total * 20 // 60 + 1} daqiqa (Crawl-delay 20 s)[/dim]\n")
    if not wait:
        return

    with console.status("yangilanmoqda…") as status:
        while manager.status is SyncStatus.RUNNING:
            cur = manager.current
            if cur:
                status.update(
                    f"{cur.processed}/{cur.total} · yangi {cur.new} · "
                    f"o'zgargan {cur.changed} · o'zgarmagan {cur.unchanged} · xato {cur.errors}"
                )
            _time.sleep(1)

    cur = manager.current
    if cur is None:
        return
    console.print(
        f"[green]✓[/green] {cur.status.value} — yangi {cur.new}, o'zgargan {cur.changed}, "
        f"o'zgarmagan {cur.unchanged}, xato {cur.errors} ({cur.duration_s:.0f} s)"
    )
    for d in cur.documents:
        if d.status in ("new", "changed"):
            console.print(f"  {d.status:9} {d.doc_id}  {d.articles or 0} modda"
                          + (f", {d.amendments} o'zgartirish" if d.amendments else ""))
        elif d.status == "error":
            console.print(f"  [red]error[/red]     {d.doc_id}  {d.error}")


@kb_app.command("config")
def kb_config(
    interval: int = typer.Option(None, "--interval", help="Yangilash oralig'i (kun)"),
    auto: bool = typer.Option(None, "--auto/--no-auto", help="Avtomatik yangilash"),
) -> None:
    """Avtomatik yangilash sozlamalari."""
    from uzlegal.ingest.sync import SyncManager

    manager = SyncManager()
    try:
        manager.configure(interval_days=interval, auto_enabled=auto)
    except ValueError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(2) from exc
    console.print(f"[green]✓[/green] Avtomatik: "
                  f"{'yoqilgan' if manager.state.auto_enabled else 'o’chirilgan'}, "
                  f"har {manager.state.interval_days} kunda")


@kb_app.command("parse")
def kb_parse(
    doc_id: str = typer.Argument(..., help="Hujjat ID (arxivdan o'qiladi)"),
) -> None:
    """Arxivdagi hujjatni ajratib, statistikasini ko'rsatish (tarmoqsiz)."""
    from uzlegal.ingest.connectors.lex_uz import LexUzConnector
    from uzlegal.ingest.parsers.lex_uz import LexUzParser

    raw = LexUzConnector().load_cached(doc_id)
    if raw is None:
        console.print(f"[red]✕[/red] Arxivda topilmadi: {doc_id}. Avval: uzlegal kb sync --docs {doc_id}")
        raise typer.Exit(4)

    doc = LexUzParser().parse(raw)
    console.print(f"[bold]{doc.title[:90]}[/bold]")
    console.print(f"  turi {doc.doc_type} · til {doc.lang} · qabul {doc.adopted_at or '—'}")
    console.print(f"  {doc.stats()}")
    console.print(f"  o'zgartirish eslatmalari: {len(doc.amendments)}")
    empty = [a for a in doc.articles if len(a.body) < 30]
    if empty:
        console.print(f"  [yellow]tanasi bo'sh moddalar: {len(empty)}[/yellow]")
    for w in doc.warnings[:5]:
        console.print(f"  [yellow]⚠ {w}[/yellow]")


# --------------------------------------------------------------------------- #
# Indeks
# --------------------------------------------------------------------------- #


@index_app.command("build")
def index_build(
    docs: str = typer.Option(None, "--docs", help="Hujjat ID lari (standart: arxivdagi hammasi)"),
    out: Path = typer.Option(Path("kb/current"), "--out"),
    batch_size: int = typer.Option(16, "--batch-size"),
) -> None:
    """Arxivdagi hujjatlardan qidiruv indeksini qurish (tarmoqsiz)."""
    from uzlegal.index.chunker import Chunker
    from uzlegal.index.embedder import Embedder
    from uzlegal.index.store import KnowledgeIndex
    from uzlegal.ingest.connectors.lex_uz import LexUzConnector
    from uzlegal.ingest.parsers.lex_uz import LexUzParser
    from uzlegal.ingest.sync import SyncManager

    connector = LexUzConnector()
    ids = ([d.strip() for d in docs.split(",")] if docs
           else sorted(p.stem for p in connector.raw_dir.glob("*.html")))
    if not ids:
        console.print("[red]✕[/red] Arxiv bo'sh. Avval: uzlegal kb sync")
        raise typer.Exit(4)

    parser, chunker = LexUzParser(), Chunker()
    chunks = []
    for doc_id in ids:
        raw = connector.load_cached(doc_id)
        if raw is None:
            console.print(f"  [yellow]⚠ arxivda yo'q: {doc_id}[/yellow]")
            continue
        doc = parser.parse(raw)
        produced = chunker.chunk_document(doc)
        chunks.extend(produced)
        console.print(f"  {doc_id}  {len(doc.articles)} modda → {len(produced)} chunk")

    if not chunks:
        console.print("[red]✕[/red] Chunk yaratilmadi")
        raise typer.Exit(1)

    console.print(f"\nJami {len(chunks)} chunk. Embedding (~{len(chunks) / 4:.0f} s)…")
    embedder = Embedder(batch_size=batch_size)
    with console.status("vektorlar hisoblanmoqda…"):
        vectors = embedder.encode([c.indexed_text for c in chunks])

    KnowledgeIndex(out).build(chunks, vectors, kb_version=SyncManager().state.kb_version)
    console.print(f"[green]✓[/green] Indeks tayyor: {out}")


@index_app.command("stats")
def index_stats(path: Path = typer.Option(Path("kb/current"), "--path")) -> None:
    """Indeks statistikasi."""
    from uzlegal.index.store import KnowledgeIndex

    index = KnowledgeIndex(path)
    if not index.exists():
        console.print(f"[red]✕[/red] Indeks yo'q: {path}. Quring: uzlegal index build")
        raise typer.Exit(4)
    for key, value in index.meta.items():
        console.print(f"  {key:12} {value}")


@app.command()
def search(
    query: str,
    top_k: int = typer.Option(8, "--top-k", "-k"),
    as_of: str = typer.Option(None, "--as-of", help="Tarixiy holat, YYYY-MM-DD"),
    full: bool = typer.Option(False, "--full", help="To'liq matn"),
) -> None:
    """Qonunchilikda qidirish (modelsiz — tez va arzon)."""
    from datetime import date as _date

    from uzlegal.index.store import IndexNotBuiltError, KnowledgeIndex
    from uzlegal.retrieval.hybrid import HybridRetriever

    retriever = HybridRetriever(KnowledgeIndex())
    try:
        result = retriever.search(
            query, top_k=top_k, as_of=_date.fromisoformat(as_of) if as_of else None
        )
    except IndexNotBuiltError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(4) from exc

    console.print(
        f"[dim]{result.query_kind} · {result.latency_ms} ms · "
        f"vektor {result.vector_hits} · leksik {result.lexical_hits}"
        + (f" · versiya filtri {result.dropped_by_version} ta chiqardi"
           if result.dropped_by_version else "") + "[/dim]\n"
    )
    if not result.results:
        console.print("[yellow]Ishonchli manba topilmadi.[/yellow]")
        raise typer.Exit(5)

    for i, item in enumerate(result.results, 1):
        chunk = item.chunk
        console.print(f"[bold]{i}. {chunk.citation_label}[/bold]  [dim]{item.score:.4f}[/dim]")
        text = chunk.content if full else chunk.content[:220]
        console.print(f"   {text}{'' if full else '…'}")
        console.print(f"   [dim]{chunk.source_url}[/dim]\n")


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
