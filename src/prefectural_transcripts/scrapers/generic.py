"""A config-driven scraper for the common 会議録検索システム layout.

Most prefectural assemblies publish minutes through one of a handful of vendor
systems, all of which share the same shape: a paginated result list linking to
per-sitting detail pages, where each speech is a block carrying a speaker name.
Only the CSS selectors differ.

So a new prefecture is a TOML file in `sites/`, not a new Python module. See
`sites/_example.toml` for the full set of fields.
"""

from __future__ import annotations

import logging
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from prefectural_transcripts.dates import parse_japanese_date
from prefectural_transcripts.http import Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef, Speech
from prefectural_transcripts.scrapers.base import BaseScraper

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ListSelectors:
    meeting_link: str
    row: str | None = None
    date: str | None = None
    next_page: str | None = None
    max_pages: int = 50


@dataclass(slots=True)
class DetailSelectors:
    container: str | None = None
    speech: str | None = None
    speaker: str | None = None
    role: str | None = None
    text: str | None = None
    date: str | None = None
    session: str | None = None
    committee: str | None = None
    title: str | None = None


@dataclass(slots=True)
class SiteConfig:
    prefecture: str
    start_urls: list[str]
    list: ListSelectors
    detail: DetailSelectors
    name: str = ""

    @classmethod
    def from_toml(cls, path: Path) -> SiteConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        try:
            return cls(
                prefecture=raw["prefecture"],
                start_urls=list(raw["start_urls"]),
                list=ListSelectors(**raw.get("list", {})),
                detail=DetailSelectors(**raw.get("detail", {})),
                name=raw.get("name", path.stem),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid site config {path}: {exc}") from exc


def _soup(page: Page) -> BeautifulSoup:
    return BeautifulSoup(page.text, "lxml")


def _text(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _select_text(root: Tag, selector: str | None) -> str:
    if not selector:
        return ""
    return _text(root.select_one(selector))


class GenericScraper(BaseScraper):
    """Drives one site from a `SiteConfig`."""

    def __init__(self, config: SiteConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        seen: set[str] = set()
        for start in self.config.start_urls:
            url: str | None = start
            for _ in range(self.config.list.max_pages):
                if url is None:
                    break
                page = client.get(url)
                soup = _soup(page)
                yield from self._refs_on_page(soup, page.url, seen)
                url = self._next_page(soup, page.url)

    def _refs_on_page(
        self, soup: BeautifulSoup, base_url: str, seen: set[str]
    ) -> Iterator[MeetingRef]:
        sel = self.config.list
        # When `row` is set, each row scopes one link plus its own date cell;
        # otherwise links are taken straight off the page with no date.
        scopes: list[Tag] = soup.select(sel.row) if sel.row else [soup]
        for scope in scopes:
            for link in scope.select(sel.meeting_link):
                href = link.get("href")
                if not isinstance(href, str):
                    continue
                url = urljoin(base_url, href)
                if url in seen:
                    continue
                seen.add(url)
                row_date = parse_japanese_date(_select_text(scope, sel.date)) if sel.date else None
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=url,  # type: ignore[arg-type]
                    date=row_date or parse_japanese_date(_text(link)),
                    title=_text(link) or None,
                )

    def _next_page(self, soup: BeautifulSoup, base_url: str) -> str | None:
        if not self.config.list.next_page:
            return None
        link = soup.select_one(self.config.list.next_page)
        href = link.get("href") if link else None
        return urljoin(base_url, href) if isinstance(href, str) else None

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        sel = self.config.detail
        soup = _soup(page)
        root: Tag = (soup.select_one(sel.container) if sel.container else None) or soup

        return Meeting(
            prefecture=self.prefecture,
            url=page.url,  # type: ignore[arg-type]
            date=parse_japanese_date(_select_text(root, sel.date)) or ref.date,
            session=_select_text(root, sel.session) or None,
            committee=_select_text(root, sel.committee) or None,
            title=_select_text(root, sel.title) or ref.title,
            speeches=self._speeches(root),
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )

    def _speeches(self, root: Tag) -> list[Speech]:
        sel = self.config.detail
        if not sel.speech:
            # No per-speech markup configured: keep the page as a single block
            # rather than silently dropping the transcript.
            body = _text(root)
            return [Speech(order=0, speaker="", text=body)] if body else []

        speeches = []
        for i, block in enumerate(root.select(sel.speech)):
            speaker = _select_text(block, sel.speaker)
            role = _select_text(block, sel.role)
            text = _select_text(block, sel.text) if sel.text else _text(block)
            if not text:
                continue
            speeches.append(Speech(order=i, speaker=speaker, role=role or None, text=text))
        return speeches
