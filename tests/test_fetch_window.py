"""The hours an operator restricts fetching to.

滋賀県議会事務局 permitted collection on 2026-09-18 and asked for one thing:
「取得の時間帯を土日の夜間帯（20時以降）に限定するようお願い申し上げます」.
These are the rules that condition turns into.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest

from prefectural_transcripts.config import FetchWindow, Settings
from prefectural_transcripts.http import OutsideFetchWindow, PoliteClient

JST = ZoneInfo("Asia/Tokyo")

SHIGA = """
[fetch_window]
days = ["sat", "sun"]
start = "20:00"
end = "24:00"
reason = "滋賀県議会事務局の指示 (2026-09-18): 取得の時間帯を土日の夜間帯（20時以降）に限定"
decided_on = "2026-09-18"
"""


def window() -> FetchWindow:
    table = tomllib.loads(SHIGA)["fetch_window"]
    parsed = FetchWindow.from_toml(table)
    assert parsed is not None
    return parsed


def test_the_window_is_saturday_and_sunday_evenings() -> None:
    w = window()
    # 2026-09-18 is a Friday, 2026-09-19 a Saturday.
    assert not w.allows(datetime(2026, 9, 18, 21, 0, tzinfo=JST))  # Friday night
    assert not w.allows(datetime(2026, 9, 19, 19, 59, tzinfo=JST))  # Saturday, a minute early
    assert w.allows(datetime(2026, 9, 19, 20, 0, tzinfo=JST))  # Saturday, open
    assert w.allows(datetime(2026, 9, 20, 23, 59, tzinfo=JST))  # Sunday, still open
    assert not w.allows(datetime(2026, 9, 21, 0, 30, tzinfo=JST))  # Monday morning


def test_midnight_ends_the_day_rather_than_starting_it() -> None:
    # 「20時以降」 with no end given means until the day is out, not until 00:00
    # of a day that has not started — a window that read [20:00, 00:00) as empty
    # would refuse every request and look like a bug in the crawler.
    assert window().allows(datetime(2026, 9, 19, 23, 59, 59, tzinfo=JST))


def test_the_next_opening_is_a_time_a_person_can_act_on() -> None:
    w = window()
    friday_afternoon = datetime(2026, 9, 18, 16, 31, tzinfo=JST)
    assert w.next_open(friday_afternoon) == datetime(2026, 9, 19, 20, 0, tzinfo=JST)

    saturday_open = datetime(2026, 9, 19, 21, 0, tzinfo=JST)
    assert w.next_open(saturday_open) == saturday_open

    sunday_late = datetime(2026, 9, 20, 23, 0, tzinfo=JST)
    # Past this weekend, the next one.
    assert w.next_open(datetime(2026, 9, 21, 9, 0, tzinfo=JST)) == datetime(
        2026, 9, 26, 20, 0, tzinfo=JST
    )
    assert w.allows(sunday_late)


def test_the_window_is_read_in_its_own_timezone() -> None:
    # A server set to UTC must not fetch at 20:00 UTC, which is 05:00 in 滋賀.
    w = window()
    assert not w.allows(datetime(2026, 9, 19, 20, 0, tzinfo=UTC))
    assert w.allows(datetime(2026, 9, 19, 11, 0, tzinfo=UTC))  # 20:00 JST


def test_a_window_must_say_whose_instruction_it_is() -> None:
    from datetime import time

    with pytest.raises(ValueError, match="whose instruction"):
        FetchWindow(days=(5, 6), start=time(20), end=time(0), reason=" ", decided_on="2026-09-18")
    with pytest.raises(ValueError, match="decided_on"):
        FetchWindow(days=(5, 6), start=time(20), end=time(0), reason="asked", decided_on="soon")
    with pytest.raises(ValueError, match="at least one day"):
        FetchWindow(days=(), start=time(20), end=time(0), reason="asked", decided_on="2026-09-18")


def _client(tmp_path: Path, now: datetime, monkeypatch: pytest.MonkeyPatch) -> PoliteClient:
    monkeypatch.setattr("prefectural_transcripts.http.current_time", lambda: now)
    settings = Settings()
    settings.cache_dir = tmp_path
    settings.min_interval = 0.0
    settings.respect_robots = False
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="会議録"))
    return PoliteClient(settings, client=httpx.Client(transport=transport), fetch_window=window())


def test_the_client_refuses_outside_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    friday = datetime(2026, 9, 18, 16, 31, tzinfo=JST)
    with _client(tmp_path, friday, monkeypatch) as client, pytest.raises(OutsideFetchWindow) as err:
        client.get("https://www.shigaken-gikai.jp/voices/cgi-bin/x.exe")

    # The message has to carry what to do about it, not just that it happened.
    assert "2026-09-19 20:00" in str(err.value)
    assert "滋賀県議会事務局" in str(err.value)


def test_the_client_fetches_inside_the_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saturday = datetime(2026, 9, 19, 20, 30, tzinfo=JST)
    with _client(tmp_path, saturday, monkeypatch) as client:
        assert client.get("https://www.shigaken-gikai.jp/voices/a").status == 200


def test_a_cached_page_is_served_at_any_hour(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Re-parsing and auditing read only the cache, and they are the checks this
    # project asks for most often. Making them wait for Saturday night would be
    # a promise about fetching enforced against something that is not a fetch.
    url = "https://www.shigaken-gikai.jp/voices/b"
    saturday = datetime(2026, 9, 19, 21, 0, tzinfo=JST)
    with _client(tmp_path, saturday, monkeypatch) as client:
        client.get(url)

    monday = datetime(2026, 9, 21, 10, 0, tzinfo=JST)
    with _client(tmp_path, monday, monkeypatch) as client:
        page = client.get(url)

    assert page.from_cache and "会議録" in page.text


def test_a_window_refusal_stops_a_run_rather_than_repeating_per_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `scrape()` swallows a FetchError and moves to the next document, which is
    # right for one bad page and wrong for the hours: it would break the same
    # promise once per document, thousands of times, and finish looking normal.
    from prefectural_transcripts.models import MeetingRef
    from prefectural_transcripts.scrapers.base import BaseScraper

    class OneDocument(BaseScraper):
        prefecture = "滋賀県"
        fetch_window = window()

        def list_meetings(self, client: PoliteClient):  # type: ignore[no-untyped-def]
            for n in range(3):
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=f"https://www.shigaken-gikai.jp/voices/{n}",  # type: ignore[arg-type]
                )

        def parse_meeting(self, ref, page):  # type: ignore[no-untyped-def]
            raise AssertionError("never reached")

    friday = datetime(2026, 9, 18, 16, 31, tzinfo=JST)
    with _client(tmp_path, friday, monkeypatch) as client, pytest.raises(OutsideFetchWindow):
        list(OneDocument().scrape(client))


# --- who the operator can reach --------------------------------------------


def test_a_site_can_name_the_address_its_operator_knows() -> None:
    # 滋賀's permission answers an enquiry a collaborator made, so the address
    # its secretariat has on file is not this project's PT_CONTACT.
    from prefectural_transcripts.config import Contact

    table = tomllib.loads(
        "[contact]\n"
        'address = "someone@example.ac.jp"\n'
        'note = "照会は共同研究者が行い、2026-09-18に許可を得た"\n'
    )["contact"]
    contact = Contact.from_toml(table)

    assert contact is not None
    assert contact.address == "someone@example.ac.jp"
    assert "共同研究者" in contact.note


def test_a_contact_has_to_be_reachable() -> None:
    from prefectural_transcripts.config import Contact

    with pytest.raises(ValueError, match="an operator can use"):
        Contact(address="共同研究者A")
