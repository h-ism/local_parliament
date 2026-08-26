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
