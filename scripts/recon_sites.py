"""Reconnaissance on the assemblies that have answered, inside their own terms.

Five so far, on three different products, and **no two sets of terms are the
same**: 滋賀 and 石川 (VOICES) allow weekend evenings from 20:00; 岩手 (VOICES,
root-level `.asp`), 茨城 (**DB-Search**) and 栃木 (VOICES) allow collection by the
method our letter described, which commits us to avoiding business hours; and
栃木 also wants to be told when we will run, and — after its vendor was
consulted — to keep to **weekend** nights while the assembly is sitting.
Each robots.txt in question is the vendor's boilerplate,
identical across its product's installs; the operators' own answers are what
these exemptions rest on.

This file was `recon_voices.py` until 茨城 answered and made the name wrong.

**Why a separate script rather than `pt inspect`.** The window is a few hours a
week and thinking is not. Everything this fetches lands in the cache, so the work
that needs judgement — reading the markup, writing the selectors, counting what a
rule catches — happens afterwards, offline, at no cost to their servers. Fetch
inside the window; think outside it.

Bounded on purpose: at most `MAX_PAGES` pages per site, all under that site's own
`/voices/`, 2 seconds apart (the first undertaking in our letter), and
`PoliteClient` refuses outright when the window is shut — so a timer that fires
on a Tuesday fetches nothing at all and says why.

    uv run python scripts/recon_sites.py             # every site that has answered
    uv run python scripts/recon_sites.py shiga       # one of them
    uv run python scripts/recon_sites.py --dry-run
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

from prefectural_transcripts.config import Contact, FetchWindow, Notice, RobotsExemption, Settings
from prefectural_transcripts.http import (
    FetchError,
    OutsideFetchWindow,
    Page,
    PoliteClient,
    current_time,
)

log = logging.getLogger("recon")

SITES_DIR = Path(__file__).resolve().parent.parent / "src/prefectural_transcripts/sites"

MAX_PAGES = 150
MAX_DEPTH = 4
# 40 pages at depth 2 reached 石川's year listings and stopped one level short of
# a transcript, which is the one page a config cannot be written without. 150 at
# depth 4 is five minutes at 2 s — still nothing to their server, and the
# difference between a survey somebody can act on and one that has to be redone.
#
# MAX_PAGES counts **requests**, not pages walked. Until 2026-09-28 it counted
# both, so once the first 150 pages were cached every later window walked the
# same 150 from cache, fetched nothing, and reported success — three nights in a
# row. A cached page costs their server nothing and should not spend the budget.
MAX_WALKED = 2000
"""A bound on the walk itself, cached or not, so a loop in the cache ends."""

PER_SHAPE = 6
# A page with 40 year links or 93 calendar months of the same shape is one
# question asked 40 times. Keep an evenly spaced sample that includes the first
# and the last, so the survey sees the oldest markup as well as the newest —
# 静岡 needed five marker shapes and the old years were the worst.

# Both answers name the same hours, and both letters were sent by the same
# collaborator, so the address they have on file is 共同研究者A's.
WEEKEND_EVENINGS = dict(days=(5, 6), start=time(20, 0), end=time(0, 0), decided_on="2026-09-18")
# 岩手・茨城・栃木 (2026-09-24) permitted collection "by the method described", and
# the method we described says 業務時間帯を避ける. 20:00-07:00 every day is
# unambiguously outside business hours; the window wraps past midnight.
OUTSIDE_BUSINESS_HOURS = dict(
    days=(0, 1, 2, 3, 4, 5, 6), start=time(20, 0), end=time(7, 0), decided_on="2026-09-24"
)
# 栃木, later the same day: their system vendor asked for 土日夜間 while the
# assembly is sitting (会期 2026-09-17〜10-13). So the two conditions are ANDed —
# weekends, and the night window that avoids business hours — which is 滋賀's days
# with 岩手's hours, and the first window this project has that is both.
#
# It does not widen again by itself when the 会期 ends on 2026-10-13. Deciding
# that a recommendation lapses with the sitting is an answer nobody has given us;
# the cost of staying narrow is wall-clock time, and the cost of guessing wrong
# is the permission. Ask in the next notice instead.
WEEKEND_NIGHTS = dict(days=(5, 6), start=time(20, 0), end=time(7, 0), decided_on="2026-09-24")
# The letters were not all sent by the same person, and the address an operator
# sees has to be the one *that* assembly can reply to. A wrong address is worse
# than none: it tells them who to complain to and the complaint never arrives.
COLLABORATOR_A = Contact(
    address="(共同研究者Aの連絡先)",
    note="照会は共同研究者Aが行った",
)
COLLABORATOR_B = Contact(
    address="(共同研究者Bの連絡先)",
    note="照会は共同研究者Bが行った — 岩手・茨城・栃木",
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
    exemption: RobotsExemption | None
    """None where robots.txt is to be obeyed as it stands — 岩手's www3, which
    the letter did not name and whose rules file nobody has answered about."""
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

    requires_notice: bool = False
    """The operator asked to be told before we run. 栃木 did.

    The crawler cannot send that email, so it refuses instead: nothing is
    fetched until a `[notice]` records who was told and what period it covers.
    A reconnaissance visit is a run like any other — the first notice should say
    so.
    """

    notice: Notice | None = None

    contact: Contact | None = None
    """Whose enquiry this assembly answered. **None means unconfirmed**, and a
    site with no confirmed contact is not fetched at all: running under the wrong
    colleague's name is not a smaller mistake than running unannounced."""

    avoid: str = (
        r"Video|broadcasting|help_|index_s|Nittei|Congress|Shitsumon|Oshirase|Koho|"
        r"\.pdf$|\.docx?$|\.xlsx?$|\.zip$"
    )
    """Links not worth a slot in the cap.

    石川's first run spent 23 of its 40 pages on 録画中継 (video) listings and one
    on a PDF. The cap exists to keep the visit small; it should be spent on the
    minutes. The schedule pages went the same way on 2026-09-28: 岩手's 150 were
    93 calendar months, and 滋賀's 23 were 本会議の開催状況 — none of them a
    transcript."""

    focus: str = r"voiweb\.exe"
    """Links that jump the queue. VOICES serves every listing and transcript from
    its CGI, so that is where the budget should go first."""


def _voices(
    key: str,
    prefecture: str,
    host: str,
    who: str,
    reason: str,
    note: str = "",
    discover: tuple[str, ...] = (),
    start: str = "",
    path: str = "/voices/",
    hours: dict[str, object] | None = None,
    requires_notice: bool = False,
    notice: Notice | None = None,
    contact: Contact | None = None,
    scheme: str = "https",
    exempt: bool = True,
) -> Site:
    prefix = f"{scheme}://{host}{path}"
    return Site(
        key=key,
        prefecture=prefecture,
        start=start or prefix,
        prefix=prefix,
        window=FetchWindow(reason=reason, **(hours or WEEKEND_EVENINGS)),  # type: ignore[arg-type]
        exemption=RobotsExemption(
            prefixes=(prefix,),
            reason=(
                f"{who}: 運営者本人の回答による許可。robots.txt の Disallow は"
                f"ベンダー標準で、回答が優先する。docs/{key}.md"
            ),
            decided_on="2026-09-18",
        )
        if exempt
        else None,
        note=note,
        discover=discover,
        requires_notice=requires_notice,
        notice=notice,
        contact=contact,
    )


# The rules file itself is always fetchable — RFC 9309 says so, and a parser
# that refused to read it could never learn what it says. The stdlib parser
# applies `Disallow: /` to `/robots.txt` like any other path, so it is named.
ROBOTS_READABLE = RobotsExemption(
    prefixes=("https://www.shigaken-gikai.jp/robots.txt",),
    reason="robots.txt itself, to find where 滋賀's minutes moved to. RFC 9309 §2.3.",
    decided_on="2026-09-21",
)


_BY_METHOD = (
    "（2026-09-24）手紙に記載した方法（1件2秒以上・直列、既取得は再取得しない、"
    "User-Agent に研究目的と連絡先、業務時間帯を避ける、支障があれば即停止）であれば"
    "スクレイピング可、との回答"
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
            contact=COLLABORATOR_A,
            # Given by the researcher 2026-09-21. `/voices/` itself is only a
            # meta-refresh to the assembly's top page; the search form is at
            # g07v_search.asp, and the vendor's naming matches 石川's (g07…, g08v…).
            # The walk starts at the 本会議 listing instead (2026-09-28): from the
            # search form a transcript sits at depth 5, one past MAX_DEPTH.
            start="https://www.shigaken-gikai.jp/voices/g08v_viewh.asp",
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
            contact=COLLABORATOR_A,
            # From the first window: the 本会議会議録 listing, rather than the
            # directory, so the cap is spent inside the archive instead of
            # rediscovering the way in.
            start="https://pref-ishikawa.gijiroku.com/voices/g08v_viewh.asp?Sflg=10",
            note=(
                "定例会の会期中（9月30日まで）につき、取得時間帯にくれぐれも留意するよう"
                "念を押されている。会期中は下見にとどめ、本収集は10月以降に回すのが安全。"
            ),
        ),
        _voices(
            "tochigi",
            "栃木県",
            "pref-tochigi.gijiroku.com",
            "栃木県議会事務局",
            f"栃木県議会事務局{_BY_METHOD}"
            "／同日の追報 (2026-09-24): システムベンダーより、会期中"
            "（9/17〜10/13）につき土日夜間での実施を推奨、との連絡。"
            "業務時間帯を避ける約束と合わせ、土日の20時〜翌7時に限定する",
            contact=COLLABORATOR_B,
            hours=WEEKEND_NIGHTS,
            requires_notice=True,
            note=(
                "**実行のタイミングを事前に知らせること**（先方の指示）。本収集の前に"
                "通知を送り、sites/tochigi.toml の [notice] に記録する。下見も同じ扱いに"
                "しておくのが筋なので、最初の通知に下見の予定も書くこと。"
                " また 2026-09-24 の追報により、会期中（9/17〜10/13）は"
                "**土日夜間**に限定する。会期後に平日夜間へ戻すかどうかは、"
                "こちらで決めずに次の通知で確認すること。"
            ),
        ),
        _voices(
            "iwate",
            "岩手県",
            # Not iwatekengikai.gijiroku.com, which the letter named: that host
            # is the assembly's site, and its 「本会議会議録」 link leaves it for
            # the prefecture's server (found in the cache 2026-09-28, after
            # 150 pages there had surveyed calendars and member lists). The
            # permission was for 岩手県議会's 会議録, and this is where the
            # assembly itself says they are — the researcher's call, the same
            # day. robots.txt is obeyed as it stands: nobody has answered about
            # this host's rules file, so there is no exemption to write.
            "www3.pref.iwate.jp",
            "岩手県議会事務局",
            f"岩手県議会事務局{_BY_METHOD}",
            contact=COLLABORATOR_B,
            scheme="http",  # as the assembly's own link gives it
            path="/gikai/user/www/",
            start="http://www3.pref.iwate.jp/gikai/user/www/index.php",
            exempt=False,
            hours=OUTSIDE_BUSINESS_HOURS,
            note=(
                "会議録は gijiroku.com（手紙で名指ししたホスト）ではなく、県議会サイトの"
                "「本会議会議録」リンク先 www3.pref.iwate.jp/gikai/user/www/ にある。"
                "robots.txt は免除せずそのまま守る（2026-08 時点で 404）。"
            ),
        ),
        _voices(
            "ibaraki",
            "茨城県",
            "www.pref.ibaraki.dbsr.jp",
            "茨城県議会事務局",
            f"茨城県議会事務局{_BY_METHOD}",
            contact=COLLABORATOR_B,
            path="/",
            hours=OUTSIDE_BUSINESS_HOURS,
            note=(
                "DB-Search。**山梨と同じ製品で、山梨は「自動取得は控えて」だった**。"
                "ベンダーの robots は同一でも議会の意思は別物だという実例なので、"
                "他の DB-Search 15県の可否をここから推測しないこと。"
            ),
        ),
    )
}


def settings(site: Site) -> Settings:
    s = Settings()
    assert site.contact is not None  # main() refuses a site without one
    s.contact = site.contact.address
    s.min_interval = 2.0  # our first undertaking to them
    return s


def links(page: Page) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page.text, "lxml")
    return [
        (node.get_text(" ", strip=True)[:60], urldefrag(urljoin(page.url, str(node["href"]))).url)
        for node in soup.find_all("a", href=True)
    ]


def frames(page: Page) -> list[str]:
    """What an `<iframe>` or `<frame>` pulls into this page.

    VOICES puts every listing and every transcript inside one:
    `g08v_viewh.asp` is a wrapper, and the sittings are in
    `<iframe src="cgi/voiweb.exe?ACT=100…">`. A walk that follows only `<a href>`
    surveyed 150 wrappers on 滋賀 and 石川 and not one sitting — and wrote a report
    that looked complete.
    """
    soup = BeautifulSoup(page.text, "lxml")
    return [
        urldefrag(urljoin(page.url, str(node["src"]))).url
        for node in soup.find_all(["iframe", "frame"], src=True)
    ]


def spread(urls: list[str], k: int = PER_SHAPE) -> list[str]:
    """At most `k` of each URL shape, evenly spaced, first and last included."""
    groups: dict[str, list[str]] = {}
    for url in dict.fromkeys(urls):
        groups.setdefault(shape(url), []).append(url)
    keep: set[str] = set()
    for group in groups.values():
        if len(group) <= k:
            keep.update(group)
        else:
            step = (len(group) - 1) / (k - 1)
            keep.update(group[round(i * step)] for i in range(k))
    return [u for u in dict.fromkeys(urls) if u in keep]


def title(page: Page) -> str:
    soup = BeautifulSoup(page.text, "lxml")
    return soup.title.get_text(strip=True) if soup.title else ""


def shape(url: str) -> str:
    """A URL with its numbers blanked, so repeated shapes collapse into one row.

    A CGI's `ACT=` is kept: `voiweb.exe?ACT=100` (a listing) and `?ACT=203` (a
    transcript) are one path and entirely different pages.
    """
    parts = urlparse(url)
    act = re.search(r"(?:^|&)ACT=(\d+)", parts.query)
    return re.sub(r"\d+", "N", parts.path) + (f"?ACT={act.group(1)}" if act else "")


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


def inside(url: str, prefix: str) -> bool:
    """Whether `url` is in the area `prefix` names, whichever scheme each uses.

    岩手's own link to its minutes is `http://`; if the server answers on
    `https://`, every link it yields would otherwise fall outside the area and the
    walk would end after one page, looking like a site with nothing in it.
    """
    return url.split("://", 1)[-1].startswith(prefix.split("://", 1)[-1])


def walk(site: Site, client: PoliteClient) -> list[tuple[str, Page]]:
    seen: set[str] = set()
    queue: list[tuple[str, int]] = [(site.start, 0)]
    fetched: list[tuple[str, Page]] = []
    requests = 0
    avoid = re.compile(site.avoid)
    focus = re.compile(site.focus)
    while queue and requests < MAX_PAGES and len(fetched) < MAX_WALKED:
        url, depth = queue.pop(0)
        if url in seen or not inside(url, site.prefix) or avoid.search(url):
            continue
        seen.add(url)
        try:
            page = client.get(url)
        except OutsideFetchWindow:
            log.warning("%s: the window closed mid-run; stopping at %d", site.key, requests)
            break
        except FetchError as exc:
            requests += 1
            log.warning("%s: could not fetch %s: %s", site.key, url, exc)
            continue
        if not page.from_cache:
            requests += 1
        fetched.append((url, page))
        found = links(page)
        inner = frames(page)
        log.info(
            "%s [%3d/%3d] %s — %s (%d links, %d frames)%s",
            site.key,
            requests,
            len(fetched),
            url,
            title(page),
            len(found),
            len(inner),
            " cached" if page.from_cache else "",
        )
        # A frame is part of the page it sits in, not a page further away: same
        # depth, and first in line, because it is usually the only thing there.
        queue[:0] = [(u, depth) for u in inner if u not in seen]
        if depth < MAX_DEPTH:
            nxt = [(u, depth + 1) for u in spread([u for _, u in found]) if u not in seen]
            first = [item for item in nxt if focus.search(item[0])]
            queue[:0] = first
            queue.extend(item for item in nxt if not focus.search(item[0]))
    log.info("%s: %d requests, %d pages walked", site.key, requests, len(fetched))
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
            # 60, not 25: the first two dozen links on these pages are the site's
            # own navigation, and the ones that lead to a sitting come after it.
            for text, target in links(page)[:60]:
                fh.write(f"    link  {text!r} -> {target}\n")
            for target in frames(page):
                fh.write(f"    frame -> {target}\n")
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

        # Once a config exists the survey has done its job, and `collect_voices.sh`
        # takes the site over — from the same timer, at the same minute. Surveying
        # it as well would put two processes on one host at once, which is the
        # first undertaking in our letter broken by our own scheduling.
        if (SITES_DIR / f"{key}.toml").exists():
            log.info("%s: has a config; collected by collect_voices.sh, not surveyed", key)
            continue

        if site.contact is None:
            log.error("%s: 照会者が未確認。誰の名義で取得するか決まるまで実行しない", key)
            failed += 1
            continue

        now = current_time()
        if site.requires_notice and not (site.notice and site.notice.covers(now.date())):
            log.error("%s: 事前通知が条件。通知を送り、[notice] に記録するまで実行しない", key)
            log.error("  %s", site.note or "")
            failed += 1
            continue
        if not site.window.allows(now):
            log.error("%s: outside the agreed hours (%s)", key, site.window.describe())
            log.error(
                "  next window opens %s", site.window.next_open(now).strftime("%Y-%m-%d %H:%M %Z")
            )
            log.error("  %s", site.window.reason)
            failed += 1
            continue
        log.info("%s: inside the window; contact %s", key, site.contact.address)
        if site.note:
            log.info("%s: %s", key, site.note)
        if dry_run:
            log.info("%s: --dry-run, would start at %s (cap %d)", key, site.start, MAX_PAGES)
            continue

        out_dir = Path(f"data/logs/{key}")
        out_dir.mkdir(parents=True, exist_ok=True)
        exemption = site.exemption
        if site.discover and exemption is not None:
            exemption = RobotsExemption(
                prefixes=exemption.prefixes + ROBOTS_READABLE.prefixes,
                reason=f"{exemption.reason} / {ROBOTS_READABLE.reason}",
                decided_on=exemption.decided_on,
            )
        with PoliteClient(
            settings(site), robots_exempt=exemption, fetch_window=site.window
        ) as client:
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
            "%s: %d pages walked, all now cached; report %s",
            key,
            len(fetched),
            report(site, fetched, out_dir),
        )

    if not dry_run and not failed:
        log.info("next: read the reports and the cache — selectors need no further requests")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
