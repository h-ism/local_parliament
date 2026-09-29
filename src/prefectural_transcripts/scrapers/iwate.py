"""Scraper for 岩手県議会's own 会議録 server (`www3.pref.iwate.jp/gikai/user/www/`).

Not a vendor product, and not the VOICES install the letter named: the
assembly's 「本会議会議録」 link leaves `iwatekengikai.gijiroku.com` for this
prefectural server, which is where the minutes actually are. See
`docs/iwate-ibaraki-tochigi.md`.

The pages are plain server-rendered HTML with plain hrefs. The reason this is a
scraper and not a config is one thing selectors cannot say:

**A sitting is several pages.** Each page is a range of the server's paragraph
ids, `Zenbun/page/<目次>/<first>/<last>`, and the 目次 links them in order:

    第２号（10月４日）   page/2/376282/376296   <- 開議 up to 「〔32番佐々木博君登壇〕」
    佐々木（博）議員     page/2/376297/376314   <- the question itself
    柳村議員             page/2/376315/376331
    亀卦川議員           page/2/376332/376347
    第３号（10月５日）   page/2/376348/376362   <- the next sitting

The member links are not slices of the 第２号 page (as 和歌山's are of its
whole-sitting page) — they are the *rest* of it. The first page stops mid-
sitting, and only it carries the date. One record per page would give a corpus
where most 一般質問 are undated fragments with no 開議 and no 散会. So a sitting
is every page link from one 第N号 up to the next, fetched in order and joined:
the same number of requests as one record per page, just one record.

The ranges make that checkable: they are contiguous (`last + 1 == next first`)
all through a sitting. A gap is a page the 目次 does not link, which would lose
text without a sound, so it is counted and reported rather than trusted.

Committees (予算・決算特別委員会) are the same shape with one page per sitting,
and verbatim — 会議録, in the first person — so they are in scope.
"""

from __future__ import annotations

import logging
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from prefectural_transcripts.config import Contact, FetchWindow, Notice, RobotsExemption
from prefectural_transcripts.dates import parse_japanese_date
from prefectural_transcripts.http import Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef
from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import split_speeches

log = logging.getLogger(__name__)

_MOKUJI = re.compile(r"/Zenbun/mokuji/\d+$")
_PAGE = re.compile(r"/Zenbun/page/(\d+)/(\d+)/(\d+)$")

# 「第２号（10月４日）」 on 本会議, 「第１号　　３月４日（水）」 on committees.
_SITTING = re.compile(r"^第[０-９0-9]+号")
_MONTH_DAY = re.compile(r"([０-９0-9]{1,2})月\s*([０-９0-9]{1,2})日")

# The first date on a sitting's first page is the sitting's own:
# 「第３回岩手県議会定例会会議録（第２号）|平成19年10月４日（木曜日）」 or, on a
# committee, the very first line 「令和８年３月４日（水）」.
_DATE = re.compile(
    r"((?:令和|平成|昭和)[０-９0-9元]{1,3}年\s*[０-９0-9]{1,2}月\s*[０-９0-9]{1,2}日)"
    r"\s*（[日月火水木金土]"
)

DEFAULT_SPEECH_SPLIT = (
    # 本会議: 「〇議長（渡辺幸貫君）　」「〇27番（大宮惇幸君）　」 — and 令和3年 writes
    # 「〇議長（関根敏伸君）これより…」 with no space after the bracket, which a
    # required space lost five whole sittings to on the first night. The bracket
    # closes the marker by itself, so the space is optional there; 「君」 before
    # the bracket is what keeps 「〇七年度の予算（案）」 out instead.
    #
    # Three more from the first night's 1,895 pages: some sittings use ○ (U+25CB)
    # rather than 〇 (U+3007); one writes 「〇2番(畠山茂君)」 in half-width brackets;
    # and a committee marker may stand alone on its line with the speech on the
    # next. The role may still contain a half-width bracket (兵庫's 「参事(園芸・
    # 公園担当)兼公園緑地課長（…）」) because it is matched lazily up to the one
    # that closes on 「君」.
    #
    # 「〇高田一郎委員（続）」 is a speaker resuming after an interruption (166 on
    # the first night): without its own branch the bracket reads as a person
    # named 「続」. And two sittings print 「〇２番（畠山茂君　」 with the closing
    # bracket missing — 「君」 and a space end the marker as surely as 「）」 does.
    r"(?m)^[〇○](?:(?P<speaker3>[^（(\n　]{1,60}?)[（(]続[）)]　?"
    r"|(?P<role>[^（\n　]{1,60}?)[（(](?P<speaker>[^）)\n　]{1,30})"
    r"(?:[）)](?:　|(?<=君[）)]))|(?<=君)　)"
    # 委員会: 「〇佐々木朋和委員長　」「〇菊池（雄）委員　」 — name and office run
    # together, and the longest seen is a 36-character office.
    r"|(?P<speaker2>[^　\n、。「」]{1,60}?)(?:　|$))"
)
"""Every speech opens a line with 〇 (U+3007) and ends its marker with a
full-width space or the bracket. First counted over the 56 reconnaissance pages (1995-2026, both
kinds of sitting): 7,493 speeches, 0 〇-lines unmatched, 0 swallowed."""


def _digits(s: str) -> int:
    return int(s.translate(str.maketrans("０１２３４５６７８９", "0123456789")))


@dataclass(slots=True)
class Sitting:
    """One sitting as the 目次 lists it: its label and every page, in order."""

    label: str
    pages: list[str] = field(default_factory=list)
    gaps: int = 0


def sittings_on(mokuji_html: str, base_url: str) -> tuple[str, list[Sitting], list[str]]:
    """Read one 目次: its heading, its sittings, and any page link before the first.

    The heading is the first cell — 「令和8年2月定例会　予算特別委員会会議記録」.
    Page links that come before any 第N号 cannot be placed in a sitting; they are
    returned rather than dropped so the caller can say so.
    """
    soup = BeautifulSoup(mokuji_html, "lxml")
    cell = soup.find("td")
    heading = cell.get_text(" ", strip=True) if isinstance(cell, Tag) else ""
    out: list[Sitting] = []
    orphans: list[str] = []
    for link in soup.find_all("a", href=True):
        url = urljoin(base_url, str(link["href"]))
        if not _PAGE.search(url):
            continue  # 附録 (日程, 議案, 報告) and navigation
        label = link.get_text(" ", strip=True)
        if _SITTING.match(label):
            out.append(Sitting(label=label))
        if not out:
            orphans.append(url)
            continue
        out[-1].pages.append(url)
    for sitting in out:
        ranges = [tuple(int(x) for x in _PAGE.search(u).groups()[1:]) for u in sitting.pages]  # type: ignore[union-attr]
        sitting.gaps = sum(1 for a, b in zip(ranges, ranges[1:], strict=False) if a[1] + 1 != b[0])
    return heading, out, orphans


def split_heading(heading: str) -> tuple[str | None, str | None]:
    """「令和8年2月定例会　予算特別委員会会議記録」 -> (session, committee).

    The 本会議 heading names the assembly instead — 「第３回岩手県議会定例会会議録」
    — and has no committee.
    """
    session, _, rest = heading.replace("　", " ").partition(" ")
    rest = rest.strip()
    committee = None
    if "委員会" in rest and "県議会" not in rest:
        committee = re.sub(r"会議(?:記)?録$", "", rest).strip() or None
    return (session.strip() or None), committee


@dataclass(slots=True)
class IwateConfig:
    """Mirrors `sites/iwate.toml`."""

    prefecture: str
    index_url: str
    name: str = ""
    speech_split: str = DEFAULT_SPEECH_SPLIT
    robots_exempt: RobotsExemption | None = None
    fetch_window: FetchWindow | None = None
    contact: Contact | None = None
    notice: Notice | None = None

    @classmethod
    def from_toml(cls, path: Path) -> IwateConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        opts = dict(raw.get("iwate", {}))
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


class IwateScraper(BaseScraper):
    """岩手県議会 本会議 and 予算・決算特別委員会, 平成7年 onward."""

    def __init__(self, config: IwateConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture
        self.robots_exempt = config.robots_exempt
        self.fetch_window = config.fetch_window
        self.contact = config.contact
        self.notice = config.notice
        self._parts: dict[str, Sitting] = {}
        self._heading: dict[str, str] = {}
        self._gaps: list[str] = []
        self._orphans: list[str] = []
        self._date_mismatch: list[str] = []

    def url_prefixes(self) -> list[str]:
        return [urljoin(self.config.index_url, "./")]

    # -- listing ---------------------------------------------------------------

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        index = client.get(self.config.index_url)
        soup = BeautifulSoup(index.text, "lxml")
        mokuji = list(
            dict.fromkeys(
                urljoin(index.url, str(a["href"]))
                for a in soup.find_all("a", href=True)
                if _MOKUJI.search(urljoin(index.url, str(a["href"])))
            )
        )
        log.info("%d 目次 on the index", len(mokuji))
        for url in mokuji:
            page = client.get(url)
            heading, sittings, orphans = sittings_on(page.text, page.url)
            if orphans:
                self._orphans.append(f"{url}: {len(orphans)} page(s) before the first 第N号")
                log.warning(
                    "%s: %d page link(s) before any 第N号, not collected", url, len(orphans)
                )
            if not sittings:
                log.warning("%s (%s): no 第N号 at all", url, heading)
            for sitting in sittings:
                first = sitting.pages[0]
                self._parts[first] = sitting
                self._heading[first] = heading
                if sitting.gaps:
                    self._gaps.append(f"{first} {heading} {sitting.label}: {sitting.gaps} gap(s)")
                    log.warning("%s %s: page ranges not contiguous", heading, sitting.label)
                session, _ = split_heading(heading)
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=first,  # type: ignore[arg-type]
                    title=f"{session or heading} {sitting.label}",
                )

    def prepare(self, client: PoliteClient) -> None:
        """A re-parse needs the page list, which only the 目次 knows."""
        if not self._parts:
            for _ in self.list_meetings(client):
                pass

    # -- fetching --------------------------------------------------------------

    def fetch_meeting(self, ref: MeetingRef, client: PoliteClient) -> Page:
        """Every page of the sitting, in the 目次's order, as one body."""
        sitting = self._parts.get(str(ref.url))
        urls = sitting.pages if sitting else [str(ref.url)]
        pages = [client.get(u) for u in urls]
        parts: list[str] = []
        for page in pages:
            soup = BeautifulSoup(page.text, "lxml")
            body = soup.select_one("div[style]")
            parts.append(str(body) if body else "")
        return Page(
            url=str(ref.url),
            status=200,
            body="\n".join(parts).encode("utf-8"),
            encoding="utf-8",
            fetched_at=datetime.now(UTC),
            from_cache=all(p.from_cache for p in pages),
        )

    # -- detail ----------------------------------------------------------------

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        text = BeautifulSoup(page.text, "lxml").get_text("\n", strip=True)
        heading = self._heading.get(str(ref.url), "")
        session, committee = split_heading(heading)
        sitting = self._parts.get(str(ref.url))

        m = _DATE.search(text[:400])
        when = parse_japanese_date(m.group(1)) if m else None
        # The 目次 label carries the month and day too; a disagreement means one
        # of the two is not what it looks like, so it is counted.
        label_md = _MONTH_DAY.search(sitting.label) if sitting else None
        if (
            when
            and label_md
            and (when.month, when.day)
            != (
                _digits(label_md.group(1)),
                _digits(label_md.group(2)),
            )
        ):
            self._date_mismatch.append(f"{ref.url}: page {when}, 目次 {sitting.label}")  # type: ignore[union-attr]

        return Meeting(
            prefecture=self.prefecture,
            url=ref.url,
            date=when,
            session=session,
            committee=committee,
            title=f"{heading} {sitting.label}".strip() if sitting else ref.title,
            speeches=split_speeches(text, self.config.speech_split),
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )

    def report(self) -> list[str]:
        out = []
        if self._gaps:
            out.append(f"{len(self._gaps)} sitting(s) with non-contiguous page ranges:")
            out += [f"  {g}" for g in self._gaps]
        if self._orphans:
            out.append(f"{len(self._orphans)} 目次 with pages before the first 第N号:")
            out += [f"  {o}" for o in self._orphans]
        if self._date_mismatch:
            out.append(f"{len(self._date_mismatch)} date(s) disagreeing with the 目次:")
            out += [f"  {d}" for d in self._date_mismatch]
        return out
