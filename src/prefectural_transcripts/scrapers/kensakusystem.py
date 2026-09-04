"""Scraper for the `kensakusystem.jp` 会議録検索システム (三重・兵庫・愛媛).

This is the one site so far that genuinely cannot be expressed as selectors, for
three separate reasons:

* **The browse tree has no hrefs.** Every node is
  `<A HREF="javascript:document.viewtree.submit()" onClick="…treedepth.value='令和 7年'">`,
  so the thing to follow lives in an `onClick` attribute, not in a link. Worse,
  `treedepth` is a *label*, and it must be percent-encoded in **cp932** — the page's
  own charset — before it can be sent.
* **A sitting is assembled from a list of offsets.** The transcript is not one
  page; the site's own ダウンロード button posts a repeated `downloadPos` to
  `GetPerson.exe`. Composing that URL is more than following a link.
* **The transcript is not HTML.** `GetPerson.exe` returns plain text, so there is
  no container to select and `speech_split` has to run on the body as fetched.

Everything else — politeness, caching, cp932 decoding, resume, the date filter —
comes from the existing machinery unchanged.

The flow, all over GET (the forms are POST in a browser, but the CGI accepts the
same fields as a query string):

    index.html                      -> Code= session token
    See.exe?Code=&treedepth=<年>     -> that year's sessions, and its sibling years
    See.exe?Code=&treedepth=<会期>   -> ResultFrame links carrying fileName=R070303A
    r_Speakers.exe?…/<fileName>/…   -> one downloadPos per speech
    GetPerson.exe?Code=&fileName=&downloadPos=…  -> the whole sitting as plain text

Two requests per sitting, and both are made through `fetch_meeting`, so listing
costs nothing per document and `--since/--until` prunes before either — the date
is in the `fileName`. A ref therefore points at the *speaker index*, which is also
what a `Meeting` records as its URL: the download URL runs to several kilobytes on
a busy sitting and is not a usable identity.

**兵庫 is the same product and not the same site**, which is the other thing this
module now encodes. Three differences, each of which fails without a sound:

* its tree carries labels in `data-depth="…"` rather than in an `onClick`
  assignment, and a tree with no nodes looks exactly like a year that is not there;
* it has no ダウンロード button and therefore no offsets — its 全文表示 button
  (`GetText3.exe?…&FUNC=PRINT_ALL`) returns the whole sitting in **one** request,
  as HTML, which `download = "printall"` selects;
* and the marker forms differ across all three tenants, so `speech_split` belongs
  in the config, per site, counted against a sample before it is trusted.

The GET route also has a limit the vendor does not document: `GetPerson.exe` 404s
on a URL past roughly 2,110 characters, which a busy sitting exceeds. See
`MAX_URL`.

See `docs/kensakusystem.md`.
"""

from __future__ import annotations

import logging
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from prefectural_transcripts.dates import parse_japanese_date
from prefectural_transcripts.http import FetchError, Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef, Speech
from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import split_speeches

log = logging.getLogger(__name__)

# Two generations of the same tree, and a config cannot tell them apart in
# advance — so both are read.
#
# 愛媛・三重: `onClick="document.viewtree.treedepth.value='令和 7年 第391回定例会 '"`
# 兵庫:      `<A HREF="#" class="js-tree-submit" data-depth="令和 7年  2月第370回定例会 ">`
#
# The trailing space is part of the label in both and must survive into the query
# string. Reading only the older form on 兵庫 finds no nodes at all, which looks
# exactly like a year the tree does not have.
_TREEDEPTH = re.compile(r'''treedepth\.value='([^']*)'|data-depth="([^"]*)"''')
# 「令和元年」 is a year node like any other, and 元 is not a digit. `dates.py`
# has handled that form since 静岡; forgetting it here cost a whole year — the
# node was walked, matched nothing, and said nothing.
_YEAR_NODE = re.compile(r"^(?:令和|平成|昭和)\s*(?:元|\d{1,2})年$")
# `<A href="ResultFrame.exe?…&fileName=R080225A&startPos=0"><IMG …>（第1号 2月25日）</A>`
# — the sitting's label is the anchor text, and it is the only place the 第N号 and
# the printed date appear together.
_DOCUMENT = re.compile(
    r'href="ResultFrame\.exe\?[^"]*fileName=([^"&]+)[^"]*"[^>]*>(?:\s*<[^>]+>)*\s*([^<]*)',
    re.IGNORECASE,
)
# `R080225A` — era initial, era year, month, day, serial letter, and on 三重's
# older documents a two-digit continuation: `H010518A01`. A committee that sits
# twice in one day adds `_2` before the serial: `R080119_2B10`. Everything else
# the tree offers is not a sitting: 決議案・請願・意見書 (`R07060004KETS.html`), 目次
# (`H010228MOKU.html`), 名簿 (`MEIB`), 議案 (`GIAN`) — all of them dotted.
#
# **Both optional parts were added after this rule rejected real sittings**, and
# both times the rejection was *reported* rather than silent, which is the only
# reason either was ever found. `\d{0,2}` came first: 52 三重 sittings from the
# 平成 archive. `_\d` came with the committees: 52 more, 7 on 三重 and 45 on 兵庫,
# one of them a 88-speech 総務地域連携交通常任委員会. A shape rule about which
# documents matter has to say what it is dropping, because it will be wrong about
# something.
_SITTING = re.compile(r"^[RHS]\d{6}(?:_\d)?[A-Z]\d{0,2}$")
_DOWNLOAD_POS = re.compile(r'name="downloadPos"\s+value="(\d+)"')
_CODE = re.compile(r"(cgi-bin\d*)/See\.exe\?Code=([A-Za-z0-9]+)")
# The sitting id may carry the `_2` of a second sitting on one day, so it is not
# `[A-Za-z0-9]+`. Reading it wrong does not 404 — it raises before any request,
# which is at least loud.
_INDEX_URL = re.compile(r"/(cgi-bin\d*)/r_Speakers\.exe\?([A-Za-z0-9]+)/([A-Za-z0-9_]+)/")

# `R070303A` — era initial, two-digit era year, month, day, and a serial letter.
_FILENAME_DATE = re.compile(r"^([RHS])(\d{2})(\d{2})(\d{2})")
_ERA_BASE = {"R": 2018, "H": 1988, "S": 1925}

# 「○（三宅浩正議長）　…」. The parentheses are not decoration: the same documents
# open sections with 「○議事日程」 and 「〇出席議員」, which are not speeches, and
# requiring the brackets is what separates them.
DEFAULT_SPEECH_SPLIT = r"(?m)^○[（(](?P<speaker>[^）)\n]{1,40})[）)]"

# `GetPerson.exe` marks printed page breaks in the text it returns.
_PAGE_MARK = re.compile(r'<PAGE="\d+">')

# The server refuses a request line past roughly 2,110 characters — 2,102 was
# fetched and 2,119 gave **404**, on both 三重 and 愛媛, which is a length limit
# wearing a "not found" costume. A 一般質問 day has enough speeches to cross it,
# and `scrape()` logs a FetchError and moves on, so the sitting simply is not
# there afterwards. It cost 愛媛 three sittings before anyone noticed.
#
# 1,800 leaves room for a long tenant path and a few more offsets than measured.
MAX_URL = 1800

# `GetPerson.exe` repeats these two lines at the top of every response, so they
# arrive again in the middle of a sitting that had to be fetched in chunks.
_DOWNLOAD_HEADER = ("開催日：", "会議名：")


def _chunk(stem: str, positions: list[str]) -> list[list[str]]:
    """Split the offsets into as few URLs as the server's length limit allows."""
    chunks: list[list[str]] = [[]]
    length = len(stem)
    for pos in positions:
        field = len(f"&downloadPos={pos}")
        if chunks[-1] and length + field > MAX_URL:
            chunks.append([])
            length = len(stem)
        chunks[-1].append(pos)
        length += field
    return chunks


def _strip_header(body: bytes, encoding: str) -> bytes:
    """Drop the `開催日：`/`会議名：` lines the CGI repeats on every response."""
    out = body
    for label in _DOWNLOAD_HEADER:
        marker = label.encode(encoding)
        if out.startswith(marker):
            _, _, out = out.partition(b"\n")
    return out.lstrip(b"\r\n")


def _depths(html: str) -> list[str]:
    """Every tree label on a page, whichever generation of markup it uses."""
    return [old or new for old, new in _TREEDEPTH.findall(html)]


def _squash(label: str) -> str:
    """`令和 8年 第395回定例会 ` -> `令和8年第395回定例会`.

    The tree pads its labels for display and the trailing space is significant
    when sending them back, but neither belongs in a stored record.
    """
    return re.sub(r"\s+", "", label)


def _year_key(label: str) -> tuple[int, int]:
    """Order 「平成30年」 before 「令和 2年」 — string order puts 平 after 令."""
    m = re.match(r"(令和|平成|昭和)\s*(元|\d{1,2})年", label)
    if not m:
        return (0, 0)
    year = 1 if m.group(2) == "元" else int(m.group(2))
    return (_ERA_BASE[{"令和": "R", "平成": "H", "昭和": "S"}[m.group(1)]], year)


def _cp932(value: str) -> str:
    """Percent-encode a tree label the way the page's own form would."""
    return quote(value.encode("cp932"))


# 「令和7年総務常任委員会」, 「令和8年令和8年度予算特別委員会」, 「令和6年県庁舎等再整備協議会」.
# Matched positively rather than by excluding 定例会・臨時会, because the labels
# that are not 本会議 are a closed list of shapes and the 本会議 ones are not:
# 兵庫's truncated 「昭和61年第198回定」 is a 定例会 whose label does not say so, and
# an "everything else is a committee" rule would file that sitting as one.
_COMMITTEE = re.compile(r"委員会|協議会|検討会|世話人会|分科会")
_LEADING_YEAR = re.compile(r"^(?:令和|平成|昭和)(?:元|\d{1,2})年")


def _committee(session: str | None) -> str | None:
    """The committee a sitting belongs to, or None for 本会議.

    The leading year comes off — 「令和7年総務常任委員会」 is the 総務常任委員会 — but
    only the first one, because 兵庫 names a budget committee for the fiscal year
    it examines and 「令和8年令和8年度予算特別委員会」 is genuinely a different body
    from 「令和7年度予算特別委員会」.
    """
    if not session or not _COMMITTEE.search(session):
        return None
    return _LEADING_YEAR.sub("", session).strip() or None


# 「〇出席議員　44名」 / 「〇出席理事者」 / 「〇出席事務局職員」 — the rosters a sitting
# opens with, and the only place 愛媛 ever writes a name apart from its office.
_ROSTER_HEAD = re.compile(
    r"^[○〇](?:出席|欠席)(?:議員|委員|理事者|事務局職員)|^[○〇]その他の出席者"
)
# 「　　１番　　井　川　　　剛」, 「　知事　　　　　　　　　　中　村　時　広」 — a label,
# two or more spaces, then the name. The name has single spaces inside it (and
# sometimes three, to pad a two-character surname), so the split has to be on the
# *first* run of two or more, not on whitespace generally.
_ROSTER_ROW = re.compile(r"^[ 　]+(?P<label>\S(?:[^\s]|[ 　](?![ 　]))*?)[ 　]{2,}(?P<name>\S.*)$")


# The office is easier to read than the name: it is the first token on the line,
# whatever the padding after it. That matters because the padding is not always
# two spaces — 「　　観光スポーツ文化部長　金　子　浩　一」 separates them with one, and
# the row rule above reads nothing at all from a line like that.
_ROSTER_LABEL = re.compile(r"^[ 　]+(?P<label>[^\s]{2,30})[ 　]")
# What may be left over once an office comes off: a name, not a fragment.
_NAME = re.compile(r"^[^\s0-9０-９]{2,8}$")


def roster_names(text: str) -> set[str]:
    """Every name this sitting lists as present, spaces squashed out.

    愛媛 prints 「○（三宅浩正議長）」 — name and office in one run, with nothing to
    split on — but it also prints 「　　９番　　三　宅　浩　正」 at the top of the same
    document. The roster is the missing delimiter.
    """
    names: set[str] = set()
    inside = False
    for line in text.split("\n"):
        if _ROSTER_HEAD.match(line):
            inside = True
            continue
        if not inside:
            continue
        row = _ROSTER_ROW.match(line)
        if row:
            names.add(re.sub(r"\s+", "", row.group("name")))
        elif line.strip() and not line.startswith((" ", "　")):
            inside = False
    return {n for n in names if len(n) >= 2}


def roster_offices(text: str) -> set[str]:
    """Every office the sitting lists, read as the first token of a roster line.

    A fallback for the rows `roster_names` cannot read: where the office and the
    name are separated by a single space there is nothing to split the line on,
    but the office itself is still the first thing after the indent.
    """
    offices: set[str] = set()
    inside = False
    for line in text.split("\n"):
        if _ROSTER_HEAD.match(line):
            inside = True
            continue
        if not inside:
            continue
        label = _ROSTER_LABEL.match(line)
        if label:
            offices.add(re.sub(r"\s+", "", label.group("label")))
        elif line.strip() and not line.startswith((" ", "　")):
            inside = False
    return offices


def split_on_roster(
    speaker: str,
    names: set[str],
    offices: set[str] = frozenset(),  # type: ignore[assignment]
) -> tuple[str, str | None]:
    """`三宅浩正議長` -> `(三宅浩正, 議長)`, using only names the sitting itself lists.

    The name must match and something must be left over, which is what keeps this
    from inventing a split. 「○（財政課長）」 names nobody and is left alone — the
    roster does say who holds that post, but attaching it would be attributing a
    speech the record does not attribute.

    The longest match wins, so a 田中 on the roster cannot cut a 田中一郎 short.
    """
    best = ""
    for name in names:
        if len(name) > len(best) and speaker.startswith(name) and len(speaker) > len(name):
            best = name
    if best:
        return best, speaker[len(best) :]

    # Nothing on the name side. Try the office side, which is readable on rows the
    # name rule cannot parse — 「金子浩一観光スポーツ文化部長」 is 23 speeches that stay
    # glued otherwise. What is left has to look like a name, or this would cut
    # 「保健福祉部社会福祉医療局長」 down to a fragment and call it a person.
    office = ""
    for candidate in offices:
        if len(candidate) > len(office) and speaker.endswith(candidate):
            office = candidate
    if office:
        head = speaker[: -len(office)]
        if _NAME.match(head):
            return head, office
    return speaker, None


def date_from_filename(name: str) -> date | None:
    """`R070303A` -> 2025-03-03. The listing carries no dates, but the name does.

    This is why `--since/--until` can actually save requests on this site, unlike
    静岡 and 和歌山 where the filter can only run after a page is fetched.
    """
    m = _FILENAME_DATE.match(name)
    if not m:
        return None
    era, year, month, day = m.groups()
    return parse_japanese_date(f"{_ERA_BASE[era] + int(year)}年{int(month)}月{int(day)}日")


@dataclass(slots=True)
class KensakuConfig:
    """Mirrors `sites/<name>.toml` for this scraper."""

    prefecture: str
    base_url: str
    name: str = ""
    speech_split: str = DEFAULT_SPEECH_SPLIT

    encoding: str = "cp932"
    """Charset to decode a transcript with, rather than sniffing it.

    `GetPerson.exe` returns plain text with no meta tag and no `charset` on the
    response, so `sniff_encoding` has only charset-normalizer to go on — and it
    guessed **utf-8** for 5 of 63 sittings, which decoded to mojibake. Those five
    parsed to zero speeches and warned, but on a different document the same miss
    would have produced plausible garbage instead. The vendor's charset is known,
    so it is stated rather than detected.
    """

    download: str = "getperson"
    """How a whole sitting is fetched: `getperson` (愛媛・三重) or `printall` (兵庫).

    Same product, two generations. 愛媛 and 三重 carry a ダウンロード button whose
    `GetPerson.exe` takes a repeated `downloadPos` read off the speaker index —
    two requests, and the URL has to be chunked (see `MAX_URL`). 兵庫's speaker
    index has no such form; its 全文表示 button posts `FUNC=PRINT_ALL` to
    `GetText3.exe`, which returns the whole sitting as HTML in **one** request,
    with no per-speech offsets involved at all.
    """

    roster_split: bool = False
    """Split 「三宅浩正議長」 into name and office using the sitting's own roster.

    愛媛 alone needs it: 三重 and 兵庫 print the two separately, and 愛媛's own
    平成 documents do too, so this only ever fires where `role` came back empty.

    It is not cosmetic. 「中畑保一」 spoke 51 times as a member and 「中畑保一議長」
    1,772 times as chair, and they were two speakers — 38 people were counted
    twice that way, all of them the ones who held an office.
    """

    sessions: str = "定例会|臨時会"
    """Regex on the tree label; only matching nodes are opened.

    The default is 本会議 only, which is how the three tenants were first
    collected. All three now say `.` — every node under a year — because naming
    the kinds of session wanted turned out to be a way of losing them: 兵庫's
    tree carries 「昭和61年 第198回定 」, a label truncated mid-word by whoever
    typed it, and `定例会|臨時会` skipped it in silence along with the sitting of
    1986-06-05 underneath. A node that is never opened warns about nothing.

    The year node itself is not a session and is skipped whatever this says.
    """

    years: list[str] = field(default_factory=list)
    """Tree labels to walk, e.g. `["令和 7年", "令和 6年"]`. Empty means every year.

    This is the knob that actually scopes a crawl. A date filter cannot prune the
    tree walk, only the sittings it finds — the same lesson `--start-url` taught
    on 和歌山.
    """

    @classmethod
    def from_toml(cls, path: Path) -> KensakuConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        opts = dict(raw.get("kensakusystem", {}))
        try:
            return cls(
                prefecture=raw["prefecture"],
                name=raw.get("name", path.stem),
                base_url=opts.pop("base_url"),
                **opts,
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid site config {path}: {exc}") from exc


class KensakuSystemScraper(BaseScraper):
    """Drives one `kensakusystem.jp` tenant."""

    def __init__(self, config: KensakuConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture

    # -- listing ---------------------------------------------------------------

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        cgi, code = self._session_token(client)
        see = urljoin(self.config.base_url, f"{cgi}/See.exe")

        for session in self._sessions(client, see, code):
            page = client.get(f"{see}?Code={code}&treedepth={_cp932(session)}")
            seen: set[str] = set()
            for name, label in _DOCUMENT.findall(page.text):
                if name in seen:
                    continue
                seen.add(name)
                if not _SITTING.match(name):
                    # 兵庫 lists 決議案・請願・意見書 (`…KETS.html`) beside its
                    # sittings and 三重 lists a 目次 (`R080119MOKU`). Neither is a
                    # transcript. A dotted name is a known kind and is dropped
                    # quietly; anything else is a shape we have not seen, and the
                    # one thing this project cannot afford is dropping a sitting
                    # in silence.
                    if "." in name:
                        log.debug("not a sitting, skipped: %s (%s)", name, label.strip())
                    else:
                        log.warning(
                            "unexpected document name, skipped: %s (%s)", name, label.strip()
                        )
                    continue
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=self._document_url(cgi, code, name),  # type: ignore[arg-type]
                    date=date_from_filename(name),
                    title=f"{_squash(session)}{label.strip()}",
                )

    def _session_token(self, client: PoliteClient) -> tuple[str, str]:
        """Read `Code=` out of the static landing page rather than pinning it.

        It did not change over two days of fetching, but a rotation should break
        the crawl loudly on the first request instead of quietly on every one.
        """
        page = client.get(urljoin(self.config.base_url, "index.html"))
        m = _CODE.search(page.text)
        if not m:
            raise ValueError(f"no Code= found on {page.url} — has the site changed?")
        return m.group(1), m.group(2)

    def _sessions(self, client: PoliteClient, see: str, code: str) -> Iterator[str]:
        """Walk the year tabs, yielding the session labels worth opening.

        Two phases, because the tree only ever shows one level at a time: opening
        a *tab* reveals the individual years it groups, and a year's sessions
        appear only once that year itself is opened. So the years are learned
        first and then opened — a `years` list naming a year that is not also a
        tab (令和 2年, 平成31年) is otherwise unreachable, which silently cost this
        crawl five of the eight years it was asked for.

        The two phases overlap on the tabs, and those pages are already cached, so
        the second visit costs nothing.
        """
        wanted = re.compile(self.config.sessions)
        allowed = set(self.config.years)
        root = client.get(f"{see}?Code={code}")
        tabs = [v for v in _depths(root.text) if _YEAR_NODE.match(v)]

        years: set[str] = set(tabs)
        for tab in tabs:
            page = client.get(f"{see}?Code={code}&treedepth={_cp932(tab)}")
            years.update(v for v in _depths(page.text) if _YEAR_NODE.match(v))

        if allowed:
            missing = allowed - years
            if missing:
                log.warning("no such year node: %s", ", ".join(sorted(missing)))
            years &= allowed

        for year in sorted(years, key=_year_key, reverse=True):
            page = client.get(f"{see}?Code={code}&treedepth={_cp932(year)}")
            for label in _depths(page.text):
                if _squash(label) == _squash(year):
                    # The year's own node is repeated among its children; it is
                    # not a session, and opening it again would walk in circles.
                    continue
                if label.startswith(year) and wanted.search(label):
                    yield label

    def _document_url(self, cgi: str, code: str, name: str) -> str:
        """What a ref points at — short, stable, and one request from the text.

        Under `getperson` that is the *speaker index*, because the download URL
        is composed from the offsets it carries and runs to kilobytes. Under
        `printall` there are no offsets: the 全文表示 URL is itself short, and it
        is both the identity and the fetch.
        """
        if self.config.download == "printall":
            return (
                f"{urljoin(self.config.base_url, cgi + '/GetText3.exe')}"
                f"?Code={code}&fileName={name}&startPos=0&keyMode=10"
                f"&searchMode=1&FUNC=PRINT_ALL"
            )
        return (
            f"{urljoin(self.config.base_url, cgi + '/r_Speakers.exe')}"
            f"?{code}/{name}/0/0//10/1/1073741823:2097151/0/1//0/0/0"
        )

    # -- fetching --------------------------------------------------------------

    def fetch_meeting(self, ref: MeetingRef, client: PoliteClient) -> Page:
        """Fetch the whole sitting, by whichever route this tenant offers.

        `printall` is one plain GET of the ref itself. `getperson` reads the
        offsets off the speaker index first, then downloads them — in as few
        requests as the server's URL limit allows.
        """
        if self.config.download == "printall":
            return client.get(str(ref.url))

        index = client.get(str(ref.url))
        positions = _DOWNLOAD_POS.findall(index.text)
        if not positions:
            raise FetchError(f"no downloadPos on {ref.url} — the sitting cannot be assembled")

        m = _INDEX_URL.search(str(ref.url))
        if not m:
            raise FetchError(f"cannot read the sitting id out of {ref.url}")
        cgi, code, name = m.groups()
        stem = (
            f"{urljoin(self.config.base_url, cgi + '/GetPerson.exe')}?Code={code}&fileName={name}"
        )
        pages = [
            client.get(stem + "".join(f"&downloadPos={p}" for p in chunk))
            for chunk in _chunk(stem, positions)
        ]
        if len(pages) == 1:
            return pages[0]

        # More offsets than one URL can carry. The parts are contiguous, so the
        # bodies concatenate — after dropping the two-line header the CGI puts on
        # every response, which would otherwise land in the middle of a speech.
        body = pages[0].body + b"".join(
            _strip_header(x.body, self.config.encoding) for x in pages[1:]
        )
        log.debug("%s assembled from %d requests", name, len(pages))
        return Page(
            url=str(ref.url),
            status=200,
            body=body,
            encoding=self.config.encoding,
            fetched_at=datetime.now(UTC),
            from_cache=all(x.from_cache for x in pages),
        )

    # -- detail ----------------------------------------------------------------

    def _speeches(self, text: str) -> list[Speech]:
        speeches = split_speeches(text, self.config.speech_split)
        if not self.config.roster_split:
            return speeches
        names, offices = roster_names(text), roster_offices(text)
        if not names and not offices:
            return speeches
        for speech in speeches:
            if speech.role:
                continue
            speech.speaker, speech.role = split_on_roster(speech.speaker, names, offices)
        return speeches

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        # `GetPerson.exe` returns plain text with CRLF line endings and printed
        # page markers; there is no markup to select, so the split rule runs on
        # the body as fetched. `GetText3.exe?FUNC=PRINT_ALL` returns the same
        # transcript as HTML with `<BR>` for every line break, so it is reduced
        # to text first — the split rule is the same either way.
        body = page.body.decode(self.config.encoding, errors="replace")
        if self.config.download == "printall":
            body = BeautifulSoup(body, "lxml").get_text("\n", strip=True)
        text = _PAGE_MARK.sub("", body).replace("\r\n", "\n").replace("\r", "\n")
        title = ref.title or ""
        # 「令和8年第395回定例会（第1号 2月25日）」 — the session is everything before
        # the bracket.
        session = title.split("（")[0].strip() or None
        return Meeting(
            prefecture=self.prefecture,
            # The download URL runs past pydantic's 2,083-character URL limit on a
            # busy sitting, and is not a useful identity anyway; the speaker index
            # names the same sitting in ~100 characters.
            url=ref.url,
            date=ref.date,
            session=session,
            committee=_committee(session),
            title=title or None,
            speeches=self._speeches(text),
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )
