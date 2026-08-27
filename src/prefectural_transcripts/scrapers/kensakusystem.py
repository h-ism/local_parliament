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

from prefectural_transcripts.dates import parse_japanese_date
from prefectural_transcripts.http import FetchError, Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef
from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import split_speeches

log = logging.getLogger(__name__)

# `onClick="document.viewtree.treedepth.value='令和 7年 第391回定例会 '"` — note that
# the trailing space is part of the label and must survive into the query string.
_TREEDEPTH = re.compile(r"treedepth\.value='([^']*)'")
# 「令和元年」 is a year node like any other, and 元 is not a digit. `dates.py`
# has handled that form since 静岡; forgetting it here cost a whole year — the
# node was walked, matched nothing, and said nothing.
_YEAR_NODE = re.compile(r"^(?:令和|平成|昭和)\s*(?:元|\d{1,2})年$")
# `<A href="ResultFrame.exe?…&fileName=R080225A&startPos=0"><IMG …>（第1号 2月25日）</A>`
# — the sitting's label is the anchor text, and it is the only place the 第N号 and
# the printed date appear together.
_DOCUMENT = re.compile(
    r'href="ResultFrame\.exe\?[^"]*fileName=([A-Za-z0-9]+)[^"]*"[^>]*>(?:\s*<[^>]+>)*\s*([^<]*)',
    re.IGNORECASE,
)
_DOWNLOAD_POS = re.compile(r'name="downloadPos"\s+value="(\d+)"')
_CODE = re.compile(r"(cgi-bin\d*)/See\.exe\?Code=([A-Za-z0-9]+)")
_INDEX_URL = re.compile(r"/(cgi-bin\d*)/r_Speakers\.exe\?([A-Za-z0-9]+)/([A-Za-z0-9]+)/")

# `R070303A` — era initial, two-digit era year, month, day, and a serial letter.
_FILENAME_DATE = re.compile(r"^([RHS])(\d{2})(\d{2})(\d{2})")
_ERA_BASE = {"R": 2018, "H": 1988, "S": 1925}

# 「○（三宅浩正議長）　…」. The parentheses are not decoration: the same documents
# open sections with 「○議事日程」 and 「〇出席議員」, which are not speeches, and
# requiring the brackets is what separates them.
DEFAULT_SPEECH_SPLIT = r"(?m)^○[（(](?P<speaker>[^）)\n]{1,40})[）)]"

# `GetPerson.exe` marks printed page breaks in the text it returns.
_PAGE_MARK = re.compile(r'<PAGE="\d+">')


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

    sessions: str = "定例会|臨時会"
    """Regex on the tree label; only matching nodes are opened.

    Defaults to 本会議 only. The same tree carries every 委員会, which would
    multiply the crawl several times over.
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
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=self._index_url(cgi, code, name),  # type: ignore[arg-type]
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
        tabs = [v for v in _TREEDEPTH.findall(root.text) if _YEAR_NODE.match(v)]

        years: set[str] = set(tabs)
        for tab in tabs:
            page = client.get(f"{see}?Code={code}&treedepth={_cp932(tab)}")
            years.update(v for v in _TREEDEPTH.findall(page.text) if _YEAR_NODE.match(v))

        if allowed:
            missing = allowed - years
            if missing:
                log.warning("no such year node: %s", ", ".join(sorted(missing)))
            years &= allowed

        for year in sorted(years, key=_year_key, reverse=True):
            page = client.get(f"{see}?Code={code}&treedepth={_cp932(year)}")
            for label in _TREEDEPTH.findall(page.text):
                if label.startswith(year) and wanted.search(label):
                    yield label

    def _index_url(self, cgi: str, code: str, name: str) -> str:
        """The speaker index for one sitting.

        Short and stable, which is why it — not the download URL — is what a ref
        and a stored `Meeting` point at.
        """
        return (
            f"{urljoin(self.config.base_url, cgi + '/r_Speakers.exe')}"
            f"?{code}/{name}/0/0//10/1/1073741823:2097151/0/1//0/0/0"
        )

    # -- fetching --------------------------------------------------------------

    def fetch_meeting(self, ref: MeetingRef, client: PoliteClient) -> Page:
        """Read the offsets from the speaker index, then download the sitting.

        `GetPerson.exe` is the page's own ダウンロード button. It accepts GET with
        a repeated `downloadPos` and returns the selected speeches concatenated as
        plain text, which is one request instead of one per speech.
        """
        index = client.get(str(ref.url))
        positions = _DOWNLOAD_POS.findall(index.text)
        if not positions:
            raise FetchError(f"no downloadPos on {ref.url} — the sitting cannot be assembled")

        m = _INDEX_URL.search(str(ref.url))
        if not m:
            raise FetchError(f"cannot read the sitting id out of {ref.url}")
        cgi, code, name = m.groups()
        url = (
            f"{urljoin(self.config.base_url, cgi + '/GetPerson.exe')}"
            f"?Code={code}&fileName={name}" + "".join(f"&downloadPos={p}" for p in positions)
        )
        return client.get(url)

    # -- detail ----------------------------------------------------------------

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        # `GetPerson.exe` returns plain text with CRLF line endings and printed
        # page markers; there is no markup to select, so the split rule runs on
        # the body as fetched.
        body = page.body.decode(self.config.encoding, errors="replace")
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
            title=title or None,
            speeches=split_speeches(text, self.config.speech_split),
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )
