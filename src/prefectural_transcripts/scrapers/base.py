"""Scraper interface.

Scraping is split into two phases on purpose:

* `list_meetings` walks the site's search/index pages and yields cheap `MeetingRef`s.
* `parse_meeting` turns one fetched detail page into a `Meeting`.

Keeping them apart means a crawl can be resumed, filtered by date, or capped
without the listing logic knowing anything about transcripts.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import date

from prefectural_transcripts.http import FetchError, Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef

log = logging.getLogger(__name__)


class BaseScraper(ABC):
    """One prefecture's assembly site."""

    prefecture: str

    @abstractmethod
    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        """Yield references to every meeting reachable from the site's index."""

    @abstractmethod
    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        """Turn a fetched detail page into a Meeting."""

    def scrape(
        self,
        client: PoliteClient,
        *,
        since: date | None = None,
        until: date | None = None,
        limit: int | None = None,
        skip: set[str] | None = None,
    ) -> Iterator[Meeting]:
        """Walk the index and yield parsed meetings.

        A meeting whose date is unknown at listing time is always fetched; the
        date filter is re-applied after parsing, when the real date is known.
        """
        skip = skip or set()
        produced = 0
        for ref in self.list_meetings(client):
            if limit is not None and produced >= limit:
                return
            if ref.key in skip:
                log.debug("already have %s", ref.key)
                continue
            if ref.date and not _in_range(ref.date, since, until):
                continue

            try:
                page = client.get(str(ref.url))
                meeting = self.parse_meeting(ref, page)
            except FetchError as exc:
                log.error("could not fetch %s: %s", ref.url, exc)
                continue
            except Exception:
                log.exception("could not parse %s", ref.url)
                continue

            if meeting.date and not _in_range(meeting.date, since, until):
                continue
            if not meeting.speeches:
                log.warning("no speeches extracted from %s — check selectors", ref.url)

            produced += 1
            yield meeting


def _in_range(value: date, since: date | None, until: date | None) -> bool:
    if since and value < since:
        return False
    return not (until and value > until)
