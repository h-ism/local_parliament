"""Scraper for DB-Search (大和速記情報センター, `*.dbsr.jp`), where fetching is permitted.

**Which is not the product, it is the assembly.** 山梨 runs the same system and
asked on 2026-09-17 that it not be fetched automatically — 山梨 is collected by
hand and imported (`importers/dbsearch.py`). 茨城 answered on 2026-09-24 that
scraping is fine, done the way our letter described. So this scraper exists for
茨城, and a config for any other DB-Search tenant needs its own answer first.

The route, all GET, verified on 茨城 on 2026-09-29 (`scripts/probe_ibaraki_part.py`):

    ?Template=search-library                 年別の会議録閲覧: every 定例会 and every
                                             committee-year as a list link (483)
    <list link>&Part=3                       the same list, 本文 only (63 -> 21 件)
    <list link>&Part=3&Page=N                10 to a page
    /100000?Template=document&Id=N           one sitting, every speech numbered

Three things the probe and the cache settled:

* **`Id` is the document; the number before `?` is a session.** `Id=10978` under
  `/669261` and `/100000` is the same text, while `Id=0` means "whatever this
  session last showed". Records point at `/100000?…&Id=N` and nothing else.
* **The listing is filtered to 本文.** Each sitting is also a 議事日程, a 名簿 and
  sometimes a 質疑通告一覧表. `Part=3` is the search form's own field, so the
  server does the filtering and a quarter of the requests are made.
* **The page is the download.** `importer.page_to_download` rebuilds the text the
  ダウンロード button saves, and `importer.parse_document` — written for 山梨 — reads it.
  One parser for both routes, so a fix found on one tenant reaches the other.

Every list states its count (「21 件」); the documents collected from its pages
are counted against it, and a shortfall is reported rather than trusted.
"""

from __future__ import annotations

import logging
import math
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from prefectural_transcripts.config import Contact, FetchWindow, Notice, RobotsExemption
from prefectural_transcripts.http import Page, PoliteClient

# The module, not its names: the importer uses `scrapers.generic`, so importing
# its functions here would be circular while the package is still loading.
from prefectural_transcripts.importers import dbsearch as importer
from prefectural_transcripts.models import Meeting, MeetingRef
from prefectural_transcripts.scrapers.base import BaseScraper

log = logging.getLogger(__name__)

PER_PAGE = 10
_COUNT = re.compile(r"(\d+)\s*件")
_ID = re.compile(r"[?&]Id=(\d+)")


@dataclass(slots=True)
class DbSearchConfig:
    """Mirrors `sites/<name>.toml` for this scraper."""

    prefecture: str
    base_url: str
    """`https://<tenant>.dbsr.jp/100000` — the default session, used for every URL."""
    name: str = ""
    part: str = "3"
    """The search form's 文書種別 value for 本文."""
    robots_exempt: RobotsExemption | None = None
    fetch_window: FetchWindow | None = None
    contact: Contact | None = None
    notice: Notice | None = None

    @classmethod
    def from_toml(cls, path: Path) -> DbSearchConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        opts = dict(raw.get("dbsearch", {}))
        try:
            return cls(
                prefecture=raw["prefecture"],
                name=raw.get("name", path.stem),
                base_url=opts.pop("base_url"),
                **opts,
                robots_exempt=RobotsExemption.from_toml(raw.get("robots", {})),
                fetch_window=FetchWindow.from_toml(raw.get("fetch_window", {})),
                contact=Contact.from_toml(raw.get("contact", {})),
                notice=Notice.from_toml(raw.get("notice", {})),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid site config {path}: {exc}") from exc


def list_links(library_html: str, base_url: str) -> list[str]:
    """Every result-list link on 年別の会議録閲覧, in page order, once each."""
    soup = BeautifulSoup(library_html, "lxml")
    out: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, str(a["href"]))
        if "Template=list" in url and "QueryType=new" in url:
            out[url] = None
    return list(out)


def stated_count(list_html: str) -> int | None:
    """The 「N 件」 a result list says it holds."""
    m = _COUNT.search(BeautifulSoup(list_html, "lxml").get_text(" ", strip=True))
    return int(m.group(1)) if m else None


def documents(list_html: str) -> list[tuple[str, str]]:
    """(Id, label) for each document on one page of a result list."""
    soup = BeautifulSoup(list_html, "lxml")
    out: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        m = _ID.search(href)
        if "Template=document" in href and m and m.group(1) != "0":
            out.setdefault(m.group(1), a.get_text(" ", strip=True))
    return list(out.items())


class DbSearchScraper(BaseScraper):
    """One DB-Search tenant whose assembly has permitted fetching."""

    def __init__(self, config: DbSearchConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture
        self.robots_exempt = config.robots_exempt
        self.fetch_window = config.fetch_window
        self.contact = config.contact
        self.notice = config.notice
        self._short: list[str] = []
        self._not_honbun: list[str] = []
        self._unattributed = 0
        self._trimmed = 0

    def url_prefixes(self) -> list[str]:
        return [self.config.base_url + "?"]

    def document_url(self, doc_id: str) -> str:
        return f"{self.config.base_url}?Template=document&Id={doc_id}"

    # -- listing ---------------------------------------------------------------

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        library = client.get(f"{self.config.base_url}?Template=search-library")
        lists = list_links(library.text, library.url)
        log.info("%d result lists on 年別の会議録閲覧", len(lists))
        seen: set[str] = set()
        for url in lists:
            filtered = f"{url}&Part={self.config.part}"
            first = client.get(filtered)
            count = stated_count(first.text)
            found = documents(first.text)
            pages = math.ceil(count / PER_PAGE) if count else 1
            for n in range(2, pages + 1):
                found += documents(client.get(f"{filtered}&Page={n}").text)
            ids = {doc_id for doc_id, _ in found}
            if count is not None and len(ids) != count:
                self._short.append(f"{filtered}: states {count} 件, listed {len(ids)}")
                log.warning("%s: states %s 件, listed %d", filtered, count, len(ids))
            for doc_id, label in found:
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                if not label.endswith("本文"):
                    # The filter is the server's; if it lets something else
                    # through, say so rather than parse a 名簿 as a sitting.
                    self._not_honbun.append(f"Id={doc_id} {label}")
                    continue
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=self.document_url(doc_id),  # type: ignore[arg-type]
                    title=label,
                )

    # -- detail ----------------------------------------------------------------

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        result = importer.parse_document(
            importer.page_to_download(page.text),
            prefecture=self.prefecture,
            source_file=str(ref.url),
        )
        if result.meeting is None:
            raise ValueError(f"{ref.url} is a {result.header.kind}, not a 本文")
        self._unattributed += len(result.unattributed)
        self._trimmed += result.trimmed
        for line in result.unattributed:
            log.debug("unattributed: %s", line)
        return result.meeting.model_copy(
            update={
                "url": ref.url,
                "source_file": None,
                "source_html_sha256": page.sha256,
            }
        )

    def report(self) -> list[str]:
        out = [
            f"{self._unattributed} speech(es) with no speaker (headers such as 開議 are expected)",
            f"{self._trimmed} block(s) cut at a 罫線",
        ]
        if self._short:
            out.append(f"{len(self._short)} list(s) whose pages did not add up to their 件:")
            out += [f"  {s}" for s in self._short]
        if self._not_honbun:
            out.append(f"{len(self._not_honbun)} non-本文 document(s) the filter let through:")
            out += [f"  {s}" for s in self._not_honbun[:20]]
        return out
