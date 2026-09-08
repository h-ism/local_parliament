"""Re-parse a collected corpus from cache, in place.

Zero requests: every response body is on disk, so this costs nothing and can be
run as often as a rule changes. It is the check this repository keeps asking for
— *re-parse and diff before and after a rule change* — and the only way to bring
records collected under an older rule into line without asking the site again.

    uv run python scripts/reparse.py <site> <corpus.jsonl> [backup.jsonl]

The previous contents are copied to the backup path first (default: the corpus
with a `.bak` suffix). What it prints is the diff that matters: how many speeches
before and after, and which sittings changed.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from prefectural_transcripts.config import Settings
from prefectural_transcripts.http import PoliteClient
from prefectural_transcripts.models import MeetingRef
from prefectural_transcripts.scrapers import load_scraper


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print(__doc__)
        return 2
    site, corpus = argv[0], Path(argv[1])
    backup = Path(argv[2]) if len(argv) == 3 else corpus.with_suffix(corpus.suffix + ".bak")

    scraper = load_scraper(site)
    records = [json.loads(line) for line in corpus.open(encoding="utf-8") if line.strip()]
    shutil.copy(corpus, backup)

    out: list[str] = []
    before = after = changed = 0
    with PoliteClient(Settings()) as client:
        for record in records:
            ref = MeetingRef(
                prefecture=scraper.prefecture,
                url=record["url"],
                date=record.get("date"),
                title=record.get("title"),
            )
            meeting = scraper.parse_meeting(ref, scraper.fetch_meeting(ref, client))
            before += len(record["speeches"])
            after += len(meeting.speeches)
            if len(meeting.speeches) != len(record["speeches"]):
                changed += 1
                print(
                    f"  {(record.get('title') or record['url'])[:48]}: "
                    f"{len(record['speeches'])} -> {len(meeting.speeches)}"
                )
            out.append(meeting.model_dump_json())
    corpus.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(
        f"{site}: {len(records)} records rewritten; speeches {before} -> {after} "
        f"({after - before:+d}); {changed} sittings changed. Backup at {backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
