"""Count a site's listing against the corpus, per item.

    uv run python scripts/audit.py <site> <corpus.jsonl>

The total is not the check; the per-URL difference is. 愛媛 once reported 201
sittings and looked complete while the listing offered 212 — of the eleven, eight
were correctly filtered and **three were fetch failures nobody had noticed**.
Re-listing costs nothing because every index page is cached, and this is the only
check that catches a document the crawler asked for and failed to get.

One corpus file may hold more than one site (本会議 and 委員会 write to the same
prefecture), so what is compared is the listing against the whole file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from prefectural_transcripts.config import Settings
from prefectural_transcripts.http import PoliteClient
from prefectural_transcripts.scrapers import load_scraper


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    site, corpus = argv[0], Path(argv[1])
    scraper = load_scraper(site)
    have = {json.loads(line)["url"] for line in corpus.open(encoding="utf-8") if line.strip()}

    listed: dict[str, str] = {}
    with PoliteClient(Settings()) as client:
        for ref in scraper.list_meetings(client):
            listed[str(ref.url)] = f"{ref.date} {ref.title or ''}"

    missing = [url for url in listed if url not in have]
    print(
        f"{site}: listing offers {len(listed)}, corpus holds {len(have)} for this prefecture, "
        f"{len(missing)} listed but not collected"
    )
    for url in missing[:40]:
        print(f"   {listed[url][:60]}  {url}")
    if len(missing) > 40:
        print(f"   … and {len(missing) - 40} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
