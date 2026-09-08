"""Re-parse a collected corpus from cache, in place.

Zero requests: every response body is on disk, so this costs nothing and can be
run as often as a rule changes. It is the check this repository keeps asking for
— *re-parse and diff before and after a rule change* — and the only way to bring
records collected under an older rule into line without asking the site again.

    uv run python scripts/reparse.py <site>[,<site>...] <corpus.jsonl> [backup.jsonl]

**Name every site that writes into the corpus.** One file holds a prefecture, and
a prefecture is more than one site: 静岡's 32,275 records are 14,030 本会議 under
`ggiji.nsf` and 18,245 委員会 under `comgiji.nsf`, and 和歌山 is the same shape.
Re-parsing all of them with one scraper does not fail — the 本会議 rule requires a
「君」 no committee marker carries, so it would rewrite 18,245 documents to zero
speeches and report it as a diff. Records are routed by URL to the site whose
`start_urls` they came from, and a record no named site claims stops the run
before anything is written.

The previous contents are copied to the backup path first (default: the corpus
with a `.bak` suffix). What it prints is the diff that matters: how many speeches
before and after, and which sittings changed.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

from prefectural_transcripts.config import Settings
from prefectural_transcripts.http import PoliteClient
from prefectural_transcripts.models import MeetingRef
from prefectural_transcripts.scrapers import load_scraper
from prefectural_transcripts.scrapers.base import BaseScraper


def _prefixes(scraper: BaseScraper) -> list[str]:
    """The URL prefixes a site's documents live under, from its own start_urls.

    A Domino application is one `.nsf` and everything it serves hangs off it, so
    the directory of a start URL separates 静岡's two sites cleanly. Taking the
    directory rather than the whole URL matters because the listing carries a
    query string and the documents do not.
    """
    out = []
    for url in getattr(scraper.config, "start_urls", []) or []:
        split = urlsplit(str(url))
        directory = split.path.rsplit("/", 1)[0]
        out.append(f"{split.scheme}://{split.netloc}{directory}/")
    return sorted(set(out), key=len, reverse=True)


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print(__doc__)
        return 2
    names, corpus = argv[0].split(","), Path(argv[1])
    backup = Path(argv[2]) if len(argv) == 3 else corpus.with_suffix(corpus.suffix + ".bak")

    scrapers = {name: load_scraper(name) for name in names}
    routes = [(prefix, name) for name in names for prefix in _prefixes(scrapers[name])]
    routes.sort(key=lambda pair: len(pair[0]), reverse=True)

    records = [json.loads(line) for line in corpus.open(encoding="utf-8") if line.strip()]

    def route(url: str) -> str | None:
        return next((name for prefix, name in routes if url.startswith(prefix)), None)

    # Route everything before touching the file: a record nobody claims would be
    # re-parsed by the wrong rule, and the wrong rule here means zero speeches.
    unclaimed = [r["url"] for r in records if route(r["url"]) is None]
    if unclaimed:
        print(f"{len(unclaimed)} records match none of {names}; nothing written. First:")
        for url in unclaimed[:5]:
            print(f"  {url}")
        return 1

    shutil.copy(corpus, backup)
    out: list[str] = []
    before = after = changed = 0
    per_site: dict[str, int] = dict.fromkeys(names, 0)
    with PoliteClient(Settings()) as client:
        for record in records:
            name = route(record["url"])
            assert name is not None  # checked above, before the backup was taken
            scraper = scrapers[name]
            per_site[name] += 1
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
        f"{'+'.join(f'{n}:{c}' for n, c in per_site.items())}; "
        f"{len(records)} records rewritten; speeches {before} -> {after} "
        f"({after - before:+d}); {changed} sittings changed. Backup at {backup}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
