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
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin

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

    exclude: str | None = None
    """Regex; links whose text or URL matches are not followed.

    Index pages mix transcripts with things that merely sit in the same list —
    a 【目次】 entry, a notice, a PDF of the agenda. Skipping them at listing time
    keeps them out of the corpus and saves the fetch.
    """

    include: str | None = None
    """Regex; when set, only links whose text or URL matches are followed.

    The counterpart to `exclude`, for pages where the transcripts are the
    exception rather than the rule. `exclude` still wins where both match.
    """

    index_link: str | None = None
    """Selector for links leading to *another listing page* rather than a
    transcript.

    Assemblies commonly publish an index of sessions, each session listing its
    sittings, and only the sitting carrying the transcript — 和歌山 and 愛媛 are
    both this shape. Without an intermediate level, every session page has to be
    written out by hand as a `start_url`.

    `meeting_link` and `index_link` are both applied at every level, so the two
    sets usually separate themselves: a session index holds no transcript links
    and a session page holds no further index links. `max_depth` bounds the walk
    regardless.
    """

    index_include: str | None = None
    """Regex filter for `index_link`, matched on link text or URL.

    Needed where the two levels are told apart by the link's text rather than by
    its markup — a CMS that renders both as a bare `<a>` in the same block.
    """

    index_exclude: str | None = None
    """Regex; index links whose text or URL matches are not followed."""

    max_depth: int = 3
    """How many listing levels to walk, counting the start URL as level 1."""


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

    speech_split: str | None = None
    """Regex marking where each speech starts, for pages with no per-speech markup.

    Japanese minutes conventionally prefix every utterance with 「○」 followed by
    the speaker's office and name — 「○知事（鈴木康友君）　…」 — and many older
    systems emit the whole sitting as one run of text with no element to select.
    Give a pattern with a `speaker` group (and optionally `role`); the text from
    one match to the next becomes that speech.
    """

    patterns: dict[str, str] = field(default_factory=dict)
    """Regex fallbacks for meeting fields CSS cannot reach, matched on the
    container's text. Keys are `date`, `session`, `committee`, `title`; each value
    is a regex whose first group (or whole match, if it has no group) is the value.

    Legacy table layouts label their fields by the text of the neighbouring cell
    rather than by class or id, and CSS has no way to say "the cell after the one
    reading 質問日：". A selector is still preferred when one exists; a pattern is
    only consulted when the selector is absent or matches nothing.
    """


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


def _resolve(base_url: str, href: str) -> str:
    """Absolute URL with any `#fragment` dropped.

    Index pages often link the same document several times at different anchors
    (和歌山 links 「◎第二号全文」 and each member's question into one page). The
    fragment never selects a different document server-side, so dropping it is
    what makes the `seen` set deduplicate correctly instead of refetching.
    """
    return urldefrag(urljoin(base_url, href)).url


def _wanted(label: str, url: str, include: str | None, exclude: str | None) -> bool:
    """Whether a link passes the config's include/exclude regexes.

    Both are matched against the link's text *or* its URL, because index pages
    label some links only by text and others only by href. `exclude` wins.
    """
    if exclude and (re.search(exclude, label) or re.search(exclude, url)):
        return False
    return not (include and not (re.search(include, label) or re.search(include, url)))


def _first_group(pattern: str, text: str) -> str:
    m = re.search(pattern, text)
    if not m:
        return ""
    return (m.group(1) if m.re.groups else m.group(0)).strip()


class GenericScraper(BaseScraper):
    """Drives one site from a `SiteConfig`."""

    def __init__(self, config: SiteConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        sel = self.config.list
        seen: set[str] = set()
        visited: set[str] = set()
        # (url, depth); the start URLs are depth 1.
        pending: list[tuple[str, int]] = [(u, 1) for u in self.config.start_urls]

        while pending:
            start, depth = pending.pop(0)
            url: str | None = start
            for _ in range(sel.max_pages):
                if url is None or url in visited:
                    break
                visited.add(url)
                page = client.get(url)
                soup = _soup(page)
                yield from self._refs_on_page(soup, page.url, seen)
                if depth < sel.max_depth:
                    for child in self._index_links(soup, page.url, visited):
                        pending.append((child, depth + 1))
                url = self._next_page(soup, page.url)

    def _index_links(self, soup: BeautifulSoup, base_url: str, visited: set[str]) -> list[str]:
        """Links on this page that lead to another listing page."""
        sel = self.config.list
        if not sel.index_link:
            return []
        out: list[str] = []
        for link in soup.select(sel.index_link):
            href = link.get("href")
            if not isinstance(href, str):
                continue
            url = _resolve(base_url, href)
            if url in visited:
                continue
            if not _wanted(_text(link), url, sel.index_include, sel.index_exclude):
                continue
            out.append(url)
        return out

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
                url = _resolve(base_url, href)
                if url in seen:
                    continue
                seen.add(url)
                label = _text(link)
                if not _wanted(label, url, sel.include, sel.exclude):
                    log.debug("skipped %s (%s)", url, label)
                    continue
                row_date = parse_japanese_date(_select_text(scope, sel.date)) if sel.date else None
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=url,  # type: ignore[arg-type]
                    date=row_date or parse_japanese_date(label),
                    title=label or None,
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
        # Only paid for when the config actually uses patterns.
        body = _text(root) if sel.patterns else ""

        def value(name: str, selector: str | None) -> str:
            return _select_text(root, selector) or (
                _first_group(sel.patterns[name], body) if name in sel.patterns else ""
            )

        return Meeting(
            prefecture=self.prefecture,
            url=page.url,  # type: ignore[arg-type]
            date=parse_japanese_date(value("date", sel.date)) or ref.date,
            session=value("session", sel.session) or None,
            committee=value("committee", sel.committee) or None,
            title=value("title", sel.title) or ref.title,
            speeches=self._speeches(root),
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )

    def _speeches(self, root: Tag) -> list[Speech]:
        sel = self.config.detail
        if sel.speech_split and not sel.speech:
            # Newlines are kept here: the split is done on text, and paragraph
            # breaks are the only structure these pages have left.
            return _split_speeches(root.get_text("\n", strip=True), sel.speech_split)
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


def _split_speeches(text: str, pattern: str) -> list[Speech]:
    """Cut a flat transcript into speeches at each `pattern` match.

    Everything from one marker to the next is that speaker's text. Anything
    before the first marker is procedural chrome (a heading, a table of
    contents) and is dropped.
    """
    regex = re.compile(pattern)
    marks = list(regex.finditer(text))
    speeches: list[Speech] = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[mark.end() : end].strip()
        if not body:
            continue
        groups = mark.groupdict()
        speeches.append(
            Speech(
                order=len(speeches),
                speaker=_clean_speaker(groups.get("speaker", "")),
                role=(groups.get("role") or "").strip() or None,
                text=body,
            )
        )
    return speeches


def _clean_speaker(name: str) -> str:
    """Drop the 「君」 the minutes append to every name; keep the name itself."""
    return re.sub(r"\s*君$", "", name.strip())
