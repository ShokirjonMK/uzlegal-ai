"""`uzlegal consult` — ko'p-agentli maslahat buyrug'i.

Bu alohida sub-app: `cli/main.py` ga tegmasdan ulanadi. Ulash uchun bitta
satr yetarli —

    from uzlegal.cli.consult import consult_app
    app.add_typer(consult_app, name="consult")

Qobiq ataylab yupqa: u faqat `ConsultRequest` yig'adi va `ConsultResult` ni
terminalga chizadi. Router, agentlar, gate va disclaimer — hammasi
`uzlegal.core.consult()` ichida (docs/07 § 1).
"""

from __future__ import annotations

import json
from datetime import date as _date
from pathlib import Path

import typer
from rich.console import Console

consult_app = typer.Typer(help="Ko'p-agentli huquqiy maslahat", no_args_is_help=True)
console = Console()


@consult_app.command("ask")
def consult_ask(
    question: str = typer.Argument(..., help="Huquqiy savol"),
    mode: str = typer.Option("auto", "--mode", "-m", help="auto · simple · standard · complex"),
    as_of: str = typer.Option(None, "--as-of", help="Tarixiy holat, YYYY-MM-DD"),
    client_position: str = typer.Option(None, "--client", help="Mijoz pozitsiyasi (advokat uchun)"),
    agents: str = typer.Option(None, "--agents", help="Vergul bilan: jurist,advocate,…"),
    show_trace: bool = typer.Option(False, "--trace", help="Asoslash zanjirini ko'rsatish"),
    as_json: bool = typer.Option(False, "--json", help="Mashina uchun JSON"),
    out: Path = typer.Option(None, "--out", help="Javobni faylga yozish"),
) -> None:
    """Savol berish va to'liq maslahat olish."""
    from uzlegal.core import ConsultRequest, consult

    request = ConsultRequest(
        question=question,
        mode=mode,  # type: ignore[arg-type]
        as_of=_date.fromisoformat(as_of) if as_of else None,
        client_position=client_position,
        agents=[a.strip() for a in agents.split(",") if a.strip()] if agents else None,
        trace=show_trace or as_json,
    )

    try:
        if as_json:
            result = consult(request)
        else:
            with console.status("tahlil qilinmoqda…"):
                result = consult(request)
    except Exception as exc:
        console.print(f"[red]✕[/red] {exc}")
        raise typer.Exit(3) from exc

    if as_json:
        payload = result.model_dump(mode="json", exclude_none=True)
        console.print_json(json.dumps(payload, ensure_ascii=False))
    else:
        _render(result, show_trace)

    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_markdown(result), encoding="utf-8")
        console.print(f"\n[green]✓[/green] Saqlandi: {out}")

    # Rad etilgan javob — xato emas, lekin skript uni ajrata olishi kerak.
    if result.refused:
        raise typer.Exit(5)


@consult_app.command("roles")
def consult_roles() -> None:
    """Mavjud rollar va ularning sozlamalari."""
    from uzlegal.agents.roles import AGENT_CLASSES, ROLE_ORDER

    for role in ROLE_ORDER:
        agent = AGENT_CLASSES[role]()
        console.print(
            f"  [bold]{role:11}[/bold] {agent.display_name:10} "
            f"harorat {agent.temperature:.1f} · "
            f"chiqish {agent.output_schema.__name__} · "
            f"{'prompt bor' if agent.system_prompt else '[yellow]prompt yo’q[/yellow]'}"
        )


def _render(result: object, show_trace: bool) -> None:
    from uzlegal.core import ConsultResult

    assert isinstance(result, ConsultResult)
    console.print(f"\n{result.answer}\n")

    if result.citations:
        console.print(
            f"[dim]ISHONCH: {result.confidence:.2f} · MANBALAR: {len(result.citations)}[/dim]\n"
        )
        for c in result.citations:
            label = c.doc_title or c.doc_id
            article = f", {c.article}-modda" if c.article else ""
            console.print(f"[{c.tag}] {label}{article}  [dim]{c.url or ''}[/dim]")

    for caveat in result.caveats:
        console.print(f"[yellow]• {caveat}[/yellow]")

    if show_trace and result.trace:
        console.print("\n[bold]Asoslash zanjiri[/bold]")
        for step in result.trace.steps:
            detail = " · ".join(f"{k}={v}" for k, v in step.detail.items())
            console.print(f"  {step.node:14} {step.ms:6d} ms  [dim]{detail}[/dim]")
        console.print(f"  {'jami':14} {result.trace.total_ms:6d} ms")

    console.print(f"\n[yellow]{result.disclaimer}[/yellow]")


def _markdown(result: object) -> str:
    from uzlegal.core import ConsultResult

    assert isinstance(result, ConsultResult)
    lines = [f"# {result.trace_id}", "", result.answer, ""]
    if result.citations:
        lines += ["## Manbalar", ""]
        lines += [
            f"- [{c.tag}] {c.doc_title or c.doc_id}"
            + (f", {c.article}-modda" if c.article else "")
            + (f" — {c.url}" if c.url else "")
            for c in result.citations
        ]
        lines.append("")
    if result.caveats:
        lines += ["## Ogohlantirishlar", ""] + [f"- {c}" for c in result.caveats] + [""]
    lines += ["---", "", result.disclaimer]
    return "\n".join(lines)
