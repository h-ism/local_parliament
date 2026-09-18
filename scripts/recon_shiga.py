"""Reconnaissance on 滋賀県議会's VOICES install, inside the agreed hours.

滋賀県議会事務局 permitted collection on 2026-09-18 and asked for one thing:
「取得の時間帯を土日の夜間帯（20時以降）に限定するようお願い申し上げます」. Nothing
here has ever been fetched — not even a page to work selectors out from — so the
first thing the window is good for is *looking*.

**Why a separate script rather than `pt inspect`.** The window is a few hours a
week and thinking is not. Everything this fetches lands in the cache, so the work
that needs judgement — reading the markup, writing the selectors, counting what a
rule catches — happens afterwards, offline, at no cost to their server. Fetch
inside the window; think outside it.

It is deliberately small and bounded:

* at most `MAX_PAGES` pages, all under `/voices/` on that host;
* 2 seconds apart, which is the first undertaking in our letter;
* `PoliteClient` refuses outright if the window is shut, so a scheduler that
  fires at the wrong time fetches nothing at all;
* the User-Agent carries 共同研究者A's address — the enquiry 滋賀 answered was made by
  a collaborator, and theirs is the address the secretariat has on file.

    uv run python scripts/recon_shiga.py            # inside the window
    uv run python scripts/recon_shiga.py --dry-run  # say what it would do, fetch nothing
"""

from __future__ import annotations

import logging
import re
import sys
from collections import Counter
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

START = "https://www.shigaken-gikai.jp/voices/"
PREFIX = "https://www.shigaken-gikai.jp/voices/"
MAX_PAGES = 40
MAX_DEPTH = 2

WINDOW = FetchWindow(
    days=(5, 6),
    start=time(20, 0),
    end=time(0, 0),
    reason=(
        "滋賀県議会事務局の指示 (2026-09-18): 取得の時間帯を土日の夜間帯（20時以降）に限定"
        "するようお願い申し上げます"
    ),
    decided_on="2026-09-18",
)

CONTACT = Contact(
    address="(共同研究者Aの連絡先)",
    note="照会は共同研究者Aが行い、2026-09-18 に許可を得た",
)

# robots.txt closes the CGI directory — the search engine itself — which is the
# vendor's boilerplate across all nine VOICES installs. The assembly that runs
# this one has since said in writing that collection is acceptable inside the
# hours above, so the exemption is theirs and not a reading of that file.
EXEMPTION = RobotsExemption(
    prefixes=(PREFIX,),
    reason=(
        "滋賀県議会事務局 2026-09-18: 取得を許可、土日20時以降に限定。robots.txt の "
        "Disallow: /voices/cgi/ はベンダー標準で、運営者本人の回答が優先する。docs/shiga.md"
    ),
    decided_on="2026-09-18",
)


def settings() -> Settings:
    s = Settings()
    s.contact = CONTACT.address
    s.min_interval = 2.0  # our first undertaking to them
    return s


def links(page: Page) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page.text, "lxml")
    out: list[tuple[str, str]] = []
    for node in soup.find_all("a", href=True):
        url = urldefrag(urljoin(page.url, str(node["href"]))).url
        out.append((node.get_text(" ", strip=True)[:60], url))
    return out


def title(page: Page) -> str:
    soup = BeautifulSoup(page.text, "lxml")
    return soup.title.get_text(strip=True) if soup.title else ""


def shape(url: str) -> str:
    """A URL with its numbers blanked, so repeated shapes collapse into one row."""
    path = urlparse(url).path
    return re.sub(r"\d+", "N", path)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    dry_run = "--dry-run" in sys.argv

    now = current_time()
    if not WINDOW.allows(now):
        opens = WINDOW.next_open(now)
        log.error("outside the agreed hours (%s)", WINDOW.describe())
        log.error("next window opens %s", opens.strftime("%Y-%m-%d %H:%M %Z"))
        log.error("%s", WINDOW.reason)
        return 1
    log.info("inside the window (%s); contact %s", WINDOW.describe(), CONTACT.address)
    if dry_run:
        log.info("--dry-run: would start at %s, at most %d pages", START, MAX_PAGES)
        return 0

    out_dir = Path("data/logs/shiga")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"recon-{now.astimezone(WINDOW.zone):%Y%m%d-%H%M}.txt"

    seen: set[str] = set()
    queue: list[tuple[str, int]] = [(START, 0)]
    fetched: list[tuple[str, Page]] = []
    shapes: Counter[str] = Counter()

    with PoliteClient(settings(), robots_exempt=EXEMPTION, fetch_window=WINDOW) as client:
        while queue and len(fetched) < MAX_PAGES:
            url, depth = queue.pop(0)
            if url in seen or not url.startswith(PREFIX):
                continue
            seen.add(url)
            try:
                page = client.get(url)
            except OutsideFetchWindow:
                log.warning("the window closed mid-run; stopping with %d pages", len(fetched))
                break
            except FetchError as exc:
                log.warning("could not fetch %s: %s", url, exc)
                continue

            fetched.append((url, page))
            shapes[shape(url)] += 1
            found = links(page)
            log.info("[%2d] %s — %s (%d links)", len(fetched), url, title(page), len(found))
            if depth < MAX_DEPTH:
                queue.extend((u, depth + 1) for _, u in found if u not in seen)

    with report.open("w", encoding="utf-8") as fh:
        fh.write(f"# 滋賀 recon {now.astimezone(WINDOW.zone):%Y-%m-%d %H:%M %Z}\n")
        fh.write(f"# {len(fetched)} pages, cap {MAX_PAGES}, depth {MAX_DEPTH}\n\n")
        fh.write("## URL shapes\n")
        for form, count in shapes.most_common():
            fh.write(f"{count:4d}  {form}\n")
        fh.write("\n## Pages\n")
        for url, page in fetched:
            fh.write(f"\n--- {url}\n")
            fh.write(f"    status={page.status} encoding={page.encoding} bytes={len(page.body)}\n")
            fh.write(f"    title={title(page)}\n")
            for text, target in links(page)[:25]:
                fh.write(f"    link  {text!r} -> {target}\n")

    log.info("%d pages fetched; everything is cached", len(fetched))
    log.info("report: %s", report)
    log.info("next: read the report and the cache, write the selectors — no more requests needed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
