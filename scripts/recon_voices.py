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
    """The page to begin at — the search form, or the directory when that is all
    we know."""

    prefix: str
    """The area the walk stays inside, and the area the operator answered about.

    Kept apart from `start` because they are different things: 滋賀's entry is
    `/voices/g07v_search.asp` while the permission and the exemption are about
    `/voices/`. Filtering on the start URL instead — which this did until
    2026-09-21 — means a walk that begins at a page follows nothing at all,
    because no other URL begins with that page's name.
    """

    window: FetchWindow
    exemption: RobotsExemption
    note: str = ""

    discover: tuple[str, ...] = ()
    """Where to look when the install is not at `start` any more.

    滋賀's `/voices/` turned out to be a 271-byte meta-refresh to the assembly's
    top page: the system has moved or been retired since the letter was written
    on 2026-08-26. These are walked with **robots enforced normally** — the
    exemption covers the path the operator answered about, not the whole host —
    so if their robots.txt closes the rest of the site, the walk stops there and
    the answer is to look in a browser instead.
    """

    discover_hint: str = r"会議録|議事録|会議|録画|検索|voices|gijiroku|minutes"
    """Only links whose text or URL says they might lead to the minutes."""

    avoid: str = r"Video|\.pdf$|\.docx?$|\.xlsx?$|\.zip$"
    """Links not worth a slot in the cap.

    石川's first run spent 23 of its 40 pages on 録画中継 (video) listings and one
    on a PDF. The cap exists to keep the visit small; it should be spent on the
    minutes."""


def _voices(
    key: str,
    prefecture: str,
    host: str,
    who: str,
    reason: str,
    note: str = "",
    discover: tuple[str, ...] = (),
    start: str = "",
) -> Site:
    prefix = f"https://{host}/voices/"
    return Site(
        key=key,
        prefecture=prefecture,
        start=start or prefix,
        prefix=prefix,
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
        discover=discover,
    )


# The rules file itself is always fetchable — RFC 9309 says so, and a parser
# that refused to read it could never learn what it says. The stdlib parser
# applies `Disallow: /` to `/robots.txt` like any other path, so it is named.
ROBOTS_READABLE = RobotsExemption(
    prefixes=("https://www.shigaken-gikai.jp/robots.txt",),
    reason="robots.txt itself, to find where 滋賀's minutes moved to. RFC 9309 §2.3.",
    decided_on="2026-09-21",
)


SITES: dict[str, Site] = {
    site.key: site
    for site in (  # noqa: E501
        _voices(
            "shiga",
            "滋賀県",
            "www.shigaken-gikai.jp",
            "滋賀県議会事務局",
            "滋賀県議会事務局の指示 (2026-09-18): 取得の時間帯を土日の夜間帯（20時以降）に限定"
            "するようお願い申し上げます",
            # Given by the researcher 2026-09-21. `/voices/` itself is only a
            # meta-refresh to the assembly's top page; the search form is here,
            # and the vendor's naming matches 石川's (g07…, g08v…).
            start="https://www.shigaken-gikai.jp/voices/g07v_search.asp",
            discover=(
                "https://www.shigaken-gikai.jp/robots.txt",
                "https://www.shigaken-gikai.jp/index.asp",
                "https://www.shigaken-gikai.jp/",
            ),
            note=(
                "/voices/ は3秒で ../index.asp に飛ばす移転案内だけになっている"
                "（2026-09-19 確認）。会議録検索システムの現在地が不明なので、"
                "まず探す。移った先の robots は別途確認すること。"
            ),
        ),
        _voices(
            "ishikawa",
            "石川県",
            "pref-ishikawa.gijiroku.com",
            "石川県議会事務局企画調査課",
            "石川県議会事務局企画調査課の指示 (2026-09-18): 取得の時間帯を土日の夜間帯"
            "（20時以降など）に限定いただいた上での自動取得は可能",
            # From the first window: the 本会議会議録 listing, rather than the
            # directory, so the cap is spent inside the archive instead of
            # rediscovering the way in.
            start="https://pref-ishikawa.gijiroku.com/voices/g08v_viewh.asp?Sflg=10",
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


def discover(site: Site, client: PoliteClient) -> list[tuple[str, str]]:
    """Follow the site's own signposts to wherever its minutes live now.

    Bounded hard: a dozen pages, same host, and only links that say they lead to
    a 会議録. What it prints is candidates for a human to choose between, not a
    new start URL it has decided on by itself.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    host = urlparse(site.start).netloc
    queue = list(site.discover)
    hint = re.compile(site.discover_hint)
    while queue and len(seen) < 12:
        url = queue.pop(0)
        if url in seen or urlparse(url).netloc != host:
            continue
        seen.add(url)
        try:
            page = client.get(url)
        except OutsideFetchWindow:
            raise
        except FetchError as exc:
            log.warning("%s: %s — %s", site.key, url, exc)
            continue
        for text, target in links(page):
            if hint.search(text) or hint.search(target):
                found.append((text, target))
                if target not in seen and len(queue) < 12:
                    queue.append(target)
    log.info("%s: %d pages walked, %d candidate links", site.key, len(seen), len(found))
    for text, target in dict((t, u) for t, u in found).items():
        log.info("%s:   %r -> %s", site.key, text, target)
    return found


def walk(site: Site, client: PoliteClient) -> list[tuple[str, Page]]:
    seen: set[str] = set()
    queue: list[tuple[str, int]] = [(site.start, 0)]
    fetched: list[tuple[str, Page]] = []
    avoid = re.compile(site.avoid)
    while queue and len(fetched) < MAX_PAGES:
        url, depth = queue.pop(0)
        if url in seen or not url.startswith(site.prefix) or avoid.search(url):
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
        exemption = site.exemption
        if site.discover:
            exemption = RobotsExemption(
                prefixes=exemption.prefixes + ROBOTS_READABLE.prefixes,
                reason=f"{exemption.reason} / {ROBOTS_READABLE.reason}",
                decided_on=exemption.decided_on,
            )
        with PoliteClient(settings(), robots_exempt=exemption, fetch_window=site.window) as client:
            fetched = walk(site, client)
            if site.discover and len(fetched) <= 1:
                # One page and no further links means the install is not there
                # any more. Go looking, with robots enforced outside the path the
                # operator answered about.
                log.info("%s: %s looks like a signpost, not a system — searching", key, site.start)
                candidates = discover(site, client)
                (out_dir / "candidates.txt").write_text(
                    "\n".join(f"{t}\t{u}" for t, u in candidates), encoding="utf-8"
                )
        log.info(
            "%s: %d pages, all cached; report %s", key, len(fetched), report(site, fetched, out_dir)
        )

    if not dry_run and not failed:
        log.info("next: read the reports and the cache — selectors need no further requests")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
