"""Data model for assembly proceedings.

One `Meeting` is one sitting (本会議 or a committee session) and owns an ordered
list of `Speech` records. Everything is serialised to JSONL, one Meeting per line.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, computed_field

# `datetime` is imported under an alias because both models carry a field named
# `date`, which would otherwise shadow the type inside the class body.


Kind = Literal["verbatim", "summary"]
"""What a passage is: somebody's own words, or a record *of* what was said.

A 要点筆記 (和歌山's committees), a 要点記録 (秋田's and 神奈川's 議会運営委員会)
and 兵庫's 「○（委員長発言の概要）」 attribute words to a person without being that
person's words. They are kept — the researcher's decision of 2026-10-15 — but as
what they are: a passage marked `summary` is never a speech, and every count of
speeches, speakers or characters must leave it out. See `Meeting.kind` for where
a whole record of them is stored.
"""


class Speech(BaseModel):
    """A single contiguous utterance by one speaker — or, when `kind` says so,
    a passage of a summary record attributed to one."""

    order: int = Field(description="0-based position within the meeting")
    speaker: str = Field(description="Speaker name as printed, e.g. '山田太郎'")
    role: str | None = Field(
        default=None,
        description="Title/office as printed, e.g. '議長', '知事', '総務部長'",
    )
    text: str
    kind: Kind = Field(
        default="verbatim",
        description="'summary' for a 要点筆記/要点記録/発言の概要 passage; see `Kind`",
    )


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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def kind(self) -> Kind:
        """`summary` when every passage is one; derived, so it cannot disagree.

        A record that is summary throughout is not a transcript and is stored
        apart from the transcripts (`TranscriptStore`). A transcript with a few
        summarised passages — 兵庫's chair reading out 「発言の概要」 in a sitting
        that is otherwise verbatim — stays a transcript, with those passages
        marked in place, because moving them would lose where they were said.
        """
        if self.speeches and all(s.kind == "summary" for s in self.speeches):
            return "summary"
        return "verbatim"

    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.speeches)
