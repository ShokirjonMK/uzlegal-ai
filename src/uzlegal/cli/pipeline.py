"""Quvurning versiyalash, havola va validatsiya buyruqlari.

Alohida sub-app: `uzlegal.cli.main` ga tegmasdan qo'shiladi. Ulash uchun
bitta qator yetarli —

    from uzlegal.cli.pipeline import pipeline_app
    app.add_typer(pipeline_app, name="pipeline")

— shu bo'lmaganda ham modul mustaqil ishlaydi:

    python -m uzlegal.cli.pipeline versions --docs -111189

Barcha buyruqlar **arxivdan** o'qiydi (tarmoqsiz, tez): parser yaxshilanganda
butun quvurni qayta ishga tushirish shu tarzda bo'ladi (docs/03 § 3).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from uzlegal.ingest.connectors.lex_uz import LexUzConnector
from uzlegal.ingest.parsers.lex_uz import LexUzParser
from uzlegal.ingest.types import ParsedDocument

pipeline_app = typer.Typer(help="Versiyalash · havolalar · validatsiya", no_args_is_help=True)
console = Console()


def _load(docs: str | None, lang: str = "uz") -> list[tuple[ParsedDocument, str]]:
    """Arxivdagi hujjatlarni ajratadi. `(hujjat, xom HTML)` juftliklari."""
    connector = LexUzConnector()
    ids = (
        [d.strip() for d in docs.split(",")]
        if docs
        else sorted(connector._from_safe_name(p.stem) for p in connector.raw_dir.glob("*.html"))
    )
    if not ids:
        console.print("[red]✕[/red] Arxiv bo'sh. Avval: uzlegal kb sync")
        raise typer.Exit(4)

    parser = LexUzParser()
    out: list[tuple[ParsedDocument, str]] = []
    for doc_id in ids:
        raw = connector.load_cached(doc_id)
        if raw is None:
            console.print(f"  [yellow]⚠ arxivda yo'q: {doc_id}[/yellow]")
            continue
        doc = parser.parse(raw)
        if lang and doc.lang != lang:
            continue
        out.append((doc, raw.content))
    return out


@pipeline_app.command("versions")
def versions(
    docs: str = typer.Option(None, "--docs", help="Hujjat ID lari (standart: arxivdagi hammasi)"),
    as_of: str = typer.Option(None, "--as-of", help="Sanani belgilash, YYYY-MM-DD"),
    show: int = typer.Option(0, "--show", help="Nechta modda misol qilib ko'rsatilsin"),
) -> None:
    """Tahrir izohlaridan modda versiyalarini qurish (docs/03 § 3.4)."""
    from uzlegal.ingest.versioning import build_versions

    today = date.fromisoformat(as_of) if as_of else None
    table = Table(box=None, pad_edge=False)
    for name in ("Hujjat", "Modda", "Izoh", "Versiyali", "Bekor", "Matnda yo'q", "Sanasiz"):
        table.add_column(name, justify="right" if name != "Hujjat" else "left")

    totals = [0, 0, 0, 0, 0, 0]
    for doc, _html in _load(docs):
        report = build_versions(doc, today=today)
        present = {a.article_number for a in doc.articles}
        dated = sum(1 for n, v in report.versions.items() if n in present and (v.valid_from or v.valid_to))
        repealed = sum(1 for n, v in report.versions.items() if n in present and v.status == "repealed")
        row = [len(doc.articles), report.notes_seen, dated, repealed,
               len(report.repealed_absent), len(report.warnings)]
        totals = [t + r for t, r in zip(totals, row, strict=True)]
        table.add_row(doc.doc_id, *(str(v) for v in row))

        for number in sorted(report.versions)[:show]:
            v = report.versions[number]
            console.print(f"  [dim]{number:>8}  {v.valid_from or '—'} → {v.valid_to or '—'}  "
                          f"{v.status}  {','.join(v.amended_by[:3])}[/dim]")

    table.add_section()
    table.add_row("[bold]jami[/bold]", *(f"[bold]{v}[/bold]" for v in totals))
    console.print(table)


@pipeline_app.command("links")
def links(
    docs: str = typer.Option(None, "--docs"),
    article: str = typer.Option(None, "--article", help="Qo'shnilarini ko'rsatish: `doc:modda`"),
    depth: int = typer.Option(1, "--depth"),
    out: Path = typer.Option(None, "--out", help="Grafni JSONL ga yozish"),
) -> None:
    """Havola grafini qurish (docs/03 § 3.5)."""
    from uzlegal.ingest.linking import build_graph

    pairs = _load(docs)
    graph = build_graph([d for d, _ in pairs], {d.doc_id: h for d, h in pairs})

    for key, value in graph.stats().items():
        console.print(f"  {key:12} {value}")

    if article:
        neighbours = graph.neighbors(article, depth=depth)
        console.print(f"\n[bold]{article}[/bold] → {len(neighbours)} qo'shni ({depth} daraja)")
        for node in neighbours[:20]:
            console.print(f"  {node}")

    if out:
        console.print(f"\n[green]✓[/green] Saqlandi: {graph.save(out)}")


@pipeline_app.command("validate")
def validate(
    docs: str = typer.Option(None, "--docs"),
    as_of: str = typer.Option(None, "--as-of"),
    limit: int = typer.Option(10, "--limit", help="Nechta muammo ko'rsatilsin"),
) -> None:
    """Hujjatlarni indekslashdan oldin tekshirish (docs/03 § 3.8)."""
    from uzlegal.ingest.validate import validate_documents
    from uzlegal.ingest.versioning import apply_versions

    today = date.fromisoformat(as_of) if as_of else None
    documents = [apply_versions(d, today=today) for d, _ in _load(docs)]
    summary = validate_documents(documents, today=today)

    console.print(f"Hujjat {summary.documents} · modda {summary.articles} · "
                  f"xato {summary.errors} · ogohlantirish {summary.warnings}")
    for code, count in summary.by_code().items():
        console.print(f"  {code:24} {count}")

    rate = summary.quarantine_rate
    mark = "[green]✅[/green]" if rate <= 0.05 else "[red]❌[/red]"
    console.print(f"\nKarantin {len(summary.quarantined)} ({rate:.2%}, maqsad ≤ 5%) {mark}")
    console.print(f"Tashlab yuboriladi {len(summary.dropped)}")

    for issue in summary.issues[:limit]:
        colour = "red" if issue.severity == "error" else "yellow"
        console.print(f"  [{colour}]{issue.code}[/{colour}] {issue.message[:100]}")


@pipeline_app.command("redact")
def redact(
    path: Path = typer.Argument(..., help="Matn fayli (sud qarori)"),
    out: Path = typer.Option(None, "--out"),
) -> None:
    """Matnni anonimizatsiya qilish (docs/03 § 3.7)."""
    from uzlegal.ingest.redact import Redactor

    if not path.exists():
        console.print(f"[red]✕[/red] Fayl topilmadi: {path}")
        raise typer.Exit(4)

    result = Redactor().redact(path.read_text(encoding="utf-8"))
    console.print(f"Almashtirildi: {len(result.redactions)} · shaxs {len(result.persons)} · "
                  f"ishonch {result.confidence:.2f}")
    if result.quarantine:
        console.print("[yellow]⚠ Karantin:[/yellow] " + "; ".join(result.reasons))

    if out:
        out.write_text(result.text, encoding="utf-8")
        console.print(f"[green]✓[/green] Saqlandi: {out}")
    else:
        console.print(result.text[:2000])


if __name__ == "__main__":
    pipeline_app()
