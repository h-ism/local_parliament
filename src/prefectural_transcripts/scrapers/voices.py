"""Scraper for gijiroku VOICES (`/voices/cgi/voiweb.exe`) — 滋賀, 石川 and 栃木.

Worked out on 2026-10-13 from the reconnaissance cache of 2026-10-10/11, offline:
375 + 359 pages, 107 sittings with both their speech list and their text.

Every page a reader sees is a frame, and the survey that followed only `<a href>`
cached 270 wrappers and no sitting (`docs/shiga.md`). The route, link by link:

    g08v_viewh.asp                      the 本会議 index: one link per year
      g08v_viewh.asp?Sflg=11&FYY=2020   a wrapper whose <iframe> is …
        voiweb.exe?ACT=100&…            the year's list: one row per document,
                                        opened by onClick="winopen('…ACT=200…')"
          voiweb.exe?ACT=200&…          a frameset; its frame NAME="hat" is …
            voiweb.exe?ACT=203&…        **the whole sitting**, one page

`ACT=203` is named after one speech (`HUID=`) and scrolls to it, but it carries
every speech of the document, each opened by `<A NAME="HUID…"></A>`. Checked on
all 107 cached pairs: the anchors on the 203 page are exactly the checkboxes of
the speech list (`ACT=202`), 107 of 107. So a sitting is two requests, and the
speech boundaries are the vendor's own — the 山梨 lesson, *where the vendor
numbers the speeches, take the numbering*: a marker this cannot read costs a
name, which is counted, never the words.

What a block is, by its first character:

* block 0 — the front matter (title, 議事日程, rosters). Not a speech.
* 「△」 — an agenda heading, 「△諸般の報告」. Not a speech; counted.
* 「○」 chair, 「◆」 member, 「◎」 executive or reporting chair — a speech.
* anything else — kept as a speech with no speaker, and counted.

The 「目次」 documents are listed beside the sittings and are skipped by label.

**栃木 (2026-10-25, from the survey of 10/24)** is the same product with three
differences, each of which failed quietly until looked for:

* Its index is by **fiscal year** (`FYY=2015&FMM=4&TYY=2016&TMM=3`), and the
  list shows **one calendar year per page** — the other is behind a `YEAR=`
  link in the year bar. Reading only the first page read 7 of FY2015's 20.
* Its session titles carry **no month** — 「平成２１年第３００回（第４号）定例会」,
  「令和　７年度栃木県議会第４０９回通常会議」 — so the year comes from the list
  page instead: the year bar's one entry that is not a link.
* Its officials are marked 「○関谷暢之　議長　ただいまから…」 — name, office, each
  closed by a full-width space — beside the 「◆50番（螺良昭人議員）」 滋賀 also uses.

**The committee side is not configured yet.** Both sites publish committees as
会議要録 / 会議記録 whose body is 「議事の経過概要」 — first person, but condensed
by the secretariat. Decided 2026-10-15: kept, as summary (`models.Kind`), not as
speech. What is missing is a rule: committee markers are 「◆重田剛　委員」 and
「◎橋本　財政課長」, which `_MARKER` reads on none of the ~20 cached committee
sittings, and those are one committee-year on 石川 and one session on 滋賀 — too
narrow to write a rule from. See `docs/shiga.md`.
"""

from __future__ import annotations

import html
import logging
import re
import tomllib
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from prefectural_transcripts.config import Contact, FetchWindow, Notice, RobotsExemption
from prefectural_transcripts.dates import kanji_to_int, parse_japanese_date
from prefectural_transcripts.http import FetchError, Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef, Speech
from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import _clean_speaker

log = logging.getLogger(__name__)

# A year on the index: 「令和8年」, 「平成31年・ 令和元年」, 「平成 3年」. 石川 lists
# 定例会 (`Sflg=11`) and 臨時会 (`Sflg=21`) as two sets of years and 滋賀 one —
# so the rule is "every year link", not a named kind of session. Naming the
# kinds you want is how 兵庫 lost 「第198回定 」.
_YEAR_LINK = re.compile(r"[?&]Sflg=\d+&FYY=\d{4}")
_YEAR_TEXT = re.compile(r"(?:令和|平成|昭和)\s*[元0-9０-９]{1,2}\s*年")

_WINOPEN = re.compile(r"winopen\('([^']*ACT=200[^']*)'\)")
_HITS = re.compile(r"(\d+)件の日程がヒット")
_PAGE_LINK = re.compile(r"[?&]PAGE=\d+")
_YEAR_PAGE = re.compile(r"[?&]YEAR=(\d{4})")
# The year bar above a list: 「平成　28年 <A …YEAR=2015>平成　27年</A>」 — the year
# shown is the one that is not a link.
_BAR_YEAR = re.compile(r"(令和|平成|昭和)\s*([元0-9０-９]{1,2})\s*年")
_ANCHOR = re.compile(r'<A NAME="HUID(\d+)"></A>', re.I)

# 「11月27日-01号」, 「05月28日-目次」 — the vendor's label for the document.
_LABEL = re.compile(r"^(\d{1,2})月(\d{1,2})日-(.+)$")
# 「令和　２年１１月定例会議（第17号～第23号）」「平成　４年　２月第　１回定例会」
_SESSION = re.compile(r"^(令和|平成|昭和)\s*([元0-9０-９]{1,2})\s*年\s*([0-9０-９]{1,2})\s*月")
_SESSION_RANGE = re.compile(r"[（(]第[0-9０-９]+号(?:[～~〜][^）)]*)?[）)]\s*$")

# The printed date, used only as a check. 滋賀 prints 「令和２年12月10日（木曜日）」;
# 石川 prints 「三月四日（水曜日）」 with no year — and from 平成28年 on, sometimes
# the full 「平成二十八年二月二十六日（金曜日）」 on the first sitting of a session.
_PRINTED_FULL = re.compile(
    r"((?:令和|平成|昭和)[元0-9０-９〇一二三四五六七八九十]{1,4}年"
    r"[0-9０-９〇一二三四五六七八九十]{1,3}月[0-9０-９〇一二三四五六七八九十]{1,3}日)\s*（"
)
_PRINTED_MD = re.compile(r"^([〇一二三四五六七八九十]{1,3})月([〇一二三四五六七八九十]{1,3})日（")
# 栃木 prints 「６月４日（木曜日）」, in full-width figures.
_PRINTED_MD_FIG = re.compile(r"^([0-9０-９]{1,2})月([0-9０-９]{1,2})日（")

# 「○議長（細江正人）　」「◆11番（黄野瀬明子議員）　」「◎知事（三日月大造）　」
# 「◎20番（総務企画常任委員長黒川治君）」 — 滋賀, every era.
# 「○議長（福村章君）」「◆北村茂男君　」「◆（櫻井廣明君）」「◎矢田富郎君　」 — 石川.
#
# The role class excludes only the full-width brackets, which are the marker's own
# (兵庫: an office can carry half-width ones). Every branch stops at a full-width
# space or the end of the line, so none can read on into the speech — the
# 和歌山 greedy-speaker failure. The bare-name branch needs an honorific for the
# same reason: without one, 「◆北村茂男君」 and 「◆ただいま議題となりました」 look alike.
_MARKER = re.compile(
    r"^[○◎◆]"
    r"(?:"
    r"(?P<role>[^（）　\s]{1,60}?)（(?P<name>[^（）]{1,60})）"
    r"|（(?P<name0>[^（）]{1,40})）"
    r"|(?P<name2>[^（）　\s、。，「」]{1,20}?(?:君|さん|氏|議員))(?=[　\s]|$)"
    # 栃木: 「○関谷暢之　議長　」「◎福田富一　知事　」 — the name and the office each
    # closed by a full-width space (or the line's end). Last, so it can only read a
    # line every branch above has already declined.
    r"|(?P<name3>[^（）　\s、。，「」]{2,12})　(?P<office3>[^（）　\s、。，「」]{1,30})(?=　|$)"
    r")"
)
# 「総務企画常任委員長黒川治君」: a chair reporting, office and name in one bracket.
# Split at the last 委員長 so the speaker is the person, not 「総務企画常任委員長黒川治」
# — a speaker made of an office is the 兵庫 failure.
_OFFICE_IN_NAME = re.compile(r"^(?P<office>.+委員長)(?P<name>[^委]{2,12})$")
# Recent 滋賀 writes the same thing the other way round, name first and the office
# in square brackets inside the round ones: 「◎20番（目片信悟議員［総務・企画常任委員長］）」.
_NAME_THEN_OFFICE = re.compile(r"^(?P<name>[^［\[]+)[［\[](?P<office>[^］\]]+)[］\]]$")
# 滋賀 writes members 「（黄野瀬明子議員）」 in recent years and 「（野村政夫君）」 before;
# without this one member is two speakers along a line that is only the year.
_GIIN = re.compile(r"議員$")
# 栃木 reports a committee as 「○県政経営委員会　岩崎信委員長　」: the committee
# where the name goes, the chair's name inside the office. Read as written, the
# speaker would be a committee.
_COMMITTEE_FIRST = re.compile(r"^(?P<office>.+委員会)$")
_CHAIR_NAMED = re.compile(r"^(?P<name>[^委]{2,12})委員長$")
# 「○○議会議長○○」 is a form's placeholder printed in a 栃木 sitting, not a name.
_NOT_A_NAME = re.compile(r"^[0-9０-９]|^[0-9０-９\s　、。・]+$|[○〇◯]")

_KUN_END = re.compile(r"君[　\s]*$")

_RULE_ONLY = re.compile(r"^[─━―\-‐ー\s　・]+$")


_ASCII_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def _digits(s: str) -> int:
    if s == "元":
        return 1
    return int(s.translate(str.maketrans("０１２３４５６７８９", "0123456789")))


def _plain(fragment: str) -> str:
    """A block of the 203 page as text: <BR> to newlines, tags and scripts gone."""
    fragment = re.sub(r"(?is)<script.*?</script>|<script.*$", "", fragment)
    fragment = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def blocks_of(sitting_html: str) -> list[tuple[str, str]]:
    """Split a whole-sitting page into (HUID, text) at the vendor's anchors."""
    parts = _ANCHOR.split(sitting_html)
    # parts = [before, id1, body1, id2, body2, ...]
    return [(parts[i], _plain(parts[i + 1])) for i in range(1, len(parts) - 1, 2)]


def speaker_of(line: str) -> tuple[str, str | None, str]:
    """Split a speech's first line into (speaker, role, rest). Empty speaker if unread."""
    m = _MARKER.match(line)
    if not m:
        return "", None, line
    # 「４番」 and 「40番」 are one column of seat numbers typed two ways.
    role = (m["role"] or m["office3"] or "").strip().translate(_ASCII_DIGITS) or None
    raw = m["name"] or m["name0"] or m["name2"] or m["name3"] or ""
    office = _OFFICE_IN_NAME.match(raw.strip()) or _NAME_THEN_OFFICE.match(raw.strip())
    committee = _COMMITTEE_FIRST.match(raw.strip()) if m["name3"] else None
    chair = _CHAIR_NAMED.match(role or "") if committee else None
    if committee and chair:
        role, raw = f"{committee['office']}委員長", chair["name"]
    elif office:
        role = f"{role}　{office['office']}" if role else office["office"]
        raw = office["name"]
    elif role and raw.startswith(role) and len(raw) - len(role) >= 2:
        # 長野 types the office twice once: 「◎教育長（教育長原山隆一　君）」.
        raw = raw[len(role) :]
    speaker = _clean_speaker(_GIIN.sub("", _clean_speaker(raw)))
    if not speaker or _NOT_A_NAME.search(speaker):
        return "", None, line
    return speaker, role, line[m.end() :]


# Older sittings append the signatures to the chair's last words — 「午後４時３分
# 閉会」「会議録署名議員」「議　長　黒　川　　　治」… — a roster, not speech.
_SIGNATURES = "会議録署名議員"


def _turns(lines: list[str]) -> list[list[str]]:
    """Split one anchored block where a 栃木-shaped marker opens a line inside it.

    The vendor's anchors are the speech boundaries — except in a few 栃木
    sittings (令和4年2〜3月 most of all) where the vice-chair's turns carry none:
    「○佐藤良　副議長　相馬政二議員。」 sits inside the member's speech before it.
    Only the name-then-office shape splits: 「○県政経営委員会（定数九人）」 opens
    lines of committee rosters inside speeches, and is not a speaker.
    """
    turns: list[list[str]] = [[]]
    for ln in lines:
        m = _MARKER.match(ln.strip())
        # 長野 drops an anchor twice in 75,081 speeches, before the full form
        # 「○議長（向山公人　君）」. The 「君」 is what tells it from a roster heading.
        full = m and m["name"] and _KUN_END.search(m["name"])
        if turns[-1] and m and (m["name3"] or full) and speaker_of(ln.strip())[0]:
            turns.append([])
        turns[-1].append(ln)
    return turns


def _body(first_rest: str, lines: list[str]) -> str:
    kept: list[str] = []
    for raw in [first_rest, *lines]:
        ln = raw.strip().strip("　").strip()
        if ln.replace("　", "") == _SIGNATURES:
            break
        if ln and not _RULE_ONLY.match(ln):
            kept.append(ln)
    return "\n".join(kept).strip()


def sitting_date(session: str, label: str, year: int | None = None) -> date | None:
    """The year from the session title, the month and day from the vendor's label.

    A sitting whose month is earlier than its session's is in the next year — a
    December session that runs into January. Neither site has one in the sample;
    `report()` counts them if they appear.

    Where the title has no month (栃木), `year` — the calendar year of the list
    page the row was on — is the year instead.
    """
    s = _SESSION.match(session)
    lab = _LABEL.match(label)
    if lab and not s and year is not None:
        try:
            return date(year, int(lab[1]), int(lab[2]))
        except ValueError:
            return None
    if not s or not lab:
        return None
    first = parse_japanese_date(f"{s[1]}{_digits(s[2])}年1月1日")
    if first is None:
        return None
    month, day = int(lab[1]), int(lab[2])
    y = first.year + (1 if month < _digits(s[3]) else 0)
    try:
        return date(y, month, day)
    except ValueError:
        return None


def split_session(row_title: str) -> str:
    """「令和　２年１１月定例会議（第17号～第23号）」 -> 「令和2年11月定例会議」.

    Spaces and digit widths are normalised because the vendor pads 「令和　２年」 to
    a column — the same session must have one name (和歌山's 「令和８年２月」).
    """
    s = _SESSION_RANGE.sub("", row_title).replace("　", "").replace(" ", "")
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


@dataclass(slots=True)
class Row:
    """One document as the year list shows it."""

    title: str
    label: str
    url: str
    year: int | None = None
    """The calendar year of the list page it was read from, where the bar says."""


def shown_year(list_html: str) -> int | None:
    """The year a list page is showing: the year bar's one entry that is not a link.

    None when the page has no bar (滋賀・石川 list one year at a time without one)
    or when the bar does not single one out.
    """
    soup = BeautifulSoup(list_html, "lxml")
    for td in soup.find_all("td"):
        # The bar is a cell of era-years and nothing else; a row's cell carries
        # its session title, which has a year too (「令和　２年１１月定例会議」).
        if not _BAR_YEAR.search(td.get_text()) or _BAR_YEAR.sub("", td.get_text()).strip(" 　\n"):
            continue
        for a in td.find_all("a"):
            a.extract()
        plain = _BAR_YEAR.findall(td.get_text())
        if len(plain) == 1:
            era, n = plain[0]
            d = parse_japanese_date(f"{era}{_digits(n)}年1月1日")
            return d.year if d else None
    return None


def rows_on(list_html: str, base_url: str) -> list[Row]:
    """Every document on an `ACT=100` list, in order.

    A row is 「令和　２年１１月定例会議（第17号～第23号）,<A … onClick="winopen('…')">
    11月27日-01号</A>」 — the title is the text before the link.
    """
    soup = BeautifulSoup(list_html, "lxml")
    year = shown_year(list_html)
    out: list[Row] = []
    for a in soup.find_all("a", onclick=True):
        m = _WINOPEN.search(str(a["onclick"]))
        if not m:
            continue
        prev = a.previous_sibling
        title = str(prev).strip().rstrip(",") if prev is not None else ""
        out.append(
            Row(
                title=title.strip(),
                label=a.get_text(strip=True),
                url=urljoin(base_url, m[1]),
                year=year,
            )
        )
    return out


@dataclass(slots=True)
class VoicesConfig:
    """Mirrors `sites/<name>.toml` with `scraper = "voices"`."""

    prefecture: str
    index_url: str
    name: str = ""
    robots_exempt: RobotsExemption | None = None
    fetch_window: FetchWindow | None = None
    contact: Contact | None = None
    notice: Notice | None = None

    @classmethod
    def from_toml(cls, path: Path) -> VoicesConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        opts = dict(raw.get("voices", {}))
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


class VoicesScraper(BaseScraper):
    """本会議 of one gijiroku VOICES install."""

    def __init__(self, config: VoicesConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture
        self.robots_exempt = config.robots_exempt
        self.fetch_window = config.fetch_window
        self.contact = config.contact
        self.notice = config.notice
        self._rows: dict[str, Row] = {}
        self._short_lists: list[str] = []
        self._mokuji = 0
        self._no_frame: list[str] = []
        self._kinds: Counter[str] = Counter()
        self._unattributed: list[str] = []
        self._date_mismatch: list[str] = []
        self._undated: list[str] = []
        self._next_year: list[str] = []
        self._office_split = 0

    def url_prefixes(self) -> list[str]:
        return [urljoin(self.config.index_url, "./")]

    # -- listing ---------------------------------------------------------------

    def _lists_of_year(self, client: PoliteClient, wrapper_url: str) -> Iterator[Page]:
        """The year's `ACT=100` list, and any further page of it.

        Further pages are `PAGE=` (滋賀・石川) and `YEAR=` (栃木: a fiscal year is
        two calendar years, one per page). The `YEAR=` links that also carry
        `TITL_SUBT=` open one session's speakers inline and list nothing new.
        """
        wrapper = client.get(wrapper_url)
        frame = BeautifulSoup(wrapper.text, "lxml").find("iframe", src=True)
        if not isinstance(frame, Tag):
            self._no_frame.append(wrapper_url)
            log.warning("%s: no <iframe> — nothing listed for this year", wrapper_url)
            return
        todo = [urljoin(wrapper.url, str(frame["src"]))]
        seen: set[str] = set()
        years_read: set[int] = set()
        while todo:
            url = todo.pop(0)
            if url in seen:
                continue
            seen.add(url)
            page = client.get(url)
            yield page
            soup = BeautifulSoup(page.text, "lxml")
            showing = shown_year(page.text)
            if showing is not None:
                years_read.add(showing)
            for a in soup.find_all("a", href=True):
                href = urljoin(page.url, str(a["href"]))
                if "ACT=100" not in href or "FINO=" in href or "TITL_SUBT=" in href:
                    continue
                year = _YEAR_PAGE.search(href)
                if _PAGE_LINK.search(href) or (year and int(year[1]) not in years_read):
                    todo.append(href)

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        index = client.get(self.config.index_url)
        soup = BeautifulSoup(index.text, "lxml")
        years = list(
            dict.fromkeys(
                urljoin(index.url, str(a["href"]))
                for a in soup.find_all("a", href=True)
                if _YEAR_LINK.search(str(a["href"])) and _YEAR_TEXT.search(a.get_text())
            )
        )
        log.info("%d year lists on the index", len(years))
        for wrapper_url in years:
            rows: list[Row] = []
            hits: int | None = None
            for page in self._lists_of_year(client, wrapper_url):
                m = _HITS.search(page.text)
                hits = int(m[1]) if m and hits is None else hits
                rows += rows_on(page.text, page.url)
            unique = list({r.url: r for r in rows}.values())
            if hits is not None and hits != len(unique):
                self._short_lists.append(f"{wrapper_url}: {hits} listed, {len(unique)} read")
                log.warning("%s: the list says %d, %d rows read", wrapper_url, hits, len(unique))
            for row in unique:
                if row.label.endswith("目次"):
                    self._mokuji += 1
                    continue
                self._rows[row.url] = row
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=row.url,  # type: ignore[arg-type]
                    date=sitting_date(row.title, row.label, row.year),
                    title=f"{row.title} {row.label}",
                )

    def prepare(self, client: PoliteClient) -> None:
        """A re-parse needs the row's title and label, which only the list has."""
        if not self._rows:
            for _ in self.list_meetings(client):
                pass

    # -- fetching --------------------------------------------------------------

    def fetch_meeting(self, ref: MeetingRef, client: PoliteClient) -> Page:
        """The frameset, then its 「hat」 frame: the whole sitting."""
        frameset = client.get(str(ref.url))
        frame = BeautifulSoup(frameset.text, "lxml").find("frame", attrs={"name": "hat"})
        if not isinstance(frame, Tag) or not frame.get("src"):
            self._no_frame.append(str(ref.url))
            raise FetchError(f"{ref.url}: no frame named hat")
        src = str(frame["src"]).split("#", 1)[0]
        return client.get(urljoin(frameset.url, src))

    # -- detail ----------------------------------------------------------------

    def _check_date(self, ref: MeetingRef, when: date | None, front: str) -> None:
        if when is None:
            self._undated.append(f"{ref.url} {ref.title}")
            return
        # 栃木 opens the day with a bullet, 「〇十二月十四日（月曜日）」, and 〇 is
        # also a kanji digit: read as one, that date is 2/14.
        lines = [ln.strip("　 ").lstrip("〇○") for ln in front.split("\n") if ln.strip("　 ")][:8]
        printed: tuple[int, int] | None = None
        for ln in lines:
            full = _PRINTED_FULL.search(ln)
            if full and (d := parse_japanese_date(full[1])):
                if d != when:
                    self._date_mismatch.append(f"{ref.url}: label {when}, printed {d}")
                return
            md = _PRINTED_MD.match(ln)
            if md:
                printed = (kanji_to_int(md[1]), kanji_to_int(md[2]))
                break
            fig = _PRINTED_MD_FIG.match(ln)
            if fig:
                printed = (_digits(fig[1]), _digits(fig[2]))
                break
        if printed and printed != (when.month, when.day):
            self._date_mismatch.append(f"{ref.url}: label {when}, printed {printed}")

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        row = self._rows.get(str(ref.url))
        title = row.title if row else (ref.title or "")
        label = row.label if row else ""
        session = split_session(title) or None
        when = sitting_date(title, label, row.year) if row else ref.date
        if when and _LABEL.match(label) and _SESSION.match(title):
            s = _SESSION.match(title)
            if s and when.month < _digits(s[3]):
                self._next_year.append(f"{ref.url} {title} {label}")

        blocks = blocks_of(page.text)
        speeches: list[Speech] = []
        for i, (huid, text) in enumerate(blocks):
            if i == 0:
                self._check_date(ref, when, text)
                self._kinds["front matter"] += 1
                continue
            turns = _turns(text.strip().split("\n"))
            if len(turns) > 1:
                self._kinds["turn with no anchor"] += len(turns) - 1
            for lines in turns:
                first = lines[0].strip() if lines else ""
                if not first:
                    self._kinds["empty"] += 1
                    continue
                if first.startswith("△"):
                    self._kinds["△ heading"] += 1
                    continue
                speaker, role, rest = speaker_of(first)
                marker = _MARKER.match(first)
                inner = (marker["name"] or "").strip() if marker else ""
                if _OFFICE_IN_NAME.match(inner) or _NAME_THEN_OFFICE.match(inner):
                    self._office_split += 1
                body = _body(rest, lines[1:])
                if not body:
                    self._kinds["no text"] += 1
                    continue
                self._kinds[first[0] if speaker else "unattributed"] += 1
                if not speaker:
                    self._unattributed.append(f"{ref.url} HUID{huid}: {first[:40]}")
                speeches.append(Speech(order=len(speeches), speaker=speaker, role=role, text=body))

        return Meeting(
            prefecture=self.prefecture,
            url=ref.url,
            date=when,
            session=session,
            committee=None,
            title=f"{title} {label}".strip(),
            speeches=speeches,
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )

    def report(self) -> list[str]:
        out = [
            "blocks: " + ", ".join(f"{k} {v}" for k, v in self._kinds.most_common()),
            f"{self._mokuji} 目次 document(s) listed and skipped",
            f"{self._office_split} speaker(s) split from an office in the bracket (…委員長＋name)",
        ]
        if self._short_lists:
            out.append(
                f"{len(self._short_lists)} year list(s) whose row count differs from its hit count:"
            )
            out += [f"  {s}" for s in self._short_lists]
        if self._no_frame:
            out.append(f"{len(self._no_frame)} page(s) without the expected frame:")
            out += [f"  {s}" for s in self._no_frame]
        if self._unattributed:
            out.append(
                f"{len(self._unattributed)} speech(es) whose marker was not read (kept, unnamed):"
            )
            out += [f"  {s}" for s in self._unattributed[:50]]
        if self._undated:
            out.append(f"{len(self._undated)} undated sitting(s):")
            out += [f"  {s}" for s in self._undated]
        if self._next_year:
            out.append(
                f"{len(self._next_year)} sitting(s) dated into the year after their session:"
            )
            out += [f"  {s}" for s in self._next_year]
        if self._date_mismatch:
            out.append(
                f"{len(self._date_mismatch)} label date(s) disagreeing with the printed one:"
            )
            out += [f"  {s}" for s in self._date_mismatch]
        return out
