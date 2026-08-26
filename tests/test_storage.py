from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from prefectural_transcripts.models import Meeting, Speech
from prefectural_transcripts.storage import TranscriptStore, read_meetings


def _meeting(url: str) -> Meeting:
    return Meeting(
        prefecture="東京都",
        url=url,
        date=date(2025, 6, 10),
        session="令和7年第2回定例会",
        speeches=[Speech(order=0, speaker="山田太郎", role="議長", text="開会します。")],
        retrieved_at=datetime.now(UTC),
    )


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    with TranscriptStore(tmp_path, "東京都") as store:
        store.write(_meeting("https://example.invalid/1"))

    loaded = read_meetings(store.path)
    assert len(loaded) == 1
    assert loaded[0].speeches[0].speaker == "山田太郎"
    assert loaded[0].date == date(2025, 6, 10)


def test_seen_keys_enables_resume(tmp_path: Path) -> None:
    with TranscriptStore(tmp_path, "東京都") as store:
        store.write(_meeting("https://example.invalid/1"))

    reopened = TranscriptStore(tmp_path, "東京都")
    assert reopened.seen_keys() == {"https://example.invalid/1"}


def test_appends_across_runs(tmp_path: Path) -> None:
    for n in (1, 2):
        with TranscriptStore(tmp_path, "東京都") as store:
            store.write(_meeting(f"https://example.invalid/{n}"))
    assert len(read_meetings(store.path)) == 2


def test_malformed_lines_do_not_break_resume(tmp_path: Path) -> None:
    with TranscriptStore(tmp_path, "東京都") as store:
        store.write(_meeting("https://example.invalid/1"))
    store.path.open("a", encoding="utf-8").write("{ not json\n")

    assert TranscriptStore(tmp_path, "東京都").seen_keys() == {"https://example.invalid/1"}
