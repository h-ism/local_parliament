"""鳥取 委員会 on とりネット: the walk by link text, 確定版 over 速報版, visits skipped."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from conftest import FakeClient
from prefectural_transcripts.config import FetchWindow
from prefectural_transcripts.scrapers import load_scraper
from prefectural_transcripts.scrapers.tottori import TottoriCommitteeScraper, TottoriConfig

SITE = "https://www.pref.tottori.lg.jp"


def _page(middle: str, title: str = "") -> str:
    # The header carries a breadcrumb up to the excluded pages; only #Middle is read.
    return f"""<html><head><title>{title}/とりネット/鳥取県公式サイト</title></head><body>
<div id="HeaderPane"><a href="/gikai/">ホーム</a> <a href="/87615.htm">議会の動き</a>
<a href="/88112.htm">議事録・会議録・調査報告</a></div>
<div id="Middle">{middle}</div></body></html>"""


INDEX = _page(
    """<a href="https://www.pref.tottori.lg.jp/">本会議会議録(外部リンク)</a>
<a href="/305836.htm">令和4年度委員会会議録・活動報告</a>
<a href="/148047.htm">平成22年度委員会会議録・活動報告</a>
<a href="/87662.htm">議会その他</a>"""
)
YEAR_R4 = _page(
    '<a href="/305837.htm">総務教育常任委員会</a><a href="/305842.htm">議員全員協議会</a>'
    '<a href="/files/report.pdf">活動報告書</a>'
)
YEAR_H22 = _page('<a href="/dd.aspx?menuid=127695">総務教育常任委員会</a>')
SOUMU_R4 = _page(
    """<a href="/item/1340635.htm#itemid1340635">令和5年2月15日会議録（確定版）</a>
<a href="/item/1340600.htm#itemid1340600">令和5年２月15日会議録（速報版）</a>
<a href="/dd.aspx?moduleid=626220&amp;pfromid=15#moduleid626220">次のページへ</a>"""
)
SOUMU_R4_P2 = _page(
    """<a href="/item/1288898.htm#itemid1288898">令和4年8月19日会議録（確定版）</a>
<a href="/dd.aspx?moduleid=626220&amp;pfromid=15#moduleid626220">次のページへ</a>"""
)
ZENIN_R4 = _page('<a href="/item/1288950.htm">令和4年5月31日会議録（速報版）</a>')
SOUMU_H22 = _page(
    """<a href="/item/625270.htm#itemid625270">平成23年3月9日会議録</a>
<a href="/item/548629.htm">平成22年8月25日～26日・所管事項に係る県内調査</a>
<a href="/item/520314.htm">平成22年6月1日（予備調査）会議録</a>"""
)

MINUTE = _page(
    """令和4年度総務教育常任委員会議事録<br>令和5年2月15日会議録（確定版）<br>
出席者<br>（8名）<br>委員長<br>常田　賢二<br>
午前10時00分　開会<br>
◎常田委員長<br>ただいまから総務教育常任委員会を開会いたします。<br>
●松田総務部長<br>説明いたします。<br>補正額は14億円でございます。<br>
○（　　　）委員<br>伺います。<br>
◯興治委員<br>●　　の調整範囲が●　　。<br>
◎常田委員長<br>
○福浜委員<br>以上です。<br>午前11時00分　閉会""",
    title="令和5年2月15日会議録（確定版）",
)


def _scraper() -> TottoriCommitteeScraper:
    return TottoriCommitteeScraper(
        TottoriConfig(prefecture="鳥取県", index_url=f"{SITE}/88112.htm")
    )


def _client(**extra: str) -> FakeClient:
    pages = {
        f"{SITE}/88112.htm": INDEX,
        f"{SITE}/305836.htm": YEAR_R4,
        f"{SITE}/148047.htm": YEAR_H22,
        f"{SITE}/305837.htm": SOUMU_R4,
        f"{SITE}/dd.aspx?moduleid=626220&pfromid=15": SOUMU_R4_P2,
        f"{SITE}/305842.htm": ZENIN_R4,
        f"{SITE}/dd.aspx?menuid=127695": SOUMU_H22,
    }
    pages.update(extra)
    return FakeClient(pages)


def test_the_walk_follows_link_text_and_never_the_excluded_pages() -> None:
    client = _client()
    scraper = _scraper()
    refs = list(scraper.list_meetings(client))

    assert [str(r.url) for r in refs] == [
        f"{SITE}/item/1340635.htm",
        f"{SITE}/item/1288898.htm",  # from 次のページへ, which links to itself once
        f"{SITE}/item/1288950.htm",
        f"{SITE}/item/625270.htm",
        f"{SITE}/item/520314.htm",
    ]
    excluded = ("/gikai/", "87615.htm", "87662.htm", ".pdf")
    assert not any(u.endswith(excluded) for u in client.requested)
    assert refs[0].date == date(2023, 2, 15)
    assert refs[0].title == "総務教育常任委員会 令和5年2月15日会議録（確定版）"


def test_a_preliminary_edition_gives_way_to_the_final_one_of_the_same_committee() -> None:
    scraper = _scraper()
    list(scraper.list_meetings(_client()))
    report = "\n".join(scraper.report())

    # 「２月15日」 and 「2月15日」 are one label once the digits are one width.
    assert f"{SITE}/item/1340600.htm" not in scraper._listed
    assert "1 速報版 superseded" in report
    # 議員全員協議会 has no 確定版 for 5/31, so its 速報版 is kept, and said so.
    assert "1 速報版 kept" in report
    assert "1 visit report(s)" in report


def test_a_minute_parses_into_its_three_kinds_of_speaker() -> None:
    scraper = _scraper()
    client = _client(**{f"{SITE}/item/1340635.htm": MINUTE})
    ref = next(iter(scraper.list_meetings(client)))
    meeting = scraper.parse_meeting(ref, scraper.fetch_meeting(ref, client))

    assert meeting.committee == "総務教育常任委員会"
    assert meeting.date == date(2023, 2, 15)
    assert [s.speaker for s in meeting.speeches] == [
        "常田委員長",
        "松田総務部長",
        "()委員",  # a name the site itself blanked: kept, never guessed
        "興治委員",
        "福浜委員",
    ]
    assert meeting.speeches[1].text == "説明いたします。\n補正額は14億円でございます。"
    # A circle inside a sentence is speech, not a marker.
    assert meeting.speeches[3].text.startswith("●　　の調整範囲")


def test_the_config_loads_with_its_conditions() -> None:
    scraper = load_scraper("tottori_committee")
    assert isinstance(scraper, TottoriCommitteeScraper)
    window = scraper.fetch_window
    assert isinstance(window, FetchWindow)
    tz = window.zone
    assert window.allows(datetime(2026, 10, 24, 0, 30, tzinfo=tz))  # Saturday small hours
    assert window.allows(datetime(2026, 10, 25, 23, 59, tzinfo=tz))  # Sunday night
    assert not window.allows(datetime(2026, 10, 22, 2, 0, tzinfo=tz))  # Thursday 01-04
    assert not window.allows(datetime(2026, 10, 23, 21, 0, tzinfo=tz))  # Friday night
    assert scraper.robots_exempt is None  # robots.txt obeyed as it stands


def test_an_excluded_page_is_refused_even_if_something_links_to_it() -> None:
    scraper = _scraper()
    with pytest.raises(RuntimeError, match="広報課"):
        scraper._get(_client(), f"{SITE}/87660.htm")
