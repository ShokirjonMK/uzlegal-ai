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

import json
import shutil
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel
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
        dated = sum(
            1 for n, v in report.versions.items() if n in present and (v.valid_from or v.valid_to)
        )
        repealed = sum(
            1 for n, v in report.versions.items() if n in present and v.status == "repealed"
        )
        row = [
            len(doc.articles),
            report.notes_seen,
            dated,
            repealed,
            len(report.repealed_absent),
            len(report.warnings),
        ]
        totals = [t + r for t, r in zip(totals, row, strict=True)]
        table.add_row(doc.doc_id, *(str(v) for v in row))

        for number in sorted(report.versions)[:show]:
            v = report.versions[number]
            console.print(
                f"  [dim]{number:>8}  {v.valid_from or '—'} → {v.valid_to or '—'}  "
                f"{v.status}  {','.join(v.amended_by[:3])}[/dim]"
            )

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

    console.print(
        f"Hujjat {summary.documents} · modda {summary.articles} · "
        f"xato {summary.errors} · ogohlantirish {summary.warnings}"
    )
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
    console.print(
        f"Almashtirildi: {len(result.redactions)} · shaxs {len(result.persons)} · "
        f"ishonch {result.confidence:.2f}"
    )
    if result.quarantine:
        console.print("[yellow]⚠ Karantin:[/yellow] " + "; ".join(result.reasons))

    if out:
        out.write_text(result.text, encoding="utf-8")
        console.print(f"[green]✓[/green] Saqlandi: {out}")
    else:
        console.print(result.text[:2000])


# --------------------------------------------------------------------------- #
# Sana qamrovi — docs/22 § 1.5
# --------------------------------------------------------------------------- #

# `<title>` tegi sahifaning boshida turadi. Butun faylni o'qish
# (863 × ~1.5 MB) shu bitta regex uchun ortiqcha — avval bosh qismi
# o'qiladi, teg topilmasagina to'liq faylga tushiladi.
_HEAD_BYTES = 8192


def _archive_dates() -> dict[str, str]:
    """Arxivdagi har bir hujjatning qabul sanasi: `doc_id → YYYY-MM-DD`.

    Hujjatni to'liq ajratish shart emas: sana faqat `<title>` tegida
    va uni o'qish uchun `parsers.lex_uz.title_tag_date()` yetarli.
    """
    from uzlegal.ingest.parsers.lex_uz import title_tag_date

    connector = LexUzConnector()
    out: dict[str, str] = {}
    for path in sorted(connector.raw_dir.glob("*.html")):
        with path.open(encoding="utf-8", errors="replace") as fh:
            head = fh.read(_HEAD_BYTES)
            found = title_tag_date(head) or title_tag_date(head + fh.read())
        if found:
            out[connector._from_safe_name(path.stem)] = found
    return out


class DateCoverage(BaseModel):
    """`pipeline dates` o'lchovi — oldin/keyin qamrov va rad etish sabablari."""

    chunks: int = 0
    dated_before: int = 0
    dated_after: int = 0
    filled: int = 0
    future_skipped: int = 0
    no_archive_date: int = 0
    docs: int = 0
    docs_any_before: int = 0
    docs_any_after: int = 0
    docs_full_before: int = 0
    docs_full_after: int = 0

    def rate(self, part: int) -> str:
        return f"{part / self.chunks:.1%}" if self.chunks else "—"

    def doc_rate(self, part: int) -> str:
        return f"{part / self.docs:.1%}" if self.docs else "—"


def _measure_dates(
    chunks_path: Path, adopted: Mapping[str, str], today: str, *, out_path: Path | None
) -> DateCoverage:
    """`chunks.jsonl` ni satrma-satr o'qib qamrovni o'lchaydi.

    `out_path` berilsa yangilangan nusxa o'sha yerga yoziladi.
    O'zgarmagan satr **aynan** ko'chiriladi, o'zgargani esa faqat
    `valid_from` kaliti bo'yicha qayta yig'iladi: `chunk_id`, `heading`
    va `content` ga tegilmaydi (docs/22 § 5 A6).
    """
    cov = DateCoverage()
    per_doc: dict[str, list[int]] = {}  # doc_id → [jami, oldin, keyin]
    sink = out_path.open("w", encoding="utf-8", newline="\n") if out_path else None

    try:
        with chunks_path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row: dict[str, Any] = json.loads(line)
                cov.chunks += 1
                doc_id = str(row.get("doc_id", ""))
                counts = per_doc.setdefault(doc_id, [0, 0, 0])
                counts[0] += 1

                before = row.get("valid_from")
                after = before
                if before:
                    cov.dated_before += 1
                    counts[1] += 1
                else:
                    candidate = adopted.get(doc_id)
                    if candidate is None:
                        cov.no_archive_date += 1
                    elif candidate > today:
                        # Kelajak sana `valid_from` ga yozilmaydi —
                        # `version_filter` bunday bo'lakni butunlay
                        # yashirardi (docs/22 § 1.4).
                        cov.future_skipped += 1
                    else:
                        after = candidate
                        cov.filled += 1

                if after:
                    cov.dated_after += 1
                    counts[2] += 1

                if sink is not None:
                    if after == before:
                        sink.write(line if line.endswith("\n") else line + "\n")
                    else:
                        row["valid_from"] = after
                        sink.write(json.dumps(row, ensure_ascii=False) + "\n")
    finally:
        if sink is not None:
            sink.close()

    cov.docs = len(per_doc)
    for total, before_n, after_n in per_doc.values():
        cov.docs_any_before += 1 if before_n else 0
        cov.docs_any_after += 1 if after_n else 0
        cov.docs_full_before += 1 if before_n == total else 0
        cov.docs_full_after += 1 if after_n == total else 0
    return cov


@pipeline_app.command("dates")
def dates(
    index: Path = typer.Option(Path("kb/current"), "--index", help="Indeks katalogi"),
    apply: bool = typer.Option(False, "--apply", help="chunks.jsonl ni yangilash"),
    as_of: str = typer.Option(None, "--as-of", help="Bugungi sana o'rniga, YYYY-MM-DD"),
) -> None:
    """Bo'laklardagi sana qamrovi: o'lchov va (`--apply` bilan) to'ldirish.

    Sana arxivdagi `<title>` tegidan olinadi va faqat `valid_from` i
    bo'sh bo'lgan bo'laklarga yoziladi. `--apply` siz hech narsa
    yozilmaydi — quruq yugurish majburiy (docs/22 § 6).
    """
    chunks_path = index / "chunks.jsonl"
    if not chunks_path.exists():
        console.print(f"[red]✕[/red] Indeks topilmadi: {chunks_path}. Avval: uzlegal index build")
        raise typer.Exit(4)

    adopted = _archive_dates()
    if not adopted:
        console.print("[red]✕[/red] Arxivda sanali hujjat yo'q. Avval: uzlegal kb sync")
        raise typer.Exit(4)

    today = (date.fromisoformat(as_of) if as_of else date.today()).isoformat()
    tmp_path = chunks_path.with_name(chunks_path.name + ".tmp") if apply else None
    try:
        cov = _measure_dates(chunks_path, adopted, today, out_path=tmp_path)
    except json.JSONDecodeError as exc:
        # Yarim yozilgan `.tmp` qolib ketmasin — u haqiqiy fayl emas.
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        console.print(f"[red]✕[/red] chunks.jsonl buzuq: {exc}. Qayta quring: uzlegal index build")
        raise typer.Exit(4) from exc

    table = Table(box=None, pad_edge=False)
    for name in ("O'lchov", "Oldin", "Keyin"):
        table.add_column(name, justify="left" if name == "O'lchov" else "right")
    table.add_row(
        f"Bo'lak (jami {cov.chunks})",
        f"{cov.dated_before} ({cov.rate(cov.dated_before)})",
        f"{cov.dated_after} ({cov.rate(cov.dated_after)})",
    )
    table.add_row(
        f"Hujjat, kamida bitta sanali (jami {cov.docs})",
        f"{cov.docs_any_before} ({cov.doc_rate(cov.docs_any_before)})",
        f"{cov.docs_any_after} ({cov.doc_rate(cov.docs_any_after)})",
    )
    table.add_row(
        "Hujjat, to'liq sanali",
        f"{cov.docs_full_before} ({cov.doc_rate(cov.docs_full_before)})",
        f"{cov.docs_full_after} ({cov.doc_rate(cov.docs_full_after)})",
    )
    console.print(table)
    console.print(
        f"\nTo'ldiriladi {cov.filled} · kelajak sana tufayli o'tkazildi "
        f"{cov.future_skipped} · arxivda sana yo'q {cov.no_archive_date}"
    )

    if tmp_path is None:
        console.print("\n[dim]Hech narsa yozilmadi. Yozish uchun: --apply[/dim]")
        return

    backup = chunks_path.with_name(f"{chunks_path.name}.{date.today():%Y%m%d}.bak")
    shutil.copy2(chunks_path, backup)
    tmp_path.replace(chunks_path)
    console.print(f"\n[green]✓[/green] Yangilandi: {chunks_path}")
    console.print(f"[dim]Zaxira: {backup}[/dim]")
    console.print(
        "[yellow]⚠[/yellow] Bu metama'lumot patchi. Keyingi to'liq "
        "`uzlegal index build` uni bekor qiladi — u bo'laklarni qaytadan "
        "hosil qiladi (docs/22 § 1.5)."
    )


if __name__ == "__main__":
    pipeline_app()
