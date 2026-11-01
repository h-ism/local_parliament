"""The reconnaissance walk: what it follows, and what it spends its budget on.

Offline — `FakeClient` serves the pages, so nothing here touches a server.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from conftest import FakeClient, make_page
from prefectural_transcripts.config import Contact

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import recon_sites  # noqa: E402
from recon_sites import SITES, frames, inside, shape, spread, walk  # noqa: E402

BASE = "https://pref-ishikawa.gijiroku.com/voices/"
JST = ZoneInfo("Asia/Tokyo")


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


def test_tottori_follows_only_year_committee_and_minutes() -> None:
    # とりネット is the whole prefectural site, so the URL area bounds nothing;
    # the operator also excluded the navigation the index links to (2026-10-05).
    site = SITES["tottori_committee"]
    root = "https://www.pref.tottori.lg.jp/"
    year, committee, minute = root + "323536.htm", root + "323537.htm", root + "item/1432711.htm"
    old_minute = root + "item/277957.htm"
    client = FakeClient(
        {
            site.start: (
                f'<a href="{root}gikai/">ホーム</a><a href="{root}87615.htm">議会の動き</a>'
                f'<a href="{root}99999.htm">観光情報</a>'
                f'<a href="{year}">令和7年度委員会会議録・活動報告</a>'
            ),
            year: (
                f'<a href="{committee}">総務教育常任委員会</a>'
                f'<a href="{root}87659.htm">議会・議員</a>'
            ),
            committee: (
                f'<a href="{minute}">令和８年２月25日会議録（確定版）</a>'
                # 平成18年度 writes a minute as its date alone (2026-10-13).
                f'<a href="{old_minute}#itemid277957">平成19年3月8日(木)（開会中）</a>'
                f'<a href="{root}1.htm">戻る</a>'
            ),
            minute: "<p>◎東田委員長　皆さん、おはようございます。</p>",
            old_minute: "<p>◎委員長　開会します。</p>",
        }
    )
    walked = [url.split("#")[0] for url, _ in walk(site, client)]  # type: ignore[arg-type]
    assert walked == [site.start, year, committee, minute, old_minute]


def test_tottori_excludes_the_pages_it_was_asked_to() -> None:
    import re

    rule = re.compile(SITES["tottori_committee"].avoid)
    for path in ("gikai/", "87615.htm", "87659.htm", "87660.htm", "87662.htm"):
        assert rule.search("https://www.pref.tottori.lg.jp/" + path)
    assert not rule.search("https://www.pref.tottori.lg.jp/item/1432711.htm")


def test_a_sitting_opened_by_script_is_still_a_link() -> None:
    # VOICES: <a href="javascript:;" onClick="winopen('voiweb.exe?ACT=200&…')">.
    # Following href only reached 182 listings over a weekend and no sitting.
    page = make_page(
        BASE + "cgi/voiweb.exe?ACT=100&KGTP=3",
        """<a href="voiweb.exe?ACT=100&amp;PAGE=2">次</a>
        <A HREF="javascript:;" TARGET="HLD_WIN"
           onClick="winopen('voiweb.exe?ACT=200&amp;FINO=229&amp;UNID=K_H12021000011')">02月10日-01号</A>
        <a href="javascript:void(0)">印刷</a>""",
    )
    assert recon_sites.links(page) == [
        ("次", BASE + "cgi/voiweb.exe?ACT=100&PAGE=2"),
        ("02月10日-01号", BASE + "cgi/voiweb.exe?ACT=200&FINO=229&UNID=K_H12021000011"),
    ]


def _runnable(key: str) -> recon_sites.Site:
    # contacts.toml is gitignored, so without this every site fails on its contact.
    return replace(SITES[key], contact=Contact(address="test@example.org"))


def _run(monkeypatch: pytest.MonkeyPatch, when: datetime, *keys: str) -> int:
    monkeypatch.setattr(recon_sites, "SITES", {k: _runnable(k) for k in keys})
    monkeypatch.setattr(recon_sites, "current_time", lambda: when)
    monkeypatch.setattr(sys, "argv", ["recon_sites.py", "--dry-run", *keys])
    return recon_sites.main()


def test_a_held_site_is_not_a_failed_run(monkeypatch: pytest.MonkeyPatch) -> None:
    # Weekday evenings: every site is outside its window or its notice, and the
    # run used to exit 1 — systemd said "Failed" six nights a week.
    thursday = datetime(2026, 10, 8, 20, 0, tzinfo=JST)
    assert _run(monkeypatch, thursday, "shiga", "ishikawa", "hokkaido", "tottori_committee") == 0


def test_a_site_with_no_notice_is_held_not_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    after_tochigi_notice = datetime(2026, 10, 17, 21, 0, tzinfo=JST)
    assert _run(monkeypatch, after_tochigi_notice, "tochigi") == 0


def test_what_a_person_must_fix_still_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A site with a config is handed to the collector before its contact is
    # looked at, and 滋賀 has one since 2026-10-13 — so no configs here.
    monkeypatch.setattr(recon_sites, "SITES_DIR", tmp_path)
    saturday = datetime(2026, 10, 10, 21, 0, tzinfo=JST)
    assert _run(monkeypatch, saturday, "shiga") == 0
    monkeypatch.setattr(sys, "argv", ["recon_sites.py", "--dry-run", "no_such_site"])
    assert recon_sites.main() == 1
    monkeypatch.setattr(recon_sites, "SITES", {"shiga": replace(SITES["shiga"], contact=None)})
    monkeypatch.setattr(sys, "argv", ["recon_sites.py", "--dry-run", "shiga"])
    assert recon_sites.main() == 1


def test_a_site_on_hold_is_skipped_inside_its_window(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    # 2026-10-09: 栃木 and 北海道 were told on 9/30 and had not replied; the
    # researcher held both. Inside the window, with the notice covering the
    # night, the hold alone has to stop it — and stopping is not a failure.
    # Both are released now (栃木 10/22, 北海道 10/30), so the hold is put back
    # on a copy, inside 北海道's first confirmed night.
    monkeypatch.setitem(SITES, "hokkaido", replace(SITES["hokkaido"], hold="test"))
    monkeypatch.setattr(recon_sites, "SITES_DIR", tmp_path)  # its config would skip it first
    saturday = datetime(2026, 10, 31, 21, 0, tzinfo=JST)
    assert _run(monkeypatch, saturday, "hokkaido") == 0
    assert "held by the researcher" in caplog.text
    assert "inside the window" not in caplog.text


@pytest.mark.parametrize(
    ("when", "runs"),
    [
        (datetime(2026, 10, 24, 20, 30, tzinfo=JST), True),
        (datetime(2026, 10, 25, 20, 30, tzinfo=JST), True),  # the night it was collected
        (datetime(2026, 10, 26, 20, 30, tzinfo=JST), False),  # a weekday
        (datetime(2026, 10, 31, 20, 30, tzinfo=JST), False),  # done: a new run is a new notice
        (datetime(2026, 11, 29, 21, 0, tzinfo=JST), False),  # inside the old 11/30 bound
    ],
)
def test_tochigi_runs_the_weekend_it_was_told_of_and_no_other(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    when: datetime,
    runs: bool,
) -> None:
    # 2026-10-22: 「取得の件、承知しました」, and 栃木 agrees to it running until
    # the collection is complete, which it was on 10/25: the notice ends there
    # (it said 11/30, our own bound, until then). Since 10/25
    # it has a config, which hands it to the collector — so none here.
    monkeypatch.setattr(recon_sites, "SITES_DIR", tmp_path)
    assert not SITES["tochigi"].hold
    caplog.set_level(logging.INFO, logger="recon")
    _run(monkeypatch, when, "tochigi")
    assert ("inside the window" in caplog.text) is runs


@pytest.mark.parametrize(
    ("when", "runs"),
    [
        (datetime(2026, 10, 25, 20, 30, tzinfo=JST), True),
        (datetime(2026, 10, 26, 20, 30, tzinfo=JST), False),
        (datetime(2026, 10, 31, 20, 30, tzinfo=JST), False),
        (datetime(2026, 11, 29, 21, 0, tzinfo=JST), False),
    ],
)
def test_tochigi_config_carries_the_same_terms_as_the_survey(when: datetime, runs: bool) -> None:
    # The collector reads sites/tochigi.toml, not recon_sites.py: the two must agree.
    from prefectural_transcripts.scrapers.voices import VoicesConfig

    cfg = VoicesConfig.from_toml(recon_sites.SITES_DIR / "tochigi.toml")
    site = SITES["tochigi"]
    assert cfg.notice is not None and site.notice is not None
    assert (cfg.notice.last_sent, cfg.notice.covers_until) == (
        site.notice.last_sent,
        site.notice.covers_until,
    )
    assert cfg.fetch_window is not None
    allowed = cfg.fetch_window.allows(when) and cfg.notice.covers(when.date())
    assert allowed is runs


@pytest.mark.parametrize(
    ("when", "runs"),
    [
        (datetime(2026, 10, 31, 19, 59, tzinfo=JST), False),
        (datetime(2026, 10, 31, 20, 0, tzinfo=JST), True),
        (datetime(2026, 11, 1, 5, 59, tzinfo=JST), True),
        (datetime(2026, 11, 1, 12, 0, tzinfo=JST), False),
        (datetime(2026, 11, 1, 20, 0, tzinfo=JST), True),
        (datetime(2026, 11, 2, 5, 59, tzinfo=JST), True),
        (datetime(2026, 11, 2, 6, 0, tzinfo=JST), False),
        (datetime(2026, 11, 3, 21, 0, tzinfo=JST), False),  # a holiday in the period, not confirmed
        (datetime(2026, 11, 7, 21, 0, tzinfo=JST), False),
    ],
)
def test_hokkaido_config_opens_only_the_two_confirmed_nights(when: datetime, runs: bool) -> None:
    # 2026-10-30: the vendor confirmed 10/31 and 11/1, 20:00-06:00, and nothing else.
    from prefectural_transcripts.scrapers.voices import VoicesConfig

    cfg = VoicesConfig.from_toml(recon_sites.SITES_DIR / "hokkaido.toml")
    site = SITES["hokkaido"]
    assert cfg.notice is not None and site.notice is not None
    assert cfg.fetch_window is not None
    assert cfg.fetch_window.allows(when) is runs
    assert site.window.allows(when) is runs
    assert cfg.notice.covers(when.date())


@pytest.mark.parametrize(
    ("when", "runs"),
    [
        (datetime(2026, 11, 2, 19, 59, tzinfo=JST), False),
        (datetime(2026, 11, 2, 20, 0, tzinfo=JST), True),  # a Monday: every day, as 岩手・茨城
        (datetime(2026, 11, 3, 6, 59, tzinfo=JST), True),
        (datetime(2026, 11, 3, 7, 0, tzinfo=JST), False),
        (datetime(2026, 11, 4, 12, 0, tzinfo=JST), False),
    ],
)
def test_nagano_config_carries_the_same_terms_as_the_survey(when: datetime, runs: bool) -> None:
    from prefectural_transcripts.scrapers.voices import VoicesConfig

    cfg = VoicesConfig.from_toml(recon_sites.SITES_DIR / "nagano.toml")
    assert cfg.fetch_window is not None and cfg.notice is None  # none was asked for
    assert cfg.fetch_window.allows(when) is runs
    assert SITES["nagano"].window.allows(when) is runs
