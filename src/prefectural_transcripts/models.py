"""Data model for assembly proceedings.

One `Meeting` is one sitting (本会議 or a committee session) and owns an ordered
list of `Speech` records. Everything is serialised to JSONL, one Meeting per line.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, HttpUrl

# `datetime` is imported under an alias because both models carry a field named
# `date`, which would otherwise shadow the type inside the class body.


class Speech(BaseModel):
    """A single contiguous utterance by one speaker."""

    order: int = Field(description="0-based position within the meeting")
    speaker: str = Field(description="Speaker name as printed, e.g. '山田太郎'")
    role: str | None = Field(
        default=None,
        description="Title/office as printed, e.g. '議長', '知事', '総務部長'",
    )
    text: str


class MeetingRef(BaseModel):
    """A meeting located in a search index but not yet fetched.

    Scrapers list these cheaply, then fetch each one; keeping the two steps
    separate lets a run resume without re-walking the search pages.
    """

    prefecture: str
    url: HttpUrl
    date: dt.date | None = None
    title: str | None = None

    @property
    def key(self) -> str:
        """Stable identifier used for dedupe and resume."""
        return str(self.url)


class Meeting(BaseModel):
    """A fully fetched sitting with its transcript."""

    prefecture: str = Field(description="e.g. '東京都', '大阪府', '北海道'")
    url: HttpUrl
    date: dt.date | None = None
    session: str | None = Field(default=None, description="e.g. '令和7年第2回定例会'")
    committee: str | None = Field(
        default=None, description="Committee name; None for 本会議 (plenary)"
    )
    title: str | None = None
    speeches: list[Speech] = Field(default_factory=list)
    retrieved_at: dt.datetime
    source_html_sha256: str | None = Field(
        default=None, description="Hash of the raw page, to tie a record back to its cached source"
    )

    @property
    def key(self) -> str:
        return str(self.url)

    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.speeches)
