"""`pipeline dates --apply` natijasini zaxira bilan solishtirish — docs/22 § 5 A6.

`chunk_id`, `heading` va `content` **bitta bo'lakda ham** o'zgarmasligi
kerak: LanceDB qatorlari va BM25 indeksi aynan shu kalitlarga bog'langan.

    .venv/Scripts/python.exe scripts/check-dates-apply.py kb/current/chunks.jsonl.20260814.bak
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> int:
    backup = Path(sys.argv[1])
    current = Path(sys.argv[2]) if len(sys.argv) > 2 else backup.parent / "chunks.jsonl"

    before, after = rows(backup), rows(current)
    if len(before) != len(after):
        print(f"XATO: bo'lak soni o'zgardi {len(before)} → {len(after)}")
        return 1

    stable = Counter[str]()
    changed = Counter[str]()
    for a, b in zip(before, after, strict=True):
        for key in ("chunk_id", "heading", "content", "doc_id", "status", "valid_to"):
            if a.get(key) != b.get(key):
                stable[key] += 1
        if a.get("valid_from") != b.get("valid_from"):
            changed["valid_from"] += 1
            if a.get("valid_from") is not None:
                changed["mavjud sana bosildi"] += 1

    print(f"Bo'lak {len(before)} · valid_from o'zgardi {changed['valid_from']}")
    print(f"Mavjud sana bosildi: {changed['mavjud sana bosildi']}")
    print(f"Tegilmasligi kerak bo'lgan maydonlardagi farq: {sum(stable.values())} {dict(stable)}")
    dated = sum(1 for r in after if r.get("valid_from"))
    print(f"Sanali bo'lak: {sum(1 for r in before if r.get('valid_from'))} → {dated}")
    return 1 if (sum(stable.values()) or changed["mavjud sana bosildi"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
