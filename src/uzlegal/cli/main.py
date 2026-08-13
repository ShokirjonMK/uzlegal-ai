"""UzLegal-AI CLI."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from uzlegal import signature as sig
from uzlegal.cli.license import license_app
from uzlegal.config import get_registry, get_settings
from uzlegal.core import ConsultResult
from uzlegal.inference.backend import available_backends
from uzlegal.ingest.types import unit_label

app = typer.Typer(help="UzLegal-AI — O'zbekiston huquqiy AI platformasi", no_args_is_help=True)
models_app = typer.Typer(help="Model boshqaruvi", no_args_is_help=True)
eval_app = typer.Typer(help="Baholash", no_args_is_help=True)
kb_app = typer.Typer(help="Bilim bazasi", no_args_is_help=True)
index_app = typer.Typer(help="Indeks", no_args_is_help=True)
app.add_typer(models_app, name="models")
app.add_typer(eval_app, name="eval")
app.add_typer(kb_app, name="kb")
app.add_typer(index_app, name="index")
app.add_typer(license_app, name="license")

# Modul sub-applari. Har bir modul o'z faylida Typer ilovasini yaratadi va
# faqat shu yerda ulanadi — shunda parallel ishlashda to'qnashuv bo'lmaydi.
for _module, _attr, _name in (
    ("uzlegal.cli.pipeline", "pipeline_app", "pipeline"),
    ("uzlegal.cli.train", "train_app", "train"),
):
    try:
        app.add_typer(getattr(__import__(_module, fromlist=[_attr]), _attr), name=_name)
    except ImportError as _exc:  # pragma: no cover — modul hali qo'shilmagan
        logging.getLogger(__name__).debug("'%s' sub-app ulanmadi: %s", _name, _exc)

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


@eval_app.command("retrieval")
def eval_retrieval(
    suite: str = typer.Option("retrieval-gold-v1", "--suite"),
    rerank: bool = typer.Option(False, "--rerank/--no-rerank"),
    top_k: int = typer.Option(10, "--top-k"),
    out: Path = typer.Option(None, "--out"),
) -> None:
    """Retrieval sifatini o'lchash (Recall@k, MRR) — modelsiz."""
    from uzlegal.eval.retrieval_eval import load_cases, render_report, run_eval
    from uzlegal.index.store import IndexNotBuiltError, KnowledgeIndex
    from uzlegal.retrieval.hybrid import HybridRetriever

    path = Path("data/eval") / suite / "cases.jsonl"
    if not path.exists():
        console.print(f"[red]✕[/red] To'plam topilmadi: {path}")
        raise typer.Exit(4)

    cases = load_cases(path)
    console.print(
        f"To'plam: [bold]{suite}[/bold] — {len(cases)} holat"
        f"{' · reranker yoqilgan' if rerank else ''}\n"
    )

    retriever = HybridRetriever(KnowledgeIndex())
    try:
        with console.status("baholanmoqda…"):
            report = run_eval(retriever, cases, top_k=top_k, rerank=rerank)
    except IndexNotBuiltError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(4) from exc

    from uzlegal.eval.retrieval_eval import TARGETS

    for name, target in TARGETS.items():
        value = report.mrr if name == "mrr" else report.recall_at(int(name.split("@")[1]))
        mark = "[green]✅[/green]" if value >= target else "[red]❌[/red]"
        console.print(f"  {name:12} {value:6.0%}  (maqsad {target:.0%})  {mark}")
    leak = report.deprecated_leak
    console.print(
        f"  {'deprecated':12} {leak:6.0%}  (maqsad 0%)   "
        f"{'[green]✅[/green]' if leak == 0 else '[red]❌[/red]'}"
    )
    console.print(
        f"  {'kechikish':12} {report.median_latency_ms:4d} ms median, "
        f"{report.p95_latency_ms} ms p95"
    )

    if report.failures:
        console.print(f"\n[yellow]Topilmagan ({len(report.failures)}):[/yellow]")
        for r in report.failures[:8]:
            console.print(f"  {r.case.id:10} {r.case.query[:52]}")
            console.print(
                f"             kutilgan {r.case.expected_articles} · olindi {r.top_articles}"
            )

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_report(report, "reranker" if rerank else "gibrid"), encoding="utf-8")
        console.print(f"\n[green]✓[/green] Hisobot: {out}")


def _consult_for_eval(question: str, **kwargs: object) -> ConsultResult:
    """`run_suite` kutgan shakl ↔ `core.consult()` shartnomasi orasidagi ko'prik.

    ## Nima uchun bu funksiya kerak

    `run_suite(cases, consult, …)` chaqiriladigan funksiyani
    `consult(savol, mode=…)` deb chaqiradi — bu uning **sinaladigan
    chegarasi** va unit testlar shu shakldagi stub beradi.

    `uzlegal.core.consult()` esa boshqacha: u `ConsultRequest` obyektini
    oladi. Ilgari CLI unga to'g'ridan-to'g'ri `core.consult` ni uzatardi,
    natijada HAR BIR holat `consult() got an unexpected keyword argument
    'mode'` xatosi bilan yiqilardi va butun `eval run` / `eval safety`
    hech qachon ishlamagan edi.

    Unit testlar buni tutmasdi, chunki ularning hammasi stub ishlatadi va
    hech biri haqiqiy `consult` ni ulamaydi — mumtoz integratsiya
    bo'shlig'i. `test_eval_suite.py` dagi imzo testi endi shuni
    qo'riqlaydi.
    """
    from uzlegal.core import ConsultRequest, consult

    mode = str(kwargs.get("mode") or "simple")
    return consult(ConsultRequest(question=question, mode=mode))  # type: ignore[arg-type]


def _run_suite(
    suite: str,
    mode: str,
    limit: int | None,
    out: Path | None,
    target: float | None = None,
) -> object:
    """Baholash to'plamini yurgizadi va hisobotni chiqaradi (umumiy qism)."""
    from uzlegal.eval.suite import load_suite, render_report, run_suite

    try:
        cases = load_suite(suite)
    except FileNotFoundError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(4) from exc

    if limit:
        cases = cases[:limit]
    console.print(f"To'plam: [bold]{suite}[/bold] — {len(cases)} holat · rejim {mode}\n")

    with console.status("baholanmoqda…") as status:

        def progress(i: int, outcome: object) -> None:
            passed = getattr(outcome, "passed", False)
            case_id = getattr(getattr(outcome, "case", None), "id", "?")
            status.update(f"{i}/{len(cases)} · {case_id} {'✓' if passed else '✕'}")

        report = run_suite(
            cases, _consult_for_eval, suite=suite, default_mode=mode, on_case=progress
        )

    console.print(f"  {'o’tdi':16} {report.pass_rate:6.0%}")
    console.print(f"  {'o’zbek tili':16} {report.language_score:6.2f}")
    console.print(f"  {'gate o’chirdi':16} {report.gate_drop_rate:6.0%}")
    console.print(f"  {'kechikish':16} {report.median_latency_s:6.1f} s median")

    if report.failures:
        console.print(f"\n[yellow]Yiqilgan ({len(report.failures)}):[/yellow]")
        for outcome in report.failures[:10]:
            console.print(
                f"  [dim]{outcome.diagnosis:9}[/dim] {outcome.case.id:12} "
                f"{'; '.join(outcome.failures)[:70]}"
            )
        console.print(
            "\n  Tashxis: " + ", ".join(f"{k} {v}" for k, v in report.by_diagnosis().items())
        )

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_report(report, target=target), encoding="utf-8")
        console.print(f"\n[green]✓[/green] Hisobot: {out}")

    return report


@eval_app.command("run")
def eval_run(
    suite: str = typer.Option("smoke-50", "--suite"),
    mode: str = typer.Option("simple", "--mode", help="simple · standard · complex"),
    limit: int = typer.Option(None, "--limit", help="Faqat birinchi N holat"),
    fail_under: float = typer.Option(None, "--fail-under", help="Shu ulushdan past bo'lsa xato"),
    out: Path = typer.Option(None, "--out"),
) -> None:
    """Uchidan-uchiga sifat baholash — savol → RAG → agentlar → gate."""
    report = _run_suite(suite, mode, limit, out, target=fail_under)
    rate = report.pass_rate  # type: ignore[attr-defined]

    if fail_under is not None and rate < fail_under:
        console.print(f"\n[red]✕ {rate:.0%} < {fail_under:.0%} — chegaradan past[/red]")
        raise typer.Exit(1)
    console.print("\n[green]✓ Baholash o'tdi[/green]")


@eval_app.command("safety")
def eval_safety(
    suite: str = typer.Option("traps-30", "--suite"),
    mode: str = typer.Option("simple", "--mode"),
    limit: int = typer.Option(None, "--limit"),
    max_failures: int = typer.Option(None, "--max-failures", help="Ruxsat etilgan nosozlik soni"),
    out: Path = typer.Option(None, "--out"),
) -> None:
    """Xavfsizlik tuzoqlari — tizim nima **qilmasligi** kerakligini o'lchaydi.

    Bu yerda «manba topilmadi» to'g'ri javob: mavjud bo'lmagan modda
    haqida so'ralganda uni o'ylab topmaslik kerak.
    """
    report = _run_suite(suite, mode, limit, out)
    failures = len(report.failures)  # type: ignore[attr-defined]

    if max_failures is not None and failures > max_failures:
        console.print(f"\n[red]✕ {failures} nosozlik > {max_failures} ruxsat etilgan[/red]")
        raise typer.Exit(1)

    # Chegara berilmagan bo'lsa ham nosozlik bo'lsa — «o'tdi» deyilmaydi.
    # Ilgari bu yerda «✓ Xavfsizlik tekshiruvi o'tdi (30 nosozlik)» degan
    # o'zini o'zi inkor qiladigan xabar chiqardi. Xavfsizlik to'plamida
    # bu ayniqsa xavfli: u tizim mavjud bo'lmagan moddani o'ylab
    # topmasligini o'lchaydi, ya'ni nosozlik bu yerda «yaxshi emas,
    # lekin o'tadi» degani emas.
    if failures:
        console.print(
            f"\n[yellow]⚠ {failures} nosozlik[/yellow] — chegara ko'rsatilmagan "
            f"(`--max-failures N` bilan majburlang)"
        )
        return
    console.print("\n[green]✓ Xavfsizlik tekshiruvi o'tdi[/green] — nosozliksiz")


@eval_app.command("citations")
def eval_citations(
    suite: str = typer.Option("smoke-50", "--suite"),
    mode: str = typer.Option("simple", "--mode"),
    limit: int = typer.Option(12, "--limit", help="Nechta holat tekshirilsin"),
    strict: bool = typer.Option(False, "--strict", help="Bitta muammo ham xato hisoblanadi"),
) -> None:
    """Iqtibos yaxlitligi — javobdagi har bir havola haqiqiy normaga bog'lanadimi.

    Uch invariant tekshiriladi va uchalasi ham deterministik:
    iqtibos indeksda mavjudmi · bekor qilingan normaga ishora qilmaydimi ·
    javobdagi har bir `[C…]` belgisi iqtiboslar ro'yxatida bormi.
    """
    from uzlegal.core import ConsultRequest, consult
    from uzlegal.eval.suite import check_citations, load_suite
    from uzlegal.index.store import KnowledgeIndex

    try:
        cases = load_suite(suite)[:limit]
    except FileNotFoundError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(4) from exc

    index = KnowledgeIndex()
    issues = []
    checked = 0
    console.print(f"Iqtibos yaxlitligi: [bold]{suite}[/bold] — {len(cases)} holat\n")

    with console.status("tekshirilmoqda…") as status:
        for i, case in enumerate(cases, 1):
            status.update(f"{i}/{len(cases)} · {case.id}")
            try:
                result = consult(
                    ConsultRequest(question=case.question, mode=case.mode or mode)  # type: ignore[arg-type]
                )
            except Exception as exc:
                console.print(f"  [yellow]⚠ {case.id}: {exc}[/yellow]")
                continue
            checked += 1
            issues.extend(check_citations(result, index, case.id))

    console.print(f"  {'tekshirildi':16} {checked} holat")
    console.print(f"  {'muammo':16} {len(issues)}")

    for issue in issues[:15]:
        console.print(f"  [red]✕[/red] {issue.case_id:12} {issue.kind:14} {issue.detail}")

    if issues and strict:
        console.print(f"\n[red]✕ {len(issues)} iqtibos muammosi (--strict)[/red]")
        raise typer.Exit(1)
    if not issues:
        console.print("\n[green]✓ Barcha iqtiboslar haqiqiy normaga bog'langan[/green]")


@eval_app.command("bench")
def eval_bench(
    candidates: str = typer.Option(
        ..., "--candidates", help="Vergul bilan ajratilgan model ID lari"
    ),
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
                    {
                        "id": i.item_id,
                        "category": i.category,
                        "answer": i.answer,
                        "failures": i.failures,
                        "lang": round(i.lang_score, 2),
                    },
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
    console.print(
        f"Oxirgi yangilash  {info['last_sync_at'] or '[dim]hech qachon[/dim]'}"
        + (f" ({info['age_days']} kun)" if info["age_days"] is not None else "")
    )
    console.print(f"Keyingi muddat    {info['next_due_at'] or '—'}")
    console.print(
        f"Avtomatik      {'yoqilgan' if info['auto_enabled'] else 'o’chirilgan'}"
        f", har {info['interval_days']} kunda"
    )
    if info["is_stale"]:
        console.print(
            "\n[yellow]⚠ Bilim bazasi eskirgan — bekor qilingan normalar xavfi bor.[/yellow]"
        )
    elif info["is_due"]:
        console.print("\n[yellow]⏰ Yangilash muddati keldi.[/yellow]")


@kb_app.command("sync")
def kb_sync(
    docs: str = typer.Option(None, "--docs", help="Vergul bilan ajratilgan hujjat ID lari"),
    wait: bool = typer.Option(True, "--wait/--no-wait", help="Tugashini kutish"),
    from_catalog: bool = typer.Option(
        False, "--from-catalog", help="configs/discovered.yaml dagi barcha hujjatlar"
    ),
    skip_existing: bool = typer.Option(
        True, "--skip-existing/--all", help="Arxivda bor hujjatlarni o'tkazib yuborish"
    ),
) -> None:
    """Bilim bazasini yangilash.

    Diqqat: lex.uz `Crawl-delay: 20` talab qiladi — har hujjat kamida 20 soniya.

    `--from-catalog` — `kb discover --broad` qurgan katalogdan yuklaydi.
    `--skip-existing` standart holda yoqilgan: arxivda bor hujjat qayta
    yuklanmaydi. Bu uzilgan yurishni davom ettirish imkonini beradi —
    40 000 hujjatlik korpusda bu majburiy xususiyat.
    """
    import time as _time

    from uzlegal.ingest.sync import SyncAlreadyRunningError, SyncManager, SyncStatus

    manager = SyncManager()
    doc_ids = [d.strip() for d in docs.split(",")] if docs else None

    if from_catalog:
        import yaml as _yaml

        catalog = Path("configs/discovered.yaml")
        if not catalog.exists():
            console.print(f"[red]✕[/red] Katalog yo'q: {catalog}")
            console.print("[dim]Avval: uzlegal kb discover --broad[/dim]")
            raise typer.Exit(4)

        data = _yaml.safe_load(catalog.read_text(encoding="utf-8")) or {}
        doc_ids = [str(d["doc_id"]) for d in (data.get("documents") or [])]

        if skip_existing:
            from uzlegal.ingest.connectors.lex_uz import LexUzConnector

            conn = LexUzConnector()
            before = len(doc_ids)
            doc_ids = [d for d in doc_ids if not conn.raw_path(d).exists()]
            console.print(
                f"Katalog: {before} hujjat · arxivda bor: {before - len(doc_ids)} · "
                f"yuklanadi: [bold]{len(doc_ids)}[/bold]"
            )

        if not doc_ids:
            console.print("[green]✓[/green] Hammasi allaqachon arxivda")
            return

    try:
        report = manager.start(trigger="manual", doc_ids=doc_ids)
    except SyncAlreadyRunningError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(f"Boshlandi: {report.run_id} — {report.total} hujjat")
    console.print(
        f"[dim]Taxminiy vaqt: ~{report.total * 20 // 60 + 1} daqiqa (Crawl-delay 20 s)[/dim]\n"
    )
    if not wait:
        # `SyncManager` ishni **daemon oqimda** bajaradi. CLI shu yerda
        # qaytsa Python jarayoni tugaydi va daemon oqim u bilan birga
        # o'ladi — bitta ham hujjat yuklanmaydi.
        #
        # Bu jimgina sodir bo'lardi: buyruq «Boshlandi: sync_… — 843
        # hujjat» deb yozib chiqib ketardi, arxivda esa hech narsa
        # paydo bo'lmasdi. Amalda kuzatildi.
        #
        # Haqiqiy fon rejimi server jarayonida bo'ladi — u tugamaydi.
        console.print(
            "[yellow]⚠ `--no-wait` CLI da ishlamaydi[/yellow] — buyruq tugashi bilan "
            "fon oqimi ham to'xtaydi.\n"
            "  Fon rejimi uchun API ni ishlating (server jarayoni tugamaydi):\n"
            "    [bold]curl -X POST localhost:8080/v1/admin/sync -H 'X-API-Key: …'[/bold]\n"
            "  Yoki buyruqni terminalda qoldiring: [bold]uzlegal kb sync --from-catalog[/bold]"
        )
        manager.cancel()
        raise typer.Exit(2)

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
            console.print(
                f"  {d.status:9} {d.doc_id}  {d.articles or 0} modda"
                + (f", {d.amendments} o'zgartirish" if d.amendments else "")
            )
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
    console.print(
        f"[green]✓[/green] Avtomatik: "
        f"{'yoqilgan' if manager.state.auto_enabled else 'o’chirilgan'}, "
        f"har {manager.state.interval_days} kunda"
    )


@kb_app.command("discover")
def kb_discover(
    query: str = typer.Option("kodeks", "--query", "-q"),
    form: str = typer.Option("kodeks", "--form", help="kodeks · qonun · farmon · qaror"),
    save: bool = typer.Option(False, "--save", help="Natijani configs/discovered.yaml ga yozish"),
    broad: bool = typer.Option(
        False, "--broad", help="Keng kashfiyot: lug'at bo'yicha barcha shakllar"
    ),
    with_russian: bool = typer.Option(False, "--ru", help="Rus nashrlarini ham qidirish"),
    limit: int = typer.Option(0, "--limit", help="So'rovlar sonini cheklash (sinov uchun)"),
) -> None:
    """lex.uz da hujjatlarni qidirib topish.

    `--broad` — huquqiy sohalar lug'ati bo'yicha keng kashfiyot. lex.uz
    bir so'rovga 20 ta natija beradi va sahifalashni qo'llab-quvvatlamaydi,
    shuning uchun katalog **ko'p tor so'rov** bilan quriladi.

    DIQQAT: har so'rov `Crawl-delay: 20` bo'yicha 20 soniya oladi.
    To'liq keng kashfiyot ≈ 220 so'rov ≈ 73 daqiqa (rus bilan 2×).
    """
    if broad:
        _kb_discover_broad(with_russian=with_russian, limit=limit)
        return

    import yaml as _yaml

    from uzlegal.ingest.connectors.lex_uz import LexUzConnector
    from uzlegal.ingest.discover import (
        FORM_CODE,
        FORM_DECREE,
        FORM_LAW,
        FORM_RESOLUTION,
        DiscoveryQuery,
        LexUzDiscovery,
    )

    forms = {
        "kodeks": FORM_CODE,
        "qonun": FORM_LAW,
        "farmon": FORM_DECREE,
        "qaror": FORM_RESOLUTION,
    }
    if form not in forms:
        console.print(f"[red]✕[/red] Noma'lum shakl: {form}. Mavjud: {', '.join(forms)}")
        raise typer.Exit(2)

    with LexUzConnector() as conn:
        refs = LexUzDiscovery(conn).search(DiscoveryQuery(query=query, form_id=forms[form]))

    console.print(f"Topildi: [bold]{len(refs)}[/bold] ta {form} (o'zbek lotin, amaldagi)\n")
    for ref in refs:
        console.print(f"  {ref.doc_id:>10}  {(ref.title or '')[:72]}")

    if save:
        out = Path("configs/discovered.yaml")
        out.write_text(
            _yaml.safe_dump(
                {
                    "documents": [
                        {"doc_id": r.doc_id, "title": r.title, "type": r.doc_type} for r in refs
                    ]
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        console.print(f"\n[green]✓[/green] Saqlandi: {out}")


def _kb_discover_broad(*, with_russian: bool, limit: int) -> None:
    """Lug'at bo'yicha keng kashfiyot — katalogni bosqichma-bosqich quradi.

    Natija HAR SO'ROVDAN KEYIN saqlanadi. Sabab amaliy: to'liq yurish
    bir soatdan oshadi va u uzilishi mumkin (tarmoq, Ctrl+C, qayta
    ishga tushirish). Oxirida bir marta yozilsa, uzilgan yurishning
    butun mehnati yo'qolardi.
    """
    import yaml as _yaml

    from uzlegal.ingest.connectors.lex_uz import LexUzConnector
    from uzlegal.ingest.discover import (
        LANG_RU,
        LANG_UZ_LATIN,
        LexUzDiscovery,
        broad_queries,
    )

    langs = (LANG_UZ_LATIN, LANG_RU) if with_russian else (LANG_UZ_LATIN,)
    queries = broad_queries(langs=langs)
    if limit:
        queries = queries[:limit]

    out = Path("configs/discovered.yaml")
    known: dict[str, dict[str, str | None]] = {}
    if out.exists():
        existing = _yaml.safe_load(out.read_text(encoding="utf-8")) or {}
        for item in existing.get("documents") or []:
            known[str(item["doc_id"])] = item

    minutes = len(queries) * 20 / 60
    console.print(
        f"Keng kashfiyot: [bold]{len(queries)}[/bold] so'rov · "
        f"taxminan [bold]{minutes:.0f} daqiqa[/bold] (Crawl-delay 20 s)\n"
        f"[dim]Avvaldan ma'lum: {len(known)} hujjat. Natija har so'rovdan keyin saqlanadi.[/dim]\n"
    )

    with LexUzConnector() as conn:
        discovery = LexUzDiscovery(conn)
        for i, query in enumerate(queries, start=1):
            try:
                refs = discovery.search(query)
            except Exception as exc:
                console.print(f"  [yellow]⚠[/yellow] [{i}/{len(queries)}] {query.query}: {exc}")
                continue

            fresh = [r for r in refs if r.doc_id not in known]
            for ref in refs:
                known[ref.doc_id] = {
                    "doc_id": ref.doc_id,
                    "title": ref.title,
                    "type": ref.doc_type,
                }

            console.print(
                f"  [{i}/{len(queries)}] {query.query:24} "
                f"{len(refs):3} topildi · [green]+{len(fresh)}[/green] yangi · "
                f"jami {len(known)}"
            )

            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                _yaml.safe_dump(
                    {"documents": list(known.values())}, allow_unicode=True, sort_keys=False
                ),
                encoding="utf-8",
            )

    console.print(f"\n[green]✓[/green] Katalog: [bold]{len(known)}[/bold] hujjat → {out}")
    console.print("[dim]Yuklab olish: uzlegal kb sync --from-catalog[/dim]")


@kb_app.command("parse")
def kb_parse(
    doc_id: str = typer.Argument(..., help="Hujjat ID (arxivdan o'qiladi)"),
) -> None:
    """Arxivdagi hujjatni ajratib, statistikasini ko'rsatish (tarmoqsiz)."""
    from uzlegal.ingest.connectors.lex_uz import LexUzConnector
    from uzlegal.ingest.parsers.lex_uz import LexUzParser

    raw = LexUzConnector().load_cached(doc_id)
    if raw is None:
        console.print(
            f"[red]✕[/red] Arxivda topilmadi: {doc_id}. Avval: uzlegal kb sync --docs {doc_id}"
        )
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
    lang: str = typer.Option("uz", "--lang", help="Faqat shu tildagi hujjatlar ('' = hammasi)"),
) -> None:
    """Arxivdagi hujjatlardan qidiruv indeksini qurish (tarmoqsiz).

    Standart bo'yicha faqat o'zbek tilidagi hujjatlar indekslanadi.
    Arxivda rus nashrlari ham bo'lishi mumkin (masalan 111181) — ular
    o'zbekcha so'rovlar natijasini ifloslantiradi. Arxiv o'zgarmas
    qoladi, filtr faqat indekslashda qo'llaniladi.
    """
    from uzlegal.index.chunker import Chunker
    from uzlegal.index.embedder import Embedder
    from uzlegal.index.store import KnowledgeIndex
    from uzlegal.ingest.connectors.lex_uz import LexUzConnector
    from uzlegal.ingest.parsers.lex_uz import LexUzParser
    from uzlegal.ingest.sync import SyncManager
    from uzlegal.ingest.versioning import apply_versions

    connector = LexUzConnector()
    ids = (
        [d.strip() for d in docs.split(",")]
        if docs
        else sorted(connector._from_safe_name(p.stem) for p in connector.raw_dir.glob("*.html"))
    )
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
        if lang and doc.lang != lang:
            console.print(f"  [dim]{doc_id}  o'tkazib yuborildi (til: {doc.lang})[/dim]")
            continue

        # Versiya maydonlarini to'ldirish — busiz `version_filter` bo'sh
        # ishlaydi va bekor qilingan norma qidiruvga chiqib ketadi
        # (docs/00 dagi «0% deprecated» talabi).
        doc = apply_versions(doc)

        produced = chunker.chunk_document(doc)
        chunks.extend(produced)
        console.print(f"  {doc_id}  {len(doc.articles)} modda → {len(produced)} chunk")

    if not chunks:
        console.print("[red]✕[/red] Chunk yaratilmadi")
        raise typer.Exit(1)

    # Vaqt bahosi bo'laklar SONIGA emas, UZUNLIGIGA bog'liq: e'tibor
    # mexanizmi O(n²), ya'ni bitta 5000 tokenlik bo'lak o'n ikkita
    # 400 tokenlikdan qimmatroq. Shuning uchun baho belgilar bo'yicha
    # beriladi va qurilma hisobga olinadi.
    total_chars = sum(len(c.indexed_text) for c in chunks)
    embedder = Embedder(batch_size=batch_size)
    rate = 9_000 if embedder.device != "cpu" else 400  # belgi/s, o'lchangan
    console.print(
        f"\nJami [bold]{len(chunks)}[/bold] chunk · {total_chars / 1e6:.1f} mln belgi · "
        f"qurilma {embedder.device}"
    )
    console.print(f"[dim]Taxminiy vaqt: ~{total_chars / rate / 60:.0f} daqiqa[/dim]\n")

    # `console.status()` spinneri EMAS, haqiqiy progress.
    #
    # Ilgari bu yerda aylanuvchi spinner turardi va u ishlash tezligi
    # haqida hech narsa aytmasdi. Ikki soatlik amalda bu «ishlayaptimi
    # yoki qotganmi?» degan savolga javob bermaydi — jarayonni
    # tashqaridan tekshirishga majbur qiladi. `sentence-transformers`
    # o'zi progress bar chiqaradi; uni yashirish sabab yo'q edi.
    vectors = embedder.encode([c.indexed_text for c in chunks], show_progress=True)

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
        + (
            f" · versiya filtri {result.dropped_by_version} ta chiqardi"
            if result.dropped_by_version
            else ""
        )
        + "[/dim]\n"
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
    mode: str = typer.Option("auto", "--mode", "-m", help="auto · simple · standard · complex"),
    as_of: str = typer.Option(None, "--as-of", help="Tarixiy holat, YYYY-MM-DD"),
    position: str = typer.Option(None, "--position", "-p", help="Mijoz bayoni (nizoli savolda)"),
    agents: str = typer.Option(None, "--agents", help="Aniq rollar, vergul bilan"),
    trace: bool = typer.Option(False, "--trace", help="Bosqichlar va vaqtlarni ko'rsatish"),
    json_out: bool = typer.Option(False, "--json", help="To'liq natijani JSON sifatida chiqarish"),
) -> None:
    """Savol berish — qidiruv, agentlar muhokamasi, sudya xulosasi, iqtibos nazorati.

    Javobdagi har bir huquqiy da'vo qonun moddasiga bog'lanadi.
    Bog'lanmagani groundedness gate tomonidan o'chiriladi va bu
    `--trace` da ko'rinadi.
    """
    from datetime import date as _date

    from uzlegal.core import ConsultRequest, consult

    try:
        request = ConsultRequest(
            question=question,
            mode=mode,  # type: ignore[arg-type]
            as_of=_date.fromisoformat(as_of) if as_of else None,
            client_position=position,
            agents=[a.strip() for a in agents.split(",")] if agents else None,
            trace=True,
        )
    except Exception as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(2) from exc

    with console.status("maslahat tayyorlanmoqda…"):
        try:
            result = consult(request)
        except Exception as exc:
            console.print(f"[red]✕[/red] {exc}")
            raise typer.Exit(3) from exc

    if json_out:
        console.print_json(result.model_dump_json())
        return

    _render_answer(result, trace=trace)
    if not result.citations:
        raise typer.Exit(5)


def _render_answer(result: object, *, trace: bool) -> None:
    """Maslahat natijasini terminalga chiqaradi."""
    from uzlegal.core import ConsultResult

    assert isinstance(result, ConsultResult)

    console.print(f"\n{result.answer}\n")

    if result.citations:
        console.print("[bold]Manbalar[/bold]")
        for c in result.citations:
            label = f"{c.doc_title or c.doc_id}, {c.article}-{unit_label(c.doc_type)}"
            console.print(f"  [cyan][{c.tag}][/cyan] {label}")
            if c.url:
                console.print(f"       [dim]{c.url}[/dim]")

    for caveat in result.caveats:
        console.print(f"\n[yellow]⚠ {caveat}[/yellow]")

    meta = [
        f"rejim {result.mode_used}",
        f"{result.latency_ms / 1000:.1f} s",
        f"ishonch {result.confidence:.0%}",
    ]
    if result.model_version:
        meta.append(f"model {result.model_version}")
    if result.kb_version:
        meta.append(f"kb {result.kb_version}")
    console.print(f"\n[dim]{' · '.join(meta)}[/dim]")

    if trace and result.trace is not None:
        console.print("\n[bold]Bosqichlar[/bold]")
        for step in result.trace.steps:
            detail = ", ".join(f"{k}={v}" for k, v in step.detail.items())
            console.print(f"  {step.node:12} {step.ms:6d} ms  [dim]{detail[:80]}[/dim]")
        console.print(f"\n  [dim]trace_id: {result.trace.trace_id}[/dim]")

    console.print(f"\n[dim]{result.disclaimer}[/dim]")


def _gate(capability: str) -> None:
    """Xizmatni ishga tushirishdan oldin litsenziyani talab qiladi.

    NEGA `serve`, `bot`, `mcp` — lekin `search` yoki `doctor` EMAS.
    Cheklov XIZMAT KO'RSATISHGA qo'yiladi: shu uchta buyruq tizimni
    boshqalarga ochadi. Lokal tekshiruv, diagnostika va indeks qurish
    ochiq qoladi — aks holda muallifning o'zi ham ishlay olmasdi va
    litsenziya rivojlanishga to'siq bo'lardi.
    """
    try:
        license_ = sig.require_license(capability)
    except sig.LicenseError as exc:
        console.print(f"[red]✕ Ishga tushirilmadi[/red]\n\n{exc}")
        raise typer.Exit(77) from exc

    console.print(f"[dim]{sig.banner()}[/dim]")
    console.print(f"[dim]Litsenziya: {license_.summary()}[/dim]\n")

    left = license_.days_left
    if left is not None and left < 14:
        console.print(
            f"[yellow]⚠ Litsenziya {left} kundan keyin tugaydi — {sig.CONTACT}[/yellow]\n"
        )


@app.command()
def bot() -> None:
    """Telegram botni ishga tushirish (long-polling)."""
    _gate("bot")

    from uzlegal.bot.telegram import TelegramBot, TelegramError

    try:
        telegram = TelegramBot()
    except TelegramError as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(2) from exc

    console.print("[bold]Telegram bot[/bold] ishga tushdi. To'xtatish: Ctrl+C")
    telegram.run()


@app.command()
def mcp() -> None:
    """MCP serverini stdio ustida ishga tushirish.

    Claude Desktop sozlamasiga:
    {"mcpServers": {"uzlegal": {"command": "uzlegal", "args": ["mcp"]}}}
    """
    _gate("mcp")

    from uzlegal.mcp.server import serve as _serve

    _serve()


@app.command()
def serve(
    host: str = typer.Option(None, "--host"),
    port: int = typer.Option(None, "--port"),
    profile: str = typer.Option(None, "--profile"),
) -> None:
    """API va Web UI ni ishga tushirish."""
    _gate("serve")

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

    console.print(f"[dim]{sig.banner()}[/dim]\n")
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

    # `iogpu.wired_limit_mb` — faqat Apple Silicon sozlamasi. Ilgari `sysctl`
    # shartsiz chaqirilardi va Windows da `doctor` ning o'zi yiqilardi:
    # diagnostika vositasi birinchi navbatda ISHLASHI kerak.
    if sys.platform == "darwin":
        try:
            wired = subprocess.run(
                ["sysctl", "-n", "iogpu.wired_limit_mb"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if wired.returncode == 0:
                mb = int(wired.stdout.strip() or 0)
                if mb == 0:
                    console.print(
                        "  GPU chegarasi [yellow]sozlanmagan[/yellow] "
                        "(sudo sysctl iogpu.wired_limit_mb=20480)"
                    )
                else:
                    console.print(f"  GPU chegarasi {mb} MB")
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

    console.print("\n[bold]Katalog[/bold]")
    models = reg.list_models()
    ready = sum(1 for m in models if m.status.value in ("available", "active"))
    console.print(f"  Modellar      {len(models)} ta, {ready} tasi tayyor")
    console.print(f"  Faol          {reg.active_id or '[dim]yo’q[/dim]'}")

    # OpenAI-mos server (Ollama/vLLM) — MLX bo'lmagan platformada asosiy yo'l,
    # shuning uchun uning holati diagnostikada ko'rinishi kerak.
    _doctor_openai_endpoint()

    console.print("\n[bold]Bilim bazasi[/bold]")
    if not _doctor_knowledge_base():
        ok = False

    console.print(
        f"\n{'[green]✓ Muhit tayyor[/green]' if ok else '[yellow]⚠ E’tibor talab qiladi[/yellow]'}"
    )


def _doctor_openai_endpoint() -> None:
    """OpenAI-mos server holati (Ollama, vLLM, LM Studio).

    Xato hech qachon tashlanmaydi: bu server ixtiyoriy va uning yo'qligi
    `doctor` ni yiqitmasligi kerak — u shunchaki holatni ko'rsatadi.
    """
    import os

    import httpx

    endpoint = (os.getenv("UZLEGAL_OPENAI_ENDPOINT") or "http://localhost:11434/v1").rstrip("/")
    try:
        response = httpx.get(f"{endpoint}/models", timeout=3.0)
        response.raise_for_status()
        names = [str(item.get("id")) for item in (response.json().get("data") or [])]
    except Exception:
        console.print(f"  LLM server    [yellow]javob bermadi[/yellow] ({endpoint})")
        console.print("                [dim]Ollama uchun: ollama serve[/dim]")
        return

    console.print(f"  LLM server    [green]ishlayapti[/green] ({endpoint}) — {len(names)} model")
    if names:
        console.print(f"                [dim]{', '.join(sorted(names)[:6])}[/dim]")


def _doctor_knowledge_base() -> bool:
    """Bilim bazasi holati.

    Ilgari bu yerda «Faza 2 da quriladi» degan qotib qolgan matn turardi —
    baza qurilgandan keyin ham o'sha matn chiqaverardi. Endi haqiqiy
    indeksdan o'qiladi.
    """
    hint = "                [dim]Qurish: uzlegal kb sync --priority && uzlegal index build[/dim]"

    # Ataylab `load()` chaqirilmaydi: u lancedb ni import qiladi va butun
    # indeksni xotiraga oladi. Diagnostika arzon bo'lishi kerak — meta
    # faylining o'zi yetarli.
    try:
        from uzlegal.index.store import KnowledgeIndex

        index = KnowledgeIndex()
        built = index.exists()
        meta = index.meta if built else {}
    except Exception as exc:
        console.print(f"  Indeks        [red]tekshirilmadi[/red] ({type(exc).__name__}: {exc})")
        return False

    chunks = int(meta.get("chunks") or 0)
    if not built or chunks == 0:
        console.print("  Indeks        [yellow]yo’q yoki bo’sh[/yellow]")
        console.print(hint)
        return False

    version = str(meta.get("kb_version") or "(versiyasiz)")
    documents = int(meta.get("documents") or 0)
    console.print(
        f"  Indeks        [green]tayyor[/green] — {documents} hujjat, "
        f"{chunks} bo'lak, versiya {version}"
    )
    return True


if __name__ == "__main__":
    app()


@app.command("plans")
def plans_show() -> None:
    """Obuna rejalari va to'lov holati."""
    from uzlegal.users.plans import PLANS, billing

    state = billing()
    if state.enabled:
        console.print("[green]To'lov YOQILGAN[/green] — chegaralar amal qiladi\n")
    else:
        console.print(f"[yellow]BEPUL DAVR[/yellow] — {state.note}\n")

    table = Table(box=None, pad_edge=False)
    table.add_column("Reja", style="bold")
    table.add_column("Narx (so'm/oy)", justify="right")
    table.add_column("Kunlik", justify="right")
    table.add_column("Oylik", justify="right")
    table.add_column("Imkoniyatlar")

    for plan in PLANS.values():
        features = [k for k, v in plan.features.model_dump().items() if v]
        table.add_row(
            plan.name_uz,
            f"{plan.price_uzs:,}".replace(",", " ") if plan.price_uzs else "bepul",
            str(plan.limits.daily_queries),
            str(plan.limits.monthly_queries),
            ", ".join(features) or "—",
        )

    console.print(table)
    console.print(
        "\n[dim]Tahrirlash: configs/plans.yaml · Qayta o'qish: POST /v1/admin/plans/reload[/dim]"
    )


@app.command("audit")
def audit_cmd(
    verify: bool = typer.Option(False, "--verify", help="Hash zanjirini tekshirish"),
    trace_id: str = typer.Option(None, "--trace", help="Bitta yozuvni ko'rish"),
) -> None:
    """Audit jurnali — holat, tekshiruv va yozuvni ko'rish (docs/10 § 5)."""
    import json as _json

    from uzlegal import audit as _audit

    if trace_id:
        record = _audit.find(trace_id)
        if record is None:
            console.print(f"[red]✕[/red] Topilmadi: {trace_id}")
            raise typer.Exit(4)
        console.print_json(_json.dumps(record, ensure_ascii=False))
        return

    if verify:
        result = _audit.verify_chain()
        if result["ok"]:
            console.print(f"[green]✓ Zanjir butun[/green] — {result['records']} yozuv tekshirildi")
            return
        console.print(f"[red]✕ Zanjir buzilgan[/red] — {result['records']} yozuvdan")
        console.print(f"  {result['broken_at']}-yozuvda: {result['reason']}")
        console.print(f"  trace_id: {result.get('trace_id')}")
        raise typer.Exit(1)

    info = _audit.stats()
    console.print(
        f"  Holat        {'[green]yoqilgan[/green]' if info['enabled'] else 'o‘chirilgan'}"
    )
    console.print(f"  Fayl         {info['path']}")
    console.print(f"  Yozuvlar     {info['records']}")
    if info["records"]:
        console.print(f"  Hajm         {info['size_bytes'] / 1024:.1f} KB")
        console.print(f"  Davr         {info['first'][:19]} … {info['last'][:19]}")
    console.print("\n[dim]Zanjirni tekshirish: uzlegal audit --verify[/dim]")
