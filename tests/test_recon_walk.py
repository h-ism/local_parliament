"""The reconnaissance walk: what it follows, and what it spends its budget on.

Offline — `FakeClient` serves the pages, so nothing here touches a server.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from conftest import FakeClient, make_page

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import recon_sites  # noqa: E402
from recon_sites import SITES, frames, inside, shape, spread, walk  # noqa: E402

BASE = "https://pref-ishikawa.gijiroku.com/voices/"


def test_follows_an_iframe_at_the_same_depth() -> None:
    # VOICES: the listing page is a wrapper and the sittings live in an iframe.
    # A walk that follows only <a href> surveyed 150 wrappers and no sitting.
    site = SITES["ishikawa"]
    start = site.start
    listing = BASE + "cgi/voiweb.exe?ACT=100&KGTP=1"
    sitting = BASE + "cgi/voiweb.exe?ACT=203&FINO=1"
    client = FakeClient(
        {
            start: '<iframe src="cgi/voiweb.exe?ACT=100&amp;KGTP=1"></iframe>',
            listing: '<a href="voiweb.exe?ACT=203&amp;FINO=1">第1号</a>',
            sitting: "<p>○議長（某君）</p>",
        }
    )
    walked = [url for url, _ in walk(site, client)]  # type: ignore[arg-type]
    assert walked == [start, listing, sitting]


def test_frames_are_resolved_against_the_page() -> None:
    page = make_page(BASE + "g08v_viewh.asp", '<iframe src="cgi/voiweb.exe?ACT=100"></iframe>')
    assert frames(page) == [BASE + "cgi/voiweb.exe?ACT=100"]


def test_the_cap_counts_requests_not_cached_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    # Once the first 150 pages were cached, every later window walked the same
    # 150 from cache and fetched nothing new — and reported success.
    monkeypatch.setattr(recon_sites, "MAX_PAGES", 2)
    site = SITES["ishikawa"]
    a, b, c = (BASE + f"g{i}.asp" for i in (1, 2, 3))

    class Cached(FakeClient):
        def get(self, url: str, *, force: bool = False):  # type: ignore[no-untyped-def]
            page = super().get(url, force=force)
            page.from_cache = url == site.start
            return page

    client = Cached(
        {
            site.start: f'<a href="{a}">a</a><a href="{b}">b</a><a href="{c}">c</a>',
            a: "",
            b: "",
            c: "",
        }
    )
    walked = [url for url, _ in walk(site, client)]  # type: ignore[arg-type]
    assert walked == [site.start, a, b]  # the cached start page did not spend the budget


def test_shape_keeps_the_cgi_action() -> None:
    assert shape(BASE + "cgi/voiweb.exe?ACT=100&FYY=2024") != shape(BASE + "cgi/voiweb.exe?ACT=203")


def test_spread_keeps_the_first_and_the_last() -> None:
    years = [BASE + f"g08v_viewh.asp?Sflg=11&FYY={y}" for y in range(2026, 1986, -1)]
    kept = spread(years, 6)
    assert len(kept) == 6
    assert kept[0].endswith("FYY=2026") and kept[-1].endswith("FYY=1987")
    # A shape with few members is untouched.
    assert spread(years[:3], 6) == years[:3]


def test_the_area_ignores_the_scheme() -> None:
    prefix = "http://www3.pref.iwate.jp/gikai/user/www/"
    assert inside("https://www3.pref.iwate.jp/gikai/user/www/Kensaku/x.php", prefix)
    assert not inside("https://www3.pref.iwate.jp/other/", prefix)
