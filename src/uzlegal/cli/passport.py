"""`uzlegal passport` — javob pasportini tekshirish va kalitni ko'rish.

`verify` har qanday mashinada ishlaydi, lekin faqat **shu o'rnatma**
bergan pasportlarni taniydi: kalit joylashtirishga xos (docs/21 § 4.3).
Boshqa o'rnatma tokeni ko'rsatilsa buni aniq aytadi — «soxta» demaydi.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from uzlegal import passport as pp

passport_app = typer.Typer(help="Javob pasporti", no_args_is_help=True)
console = Console()


@passport_app.command("verify")
def passport_verify(
    token: str = typer.Argument(..., help="Pasport tokeni (uzlegal-pass.v1.…)"),
    answer_file: Path = typer.Option(
        None, "--answer-file", help="Javob matni fayli — xesh bilan solishtiriladi"
    ),
) -> None:
    """Pasportni tekshiradi va nima uchun yaroqsizligini aniq aytadi."""
    try:
        result = pp.verify_passport(token)
    except pp.PassportError as exc:
        console.print(f"[red]✕ Yaroqsiz[/red]\n{exc}")
        raise typer.Exit(1) from exc

    console.print(f"[green]✓ Imzo to'g'ri[/green] — {result.summary()}\n")
    console.print(f"  Trace ID     {result.trace_id}")
    console.print(f"  Berilgan     {result.issued_at}")
    console.print(f"  Holat sanasi {result.as_of or 'bugungi holat'}")
    console.print(f"  Bilim bazasi {result.kb_version or '—'}")
    console.print(f"  Model        {result.model_version or '—'}")
    console.print(f"  Manbalar     {', '.join(result.citations) or '—'}")
    console.print(f"  Savol xeshi  {result.question_hash}")
    console.print(f"  Javob xeshi  {result.answer_hash}")
    console.print(f"  Kalit        {result.key_fingerprint}")

    # Javob matni bilan solishtirish — pasportning asosiy maqsadi.
    # Imzo «bu pasportni tizim bergan» deydi; matn taqqoslash esa
    # «va u aynan qo'lingizdagi javobga tegishli» deydi.
    if answer_file is not None:
        answer = answer_file.read_text(encoding="utf-8")
        if result.matches_answer(answer):
            console.print("\n[green]✓[/green] Javob matni pasportga mos keladi")
        else:
            console.print("\n[red]✕[/red] Javob matni pasportdagi xeshga MOS KELMAYDI")
            raise typer.Exit(2)


@passport_app.command("key")
def passport_key() -> None:
    """Shu o'rnatmaning pasport ochiq kalitini ko'rsatadi.

    Kalit hali bo'lmasa yaratiladi. Ochiq kalitni tarqatish xavfsiz —
    u bilan faqat TEKSHIRISH mumkin, pasport berish emas.
    """
    try:
        public = pp.passport_public_key()
    except Exception as exc:
        console.print(f"[red]✕[/red] Kalit olinmadi: {exc}")
        raise typer.Exit(3) from exc

    console.print(f"\n{public}\n")
    console.print(f"[dim]Maxfiy kalit: {pp.key_path()} — uni hech kimga bermang.[/dim]")


__all__ = ["passport_app"]
