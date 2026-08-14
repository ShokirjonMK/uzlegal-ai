"""Sana aniqligini tekshirish — docs/22 § 5 A8.

Namuna hujjatlarda parser ajratgan `adopted_at` xom HTML dagi
`<title>` tegidagi sana bilan solishtiriladi. Etalon **mustaqil**
usulda olinadi: tegdagi birinchi `KK.OO.YYYY` shakli to'g'ridan-to'g'ri
regex bilan o'qiladi, parser kodi ishlatilmaydi. Shu bois bu skript
parserning o'z mantiqini takrorlamaydi va uning xatosini yashira
olmaydi.

    .venv/Scripts/python.exe scripts/check-date-accuracy.py --sample 20

Noto'g'ri sana bo'lsa chiqish kodi 1 bo'ladi.
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uzlegal.ingest.connectors.lex_uz import LexUzConnector  # noqa: E402
from uzlegal.ingest.parsers.lex_uz import LexUzParser  # noqa: E402

TITLE_TAG = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)
RAW_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
# Sarlavhaga tushmasligi kerak bo'lgan prefiks: «OʻRQ-982-сон 25.10.2024.»
# Defis majburiy — usiz «Inson huquqlari…» kabi nom ham «-son» deb
# noto'g'ri belgilanadi.
PREFIX = re.compile(r"^\s*[\wʻʼ'-]+-(?:сон|son)\b|^\s*\d{1,2}\.\d{1,2}\.\d{4}")


def reference_date(html: str) -> str | None:
    """`<title>` tegidagi birinchi sana — qo'lda o'qishga teng etalon."""
    tag = TITLE_TAG.search(html)
    if tag is None:
        return None
    m = RAW_DATE.search(tag.group(1))
    if m is None:
        return None
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--seed", type=int, default=22)
    ap.add_argument("--all", action="store_true", help="Butun arxiv bo'yicha")
    args = ap.parse_args()

    connector = LexUzConnector()
    parser = LexUzParser()
    paths = sorted(connector.raw_dir.glob("*.html"))
    if not args.all:
        paths = random.Random(args.seed).sample(paths, min(args.sample, len(paths)))

    wrong = 0
    missing = 0
    prefixed = 0
    for path in paths:
        doc_id = connector._from_safe_name(path.stem)
        raw = connector.load_cached(doc_id)
        if raw is None:
            continue
        doc = parser.parse(raw)
        expected = reference_date(raw.content)
        mark = "OK "
        if doc.adopted_at is None:
            mark, missing = "YO'Q", missing + 1
        elif doc.adopted_at != expected:
            mark, wrong = "XATO", wrong + 1
        if PREFIX.match(doc.title):
            mark, prefixed = "PREFIKS", prefixed + 1
        if not args.all or mark != "OK ":
            print(f"{mark:8} {doc_id:>10}  {doc.adopted_at}  etalon {expected}  {doc.title[:60]}")

    total = len(paths)
    print(f"\nTekshirildi {total} · noto'g'ri {wrong} · sanasiz {missing} · prefiksli {prefixed}")
    return 1 if (wrong or missing or prefixed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
