"""Count a manual import's 目次 against the corpus, per speaker.

    uv run python scripts/audit_manual.py <downloads-dir> <corpus.jsonl>

`audit.py` re-walks a site's listing to find what the crawler asked for and
failed to get. A hand-downloaded corpus has no listing to re-walk — but DB-Search
publishes a 目次 document beside every 本文, and the 目次 names each member who
spoke that day:

    水岸富美男議員質疑　………………………………………………九
    知　事　答　弁　………………………………………………一〇

So the 目次 is the listing side, free and offline. Two things it catches:

* a **file never downloaded** — a 目次 whose 本文 is not in the corpus at all,
  which on a manual collection is the likeliest loss of the lot and the one
  nothing else can see;
* a **speaker the marker rule missed** — a member the 目次 names on a date whose
  corpus record does not have them, which is the manual-import form of the
  swallowed-marker check.

It reports 目次 with no matching 本文 as well: downloading one and not the other
is easy to do and leaves no other trace.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

from prefectural_transcripts.importers.dbsearch import (
    INDEX_KIND,
    TRANSCRIPT_KIND,
    _parse_header,
    decode,
    find_downloads,
)
from prefectural_transcripts.scrapers.generic import normalize_speaker
from prefectural_transcripts.storage import read_meetings

# 「水岸富美男議員質疑」「菅野幹子議員反対討論」 — the 目次 names a member and what
# they did. Only the 議員 entries are used: 「知　事　答　弁」 names an office and
# pads it with spaces, so it identifies no one in particular.
_ENTRY = re.compile(
    r"(?P<name>[^\s\u3000…・]{2,12}?)議員"
    r"(?:代表質問|一般質問|反対討論|賛成討論|質疑|質問|討論)"
)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    downloads, corpus = Path(argv[0]), Path(argv[1])

    by_date: dict[str, set[str]] = defaultdict(set)
    bodies: set[str] = set()
    for path in find_downloads(downloads):
        try:
            header = _parse_header(decode(path.read_bytes()).split("\n")[0])
        except (ValueError, OSError) as exc:
            print(f"   ? {path.name}: {exc}")
            continue
        key = f"{header.date} {header.session}"
        if header.kind == TRANSCRIPT_KIND:
            bodies.add(key)
        elif header.kind == INDEX_KIND:
            text = decode(path.read_bytes())
            by_date[key] |= {normalize_speaker(m["name"]) for m in _ENTRY.finditer(text)}

    collected: dict[str, set[str]] = defaultdict(set)
    for meeting in read_meetings(corpus):
        collected[f"{meeting.date} {meeting.session}"] |= {s.speaker for s in meeting.speeches}

    orphan_index = sorted(k for k in by_date if k not in bodies)
    orphan_body = sorted(k for k in bodies if k not in by_date)
    uncollected = sorted(k for k in bodies if k not in collected)

    print(
        f"{downloads}: {len(bodies)} 本文, {len(by_date)} 目次, "
        f"corpus holds {len(collected)} sittings"
    )
    for label, items in (
        ("downloaded but not in the corpus", uncollected),
        ("目次 downloaded with no 本文", orphan_index),
        ("本文 downloaded with no 目次", orphan_body),
    ):
        if items:
            print(f"   {len(items)} {label}")
            for key in items[:20]:
                print(f"      {key}")

    missing = 0
    for key, named in sorted(by_date.items()):
        absent = named - collected.get(key, set())
        if absent:
            missing += len(absent)
            print(f"   {key}: 目次 names {', '.join(sorted(absent))}, corpus does not")
    print(f"   {missing} speakers named by a 目次 and missing from the corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
