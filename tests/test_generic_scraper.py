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
