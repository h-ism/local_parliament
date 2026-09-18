"""Reconnaissance on the gijiroku VOICES installs that have answered, in their hours.

Two assemblies have now permitted collection on the same condition — 滋賀 on
2026-09-18 and 石川 the same day — and both said the same thing: fetch only on
weekend evenings, from 20:00. They run the same product (`/voices/`), whose
robots.txt closes the CGI directory as vendor boilerplate across all nine
installs; the operators' own answers are what these exemptions rest on.

**Why a separate script rather than `pt inspect`.** The window is a few hours a
week and thinking is not. Everything this fetches lands in the cache, so the work
that needs judgement — reading the markup, writing the selectors, counting what a
rule catches — happens afterwards, offline, at no cost to their servers. Fetch
inside the window; think outside it.

Bounded on purpose: at most `MAX_PAGES` pages per site, all under that site's own
`/voices/`, 2 seconds apart (the first undertaking in our letter), and
`PoliteClient` refuses outright when the window is shut — so a timer that fires
on a Tuesday fetches nothing at all and says why.

    uv run python scripts/recon_voices.py             # every site that has answered
    uv run python scripts/recon_voices.py shiga       # one of them
    uv run python scripts/recon_voices.py --dry-run
"""

from __future__ import annotations

import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from prefectural_transcripts.config import Contact, FetchWindow, RobotsExemption, Settings
from prefectural_transcripts.http import (
    FetchError,
    OutsideFetchWindow,
    Page,
    PoliteClient,
    current_time,
)

log = logging.getLogger("recon")

MAX_PAGES = 40
MAX_DEPTH = 2

# Both answers name the same hours, and both letters were sent by the same
# collaborator, so the address they have on file is 共同研究者A's.
WEEKEND_EVENINGS = dict(days=(5, 6), start=time(20, 0), end=time(0, 0), decided_on="2026-09-18")
CONTACT = Contact(
    address="(共同研究者Aの連絡先)",
    note="照会は共同研究者Aが行った",
)


@dataclass(frozen=True, slots=True)
class Site:
    key: str
    prefecture: str
    start: str
    window: FetchWindow
    exemption: RobotsExemption
    note: str = ""


def _voices(key: str, prefecture: str, host: str, who: str, reason: str, note: str = "") -> Site:
    prefix = f"https://{host}/voices/"
    return Site(
        key=key,
        prefecture=prefecture,
        start=prefix,
        window=FetchWindow(reason=reason, **WEEKEND_EVENINGS),  # type: ignore[arg-type]
        exemption=RobotsExemption(
            prefixes=(prefix,),
            reason=(
                f"{who} 2026-09-18: 自動取得を許可、土日20時以降に限定。"
                "robots.txt の Disallow: /voices/cgi/ はベンダー標準で、"
                f"運営者本人の回答が優先する。docs/{key}.md"
            ),
            decided_on="2026-09-18",
        ),
        note=note,
    )


SITES: dict[str, Site] = {
    site.key: site
    for site in (
        _voices(
            "shiga",
            "滋賀県",
            "www.shigaken-gikai.jp",
            "滋賀県議会事務局",
            "滋賀県議会事務局の指示 (2026-09-18): 取得の時間帯を土日の夜間帯（20時以降）に限定"
            "するようお願い申し上げます",
        ),
        _voices(
            "ishikawa",
            "石川県",
            "pref-ishikawa.gijiroku.com",
            "石川県議会事務局企画調査課",
            "石川県議会事務局企画調査課の指示 (2026-09-18): 取得の時間帯を土日の夜間帯"
            "（20時以降など）に限定いただいた上での自動取得は可能",
            note=(
                "定例会の会期中（9月30日まで）につき、取得時間帯にくれぐれも留意するよう"
                "念を押されている。会期中は下見にとどめ、本収集は10月以降に回すのが安全。"
            ),
        ),
    )
}


def settings() -> Settings:
    s = Settings()
    s.contact = CONTACT.address
    s.min_interval = 2.0  # our first undertaking to them
    return s


def links(page: Page) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page.text, "lxml")
    return [
        (node.get_text(" ", strip=True)[:60], urldefrag(urljoin(page.url, str(node["href"]))).url)
        for node in soup.find_all("a", href=True)
    ]


def title(page: Page) -> str:
    soup = BeautifulSoup(page.text, "lxml")
    return soup.title.get_text(strip=True) if soup.title else ""


def shape(url: str) -> str:
    """A URL with its numbers blanked, so repeated shapes collapse into one row."""
    return re.sub(r"\d+", "N", urlparse(url).path)


def walk(site: Site, client: PoliteClient) -> list[tuple[str, Page]]:
    seen: set[str] = set()
    queue: list[tuple[str, int]] = [(site.start, 0)]
    fetched: list[tuple[str, Page]] = []
    while queue and len(fetched) < MAX_PAGES:
        url, depth = queue.pop(0)
        if url in seen or not url.startswith(site.start):
            continue
        seen.add(url)
        try:
            page = client.get(url)
        except OutsideFetchWindow:
            log.warning("%s: the window closed mid-run; stopping at %d", site.key, len(fetched))
            break
        except FetchError as exc:
            log.warning("%s: could not fetch %s: %s", site.key, url, exc)
            continue
        fetched.append((url, page))
        found = links(page)
        log.info(
            "%s [%2d] %s — %s (%d links)", site.key, len(fetched), url, title(page), len(found)
        )
        if depth < MAX_DEPTH:
            queue.extend((u, depth + 1) for _, u in found if u not in seen)
    return fetched


def report(site: Site, fetched: list[tuple[str, Page]], out_dir: Path) -> Path:
    stamp = current_time().astimezone(site.window.zone)
    path = out_dir / f"recon-{stamp:%Y%m%d-%H%M}.txt"
    shapes: Counter[str] = Counter(shape(url) for url, _ in fetched)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(f"# {site.prefecture} recon {stamp:%Y-%m-%d %H:%M %Z}\n")
        fh.write(
            f"# {len(fetched)} pages, cap {MAX_PAGES}, depth {MAX_DEPTH}, start {site.start}\n"
        )
        if site.note:
            fh.write(f"# note: {site.note}\n")
        fh.write("\n## URL shapes\n")
        for form, count in shapes.most_common():
            fh.write(f"{count:4d}  {form}\n")
        fh.write("\n## Pages\n")
        for url, page in fetched:
            fh.write(f"\n--- {url}\n")
            fh.write(f"    status={page.status} encoding={page.encoding} bytes={len(page.body)}\n")
            fh.write(f"    title={title(page)}\n")
            for text, target in links(page)[:25]:
                fh.write(f"    link  {text!r} -> {target}\n")
    return path


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    wanted = args or list(SITES)

    failed = 0
    for key in wanted:
        site = SITES.get(key)
        if site is None:
            log.error("no such site %r; known: %s", key, ", ".join(SITES))
            failed += 1
            continue

        now = current_time()
        if not site.window.allows(now):
            log.error("%s: outside the agreed hours (%s)", key, site.window.describe())
            log.error(
                "  next window opens %s", site.window.next_open(now).strftime("%Y-%m-%d %H:%M %Z")
            )
            log.error("  %s", site.window.reason)
            failed += 1
            continue
        log.info("%s: inside the window; contact %s", key, CONTACT.address)
        if site.note:
            log.info("%s: %s", key, site.note)
        if dry_run:
            log.info("%s: --dry-run, would start at %s (cap %d)", key, site.start, MAX_PAGES)
            continue

        out_dir = Path(f"data/logs/{key}")
        out_dir.mkdir(parents=True, exist_ok=True)
        with PoliteClient(
            settings(), robots_exempt=site.exemption, fetch_window=site.window
        ) as client:
            fetched = walk(site, client)
        log.info(
            "%s: %d pages, all cached; report %s", key, len(fetched), report(site, fetched, out_dir)
        )

    if not dry_run and not failed:
        log.info("next: read the reports and the cache — selectors need no further requests")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
