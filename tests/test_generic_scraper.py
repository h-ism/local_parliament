from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

from conftest import FakeClient, make_page
from prefectural_transcripts.http import PoliteClient
from prefectural_transcripts.models import MeetingRef
from prefectural_transcripts.scrapers.generic import (
    DetailSelectors,
    GenericScraper,
    ListSelectors,
    SiteConfig,
)

INDEX_1 = """
<html><body>
<table class="result">
  <tr><td class="date">令和7年6月10日</td><td><a href="/m/1">本会議</a></td></tr>
  <tr><td class="date">令和7年6月11日</td><td><a href="/m/2">総務委員会</a></td></tr>
</table>
<a class="next" href="/index?p=2">次へ</a>
</body></html>
"""

INDEX_2 = """
<html><body>
<table class="result">
  <tr><td class="date">令和6年12月3日</td><td><a href="/m/3">本会議</a></td></tr>
</table>
</body></html>
"""

DETAIL = """
<html><body>
<div id="honbun">
  <h1>令和7年第2回定例会</h1>
  <span class="date">令和7年6月10日</span>
  <div class="speech">
    <span class="speaker">山田太郎</span><span class="role">議長</span><p>開会します。</p>
  </div>
  <div class="speech">
    <span class="speaker">佐藤花子</span><span class="role">知事</span><p>提案理由を説明します。</p>
  </div>
</div>
<div class="speech"><span class="speaker">ノイズ</span><p>本文の外なので拾わない。</p></div>
</body></html>
"""


def _config(**detail_overrides: object) -> SiteConfig:
    detail = DetailSelectors(
        container="div#honbun",
        speech="div.speech",
        speaker="span.speaker",
        role="span.role",
        text="p",
        date="span.date",
        title="h1",
    )
    for key, value in detail_overrides.items():
        setattr(detail, key, value)
    return SiteConfig(
        prefecture="東京都",
        start_urls=["https://example.invalid/index"],
        list=ListSelectors(
            meeting_link="a",
            row="table.result tr",
            date="td.date",
            next_page="a.next",
        ),
        detail=detail,
    )


def _client(pages: dict[str, str]) -> PoliteClient:
    return cast(PoliteClient, FakeClient(pages))


def test_lists_meetings_across_pages_with_row_dates() -> None:
    scraper = GenericScraper(_config())
    client = _client(
        {
            "https://example.invalid/index": INDEX_1,
            "https://example.invalid/index?p=2": INDEX_2,
        }
    )

    refs = list(scraper.list_meetings(client))

    assert [str(r.url) for r in refs] == [
        "https://example.invalid/m/1",
        "https://example.invalid/m/2",
        "https://example.invalid/m/3",
    ]
    assert refs[0].date == date(2025, 6, 10)
    assert refs[2].date == date(2024, 12, 3)


def test_pagination_stops_without_a_next_link() -> None:
    scraper = GenericScraper(_config())
    client = _client({"https://example.invalid/index": INDEX_2})
    assert len(list(scraper.list_meetings(client))) == 1


def test_parses_speeches_scoped_to_the_container() -> None:
    scraper = GenericScraper(_config())
    ref = MeetingRef(prefecture="東京都", url="https://example.invalid/m/1")
    meeting = scraper.parse_meeting(ref, make_page("https://example.invalid/m/1", DETAIL))

    assert meeting.date == date(2025, 6, 10)
    assert meeting.title == "令和7年第2回定例会"
    assert [s.speaker for s in meeting.speeches] == ["山田太郎", "佐藤花子"]
    assert [s.role for s in meeting.speeches] == ["議長", "知事"]
    assert meeting.speeches[0].order == 0
    assert meeting.speeches[1].text == "提案理由を説明します。"
    assert meeting.source_html_sha256


def test_without_a_speech_selector_the_page_is_kept_as_one_block() -> None:
    scraper = GenericScraper(_config(speech=None))
    ref = MeetingRef(prefecture="東京都", url="https://example.invalid/m/1")
    meeting = scraper.parse_meeting(ref, make_page("https://example.invalid/m/1", DETAIL))

    assert len(meeting.speeches) == 1
    assert "開会します。" in meeting.speeches[0].text


def test_scrape_applies_date_range_and_skip_set() -> None:
    scraper = GenericScraper(_config())
    client = _client(
        {
            "https://example.invalid/index": INDEX_1,
            "https://example.invalid/index?p=2": INDEX_2,
            "https://example.invalid/m/2": DETAIL,
        }
    )

    meetings = list(
        scraper.scrape(
            client,
            since=date(2025, 1, 1),
            skip={"https://example.invalid/m/1"},
        )
    )

    # m/1 skipped, m/3 filtered out by `since` — only m/2 is ever fetched.
    assert [str(m.url) for m in meetings] == ["https://example.invalid/m/2"]


def test_limit_stops_early() -> None:
    scraper = GenericScraper(_config())
    client = _client(
        {
            "https://example.invalid/index": INDEX_1,
            "https://example.invalid/m/1": DETAIL,
        }
    )
    assert len(list(scraper.scrape(client, limit=1))) == 1


def test_config_loads_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "tokyo.toml"
    path.write_text(
        """
prefecture = "東京都"
start_urls = ["https://example.invalid/index"]
[list]
meeting_link = "a.result"
[detail]
speech = "div.speech"
""",
        encoding="utf-8",
    )

    config = SiteConfig.from_toml(path)
    assert config.prefecture == "東京都"
    assert config.name == "tokyo"
    assert config.list.meeting_link == "a.result"
    assert config.list.max_pages == 50


# Shaped after 静岡's Domino output: no classes inside the document, fields
# labelled by the neighbouring cell, and the transcript as one run of text with
# 「○」 marking each speaker.
FLAT_DETAIL = """
<html><body>
<div id="notes">
  <h2>質問文書</h2>
  <b>令和７年６月静岡県議会定例会</b>
  <table>
    <tr><td>質問者：</td><td>赤堀　慎吾 議員</td></tr>
    <tr><td>質問日：</td><td>06/23/2025</td></tr>
  </table>
  <p>目次のような前置き。ここは発言ではない。</p>
  <p>○議長（竹内良訓君）　質疑及び一般質問を行います。</p>
  <p>○六番（赤堀慎吾君）　おはようございます。<br>通告に従い質問します。</p>
  <p>○知事（鈴木康友君）　赤堀議員にお答えをいたします。</p>
</div>
</body></html>
"""

SPLIT = r"○(?P<role>[^（(\n]{1,24})[（(](?P<speaker>[^）)\n]{1,24})[）)]"
DATE_PATTERN = r"質問日：\s*(\d{1,2}/\d{1,2}/\d{4})"
SESSION_PATTERN = (
    r"(?:令和|平成)\s*[０-９0-9元]{1,2}年\s*[０-９0-9]{1,2}月静岡県議会(?:定例会|臨時会)"
)


def _flat_config() -> SiteConfig:
    config = _config()
    config.detail = DetailSelectors(
        container="div#notes",
        speech_split=SPLIT,
        patterns={"date": DATE_PATTERN, "session": SESSION_PATTERN},
    )
    return config


def _flat_meeting():  # type: ignore[no-untyped-def]
    scraper = GenericScraper(_flat_config())
    ref = MeetingRef(prefecture="静岡県", url="https://example.invalid/d/1", title="赤堀　慎吾")
    return scraper.parse_meeting(ref, make_page("https://example.invalid/d/1", FLAT_DETAIL))


def test_speech_split_cuts_a_flat_transcript_at_each_marker() -> None:
    meeting = _flat_meeting()

    assert [s.role for s in meeting.speeches] == ["議長", "六番", "知事"]
    assert [s.speaker for s in meeting.speeches] == ["竹内良訓", "赤堀慎吾", "鈴木康友"]
    assert [s.order for s in meeting.speeches] == [0, 1, 2]


def test_speech_split_keeps_the_whole_run_up_to_the_next_marker() -> None:
    meeting = _flat_meeting()

    assert meeting.speeches[1].text.startswith("おはようございます。")
    assert "通告に従い質問します。" in meeting.speeches[1].text
    # …and stops before the next speaker.
    assert "お答えをいたします" not in meeting.speeches[1].text


def test_text_before_the_first_marker_is_not_a_speech() -> None:
    meeting = _flat_meeting()

    assert all("前置き" not in s.text for s in meeting.speeches)


def test_patterns_fill_fields_that_css_cannot_reach() -> None:
    meeting = _flat_meeting()

    assert meeting.date == date(2025, 6, 23)
    assert meeting.session == "令和７年６月静岡県議会定例会"


def test_a_selector_wins_over_a_pattern_for_the_same_field() -> None:
    config = _flat_config()
    config.detail.container = "div#notes"
    config.detail.title = "h2"
    config.detail.patterns["title"] = r"(質問者：\s*\S+)"

    scraper = GenericScraper(config)
    ref = MeetingRef(prefecture="静岡県", url="https://example.invalid/d/1")
    meeting = scraper.parse_meeting(ref, make_page("https://example.invalid/d/1", FLAT_DETAIL))

    assert meeting.title == "質問文書"


INDEX_WITH_NOISE = """
<html><body>
<table class="result">
  <tr><td class="date">令和7年6月10日</td><td><a href="/m/toc">【目次】</a></td></tr>
  <tr><td class="date">令和7年6月10日</td><td><a href="/m/1">本会議</a></td></tr>
</table>
</body></html>
"""


def test_exclude_skips_links_by_text() -> None:
    config = _config()
    config.list.exclude = "目次"
    config.list.next_page = None
    scraper = GenericScraper(config)
    client = _client({"https://example.invalid/index": INDEX_WITH_NOISE})

    refs = list(scraper.list_meetings(client))

    assert [str(r.url) for r in refs] == ["https://example.invalid/m/1"]


def test_exclude_also_matches_the_url() -> None:
    config = _config()
    config.list.exclude = "/m/toc"
    config.list.next_page = None
    scraper = GenericScraper(config)
    client = _client({"https://example.invalid/index": INDEX_WITH_NOISE})

    assert [r.title for r in scraper.list_meetings(client)] == ["本会議"]


ROSTER_DETAIL = """
<html><body>
<div id="notes">
  <p>○出　席　議　員（六十七名）</p>
  <p>一　番　山本彰彦君　二　番　菅沼泰久君</p>
  <p>○議長（竹内良訓君）　会議を開きます。</p>
</div>
</body></html>
"""


def test_a_roster_line_is_not_mistaken_for_a_speech() -> None:
    # 「○出　席　議　員（六十七名）」 has the same shape as a speech marker; requiring
    # the 「君」 honorific is what separates a speaker from a headcount.
    config = _flat_config()
    config.detail.speech_split = r"○(?P<role>[^（(\n]{1,24})[（(](?P<speaker>[^）)\n]{1,24}君)[）)]"
    scraper = GenericScraper(config)
    ref = MeetingRef(prefecture="静岡県", url="https://example.invalid/d/2")
    meeting = scraper.parse_meeting(ref, make_page("https://example.invalid/d/2", ROSTER_DETAIL))

    assert [s.speaker for s in meeting.speeches] == ["竹内良訓"]


# --- multi-level listing -------------------------------------------------------
#
# 和歌山 and 愛媛 both publish index → session → sitting, and on 和歌山 the two
# listing levels are told apart only by the link's text. These fixtures mirror
# that shape: every link is a bare <a> in the same block.

INDEX_HTML = """
<div class="article">
  <h2>2026年(令和8年)</h2>
  <div><a href="/g/s1.html">2月定例会</a> <a href="/g/s2.html">5月臨時会</a></div>
  <div><a href="/other/help.html">人名等の正しい表記</a></div>
</div>
"""

SESSION1_HTML = """
<div class="article">
  <a href="/g/d1.html#00">◎第１号全文</a>
  <a href="/g/d2.html#00">◎第２号全文</a>
  <a href="/g/d2.html#01">山下直也議員</a>
</div>
"""

SESSION2_HTML = """<div class="article"><a href="/g/d3.html#00">◎第３号全文</a></div>"""

DETAIL_HTML = """
<div id="content">
<div class="title"><h1>令和8年2月　和歌山県議会定例会会議録　第1号（全文）</h1></div>
<div class="article">
  <p>議事日程　第一号</p>
  <p>令和八年二月十日（火曜日）午前十時開議</p>
  <p>○議長（鈴木太雄君）　これより本日の会議を開きます。</p>
  <p>○濱口太史君　皆さん、おはようございます。</p>
  <p>○知事（岸本周平君）　お答え申し上げます。</p>
  <p>〇教育長（宮﨑　泉君）　二〇〇三年度の実績を申し上げます。</p>
</div>
</div>
"""


def _wakayama_config() -> SiteConfig:
    return SiteConfig(
        prefecture="和歌山県",
        start_urls=["https://x.test/g/index.html"],
        list=ListSelectors(
            meeting_link='div.article a[href*="/g/"]',
            include="全文",
            index_link='div.article a[href*="/g/"]',
            index_include="(定例会|臨時会)$",
            max_pages=1,
            max_depth=2,
        ),
        detail=DetailSelectors(
            container="div#content",
            title="div.title h1",
            speech_split=r"[○〇](?:(?P<role>[^（(\n]{1,24})[（(])?"
            r"(?P<speaker>[^（()）\n]{1,24}君)[）)]?",
            patterns={
                "date": r"((?:令和|平成)[０-９0-9元一二三四五六七八九十]{1,4}年\s*"
                r"[０-９0-9一二三四五六七八九十]{1,3}月\s*"
                r"[０-９0-9一二三四五六七八九十]{1,3}日)\s*（[日月火水木金土]曜日）",
            },
        ),
    )


def _wakayama_pages() -> dict[str, str]:
    return {
        "https://x.test/g/index.html": INDEX_HTML,
        "https://x.test/g/s1.html": SESSION1_HTML,
        "https://x.test/g/s2.html": SESSION2_HTML,
        "https://x.test/g/d1.html": DETAIL_HTML,
        "https://x.test/g/d2.html": DETAIL_HTML,
        "https://x.test/g/d3.html": DETAIL_HTML,
    }


def test_index_link_walks_a_second_listing_level(fake_client) -> None:
    client = fake_client(_wakayama_pages())
    refs = list(GenericScraper(_wakayama_config()).list_meetings(client))

    # Transcripts from *both* session pages, reached through the index.
    assert [str(r.url) for r in refs] == [
        "https://x.test/g/d1.html",
        "https://x.test/g/d2.html",
        "https://x.test/g/d3.html",
    ]
    # The session pages themselves are never yielded as meetings.
    assert "https://x.test/g/s1.html" not in [str(r.url) for r in refs]


def test_include_keeps_out_the_per_member_slices(fake_client) -> None:
    """`/g/d2.html#01` is the same document sliced by member; only 全文 is taken."""
    client = fake_client(_wakayama_pages())
    refs = list(GenericScraper(_wakayama_config()).list_meetings(client))
    assert len(refs) == 3
    assert client.requested.count("https://x.test/g/d2.html") == 0  # listing only


def test_fragments_are_dropped_so_one_page_is_listed_once(fake_client) -> None:
    """Both 「◎第２号全文」(#00) and the member link (#01) point at one document."""
    client = fake_client(_wakayama_pages())
    cfg = _wakayama_config()
    cfg.list.include = None  # take every link, so the duplicate would show
    refs = list(GenericScraper(cfg).list_meetings(client))
    urls = [str(r.url) for r in refs]
    assert urls.count("https://x.test/g/d2.html") == 1
    assert all("#" not in u for u in urls)


def test_max_depth_bounds_the_walk(fake_client) -> None:
    client = fake_client(_wakayama_pages())
    cfg = _wakayama_config()
    cfg.list.max_depth = 1  # never leave the index
    assert list(GenericScraper(cfg).list_meetings(client)) == []
    assert client.requested == ["https://x.test/g/index.html"]


def test_bare_member_names_are_split_alongside_parenthesised_offices(fake_client) -> None:
    """静岡's rule would drop 「○濱口太史君」 — the member speeches — in silence."""
    client = fake_client(_wakayama_pages())
    scraper = GenericScraper(_wakayama_config())
    ref = next(iter(scraper.list_meetings(client)))
    meeting = scraper.parse_meeting(ref, client.get(str(ref.url)))

    assert [(s.role, s.speaker) for s in meeting.speeches] == [
        ("議長", "鈴木太雄"),
        (None, "濱口太史"),
        ("知事", "岸本周平"),
        # 〇 (U+3007) also marks speeches — 令和6年6月第1号 uses it throughout —
        # while 「二〇〇三年度」 in the body must not become a fourth speaker.
        ("教育長", "宮﨑　泉"),
    ]
    assert meeting.date == date(2026, 2, 10)  # 令和八年二月十日, in 漢数字
    assert meeting.title == "令和8年2月　和歌山県議会定例会会議録　第1号（全文）"


# --- broken and ambiguous index links ------------------------------------------

SESSION_MIXED_HTML = """
<div class="article">
  <a href="/g/d1.html#01">山下直也議員</a>
  <a href="/g/d1.html">◎第１号本文</a>
  <a href="/g/d2.html">◎第２号全文</a>
  <a href="/g/help.html">人名等の正しい表記</a>
</div>
"""


def test_a_rejected_link_does_not_decide_for_a_later_accepted_one(fake_client) -> None:
    """The member anchor and the sitting link resolve to one URL once the fragment
    is dropped, and the anchor comes first in the document."""
    pages = dict(_wakayama_pages())
    pages["https://x.test/g/s1.html"] = SESSION_MIXED_HTML
    client = fake_client(pages)
    cfg = _wakayama_config()
    cfg.list.include = "^◎"  # 全文 *and* 本文, which is why the circle is matched

    urls = [str(r.url) for r in GenericScraper(cfg).list_meetings(client)]
    assert "https://x.test/g/d1.html" in urls
    assert urls.count("https://x.test/g/d1.html") == 1
    assert "https://x.test/g/help.html" not in urls


def test_extra_meeting_urls_reach_what_a_broken_index_does_not(fake_client) -> None:
    """和歌山's 令和7年6月 page links its 第6号 with a truncated label and the wrong
    href, so the real page is unreachable from the site's own index."""
    client = fake_client(_wakayama_pages())
    cfg = _wakayama_config()
    cfg.list.extra_meeting_urls = ["https://x.test/g/d9.html"]

    urls = [str(r.url) for r in GenericScraper(cfg).list_meetings(client)]
    assert urls[0] == "https://x.test/g/d9.html"
    # and it is not fetched during listing — only when the meeting is parsed
    assert "https://x.test/g/d9.html" not in client.requested


# --- what 907 real documents taught the split rule -----------------------------

WAKAYAMA_SPLIT = (
    r"(?<![0-9０-９一二三四五六七八九十百千〇])[○〇]"
    r"(?:(?P<role>[^（(\n]{1,24})[（(])?(?P<speaker>[^（()）\n]{1,24}?君)[）)]?"
)


def _split(text: str) -> list[tuple[str | None, str]]:
    from prefectural_transcripts.scrapers.generic import _split_speeches

    return [(s.role, s.speaker) for s in _split_speeches(text, WAKAYAMA_SPLIT)]


def test_speaker_is_matched_lazily_not_greedily() -> None:
    """Greedy matching ran past the real name to a 「君」 inside the speech:
    「○林　隆一君　知事、大変失礼いたしました。林君」 became one 21-char speaker."""
    got = _split("○林　隆一君　知事、大変失礼いたしました。林君は続けます。\n")
    assert got == [(None, "林　隆一")]


def test_a_numeral_circle_is_not_a_speech_marker() -> None:
    """〇 is also a digit and 「君」 is also an ordinary word, so the 「君」 suffix
    alone is not enough: these two produced false speakers over the corpus."""
    assert _split("例えば二〇年後、三〇年後、君が四〇歳を過ぎたとき。\n") == []
    assert _split("子供一一〇番の家であるきしゅう君の家を設置し、\n") == []
    # …while the numeral rule must not reject 〇 used as a real marker.
    assert _split("〇議長（濱口太史君）　御異議なしと認めます。\n") == [("議長", "濱口太史")]


def test_a_speech_may_begin_mid_line() -> None:
    """Anchoring the marker to a line start would have killed the false positives
    above, but it loses 7 real speeches like this one."""
    text = "〔「異議なし」と呼ぶ者あり〕 ○議長（濱口太史君）　御異議なしと認めます。\n"
    assert _split(text) == [("議長", "濱口太史")]


def test_a_marker_need_not_be_followed_by_a_space() -> None:
    """Requiring whitespace after the marker loses 15 real speeches: the 「（続）」
    continuation form, and older sittings that run straight on."""
    assert _split("○浜本　収君（続）　わかっております。\n") == [(None, "浜本　収")]
    assert _split("○議長（橋本　進君）保健環境部長鈴木英明君。\n") == [("議長", "橋本　進")]
