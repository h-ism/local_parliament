"""Fetch a spread sample of 滋賀・石川's committee sittings, into the cache only.

The committee side is decided (summary, 2026-10-15) and not configured: its
markers are a new shape — 「◆重田剛　委員」「◎橋本　財政課長」 — and the cache
holds one committee-year per site, which a rule cannot be written from
(`docs/shiga.md`). This takes the sample a rule *can* be written from: the whole
committee listing (cheap — the year pages are mostly cached), then a few
sittings from every year, rotating through the committees so that no one of
them is the sample. Nothing is written to `data/*.jsonl`: the config is written
afterwards, offline, from what this leaves in the cache.

The site's own config supplies the conditions — window, robots exemption,
contact — through `cli.client_for`, so the sample keeps the same promises as the
collection. Outside the window it refuses before the first request; when the
window closes mid-sample it stops, and the next run resumes from the cache.
A marker file says when a site's sample is complete, so the collector runs this
once and not every weekend.

    uv run python scripts/sample_committees.py shiga ishikawa
    uv run python scripts/sample_committees.py shiga --per-year 2 --delay 2
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from prefectural_transcripts.cli import client_for
from prefectural_transcripts.config import Settings
from prefectural_transcripts.http import FetchError, OutsideFetchWindow, current_time
from prefectural_transcripts.models import MeetingRef
from prefectural_transcripts.scrapers import VoicesScraper, load_scraper

log = logging.getLogger("sample_committees")

COMMITTEE_INDEX = {
    # The 本会議 configs index g08v_viewh.asp; committees are its sibling.
    "shiga": "https://www.shigaken-gikai.jp/voices/g08v_views.asp",
    "ishikawa": "https://pref-ishikawa.gijiroku.com/voices/g08v_views.asp",
}
LOGS = Path("data/logs")

# 「平成２４年　９月１２日」: the vendor pads the month and day with U+3000.
_LEADING_DATE = re.compile(
    r"^(?:令和|平成|昭和)\s*[元0-9]{1,2}\s*年(?:\s*[0-9]{1,2}\s*月)?(?:\s*[0-9]{1,2}\s*日)?\s*"
)


def committee_of(ref: MeetingRef) -> str:
    """「平成２４年１２月２１日文教・警察常任委員会 12月21日-01号」 -> 文教・警察常任委員会."""
    title = unicodedata.normalize("NFKC", ref.title or "")
    words = _LEADING_DATE.sub("", title).split()
    # 「令和８年２月定例会議 予算特別委員会 …」 puts the session first.
    named = [w for w in words if re.search(r"委員会|分科会|協議会", w)]
    return (named or words or [title])[0]


def spread(refs: list[MeetingRef], per_year: int) -> list[MeetingRef]:
    """`per_year` sittings from every year, rotating through the committees.

    Deterministic: the same listing gives the same sample, so a run cut short
    by the window resumes the same sample rather than drawing a new one.
    """
    by_year: dict[int, dict[str, list[MeetingRef]]] = defaultdict(lambda: defaultdict(list))
    for ref in refs:
        year = ref.date.year if ref.date else 0
        by_year[year][committee_of(ref)].append(ref)
    picked: list[MeetingRef] = []
    used: dict[str, int] = defaultdict(int)
    for year in sorted(by_year):
        committees = by_year[year]
        for _ in range(per_year):
            # The committee sampled least so far, then the one listed first.
            name = min(committees, key=lambda c: (used[c], c))
            if not committees[name]:
                committees.pop(name)
                if not committees:
                    break
                name = min(committees, key=lambda c: (used[c], c))
            group = committees[name]
            picked.append(group.pop(len(group) // 2))  # the middle of its year
            used[name] += 1
            if not group:
                committees.pop(name)
            if not committees:
                break
    return picked


def sample(site: str, per_year: int, delay: float) -> bool:
    scraper = load_scraper(site)
    assert isinstance(scraper, VoicesScraper), site
    done = LOGS / site / "committee-sample.done"
    if done.exists():
        print(f"{site}: committee sample already complete ({done})")
        return True
    if (window := scraper.fetch_window) and not window.allows(current_time()):
        print(f"{site}: outside the agreed hours — {window.next_opening(current_time())}")
        return False

    settings = Settings()
    settings.min_interval = max(delay, settings.min_interval)
    if scraper.contact:
        settings.contact = scraper.contact.address
    scraper.config.index_url = COMMITTEE_INDEX[site]

    report = LOGS / site / f"committee-sample-{current_time():%Y%m%d-%H%M}.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    fetched = failed = 0
    with client_for(scraper, settings) as client, report.open("w", encoding="utf-8") as out:
        try:
            refs = list(scraper.list_meetings(client))
            chosen = spread(refs, per_year)
            out.write(f"{len(refs)} committee documents listed; {len(chosen)} sampled\n")
            for ref in chosen:
                try:
                    page = scraper.fetch_meeting(ref, client)
                except FetchError as exc:
                    failed += 1
                    out.write(f"FAILED {ref.date} {committee_of(ref)} {ref.url}: {exc}\n")
                    continue
                fetched += 1
                out.write(
                    f"{ref.date} {committee_of(ref)} | {ref.title} | {len(page.body)} bytes\n"
                )
        except OutsideFetchWindow as exc:
            out.write(f"STOPPED: {exc}\n")
            print(f"{site}: the window closed after {fetched} sittings; resumes next window")
            return False
    print(f"{site}: {fetched} sampled, {failed} failed — {report}")
    if failed == 0:
        done.write_text(f"{current_time().isoformat()} {fetched} sittings\n", encoding="utf-8")
    return failed == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("sites", nargs="+", choices=sorted(COMMITTEE_INDEX))
    parser.add_argument("--per-year", type=int, default=2)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s: %(message)s")
    ok = [sample(site, args.per_year, args.delay) for site in args.sites]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
