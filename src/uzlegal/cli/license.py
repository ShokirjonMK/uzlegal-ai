"""`uzlegal license` — litsenziya berish, tekshirish va ko'rish.

`issue` faqat muallif mashinasida ishlaydi: u maxfiy kalitni talab
qiladi. Qolgan buyruqlar hamma joyda ishlaydi.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console

from uzlegal import signature as sig

license_app = typer.Typer(help="Foydalanish litsenziyasi", no_args_is_help=True)
console = Console()

DEFAULT_KEY = "~/.ssh/id_ed25519"


@license_app.command("show")
def license_show() -> None:
    """Joriy litsenziya holati."""
    console.print(f"[dim]{sig.banner()}[/dim]\n")

    status = sig.license_status()
    if not status["valid"]:
        console.print(f"[yellow]⚠ Litsenziya yo'q yoki yaroqsiz[/yellow]: {status['error']}")
        console.print(f"\n[dim]Murojaat: {sig.CONTACT} · {sig.REPOSITORY}[/dim]")
        raise typer.Exit(1)

    console.print("[green]✓ Litsenziya amalda[/green]\n")
    console.print(f"  Kimga        {status['licensee']}")
    console.print(f"  Berilgan     {status['issued']}")
    console.print(f"  Muddat       {status['expires'] or 'muddatsiz'}")
    if status["days_left"] is not None:
        left = int(status["days_left"])
        style = "red" if left < 14 else "yellow" if left < 45 else "green"
        console.print(f"  Qolgan       [{style}]{left} kun[/{style}]")
    console.print(f"  Imkoniyat    {', '.join(status['scope'])}")


@license_app.command("verify")
def license_verify(
    token: str = typer.Argument(None, help="Token (ko'rsatilmasa muhitdan olinadi)"),
) -> None:
    """Tokenni tekshiradi va nima uchun yaroqsizligini aniq aytadi."""
    try:
        license_ = sig.parse_license(token) if token else sig.load_license()
    except sig.LicenseError as exc:
        console.print(f"[red]✕ Yaroqsiz[/red]\n{exc}")
        raise typer.Exit(1) from exc

    if license_ is None:
        console.print("[yellow]⚠ Litsenziya sozlanmagan[/yellow]")
        raise typer.Exit(1)

    console.print(f"[green]✓ Imzo to'g'ri[/green] — {license_.summary()}")
    console.print(f"[dim]Imzolagan: {sig.AUTHOR} · {sig.PUBLIC_KEY_FINGERPRINT}[/dim]")


@license_app.command("issue")
def license_issue(
    licensee: str = typer.Argument(..., help="Kimga beriladi (tashkilot yoki shaxs)"),
    days: int = typer.Option(365, "--days", help="Amal qilish muddati; 0 — muddatsiz"),
    scope: str = typer.Option(
        "", "--scope", help="Vergul bilan: serve,bot,mcp,train. Bo'sh — hammasi"
    ),
    note: str = typer.Option("", "--note"),
    key: str = typer.Option(DEFAULT_KEY, "--key", help="Ed25519 maxfiy kalit yo'li"),
    out: Path = typer.Option(None, "--out", help="Tokenni faylga yozish"),
) -> None:
    """Yangi litsenziya beradi — **faqat muallif mashinasida**.

    Maxfiy kalit boshqa hech kimda yo'q, shuning uchun bu buyruq boshqa
    joyda ishlamaydi. Aynan shu narsa tizimni himoya qiladi.
    """
    key_path = Path(key).expanduser()
    if not key_path.exists():
        console.print(f"[red]✕[/red] Maxfiy kalit topilmadi: {key_path}")
        console.print("[dim]Litsenziya berish faqat muallif mashinasida mumkin.[/dim]")
        raise typer.Exit(2)

    expires = None if days <= 0 else datetime.now(UTC).date() + timedelta(days=days)
    scopes = tuple(s.strip() for s in scope.split(",") if s.strip())

    try:
        token = sig.issue_license(
            licensee,
            private_key_path=str(key_path),
            expires=expires,
            scope=scopes,
            note=note,
        )
    except Exception as exc:
        console.print(f"[red]✕[/red] Imzolanmadi: {exc}")
        raise typer.Exit(3) from exc

    # O'z imzomizni darhol tekshiramiz — noto'g'ri kalit bilan yasalgan
    # token foydalanuvchiga berilib, keyin ishlamasligi mumkin edi.
    try:
        checked = sig.parse_license(token)
    except sig.LicenseError as exc:
        console.print(f"[red]✕[/red] Token yasaldi, lekin tekshiruvdan o'tmadi: {exc}")
        console.print("[dim]Maxfiy kalit repodagi ochiq kalitga mos kelmayapti.[/dim]")
        raise typer.Exit(3) from exc

    console.print(f"[green]✓[/green] Litsenziya berildi: [bold]{checked.summary()}[/bold]")
    if scopes:
        console.print(f"  Imkoniyat: {', '.join(scopes)}")

    if out:
        out.write_text(token, encoding="utf-8")
        console.print(f"\n[green]✓[/green] Saqlandi: {out}")
    else:
        console.print(f"\n{token}\n")

    console.print("[dim]Foydalanuvchiga: UZLEGAL_LICENSE=… yoki `license.key` fayli[/dim]")


@license_app.command("author")
def license_author() -> None:
    """Loyiha muallifi va imzo kalitlari."""
    data = sig.attribution()
    console.print(f"\n[bold]{data['project']}[/bold]\n")
    console.print(f"  Muallif      {data['author']}")
    console.print(f"  GitHub       @{data['author_handle']}")
    console.print(f"  Dasturchi    {data['developer']}")
    console.print(f"  Telegram     {data['contact']}")
    console.print(f"  Repo         {data['repository']}")
    console.print(f"  Kalitlar     {', '.join(sig.AUTHOR_KEYS)}")
    console.print(f"  Barmoq izi   {data['key_fingerprint']}")
    console.print(
        f"\n[dim]Mualliflik huquqi © {date.today().year} {data['author']}. "
        f"Barcha huquqlar himoyalangan.[/dim]"
    )


__all__ = ["license_app"]
