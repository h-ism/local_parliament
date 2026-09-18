"""Scraper for SSP / Discuss Net Premium (`ssp.kaigiroku.net`), 18 assemblies.

The product is NTT Advanced Technology's 会議録検索システム. Unlike every other
site here it has **no server-rendered route at all**: `MinuteView.html` is an empty
shell and the text arrives from a JSON API under `/dnp/search/`. So there are no
selectors to write and nothing to sniff — three POSTs describe the whole archive:

    councils/index          {tenant_id}                      -> every 会議, all years
    minutes/get_schedule_all{tenant_id, council_id}          -> that 会議's sittings
    minutes/get_minute      {tenant_id, council_id, schedule_id} -> one sitting

`councils/index` ignores `view_year` and returns the tenant's entire listing in one
response (宮城: 4,257 会議 back to 1947), so listing costs one request per 会議 and
nothing per year.

**The reason this is the best-shaped source in the project: the vendor splits the
speeches for us.** A sitting comes back as `tenant_minutes`, one block per
utterance, each carrying `minute_type_code` and a `title` that *is* the speaker
line — 「知事（村井嘉浩君）」, 「二十三番（天下みゆき君）」. Nothing here infers a
boundary from a 「○」, which is the single failure mode that has cost this project
the most (静岡's 124 swallowed speeches, 兵庫's 55). The marker cannot be missed
because we are not looking for one.

What still has to be got right is the *speaker*, and 委員会 differ from 本会議 in
exactly the way the notes warned: 本会議 writes 「役職（氏名君）」 with brackets, and
委員会 writes 「高橋宗也委員長」 — name and office run together, no brackets at all.
See `_split_title`, and `unsplit_titles` in the run summary for how often the rule
gives up (it gives up by keeping the whole title as the speaker, so nothing is
lost silently).

robots.txt: `/dnp/search/` is under `Disallow: /`. This scraper therefore only runs
where the site config carries a `[robots]` exemption — see `docs/ssp.md` and
`RobotsExemption`, which refuses to exist without a reason and a date.
"""

from __future__ import annotations

import json
import logging
import re
import tomllib
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from prefectural_transcripts.config import Contact, FetchWindow, RobotsExemption
from prefectural_transcripts.dates import ERA_BASE, parse_japanese_date
from prefectural_transcripts.http import FetchError, Page, PoliteClient
from prefectural_transcripts.models import Meeting, MeetingRef, Speech
from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import _clean_speaker

log = logging.getLogger(__name__)

API_ROOT = "dnp/search/"

# `dnp.config.MINUTE_TYPE_CODE` in the app's own config.js, which is how these are
# known rather than guessed: 1 目次, 2 名簿, 3 議題, 4 議長, 5 質問, 6 答弁,
# 7 一覧, 8 文書, 9 資料.
SPEECH_CODES = frozenset({4, 5, 6})
"""Blocks that are somebody talking. 3 (△議題) is an agenda heading, 1/2 front matter."""

FRONT_MATTER_CODES = frozenset({1, 2})
"""目次 and 名簿 — where the sitting prints its own date."""

KNOWN_CODES = frozenset(range(1, 10))

PROCEEDINGS_ROOT = "全会議"
"""The listing's own top-level split. The other root is 「資料」.

2,399 of the 17,309 会議 across these 17 tenants hang under 資料, and they are not
sittings: 「議第69号～議第93号」 is a list of bill titles, 「請願一覧表」 a table,
「意見書・決議」 the texts of resolutions. They carry a `文書` block and no speech,
so collecting them writes records with no speaker and no date — 熊本 would have
contributed 728 of them and 福島 336. Skipped, and counted."""

_SPACES = re.compile(r"[\s　]+")
_SCHEDULE_LABEL = re.compile(r"^(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_COUNCIL_YEAR = re.compile(r"(令和|平成|昭和|大正|明治)\s*(元|\d{1,2})\s*年")
_COUNCIL_MONTH = re.compile(r"年[\s　]*(\d{1,2})\s*月")
_TRAILING_COUNT = re.compile(r"[（(]\s*第[\d〇一二三四五六七八九十百]+回\s*[）)]\s*$")

# 「知事（村井嘉浩君）」, 「二十三番（天下みゆき君）」, 「番外［知事］（千葉三郎君）」.
# The office may itself contain ［...］, and the name is what the last bracket pair
# holds — anchored at the end so an office containing brackets cannot steal it.
_BRACKETED = re.compile(r"^(?P<role>.*?)\s*[（(](?P<speaker>[^（()）]+)[）)]\s*$")


def squash(text: str) -> str:
    """NFKC, and no whitespace at all.

    The same 会議 is labelled 「令和　８年　　６月　定例会」 and 「令和8年6月 定例会」 on
    one tenant: full-width digits against ASCII, and space used as column
    padding. Either difference files one session under two names — the 和歌山
    committee lesson, where three spellings of 令和8年2月 made three sessions.

    Space is *removed* rather than collapsed, for the reason `normalize_speaker`
    removes it from names: collapsing cannot merge a form that has no space at
    all, and what is being removed is alignment, not a word boundary.
    """
    return _SPACES.sub("", unicodedata.normalize("NFKC", text)).strip()


@dataclass(slots=True)
class SspConfig:
    """Mirrors `sites/<name>.toml` for this scraper."""

    prefecture: str
    tenant: str
    """Tenant slug in the URL, e.g. `prefmiyagi`."""

    tenant_id: int
    """Numeric id the API wants, published in `/tenant/<tenant>/js/tenant.js`."""

    name: str = ""
    base_url: str = "https://ssp.kaigiroku.net/"
    robots_exempt: RobotsExemption | None = None
    fetch_window: FetchWindow | None = None
    contact: Contact | None = None

    years: list[int] = field(default_factory=list)
    """`view_year` nodes to list, e.g. `[2025, 2026]`. Empty means every year.

    This is the only knob that prunes before a request is made. Note that a
    node's `view_year` is *not* the year printed on the 会議 inside it — 宮城
    files 「平成　１年　１２月　決算特別委員会」 under 1990 — so this scopes a run,
    it does not select a date range. `--since/--until` still apply afterwards.
    """

    committees: bool = True
    """Collect 委員会 as well as 本会議. Both are in the same listing."""

    @classmethod
    def from_toml(cls, path: Path) -> SspConfig:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        opts = dict(raw.get("ssp", {}))
        try:
            return cls(
                prefecture=raw["prefecture"],
                name=raw.get("name", path.stem),
                tenant=opts.pop("tenant"),
                tenant_id=int(opts.pop("tenant_id")),
                robots_exempt=RobotsExemption.from_toml(raw.get("robots", {})),
                fetch_window=FetchWindow.from_toml(raw.get("fetch_window", {})),
                contact=Contact.from_toml(raw.get("contact", {})),
                **opts,
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"invalid site config {path}: {exc}") from exc


@dataclass(slots=True)
class Council:
    """One 会議 in the listing: a 定例会, or one committee's sitting group."""

    council_id: int
    name: str
    view_year: int
    type_names: tuple[str, ...]

    @property
    def is_plenary(self) -> bool:
        return len(self.type_names) > 1 and self.type_names[1] == "本会議"

    @property
    def committee(self) -> str | None:
        """The committee, in the site's own words, or None for 本会議.

        Taken from the 会議's name rather than from the type path, because the two
        disagree: 宮城 files 「平成３０年　３月　環境生活農林水産委員会」 under a node
        typed 環境生活委員会, and files 1,063 委員会 under a node typed only
        「特別委員会」 whose real names — 大震災復興調査特別委員会 among them — exist
        nowhere but the 会議 name. The type path is the fallback, and the
        disagreement is logged rather than silently resolved.
        """
        if self.is_plenary:
            return None
        printed = _strip_period(self.name)
        typed = self.type_names[-1] if self.type_names else ""
        if printed.endswith(("委員会", "分科会", "協議会", "審査会", "部会")):
            if typed and typed != printed and typed.endswith(("委員会", "分科会")):
                log.debug("%s: listing types this as %s", printed, typed)
            return printed
        if typed:
            log.warning(
                "council %d: name %r does not read as a committee; using the type %r",
                self.council_id,
                printed,
                typed,
            )
            return typed
        return printed or None

    @property
    def year(self) -> int | None:
        """The 和暦 year printed on the 会議 itself, converted."""
        if m := _COUNCIL_YEAR.search(self.name):
            era, era_year = m.groups()
            return ERA_BASE[era] + (1 if era_year == "元" else int(era_year))
        return None

    @property
    def month(self) -> int | None:
        m = _COUNCIL_MONTH.search(self.name)
        return int(m.group(1)) if m else None


def _strip_period(name: str) -> str:
    """「令和 8年 3月 大震災復興調査特別委員会(第399回)」 -> the committee alone."""
    without_count = _TRAILING_COUNT.sub("", squash(name))
    after_month = re.sub(r"^.*?年\s*\d{1,2}\s*月\s*", "", without_count)
    return after_month.strip()


@dataclass(slots=True)
class Sitting:
    """One sitting inside a 会議 — one 号, which is one record in the corpus."""

    council: Council
    schedule_id: int
    label: str

    @property
    def month_day(self) -> tuple[int, int] | None:
        m = _SCHEDULE_LABEL.search(squash(self.label))
        return (int(m.group(1)), int(m.group(2))) if m else None


@dataclass(frozen=True, slots=True)
class Roster:
    """The names and the offices one sitting's own 名簿 lists.

    Both halves are read from the document rather than from a list kept here,
    because the two things a split needs — which strings are names, and which
    are offices — differ by tenant and by era, and a list in the code is a claim
    about data nobody has seen yet. 宮城 writes 「委員長　　高橋宗也君」, 長崎
    「冨岡孝介　　委員長」 with no honorific at all, 大分 「議長　　嶋　幸一」, and
    徳島 spaces its names out as 「木　　下　　賢　　功　君」.
    """

    names: frozenset[str] = frozenset()
    offices: tuple[str, ...] = ()

    @property
    def by_length(self) -> list[str]:
        return sorted(self.names, key=len, reverse=True)


_HONORIFICS = ("君", "氏", "さん")
# What ends an office in these rosters. Used only to tell the two columns of a
# roster line apart — never to split a speaker, which is why being wrong here
# costs a split that does not happen rather than a name that is wrong.
_OFFICE_TAIL = (
    "長",
    "委員",
    "番",
    "議員",
    "知事",
    "監",
    "参事",
    "官",
    "員",
    "証人",
    "参考人",
    "説明員",
)
_COLUMN_GAP = re.compile(r"[　\s]{2,}")
_DITTO = "〃々ヽ"
_HONORIFIC_TAIL = re.compile(r"(?:君|氏|さん)$")


def read_roster(front_matter: str) -> Roster:
    """Read the sitting's 名簿 into names and offices.

    A roster line is columns separated by a run of alignment space. A column
    ending in an honorific is a name; one ending in 長・委員・番… is an office;
    and on a two-column line, whichever is left over is the other. A lone column
    is taken as a name only if nothing about it says office, which is how 大分's
    41 members — listed with neither office nor honorific — are read at all.
    """
    names: set[str] = set()
    offices: set[str] = set()
    for raw_line in front_matter.splitlines():
        line = raw_line.strip().lstrip(_DITTO).strip()
        if not line or set(line) <= set("－-—─ 　"):
            continue
        columns = [squash(c).lstrip(_DITTO) for c in _COLUMN_GAP.split(line)]
        # 「宅島寿一　　〃」 — a ditto for the office above leaves an empty column,
        # and dropping it is what makes the line read as one name.
        columns = [c for c in columns if c]
        if not columns or len(columns) > 3:
            continue

        named = [c for c in columns if c.endswith(_HONORIFICS)]
        officed = [c for c in columns if not c.endswith(_HONORIFICS) and c.endswith(_OFFICE_TAIL)]
        plain = [c for c in columns if c not in named and c not in officed]

        for column in named:
            # The honorific goes, but nothing else: a roster name is compared
            # against a printed title, and normalising one side and not the
            # other is how 「髙橋」 stops matching 「高橋」. `split_title` runs
            # `_clean_speaker` on whatever it returns, once, at the end.
            _add_name(names, _HONORIFIC_TAIL.sub("", column).strip())
        for column in officed:
            if 2 <= len(column) <= 20 and not column.isdigit():
                offices.add(column)
        # A two-column line whose other half is an office: the leftover is the
        # name, honorific or not. A line with nothing else on it is a name too —
        # unless it reads as an office.
        if len(columns) <= 2 and (officed or len(columns) == 1):
            for column in plain:
                _add_name(names, column)

    return Roster(names=frozenset(names), offices=tuple(sorted(offices, key=len, reverse=True)))


def _add_name(names: set[str], candidate: str) -> None:
    if (
        2 <= len(candidate) <= 14
        and not any(c.isdigit() for c in candidate)
        and not candidate.endswith(_OFFICE_TAIL)
    ):
        names.add(candidate)


def split_title(title: str, roster: Roster | None = None) -> tuple[str, str | None]:
    """Read a block's `title` as (speaker, role).

    Three ways, and every one of them reads the answer off the document:

    * **Brackets** — 本会議 writes 「知事（村井嘉浩君）」, 「二十三番（天下みゆき君）」,
      and 「番外［知事］（千葉三郎君）」 where the office has brackets of its own.
      The name is the final bracket pair; nothing is inferred.
    * **A name from the 名簿** — 委員会 run the two together
      (「高橋宗也委員長」), and 大分 does it on 本会議 too (「嶋幸一議長」). Where the
      title starts with a name the sitting itself lists, the rest is the office.
    * **An office from the 名簿, corroborated by a name** — 長崎 titles its chair
      「冨岡委員長」 by surname while its 名簿 says 「冨岡孝介　　委員長」, so no name
      matches. The office does, and the split is accepted only because 「冨岡」 is
      the start of a name on that same roster.

    Anything else is left whole and counted. That last rule is what this file is
    most careful about: 大分 writes 「渡邊直二公安委員長」, and a plausible list of
    offices splits it into 「渡邊直二公安」 — *a speaker made of an office*, which
    is the failure 兵庫 took 124 speeches of before anyone noticed. 公安委員長 is
    not on that sitting's roster, 渡邊直二 is not a member of it, and so the title
    stays as printed and `Outcome.unsplit_titles` counts it.
    """
    roster = roster or Roster()
    cleaned = squash(title)
    if not cleaned:
        return "", None

    if m := _BRACKETED.match(cleaned):
        return _clean_speaker(m.group("speaker")), m.group("role").strip() or None

    for name in roster.by_length:
        if cleaned == name:
            return _clean_speaker(name), None
        if cleaned.startswith(name):
            return _clean_speaker(name), cleaned[len(name) :].strip() or None

    for office in roster.offices:
        if not cleaned.endswith(office):
            continue
        residual = cleaned[: -len(office)].strip()
        if len(residual) >= 2 and any(n.startswith(residual) for n in roster.names):
            return _clean_speaker(residual), office

    return _clean_speaker(cleaned), None


@dataclass(slots=True)
class Outcome:
    """What a run had to guess, counted so it can be checked afterwards.

    Every number here is a silent failure in some other prefecture. Reported by
    `pt scrape` at the end and repeated in the run notes.
    """

    documents: int = 0
    speeches: int = 0
    unsplit_titles: int = 0
    """Titles kept whole because neither rule read them. See `split_title`."""
    dates_printed: int = 0
    dates_composed: int = 0
    dates_missing: int = 0
    date_disagreements: int = 0
    impossible_years: int = 0
    skipped_materials: int = 0
    """会議 under the listing's 「資料」 root. See `PROCEEDINGS_ROOT`."""
    """会議 whose printed year cannot be true — see `_council_year`."""
    unknown_block_codes: dict[int, int] = field(default_factory=dict)
    skipped_labels: dict[str, int] = field(default_factory=dict)

    def summary(self) -> list[str]:
        lines = [
            f"documents        : {self.documents}",
            f"speeches         : {self.speeches}",
            f"speakers unsplit : {self.unsplit_titles}",
            f"dates printed    : {self.dates_printed}",
            f"dates composed   : {self.dates_composed}",
            f"dates missing    : {self.dates_missing}",
            f"date disagreed   : {self.date_disagreements}",
            f"impossible years : {self.impossible_years}",
            f"資料 skipped      : {self.skipped_materials}",
        ]
        if self.unknown_block_codes:
            lines.append(f"unknown blocks   : {self.unknown_block_codes}")
        if self.skipped_labels:
            lines.append(f"skipped schedules: {self.skipped_labels}")
        return lines


class SspScraper(BaseScraper):
    """Drives one SSP tenant over its JSON API."""

    def __init__(self, config: SspConfig) -> None:
        self.config = config
        self.prefecture = config.prefecture
        self.robots_exempt = config.robots_exempt
        self.fetch_window = config.fetch_window
        self.contact = config.contact
        self.outcome = Outcome()
        self._sittings: dict[str, Sitting] = {}
        """Listing metadata by ref key. `MeetingRef` is deliberately cheap, and the
        committee and session of a sitting are known at listing time and nowhere
        in the transcript response."""

    def report(self) -> list[str]:
        return self.outcome.summary()

    # -- API -------------------------------------------------------------------

    def _api(self, client: PoliteClient, endpoint: str, **payload: Any) -> Any:
        url = f"{self.config.base_url}{API_ROOT}{endpoint}"
        page = client.post(url, json={"tenant_id": self.config.tenant_id, **payload})
        return _decode(page)

    def permalink(self, council_id: int, schedule_id: int) -> str:
        """The page a person would be given for this sitting.

        Never fetched — it is a client-side shell — but it is short, stable and
        the site's own link, which is what a record's identity has to be.
        """
        return (
            f"{self.config.base_url}tenant/{self.config.tenant}/MinuteView.html"
            f"?council_id={council_id}&schedule_id={schedule_id}"
        )

    # -- listing ---------------------------------------------------------------

    def councils(self, client: PoliteClient) -> list[Council]:
        """Every 会議 the tenant publishes, from one request."""
        data = self._api(client, "councils/index")
        wanted = set(self.config.years)
        out: list[Council] = []
        for block in data.get("councils", []):
            for year in block.get("view_years", []):
                view_year = int(year.get("view_year"))
                if wanted and view_year not in wanted:
                    continue
                for ctype in year.get("council_type", []):
                    names = tuple(
                        ctype[f"council_type_name{i}"]
                        for i in range(1, 6)
                        if ctype.get(f"council_type_name{i}")
                    )
                    if not names or names[0] != PROCEEDINGS_ROOT:
                        self.outcome.skipped_materials += len(ctype.get("councils", []))
                        continue
                    for item in ctype.get("councils", []):
                        council = Council(
                            council_id=int(item["council_id"]),
                            name=squash(item["name"]),
                            view_year=view_year,
                            type_names=names,
                        )
                        if council.is_plenary or self.config.committees:
                            out.append(council)
        out.sort(key=lambda c: -c.council_id)
        if not out:
            # An index that yields nothing looks exactly like one that was never
            # asked for — the project's quietest failure. A tenant with no 会議 at
            # all is never right: it is a wrong `tenant_id`, or a `years` list
            # naming nodes this tenant does not have.
            raise FetchError(
                f"{self.config.name}: councils/index returned no 会議 "
                f"(tenant_id={self.config.tenant_id}, years={self.config.years or 'all'})"
            )
        log.info("%s: %d 会議 listed", self.config.name, len(out))
        return out

    def sittings(self, client: PoliteClient, council: Council) -> Iterator[Sitting]:
        """The 号 inside one 会議.

        `get_schedule_all` rather than `get_schedule`: the same list, minus the
        roster that `get_schedule` repeats in full for every sitting — 650 bytes
        against 137KB for one 定例会, and the roster arrives with the transcript
        anyway. The price is that this one also lists the 目次, which is not a
        sitting; labels that do not end in 号 are skipped and counted.
        """
        data = self._api(client, "minutes/get_schedule_all", council_id=council.council_id)
        for item in data.get("schedules_and_materials", []):
            label = squash(item["name"])
            # A sitting is labelled by its date and its 号: 「06月17日-01号」, or
            # 「02月24日-一般質問及び質疑(代表)-02号」 on 福島. Both halves are needed.
            # Ending in 号 alone lets 山形's 「議第69号~議第93号」 through — a bill
            # list, with a date nowhere and no speaker — and starting with a date
            # alone lets the 目次 through.
            if not (label.endswith("号") and _SCHEDULE_LABEL.search(label)):
                kind = label.rsplit("-", 1)[-1] if "-" in label else label
                self.outcome.skipped_labels[kind] = self.outcome.skipped_labels.get(kind, 0) + 1
                continue
            yield Sitting(council=council, schedule_id=int(item["schedule_id"]), label=label)

    def list_meetings(self, client: PoliteClient) -> Iterator[MeetingRef]:
        for council in self.councils(client):
            for sitting in self.sittings(client, council):
                key = self.permalink(council.council_id, sitting.schedule_id)
                self._sittings[key] = sitting
                yield MeetingRef(
                    prefecture=self.prefecture,
                    url=key,  # type: ignore[arg-type]
                    date=self._listing_date(sitting),
                    title=f"{council.name} {sitting.label}",
                )

    def _listing_date(self, sitting: Sitting) -> date | None:
        """The date as the listing gives it: the 会議's year, the 号's month and day.

        Known at listing time, so `--since/--until` prune before a transcript is
        fetched. The document's own printed date wins later where it parses.
        """
        md = sitting.month_day
        if md is None:
            return None
        year = self._council_year(sitting.council)
        if year is None:
            return None
        month, day = md
        council_month = sitting.council.month
        # A 会議 named 「令和7年12月定例会」 can sit in January. Roll the year rather
        # than filing that sitting twelve months early.
        if council_month is not None and council_month >= 11 and month <= 4:
            year += 1
        try:
            return date(year, month, day)
        except ValueError:
            return None

    def _council_year(self, council: Council) -> int | None:
        """The year of a 会議, from its name unless the name cannot be true.

        熊本 names one 会議 「平成５７年　６月　定例会」. There is no 平成57年 — 平成
        ended at 31 — and the listing files it under 1982, which is 昭和57年. Read
        literally, the name dates that sitting to **2045**: a date 63 years out,
        in a corpus where nothing downstream would question it.

        So the name is checked against the node it hangs under. They disagree by
        a year legitimately and often (宮城 files 「平成　１年　１２月」 under 1990),
        and by more than that only when the name is wrong.
        """
        printed = council.year
        if printed is None:
            log.warning("council %d %r: no year in the name", council.council_id, council.name)
            return council.view_year
        if abs(printed - council.view_year) > 1:
            self.outcome.impossible_years += 1
            log.warning(
                "council %d %r: name says %d, listed under %d — taking the listing",
                council.council_id,
                council.name,
                printed,
                council.view_year,
            )
            return council.view_year
        return printed

    # -- fetching --------------------------------------------------------------

    def fetch_meeting(self, ref: MeetingRef, client: PoliteClient) -> Page:
        sitting = self._sittings.get(ref.key)
        if sitting is None:
            raise FetchError(f"no listing metadata for {ref.key}")
        url = f"{self.config.base_url}{API_ROOT}minutes/get_minute"
        return client.post(
            url,
            json={
                "tenant_id": self.config.tenant_id,
                "council_id": sitting.council.council_id,
                "schedule_id": sitting.schedule_id,
            },
        )

    def parse_meeting(self, ref: MeetingRef, page: Page) -> Meeting:
        sitting = self._sittings[ref.key]
        blocks = _decode(page).get("tenant_minutes", [])

        front_matter = "\n".join(
            _strip_pre(b.get("body") or "")
            for b in blocks
            if b.get("minute_type_code") in FRONT_MATTER_CODES
        )
        roster = read_roster(front_matter)

        speeches: list[Speech] = []
        for block in blocks:
            code = int(block.get("minute_type_code") or 0)
            if code not in KNOWN_CODES:
                self.outcome.unknown_block_codes[code] = (
                    self.outcome.unknown_block_codes.get(code, 0) + 1
                )
            if code not in SPEECH_CODES:
                continue
            title = block.get("title") or ""
            speaker, role = split_title(title, roster)
            if role is None and title.strip():
                self.outcome.unsplit_titles += 1
            text = _speech_text(block.get("body") or "", title)
            if not text:
                continue
            speeches.append(Speech(order=len(speeches), speaker=speaker, role=role, text=text))

        self.outcome.documents += 1
        self.outcome.speeches += len(speeches)
        return Meeting(
            prefecture=self.prefecture,
            url=ref.key,  # type: ignore[arg-type]
            date=self._date(sitting, front_matter, ref),
            session=sitting.council.name,
            committee=sitting.council.committee,
            title=sitting.label,
            speeches=speeches,
            retrieved_at=datetime.now(UTC),
            source_html_sha256=page.sha256,
        )

    def _date(self, sitting: Sitting, front_matter: str, ref: MeetingRef) -> date | None:
        """The listing's date, cross-checked against the one the document prints.

        The listing is the authority, which is the opposite of what this project
        usually concludes and 徳島 is why. Its 名簿 opens with the 告示 that
        convened the session —

            徳島県告示第三百三号
            令和八年六月徳島県議会定例会を次のとおり招集する。
              令和八年六月八日          <- the notice
              一 期日 令和八年六月十五日 <- the sitting

        — so the *first* date in the document is a week before the sitting, and
        「一つのラベルでは足りない」 applies to documents as much as to labels. The
        schedule label 「06月15日-01号」 is the vendor's own index of the sitting and
        agreed with the printed 期日 on every tenant checked.

        The printed date is kept as the check: a disagreement means either a
        mislabelled schedule or a 会議 year that `_council_year` could not catch,
        and `Outcome.date_disagreements` is where that shows up.
        """
        composed = ref.date
        printed = parse_japanese_date(front_matter)
        if printed and composed and printed != composed:
            self.outcome.date_disagreements += 1
            log.debug(
                "%s: listing says %s, the document's first date is %s",
                ref.key,
                composed,
                printed,
            )
        if composed:
            self.outcome.dates_composed += 1
            return composed
        if printed:
            self.outcome.dates_printed += 1
            return printed
        self.outcome.dates_missing += 1
        log.warning("%s: no date in the listing or the document", ref.key)
        return None


def _decode(page: Page) -> Any:
    """Parse an API response from the raw bytes.

    Not through `page.text`: the responses are `\\u`-escaped ASCII, so
    `sniff_encoding` concludes "ascii" — correct today, and wrong the moment the
    vendor stops escaping, at which point `errors="replace"` would quietly hand
    the corpus U+FFFD instead of names. `json.loads` reads the bytes per RFC 8259.
    """
    try:
        return json.loads(page.body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{page.url}: response is not JSON ({exc})") from exc


_PRE = re.compile(r"</?pre>", re.I)


def _strip_pre(body: str) -> str:
    return _PRE.sub("", body)


_MARKERS = "◆◎○△〇"


def _speech_text(body: str, title: str) -> str:
    """The words, without the marker line the body repeats.

    Each block's body opens with its own marker — 「◆二十三番（天下みゆき君）　天下
    みゆきです。」 — and `title` already carries that same information. Dropping it
    keeps the corpus comparable with the other five prefectures, where the marker
    is a boundary and never part of a speech.

    The title has to match for anything to be removed, so a body that opens some
    other way keeps every character. Note that this is the *opposite* risk from
    every other site here: there, a marker that fails to match swallows a speech
    into its neighbour; here, at worst, one line of a speech reads as a marker.
    """
    text = _strip_pre(body).strip()
    head = text.lstrip(_MARKERS)
    if head.startswith(title.strip()):
        return head[len(title.strip()) :].strip()
    return text
