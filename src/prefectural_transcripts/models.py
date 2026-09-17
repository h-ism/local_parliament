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


def record_key(url: str | None, source_file: str | None) -> str:
    """The identity of one record, however it was obtained.

    Crawled records are identified by their URL. A record imported from a file
    the researcher downloaded by hand has no URL we have ever fetched, and
    composing a plausible-looking one would be inventing it — so the file name
    is the identity instead, under a `file:` scheme that cannot collide with a
    real URL. `TranscriptStore.seen_keys` reads records back through this, so
    resume works the same way for both.
    """
    if url:
        return url
    if source_file:
        return f"file:{source_file}"
    raise ValueError("a record needs either a url or a source_file")


class Meeting(BaseModel):
    """A fully fetched sitting with its transcript."""

    prefecture: str = Field(description="e.g. '東京都', '大阪府', '北海道'")
    url: HttpUrl | None = Field(
        default=None,
        description="Where the sitting was fetched from; None for a manual import",
    )
    source_file: str | None = Field(
        default=None,
        description="File name a manually downloaded record was imported from",
    )
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
        return record_key(str(self.url) if self.url else None, self.source_file)

    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.speeches)
