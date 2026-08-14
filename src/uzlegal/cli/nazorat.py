"""`uzlegal nazorat` — sud qarorlarida pora belgilarini terminal orqali tekshirish.

Bu modul **hech qanday mantiq qurmaydi**: aniqlash `integrity/detector.py`
da, statistika `integrity/profile.py` da allaqachon bor va API ham aynan
shularni chaqiradi. Bu yerda faqat qadoqlash — fayl o'qish, o'zbekcha
hisobot va `--json`.

Model chaqirilmaydi. Bir xil fayl → bir xil chiqish, shuning uchun
hisobotni sudda yoki nazorat organida ko'rsatish mumkin (docs/22 § 3.1).

Tizim BELGI topadi, XULOSA emas — shuning uchun hisobot oxiridagi
yuridik izohni o'chirib bo'lmaydi (docs/22 § 5 C5).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from uzlegal.court.parser import CourtDecision, parse
from uzlegal.ingest.normalize import fold
from uzlegal.integrity.detector import detect_from_text
from uzlegal.integrity.patterns import FlagCategory, IntegrityProfile, RedFlag, Severity
from uzlegal.integrity.profile import JudgeProfile, build_profile

nazorat_app = typer.Typer(help="Nazorat moduli — pora belgilari", no_args_is_help=True)
console = Console()

# Yuridik javobgarlik matni bitta joyda turadi — `JudgeProfile` da. CLI uni
# ko'chirib yozmaydi, aks holda ikki nusxa vaqt o'tib bir-biridan uzoqlashadi.
DISCLAIMER: str = JudgeProfile(judge="").disclaimer

_CATEGORY_LABELS: dict[FlagCategory, str] = {
    FlagCategory.DISPROPORTIONATE: "nomutanosiblik",
    FlagCategory.PROCEDURAL: "protsessual tartib",
    FlagCategory.EVIDENCE: "dalil bilan ishlash",
    FlagCategory.TIMING: "muddat",
    FlagCategory.STRUCTURAL: "qaror tuzilmasi",
}

_SEVERITY_LABELS: dict[Severity, str] = {
    Severity.HIGH: "yuqori",
    Severity.MEDIUM: "o'rta",
    Severity.LOW: "past",
}

# Dalil satri qaror matnidan olinadi va uzun bo'lishi mumkin. Hisobot
# terminalda o'qilishi kerak, shuning uchun u qirqiladi — to'liq matn
# `--json` da qoladi.
_EVIDENCE_MAX = 160


# --------------------------------------------------------------------------- #
# Chiqish
# --------------------------------------------------------------------------- #


def _plain(line: str) -> None:
    """Hisobot satrini o'zgartirmasdan chiqaradi.

    `markup=False` — dalil qaror matnidan olinadi va unda `[` bo'lishi
    mumkin, rich esa uni uslub tegi deb o'qib yuboradi. `soft_wrap=True` —
    satr terminal kengligiga qarab sinmasin, aks holda ekrandagi hisobot
    `--out` bilan saqlangan fayldan farq qiladi.
    """
    console.print(line, markup=False, highlight=False, soft_wrap=True)


def _emit(lines: list[str], *, out: Path | None) -> None:
    """Hisobotni ekranga yoki faylga beradi.

    Fayl tanlansa ham yuridik izoh ekranda qoladi: uni chetlab o'tishning
    yo'li bo'lmasligi kerak (C5).
    """
    if out is None:
        for line in lines:
            _plain(line)
        return

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"[green]✓[/green] Saqlandi: {out}")
    _plain(DISCLAIMER)


def _json_lines(payload: dict[str, object]) -> list[str]:
    """JSON ni satrlarga bo'ladi — faylga va ekranga bir xil matn tushsin."""
    return json.dumps(payload, ensure_ascii=False, indent=2).splitlines()


# --------------------------------------------------------------------------- #
# Hisobot
# --------------------------------------------------------------------------- #


def _evidence(flag: RedFlag) -> str:
    """Belgining dalil satri; dalil bo'sh bo'lsa — ta'rifning o'zi."""
    raw = " ".join((flag.evidence or flag.description).split())
    return raw if len(raw) <= _EVIDENCE_MAX else raw[: _EVIDENCE_MAX - 1] + "…"


def _flag_lines(flags: list[RedFlag], *, indent: str) -> list[str]:
    """Belgilarni toifa bo'yicha guruhlaydi, har biriga dalil satri qo'shadi.

    Toifalar tartibi `_CATEGORY_LABELS` dan olinadi — belgilar ro'yxati
    o'zgarsa ham hisobot tartibi o'zgarmasin (chiqish deterministik).
    """
    grouped: dict[FlagCategory, list[RedFlag]] = {}
    for flag in flags:
        grouped.setdefault(flag.category, []).append(flag)

    out: list[str] = []
    for category, label in _CATEGORY_LABELS.items():
        bucket = grouped.get(category)
        if not bucket:
            continue
        out.append(f"{indent}{label} ({len(bucket)})")
        for flag in bucket:
            severity = _SEVERITY_LABELS[flag.severity]
            out.append(f"{indent}  [{severity}] {flag.code} · {flag.title}")
            out.append(f"{indent}    dalil: «{_evidence(flag)}»")
    return out


def _check_report(profile: IntegrityProfile, *, source: Path) -> list[str]:
    """Bitta qaror hisoboti (docs/22 § 3.3)."""
    lines = [f"Sud qarori: {source.name}"]
    if profile.judge:
        lines.append(f"  Sudya  {profile.judge}")
    if profile.court:
        lines.append(f"  Sud    {profile.court}")

    lines.append("")
    lines.append(f"Xavf darajasi: {profile.risk_score:.2f} — {profile.risk_label}")
    lines.append("")

    if profile.flags:
        lines.append(f"Belgilar: {len(profile.flags)}")
        lines.extend(_flag_lines(profile.flags, indent="  "))
    else:
        lines.append("Belgilar: 0 — qoidalar hech narsa topmadi")

    if profile.caveats:
        lines.append("")
        lines.append("Eslatmalar")
        lines.extend(f"  - {caveat}" for caveat in profile.caveats)

    lines.append("")
    lines.append(DISCLAIMER)
    return lines


def _profile_report(
    profile: JudgeProfile,
    *,
    names: list[str],
    notes: list[str],
    limit: int,
) -> list[str]:
    """Sudya profili hisoboti (docs/22 § 3.3)."""
    sentencing = profile.sentencing
    stats = profile.flag_stats

    lines = [f"Sudya profili: {profile.judge}"]
    if profile.court:
        lines.append(f"  Sud       {profile.court}")
    lines.append(f"  Qarorlar  {profile.case_count}")
    lines.extend(f"  (!) {note}" for note in notes)

    lines.append("")
    lines.append(f"Xavf darajasi: {profile.risk_score:.2f} — {profile.risk_label}")

    term = sentencing.average_term_years
    average = f"{term} yil" if term is not None else "—"
    lines.append("")
    lines.append("Jazo statistikasi")
    lines.append(f"  Ozodlikdan mahrum  {sentencing.custodial}")
    lines.append(f"  shundan shartli    {sentencing.suspended} ({sentencing.suspended_ratio:.0%})")
    lines.append(f"  Jarima             {sentencing.fines}")
    lines.append(f"  O'rtacha muddat    {average}")

    lines.append("")
    lines.append(
        f"Belgilar: {stats.total} · yuqori {stats.high} · o'rta {stats.medium} · past {stats.low}"
    )
    for category, label in _CATEGORY_LABELS.items():
        count = stats.by_category.get(category.value, 0)
        if count:
            lines.append(f"  {label:20} {count}")
    if stats.most_common:
        lines.append(f"  Eng ko'p takrorlangan: {', '.join(stats.most_common)}")

    shown = profile.per_case if limit <= 0 else profile.per_case[:limit]
    if shown:
        lines.append("")
        lines.append("Ishlar")
        for name, case in zip(names[: len(shown)], shown, strict=True):
            lines.append(
                f"  {name} — {case.risk_score:.2f} · {case.risk_label} · {len(case.flags)} belgi"
            )
            lines.extend(_flag_lines(case.flags, indent="    "))
        qolgan = len(profile.per_case) - len(shown)
        if qolgan > 0:
            lines.append(f"  … yana {qolgan} ish (hammasi uchun: --limit 0)")

    if profile.caveats:
        lines.append("")
        lines.append("Eslatmalar")
        lines.extend(f"  - {caveat}" for caveat in profile.caveats)

    lines.append("")
    lines.append(profile.disclaimer)
    return lines


# --------------------------------------------------------------------------- #
# Fayl o'qish — namuna `cli/pipeline.py` `redact()` da
# --------------------------------------------------------------------------- #


def _read_decision(path: Path) -> str:
    """Bitta qaror faylini o'qiydi; xato matnlari o'zbekcha (C4)."""
    if not path.exists():
        console.print(f"[red]✕[/red] Fayl topilmadi: {path}")
        raise typer.Exit(4)
    if path.is_dir():
        console.print(f"[red]✕[/red] Bu katalog, fayl kutilgan edi: {path}")
        raise typer.Exit(4)

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        console.print(f"[red]✕[/red] Fayl bo'sh: {path}")
        raise typer.Exit(2)
    return text


def _read_directory(path: Path, pattern: str) -> list[tuple[str, CourtDecision]]:
    """Katalogdagi qarorlarni fayl nomi bo'yicha tartiblab o'qiydi."""
    if not path.exists():
        console.print(f"[red]✕[/red] Katalog topilmadi: {path}")
        raise typer.Exit(4)
    if not path.is_dir():
        console.print(f"[red]✕[/red] Bu fayl, katalog kutilgan edi: {path}")
        raise typer.Exit(4)

    files = sorted(p for p in path.glob(pattern) if p.is_file())
    if not files:
        console.print(f"[red]✕[/red] «{pattern}» naqshiga mos fayl yo'q: {path}")
        raise typer.Exit(4)

    pairs: list[tuple[str, CourtDecision]] = []
    for file in files:
        text = file.read_text(encoding="utf-8")
        if not text.strip():
            # Bo'sh fayl butun to'plamni to'xtatmaydi — u o'tkazib
            # yuboriladi va bu ochiq aytiladi.
            console.print(f"[yellow]⚠[/yellow] Bo'sh fayl o'tkazildi: {file.name}")
            continue
        pairs.append((file.name, parse(text)))

    if not pairs:
        console.print(f"[red]✕[/red] O'qiladigan qaror topilmadi: {path}")
        raise typer.Exit(4)
    return pairs


# --------------------------------------------------------------------------- #
# Buyruqlar
# --------------------------------------------------------------------------- #


@nazorat_app.command("check")
def nazorat_check(
    path: Path = typer.Argument(..., help="Sud qarori matni (fayl)"),
    json_out: bool = typer.Option(False, "--json", help="Mashina uchun JSON"),
    out: Path = typer.Option(None, "--out", help="Hisobot yoziladigan fayl"),
) -> None:
    """Bitta sud qarorida pora belgilarini tekshiradi (docs/22 § 3.2).

    Model chaqirilmaydi: chiqish deterministik qoidalardan keladi va
    shuning uchun takrorlanadi. Tizim BELGI topadi, XULOSA emas.
    """
    profile = detect_from_text(_read_decision(path))

    if json_out:
        payload: dict[str, object] = profile.model_dump()
        # `IntegrityProfile` da bu maydon yo'q, `JudgeProfile` da bor.
        # Yuridik izoh esa ikkala buyruqda ham majburiy (C5), shuning
        # uchun u JSON ichiga ham qo'shiladi.
        payload["disclaimer"] = DISCLAIMER
        _emit(_json_lines(payload), out=out)
        return

    _emit(_check_report(profile, source=path), out=out)


@nazorat_app.command("profile")
def nazorat_profile(
    path: Path = typer.Argument(..., help="Sud qarorlari katalogi"),
    judge: str = typer.Option(None, "--judge", help="Faqat shu sudyaning qarorlari"),
    pattern: str = typer.Option("*.txt", "--pattern", help="Katalogdagi fayl naqshi"),
    limit: int = typer.Option(10, "--limit", help="Nechta ish batafsil ko'rsatilsin (0 — hammasi)"),
    json_out: bool = typer.Option(False, "--json", help="Mashina uchun JSON"),
    out: Path = typer.Option(None, "--out", help="Hisobot yoziladigan fayl"),
) -> None:
    """Katalogdagi qarorlar bo'yicha sudya profilini tuzadi (docs/22 § 3.2).

    Bitta qarordan xulosa chiqarib bo'lmaydi — profil takrorlanadigan
    naqshni ko'rsatadi, ayblov emas.
    """
    pairs = _read_directory(path, pattern)

    notes: list[str] = []
    if judge:
        needle = fold(judge)
        pairs = [(name, d) for name, d in pairs if needle in fold(d.judge or "")]
        if not pairs:
            console.print(f"[red]✕[/red] «{judge}» sudyasining qarori topilmadi: {path}")
            raise typer.Exit(4)
    else:
        # Aralash katalog profilni ma'nosiz qiladi: statistika bir necha
        # sudyaning qarorlarini bitta odamniki kabi ko'rsatadi.
        found = sorted({d.judge for _, d in pairs if d.judge})
        if len(found) > 1:
            notes.append(
                f"Katalogda {len(found)} xil sudya nomi bor "
                f"({', '.join(found)}) — --judge bilan torayting."
            )

    names = [name for name, _ in pairs]
    decisions = [decision for _, decision in pairs]
    label = judge or decisions[0].judge or "Noma'lum"
    profile = build_profile(label, decisions)

    if json_out:
        # `JudgeProfile.disclaimer` — model maydoni; u `model_dump()` ichida
        # o'zi keladi va shuning uchun JSON dan tushib qolmaydi (C5).
        _emit(_json_lines(profile.model_dump()), out=out)
        return

    _emit(_profile_report(profile, names=names, notes=notes, limit=limit), out=out)
