"""Copy a delivery of 鳥取's 本会議 files into manual/鳥取県, under readable names.

The secretariat's zip (2026-10-14) stores Shift_JIS file names without the
UTF-8 flag, so the unzip on this machine read them as cp437 and wrote
「H19öN」 for 「H19年」 and 「æµéPìå.txt」 for 「第１号.txt」. Encoding the
name back to cp437 recovers the original bytes, which are cp932.

Two shapes arrive, and they are filed differently:

- **The search system's export (H19〜)** — every file is 「document (N).txt」,
  numbered per folder, and its identity is its first line,
  「2007年02月19日：平成19年２月定例会（第２号）　本文」. It is filed as
  ``export/20070219_平成19年2月定例会_第2号.txt``, so a file sent again replaces
  the old one instead of arriving as a second 「document (16).txt」.
- **A later delivery in DB-Search's download shape** (received 2026-11-09) —
  「download (N).txt」, first line 「令和７年９月定例会（第２号）　本文 :
  2025-09-16」. Filed as ``download/20250916_令和7年9月定例会_第2号.txt``, beside
  ``export/`` rather than in it, because the importer reads the shapes apart.
  Such files may also sit at the top of the zip, outside any era folder.
- **The secretariat's own files (H15〜H18)** — one folder per session, named by
  hand. They keep their folder and file names, with only the mojibake undone.

The bytes are copied unchanged. Nothing here reads the network; nothing is
deleted from the source.

    uv run python scripts/tottori_receive.py data manual/鳥取県 [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import unicodedata
from pathlib import Path

EXPORT_HEADER = re.compile(r"^(\d{4})年(\d\d)月(\d\d)日：(.+?)（(第.+?号)）[\s　]*本文\s*$")
DOWNLOAD_HEADER = re.compile(
    r"^(.+?)（(第.+?号)）[\s　]*本文[\s　]*:[\s　]*(\d{4})-(\d\d)-(\d\d)\s*$"
)


def unmangle(name: str) -> str:
    """「H19öN」 -> 「H19年」; a name that was never mangled comes back unchanged."""
    try:
        return name.encode("cp437").decode("cp932")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def first_line(path: Path) -> str:
    text = path.read_bytes().decode("cp932", errors="replace")
    return text.lstrip("\r\n").splitlines()[0] if text.strip() else ""


def target_of(path: Path, source: Path) -> Path:
    """Where one delivered file is filed, relative to the destination."""
    m = EXPORT_HEADER.match(first_line(path))
    if m:
        y, mo, d, session, number = m.groups()
        session = unicodedata.normalize("NFKC", session)
        number = unicodedata.normalize("NFKC", number)
        return Path("export") / f"{y}{mo}{d}_{session}_{number}.txt"
    m = DOWNLOAD_HEADER.match(first_line(path))
    if m:
        session, number, y, mo, d = m.groups()
        session = unicodedata.normalize("NFKC", session)
        number = unicodedata.normalize("NFKC", number)
        return Path("download") / f"{y}{mo}{d}_{session}_{number}.txt"
    parts = [unmangle(p) for p in path.relative_to(source).parts]
    return Path("H15-H18", *parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", type=Path, help="where the zip was extracted")
    ap.add_argument("dest", type=Path, help="manual/鳥取県")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Only the era folders: 「H15」…「H18」 and the mangled 「H19年」…「R7年」.
    roots = sorted(
        p for p in args.source.iterdir() if p.is_dir() and re.match(r"[HR]\d", unmangle(p.name))
    )
    files = sorted(f for r in roots for f in r.rglob("*") if f.is_file())
    # Loose files at the top count only when their first line says what they are.
    files += sorted(
        f
        for f in args.source.glob("*.txt")
        if EXPORT_HEADER.match(first_line(f)) or DOWNLOAD_HEADER.match(first_line(f))
    )
    seen: dict[Path, Path] = {}
    for f in files:
        target = target_of(f, args.source)
        if target in seen:
            print(f"COLLISION: {seen[target]} and {f} both file as {target}", file=sys.stderr)
            return 1
        seen[target] = f
    for target, f in seen.items():
        out = args.dest / target
        if args.dry_run:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
    kinds = {k: sum(1 for t in seen if t.parts[0] == k) for k in ("export", "download", "H15-H18")}
    verb = "would copy" if args.dry_run else "copied"
    print(f"{verb} {len(seen)} files: " + ", ".join(f"{n} {k}" for k, n in kinds.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
