"""Output storage: one JSONL file per prefecture, one Meeting per line.

JSONL is chosen over a database because the downstream consumer is analysis code
that wants to stream the corpus, and because a partial run leaves a valid file.
`seen_keys` lets a run resume without re-fetching what is already on disk.
"""

from __future__ import annotations

import json
import logging
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
