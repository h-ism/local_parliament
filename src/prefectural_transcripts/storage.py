"""Output storage: one JSONL file per prefecture, one Meeting per line.

A CSV view of the same records (one row per speech) can be written alongside it,
or produced later from the JSONL with `pt export`.

JSONL is chosen over a database because the downstream consumer is analysis code
that wants to stream the corpus, and because a partial run leaves a valid file.
`seen_keys` lets a run resume without re-fetching what is already on disk.
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from typing import TextIO

from prefectural_transcripts.models import Meeting

log = logging.getLogger(__name__)


def _slug(prefecture: str) -> str:
    return "".join(c for c in prefecture if c.isalnum() or c in "-_") or "unknown"


class TranscriptStore:
    """Append-only JSONL writer, one file per prefecture."""

    def __init__(self, data_dir: Path, prefecture: str) -> None:
        self.path = data_dir / f"{_slug(prefecture)}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: TextIO | None = None

    def __enter__(self) -> TranscriptStore:
        self._fh = self.path.open("a", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    def seen_keys(self) -> set[str]:
        """URLs already written, so a re-run can skip them."""
        if not self.path.exists():
            return set()
        keys: set[str] = set()
        with self.path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    keys.add(json.loads(line)["url"])
                except (json.JSONDecodeError, KeyError):
                    log.warning("skipping malformed line %d in %s", line_no, self.path)
        return keys

    def write(self, meeting: Meeting) -> None:
        if self._fh is None:
            raise RuntimeError("TranscriptStore must be used as a context manager")
        self._fh.write(meeting.model_dump_json() + "\n")
        self._fh.flush()


def read_meetings(path: Path) -> list[Meeting]:
    """Load a JSONL corpus file back into Meeting objects."""
    meetings = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                meetings.append(Meeting.model_validate_json(line))
    return meetings


SPEECH_COLUMNS = (
    "prefecture",
    "date",
    "session",
    "committee",
    "title",
    "url",
    "speech_order",
    "speaker",
    "role",
    "text",
    "retrieved_at",
    "source_html_sha256",
)


def _speech_rows(meeting: Meeting) -> list[dict[str, str]]:
    """Flatten one Meeting into one row per speech.

    A meeting with no speeches still gets a row, with the speech columns empty:
    the CSV is meant to be a faithful view of the corpus, and a sitting whose
    selectors produced nothing is exactly the thing worth noticing.
    """
    common = {
        "prefecture": meeting.prefecture,
        "date": meeting.date.isoformat() if meeting.date else "",
        "session": meeting.session or "",
        "committee": meeting.committee or "",
        "title": meeting.title or "",
        "url": str(meeting.url),
        "retrieved_at": meeting.retrieved_at.isoformat(),
        "source_html_sha256": meeting.source_html_sha256 or "",
    }
    if not meeting.speeches:
        return [{**common, "speech_order": "", "speaker": "", "role": "", "text": ""}]
    return [
        {
            **common,
            "speech_order": str(s.order),
            "speaker": s.speaker,
            "role": s.role or "",
            "text": s.text,
        }
        for s in meeting.speeches
    ]


class SpeechCsvWriter:
    """Companion to `TranscriptStore`: the same records, one row per speech.

    JSONL stays the canonical store — it round-trips the model exactly — but a
    lot of downstream analysis just wants a table, so this writes one next to it.
    Encoded utf-8-sig because these files get opened in Excel, which otherwise
    mangles Japanese text.
    """

    def __init__(self, data_dir: Path, prefecture: str) -> None:
        self.path = data_dir / f"{_slug(prefecture)}.csv"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: TextIO | None = None
        self._writer: csv.DictWriter[str] | None = None

    def __enter__(self) -> SpeechCsvWriter:
        write_header = not self.path.exists() or self.path.stat().st_size == 0
        self._fh = self.path.open("a", encoding="utf-8-sig", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=list(SPEECH_COLUMNS))
        if write_header:
            self._writer.writeheader()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None
            self._writer = None

    def write(self, meeting: Meeting) -> None:
        if self._writer is None or self._fh is None:
            raise RuntimeError("SpeechCsvWriter must be used as a context manager")
        self._writer.writerows(_speech_rows(meeting))
        self._fh.flush()


def write_csv(meetings: Iterable[Meeting], path: Path) -> int:
    """Write a whole corpus to `path` as one row per speech. Returns the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(SPEECH_COLUMNS))
        writer.writeheader()
        for meeting in meetings:
            batch = _speech_rows(meeting)
            writer.writerows(batch)
            rows += len(batch)
    return rows
