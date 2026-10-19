"""Scraper for 鳥取県議会's committee minutes on とりネット (`www.pref.tottori.lg.jp`).

Not a vendor product: とりネット is the prefecture's own website, run by its
広報課, and the committee minutes are ordinary pages on it. 本会議 is not here —
it arrives as files from the secretariat (`importers/tottori.py`). See
`docs/tottori.md`.

Why a scraper and not selectors: two things a config cannot say.

**The walk is bounded by link text, not by URL.** とりネット is every page the
prefecture has, so no URL prefix bounds anything, and 広報課 (2026-10-05)
excluded five navigation pages *that the index links to*. So the walk is three
levels, each chosen by what the link says — 「…年度委員会会議録…」 on the index,
a committee on a year page, a 会議録 on a committee page — and the five URLs are
refused by name besides (`EXCLUDED`), the way they wrote them.

**A day can be published twice.** Some committees publish a 速報版 and later a
確定版 of the same sitting, as two pages. The researcher decided on 2026-10-13:
確定版 first, a 速報版 only where that committee has no 確定版 for the same
label. Pairing needs the whole of one committee's list, which may run over
several pages (「次のページへ」), so it is decided after the list is read.

Also not minutes, and listed beside them: 「…・所管事項に係る県内調査」 and
「…県外調査」, a committee's visit reports. Their ○ lines are places visited, not
speakers, so they are skipped and counted.
"""

from __future__ import annotations

import logging
import re
import tomllib
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from prefectural_transcripts.config import Contact, FetchWindow, Notice, RobotsExemption
from prefectural_transcripts.dates import parse_japanese_date
from prefectural_transcripts.http import Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef
from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import split_speeches

log = logging.getLogger(__name__)

EXCLUDED = re.compile(
    # 「一覧ページ（/88112.htm）からリンクしていても対象外とするURL」 (広報課情報センター,
    # 2026-10-05): ホーム, 議会の動き, 議会・議員, 開かれた議会, 議会その他.
    r"^https?://www\.pref\.tottori\.lg\.jp/(?:gikai/?|87615\.htm|87659\.htm|87660\.htm|87662\.htm)$"
)

_YEAR = re.compile(r"年度委員会会議録")
_COMMITTEE = re.compile(r"委員会|協議会")
_ITEM = re.compile(r"/item/\d+\.htm$")
_NEXT = "次のページへ"
_MAX_LIST_PAGES = 30
"""Pages of one committee's list. 令和4年度 総務教育 runs to two at 15 a page;
a loop in the pagination should stop, not walk."""

# 「令和4年10月3日会議録（確定版）」「平成22年6月1日（予備調査）会議録」「平成27年2月13日議事録」
# — and before 平成20 the minutes carry no 会議録 at all: 「平成19年3月8日(木)（開会中）」.
_MINUTE = re.compile(
    r"会議録|議事録|^(?:平成|令和)[0-9０-９元]{1,2}年[0-9０-９]{1,2}月[0-9０-９]{1,2}"
)
# A visit, not a sitting: 「平成22年8月25日～26日・所管事項に係る県内調査」, and the
# 平成18 shape 「平成18年10月16日（月）～18日(水)」, which is the same multi-day trip.
_VISIT = re.compile(r"(?:県内|県外)調査|～")
_EDITION = re.compile(r"\s*[（(](確定版|速報版)[）)]\s*")

DEFAULT_SPEECH_SPLIT = r"(?m)^[◎●○◯〇](?P<speaker>[^\n。、]{1,60})$"
"""◎ the chair, ● the executive, ○ a member — alone on the line, the speech on
the next. Checked over the 113 minutes cached by the surveys of 2026-10-10..18
(平成22〜令和8): every marker line is a name and office and nothing else, except
in the 県内・県外調査 pages, which are not minutes and are not parsed. ◯ (U+25EF)
stands in for ○ in a few 令和 sittings, as it does in 山梨. A line with 。 or 、
is speech that happens to open with a circle — 「●　　の調整範囲が●　　。」."""


def _pairing(label: str) -> str:
    """A label without its edition, for pairing a 速報版 with its 確定版. NFKC,
    because the same committee types 「平成31年２月13日」 on one and 「2月13日」
    on the other."""
    return unicodedata.normalize("NFKC", _EDITION.sub("", label)).replace(" ", "")


def _canonical(url: str) -> str:
    """https, no fragment — the surveys cached both schemes for the same page."""
    split = urlsplit(url)
    return urlunsplit(("https", split.netloc, split.path, split.query, ""))


def _middle(html: str) -> Tag | BeautifulSoup:
    """The page's own content. The header carries a breadcrumb back to every
    level above, and following it would be walking the site, not the minutes."""
    soup = BeautifulSoup(html, "lxml")
    return soup.select_one("#Middle") or soup


@dataclass(slots=True)
class Listed:
    committee: str
    year: str
    label: str
    edition: str | None  # 確定版, 速報版, or neither


@dataclass(slots=True)
class TottoriConfig:
    """Mirrors `sites/tottori_committee.toml`."""

    prefecture: str
    index_url: str
    name: str = ""
    speech_split: str = DEFAULT_SPEECH_SPLIT
    robots_exempt: RobotsExemption | None = None
    fetch_window: FetchWindow | None = None
    contact: Contact | None = None
    notice: Notice | None = None

    @classmethod
    def from_toml(cls, path: Path) -> TottoriConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        opts = dict(raw.get("tottori", {}))
        try:
            return cls(
                prefecture=raw["prefecture"],
                name=raw.get("name", path.stem),
                index_url=opts.pop("index_url"),
                **opts,
                robots_exempt=RobotsExemption.from_toml(raw.get("robots", {})),
                fetch_window=FetchWindow.from_toml(raw.get("fetch_window", {})),
                contact=Contact.from_toml(raw.get("contact", {})),
                notice=Notice.from_toml(raw.get("notice", {})),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid site config {path}: {exc}") from exc


class TottoriCommitteeScraper(BaseScraper):
    """鳥取県議会 委員会, 平成18年度 onward, from とりネット."""

    def __init__(self, config: TottoriConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture
        self.robots_exempt = config.robots_exempt
        self.fetch_window = config.fetch_window
        self.contact = config.contact
        self.notice = config.notice
        self._listed: dict[str, Listed] = {}
        self._visits: list[str] = []
        self._other: list[str] = []
        self._superseded: list[str] = []
        self._kept_preliminary: list[str] = []
        self._twice: list[str] = []
        self._empty_committees: list[str] = []
        self._undated: list[str] = []
        self._date_mismatch: list[str] = []

    def url_prefixes(self) -> list[str]:
        return ["https://www.pref.tottori.lg.jp/item/"]

    # -- listing ---------------------------------------------------------------

    def _get(self, client: PoliteClient, url: str) -> Page:
        if EXCLUDED.match(url):
            # Unreachable by the walk, which follows link text; if it is ever
            # reached, the walk is wrong and should stop rather than ask.
            raise RuntimeError(f"{url} is excluded by 広報課 (2026-10-05)")
        return client.get(url)

    def _links(self, page: Page) -> list[tuple[str, str]]:
        return [
            (a.get_text(" ", strip=True), _canonical(urljoin(page.url, str(a["href"]))))
            for a in _middle(page.text).find_all("a", href=True)
        ]

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        index = self._get(client, self.config.index_url)
        years = list(dict.fromkeys((t, u) for t, u in self._links(index) if _YEAR.search(t)))
        log.info("%d 年度 on the index", len(years))
        for year, year_url in years:
            page = self._get(client, year_url)
            committees = [
                (t, u) for t, u in self._links(page) if _COMMITTEE.search(t) and not _ITEM.search(u)
            ]
            for committee, committee_url in committees:
                yield from self._committee(client, year, committee, committee_url)

    def _committee(
        self, client: PoliteClient, year: str, committee: str, url: str
    ) -> Iterator[MeetingRef]:
        items: list[tuple[str, str]] = []
        seen_pages = {url}
        next_url: str | None = url
        while next_url and len(seen_pages) <= _MAX_LIST_PAGES:
            page = self._get(client, next_url)
            links = self._links(page)
            items += [(t, u) for t, u in links if _ITEM.search(u)]
            following = [u for t, u in links if t == _NEXT and u not in seen_pages]
            next_url = following[0] if following else None
            if next_url:
                seen_pages.add(next_url)
        if not items:
            self._empty_committees.append(f"{year} {committee} {url}")
            log.warning("%s %s: no minute listed (%s)", year, committee, url)

        minutes: list[tuple[str, str, str | None]] = []
        for label, item_url in dict.fromkeys(items):
            if _VISIT.search(label) and not re.search(r"会議録|議事録", label):
                self._visits.append(f"{item_url} {committee} {label}")
                continue
            if not _MINUTE.search(label):
                self._other.append(f"{item_url} {committee} {label}")
                continue
            m = _EDITION.search(label)
            minutes.append((label, item_url, m.group(1) if m else None))

        # 確定版 first: a 速報版 is dropped when the same committee lists a 確定版
        # under the same label. 「平成30年6月14日（１）」 and 「（２）」 are two
        # sittings, so the label, not the date, is the key.
        final = {_pairing(label) for label, _, ed in minutes if ed == "確定版"}
        for label, item_url, edition in minutes:
            if edition == "速報版":
                if _pairing(label) in final:
                    self._superseded.append(f"{item_url} {committee} {label}")
                    continue
                self._kept_preliminary.append(f"{item_url} {committee} {label}")
            if item_url in self._listed:
                self._twice.append(f"{item_url} {committee} {label}")
                continue
            self._listed[item_url] = Listed(committee, year, label, edition)
            yield MeetingRef(
                prefecture=self.prefecture,
                url=item_url,  # type: ignore[arg-type]
                title=f"{committee} {label}",
                date=parse_japanese_date(label),
            )

    def prepare(self, client: PoliteClient) -> None:
        """A re-parse needs the committee of each page, which only the list knows."""
        if not self._listed:
            for _ in self.list_meetings(client):
                pass

    # -- detail ----------------------------------------------------------------

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        listed = self._listed.get(str(ref.url))
        soup = BeautifulSoup(page.text, "lxml")
        heading = soup.title.get_text().split("/")[0].strip() if soup.title else ""
        text = _middle(page.text).get_text("\n", strip=True)

        label = listed.label if listed else heading
        when = parse_japanese_date(label)
        printed = parse_japanese_date(heading)
        if when is None:
            # 「平成19年3月6(火)」 — the list dropped a 日; the page's own title is next.
            when = printed
        if when is None:
            self._undated.append(f"{ref.url} {label}")
        elif printed and printed != when:
            self._date_mismatch.append(f"{ref.url}: list {label}, page {heading}")

        return Meeting(
            prefecture=self.prefecture,
            url=ref.url,
            date=when,
            committee=listed.committee if listed else None,
            title=label,
            speeches=split_speeches(text, self.config.speech_split),
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )

    def report(self) -> list[str]:
        out = []
        for what, rows in (
            ("visit report(s) (県内・県外調査) listed and skipped", self._visits),
            ("listed item(s) that are neither minutes nor visits, skipped", self._other),
            ("速報版 superseded by a 確定版 of the same label, skipped", self._superseded),
            ("速報版 kept — no 確定版 yet; replace when one appears", self._kept_preliminary),
            ("page(s) listed under more than one committee, kept once", self._twice),
            ("committee page(s) listing no minute", self._empty_committees),
            ("minute(s) with no date in the list or the page", self._undated),
            ("date(s) where the list and the page disagree", self._date_mismatch),
        ):
            out.append(f"{len(rows)} {what}")
            if what.startswith(("速報版 kept", "committee", "minute(s)", "date(s)", "listed")):
                out += [f"  {r}" for r in rows]
        return out
