"""Output storage: one JSONL file per prefecture, one Meeting per line.

A CSV view of the same records (one row per speech) can be written alongside it,
or produced later from the JSONL with `pt export`.

JSONL is chosen over a database because the downstream consumer is analysis code
that wants to stream the corpus, and because a partial run leaves a valid file.
`seen_keys` lets a run resume without re-fetching what is already on disk.

**Transcripts and summaries are two files.** A record that is summary throughout
(`Meeting.kind`) goes to `data/summary/<prefecture>.jsonl`, never beside the
transcripts: every count this project has ever published was taken over
`data/*.jsonl`, and a 要点筆記 there would be counted as speeches by all of them.
The store routes by the record's own kind, so no scraper has to remember to.
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from types import TracebackType
from typing import TextIO

from prefectural_transcripts.models import Kind, Meeting, record_key

log = logging.getLogger(__name__)


SUMMARY_DIR = "summary"
"""Where records that are not transcripts live, under the data directory."""


def _slug(prefecture: str) -> str:
    return "".join(c for c in prefecture if c.isalnum() or c in "-_") or "unknown"


def corpus_path(data_dir: Path, prefecture: str, kind: Kind = "verbatim") -> Path:
    """`data/<prefecture>.jsonl`, or `data/summary/<prefecture>.jsonl` for summaries."""
    base = data_dir / SUMMARY_DIR if kind == "summary" else data_dir
    return base / f"{_slug(prefecture)}.jsonl"


def summary_path(corpus: Path) -> Path:
    """The summary file that belongs beside a transcript corpus file."""
    return corpus.parent / SUMMARY_DIR / corpus.name


class TranscriptStore:
    """Append-only JSONL writer, one file per prefecture and kind.

    `path` is the transcripts; `summary` is where a record that is summary
    throughout is written instead. `seen_keys` reads both, so a run resumes the
    same whichever file a record went to.
    """

    def __init__(self, data_dir: Path, prefecture: str) -> None:
        self.path = corpus_path(data_dir, prefecture)
        self.summary = corpus_path(data_dir, prefecture, "summary")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: TextIO | None = None
        self._summary_fh: TextIO | None = None
        self.written: dict[Kind, int] = {"verbatim": 0, "summary": 0}

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
        if self._summary_fh:
            self._summary_fh.close()
            self._summary_fh = None

    def seen_keys(self) -> set[str]:
        """Records already written, so a re-run can skip them.

        Read through `record_key` rather than off the `url` field: a manually
        imported record has no URL and is identified by its source file.
        """
        keys: set[str] = set()
        for path in (self.path, self.summary):
            if not path.exists():
                continue
            with path.open(encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        keys.add(record_key(record.get("url"), record.get("source_file")))
                    except (json.JSONDecodeError, ValueError):
                        log.warning("skipping malformed line %d in %s", line_no, path)
        return keys

    def write(self, meeting: Meeting) -> None:
        if self._fh is None:
            raise RuntimeError("TranscriptStore must be used as a context manager")
        fh = self._fh
        if meeting.kind == "summary":
            if self._summary_fh is None:
                self.summary.parent.mkdir(parents=True, exist_ok=True)
                self._summary_fh = self.summary.open("a", encoding="utf-8")
            fh = self._summary_fh
        fh.write(meeting.model_dump_json() + "\n")
        fh.flush()
        self.written[meeting.kind] += 1


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
    "source_file",
    "speech_order",
    "speaker",
    "role",
    "kind",
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
        "url": str(meeting.url) if meeting.url else "",
        "source_file": meeting.source_file or "",
        "retrieved_at": meeting.retrieved_at.isoformat(),
        "source_html_sha256": meeting.source_html_sha256 or "",
    }
    if not meeting.speeches:
        return [{**common, "speech_order": "", "speaker": "", "role": "", "kind": "", "text": ""}]
    return [
        {
            **common,
            "speech_order": str(s.order),
            "speaker": s.speaker,
            "role": s.role or "",
            "kind": s.kind,
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
        self.path = corpus_path(data_dir, prefecture).with_suffix(".csv")
        self.summary = corpus_path(data_dir, prefecture, "summary").with_suffix(".csv")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: TextIO | None = None
        self._writer: csv.DictWriter[str] | None = None
        self._summary_fh: TextIO | None = None
        self._summary_writer: csv.DictWriter[str] | None = None

    @staticmethod
    def _open(path: Path) -> tuple[TextIO, csv.DictWriter[str]]:
        write_header = not path.exists() or path.stat().st_size == 0
        fh = path.open("a", encoding="utf-8-sig", newline="")
        writer = csv.DictWriter(fh, fieldnames=list(SPEECH_COLUMNS))
        if write_header:
            writer.writeheader()
        return fh, writer

    def __enter__(self) -> SpeechCsvWriter:
        self._fh, self._writer = self._open(self.path)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        for fh in (self._fh, self._summary_fh):
            if fh:
                fh.close()
        self._fh = self._summary_fh = None
        self._writer = self._summary_writer = None

    def write(self, meeting: Meeting) -> None:
        if self._writer is None or self._fh is None:
            raise RuntimeError("SpeechCsvWriter must be used as a context manager")
        fh, writer = self._fh, self._writer
        if meeting.kind == "summary":
            if self._summary_fh is None or self._summary_writer is None:
                self.summary.parent.mkdir(parents=True, exist_ok=True)
                self._summary_fh, self._summary_writer = self._open(self.summary)
            fh, writer = self._summary_fh, self._summary_writer
        writer.writerows(_speech_rows(meeting))
        fh.flush()


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
