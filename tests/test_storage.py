from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from pathlib import Path

from prefectural_transcripts.models import Meeting, Speech
from prefectural_transcripts.storage import (
    SpeechCsvWriter,
    TranscriptStore,
    read_meetings,
    write_csv,
)


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


def _meeting_with_speeches(url: str, speeches: list[Speech]) -> Meeting:
    m = _meeting(url)
    m.speeches = speeches
    return m


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_csv_has_one_row_per_speech(tmp_path: Path) -> None:
    meeting = _meeting_with_speeches(
        "https://example.invalid/1",
        [
            Speech(order=0, speaker="山田太郎", role="議長", text="開会します。"),
            Speech(order=1, speaker="佐藤花子", role=None, text="質問します。"),
        ],
    )
    rows = write_csv([meeting], tmp_path / "out.csv")

    assert rows == 2
    read = _read_csv(tmp_path / "out.csv")
    assert [r["speaker"] for r in read] == ["山田太郎", "佐藤花子"]
    assert [r["speech_order"] for r in read] == ["0", "1"]
    assert read[1]["role"] == ""
    # Meeting-level fields are repeated onto every speech row.
    assert {r["session"] for r in read} == {"令和7年第2回定例会"}
    assert {r["date"] for r in read} == {"2025-06-10"}


def test_csv_survives_newlines_and_commas_in_text(tmp_path: Path) -> None:
    text = "まず、第一に。\n次に「引用, カンマ」を含む発言です。"
    meeting = _meeting_with_speeches(
        "https://example.invalid/1", [Speech(order=0, speaker="山田太郎", text=text)]
    )
    write_csv([meeting], tmp_path / "out.csv")

    assert _read_csv(tmp_path / "out.csv")[0]["text"] == text


def test_csv_keeps_meetings_with_no_speeches(tmp_path: Path) -> None:
    meeting = _meeting_with_speeches("https://example.invalid/1", [])
    assert write_csv([meeting], tmp_path / "out.csv") == 1

    row = _read_csv(tmp_path / "out.csv")[0]
    assert row["url"] == "https://example.invalid/1"
    assert row["speech_order"] == ""
    assert row["text"] == ""


def test_csv_writer_appends_across_runs_with_one_header(tmp_path: Path) -> None:
    for n in (1, 2):
        with SpeechCsvWriter(tmp_path, "東京都") as writer:
            writer.write(_meeting(f"https://example.invalid/{n}"))

    rows = _read_csv(writer.path)
    assert [r["url"] for r in rows] == [
        "https://example.invalid/1",
        "https://example.invalid/2",
    ]
    assert writer.path.read_text(encoding="utf-8-sig").count("prefecture,date") == 1


def test_csv_sits_next_to_the_jsonl_for_the_same_prefecture(tmp_path: Path) -> None:
    with TranscriptStore(tmp_path, "北海道") as store, SpeechCsvWriter(tmp_path, "北海道") as csvw:
        store.write(_meeting("https://example.invalid/1"))
        csvw.write(_meeting("https://example.invalid/1"))

    assert store.path.name == "北海道.jsonl"
    assert csvw.path.name == "北海道.csv"
