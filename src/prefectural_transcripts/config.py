"""Runtime settings.

Defaults are deliberately conservative: these are small public-sector servers and
a research crawl has no reason to be fast.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_CONTACT = "research-crawler@example.invalid"


def _default_root() -> Path:
    return Path(os.environ.get("PT_DATA_ROOT", Path.cwd()))


@dataclass(slots=True)
class Settings:
    """Crawl-wide settings, overridable from the CLI or PT_* env vars."""

    contact: str = os.environ.get("PT_CONTACT", DEFAULT_CONTACT)
    """Contact address embedded in the User-Agent so site operators can reach us."""

    min_interval: float = float(os.environ.get("PT_MIN_INTERVAL", "2.0"))
    """Minimum seconds between requests to the same host. robots.txt Crawl-delay wins if larger."""

    timeout: float = float(os.environ.get("PT_TIMEOUT", "30.0"))
    max_retries: int = int(os.environ.get("PT_MAX_RETRIES", "3"))
    respect_robots: bool = os.environ.get("PT_RESPECT_ROBOTS", "1") != "0"
    use_cache: bool = True

    offline: bool = os.environ.get("PT_OFFLINE", "0") == "1"
    """Serve only what is cached; a miss is an error rather than a request.

    The standing checks — `reparse.py`, `audit.py` — are described everywhere in
    this project as costing nothing because every response is cached. That was
    true by luck: a listing page that happened to be missing would have been
    fetched, and on 滋賀 or 石川 that could mean a request outside the hours they
    agreed to, from a script whose whole purpose is to read what we already have.
    With this set, such a miss says so instead.
    """

    cache_dir: Path = _default_root() / "cache"
    data_dir: Path = _default_root() / "data"

    @property
    def user_agent(self) -> str:
        from prefectural_transcripts import __version__

        return (
            f"prefectural-transcripts/{__version__} "
            f"(academic research crawler; contact: {self.contact})"
        )


@dataclass(frozen=True, slots=True)
class RobotsExemption:
    """A dated, reasoned exception to robots.txt, scoped to URL prefixes.

    `robots.txt` is one statement an operator makes, and not always the last one.
    山梨 taught this project that an answer can move a site into a different
    category altogether; SSP is the other direction — a blanket `Disallow: /`
    written by a vendor in 2024, over a system whose operator, asked directly,
    did not refuse.

    Acting on that is the researcher's call and not the crawler's, so the only way
    to make it is to write it down: which URL prefixes, on whose word, and when.
    `PT_RESPECT_ROBOTS=0` is the thing this exists to avoid — it is undated,
    unattributed, and applies to every site in the run.

    An exemption with no reason or no date is refused at load time rather than
    quietly honoured.
    """

    prefixes: tuple[str, ...]
    """Absolute URL prefixes the exemption covers. Nothing else is affected."""

    reason: str
    """Why, in the site config, where the next person will read it."""

    decided_on: str
    """ISO date the researcher decided. Not the date of the answer — the decision."""

    def __post_init__(self) -> None:
        if not self.prefixes:
            raise ValueError("a robots exemption must name at least one URL prefix")
        for prefix in self.prefixes:
            if not prefix.startswith(("http://", "https://")):
                raise ValueError(f"robots exemption prefix must be absolute: {prefix!r}")
        if not self.reason.strip():
            raise ValueError("a robots exemption must record why it exists")
        try:
            date.fromisoformat(self.decided_on)
        except ValueError as exc:
            raise ValueError(
                f"robots exemption needs decided_on as YYYY-MM-DD, got {self.decided_on!r}"
            ) from exc

    def covers(self, url: str) -> bool:
        return url.startswith(self.prefixes)

    @classmethod
    def from_toml(cls, raw: Mapping[str, Any]) -> RobotsExemption | None:
        """Read a `[robots]` table from a site config; None when there is none."""
        if not raw:
            return None
        try:
            return cls(
                prefixes=tuple(raw["exempt"]),
                reason=raw["reason"],
                decided_on=raw["decided_on"],
            )
        except KeyError as exc:
            raise ValueError(
                f"a [robots] table needs exempt, reason and decided_on; missing {exc}"
            ) from exc


_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


@dataclass(frozen=True, slots=True)
class FetchWindow:
    """The days and hours an operator has restricted fetching to.

    滋賀県議会事務局, answering on 2026-09-18, permitted collection and asked for
    one thing in return: 「取得の時間帯を土日の夜間帯（20時以降）に限定するよう
    お願い申し上げます」. That is a condition on a permission, not a refusal, and it
    is the first of its kind this project has been given.

    It lives here rather than in a runbook because a promise about *when* fails
    the same way a promise about *how fast* would: silently, and only in the
    logs of the person who was inconvenienced. A window in the site config is
    checked before every request, says in the config whose instruction it is,
    and refuses rather than drifting.
    """

    days: tuple[int, ...]
    """Weekdays the window is open, Monday = 0, as `datetime.weekday()` numbers them."""

    start: time
    end: time
    """Half-open [start, end) in `timezone`, and it may cross midnight.

    「20時以降」 with nothing after it is `20:00`–`24:00`: an `end` of 00:00 means
    the day's end. 「業務時間帯を避ける」 is `20:00`–`07:00`, which runs past
    midnight — so when `start` is later than `end` the window is the two pieces
    either side of it. Reading that as an empty interval would refuse every
    request and look like a bug in the crawler rather than a misread promise.
    """

    reason: str
    """Whose instruction this is, in their words where possible."""

    decided_on: str
    timezone: str = "Asia/Tokyo"

    holidays: tuple[date, ...] = ()
    """Dates the window also opens on, whatever their weekday.

    北海道 (2026-09-30) said 「土日祝の夜間帯」. Public holidays are listed as
    dates rather than computed: the operator's calendar is what counts, a list
    in the config can be checked against it, and a holiday library would be one
    more thing to be wrong in silence.
    """

    first_day: date | None = None
    last_day: date | None = None
    """The period the permission covers, inclusive, judged by the evening a
    window opens on. 北海道: 「閉会後の10月3日（土）から第４回定例会が始まる
    11月24日（火）までの間」. Outside it the window never opens — and says so,
    rather than naming a next opening that the permission does not reach."""

    def __post_init__(self) -> None:
        if not self.days and not self.holidays:
            raise ValueError("a fetch window must name at least one day")
        if self.first_day and self.last_day and self.first_day > self.last_day:
            raise ValueError("a fetch window's first_day is after its last_day")
        if not self.reason.strip():
            raise ValueError("a fetch window must record whose instruction it is")
        try:
            date.fromisoformat(self.decided_on)
        except ValueError as exc:
            raise ValueError(
                f"fetch window needs decided_on as YYYY-MM-DD, got {self.decided_on!r}"
            ) from exc
        ZoneInfo(self.timezone)

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def opens_on(self, day: date) -> bool:
        """Whether the window opens on this day's evening (or morning, if not wrapping)."""
        if self.first_day and day < self.first_day:
            return False
        if self.last_day and day > self.last_day:
            return False
        return day.weekday() in self.days or day in self.holidays

    def allows(self, when: datetime) -> bool:
        local = when.astimezone(self.zone)
        moment = local.time()
        if self.end == time(0, 0):
            return self.opens_on(local.date()) and moment >= self.start
        if self.start < self.end:
            return self.opens_on(local.date()) and self.start <= moment < self.end
        # Crosses midnight: the evening belongs to `days`, and the small hours
        # after it belong to the evening that opened them — a window that opens
        # on Saturday at 20:00 is still open at 01:00 on Sunday.
        if moment >= self.start:
            return self.opens_on(local.date())
        if moment < self.end:
            return self.opens_on((local - timedelta(days=1)).date())
        return False

    def next_open(self, when: datetime) -> datetime:
        """When the window next opens. Raises if it never does again."""
        local = when.astimezone(self.zone)
        if self.allows(local):
            return local
        # A year ahead, not a week: 北海道's period opens weeks after it was
        # given, and a holiday-only window may be a month between openings.
        for ahead in range(370):
            day = (local + timedelta(days=ahead)).date()
            if not self.opens_on(day):
                continue
            opens = datetime.combine(day, self.start, tzinfo=self.zone)
            if opens >= local:
                return opens
        raise ValueError("this fetch window does not open again")

    def next_opening(self, when: datetime) -> str:
        """`next_open` as a sentence a person can act on — including "never"."""
        try:
            return f"next window opens {self.next_open(when):%Y-%m-%d %H:%M %Z}"
        except ValueError:
            return (
                f"the agreed period ended on {self.last_day}; the window does not open "
                "again without a new answer from the operator"
            )

    def describe(self) -> str:
        names = [name for name, number in _WEEKDAYS.items() if number in self.days]
        days = "every day" if len(self.days) == 7 else "/".join(names)
        end = "24:00" if self.end == time(0, 0) else self.end.strftime("%H:%M")
        wrap = " (past midnight)" if self.start > self.end != time(0, 0) else ""
        extra = f" + {len(self.holidays)} holiday(s)" if self.holidays else ""
        period = ""
        if self.first_day or self.last_day:
            period = f", {self.first_day or '…'} to {self.last_day or '…'}"
        return f"{days}{extra} {self.start.strftime('%H:%M')}-{end}{wrap} {self.timezone}{period}"

    @classmethod
    def from_toml(cls, raw: Mapping[str, Any]) -> FetchWindow | None:
        """Read a `[fetch_window]` table from a site config; None when there is none."""
        if not raw:
            return None
        try:
            days = tuple(sorted(_WEEKDAYS[str(d).lower()[:3]] for d in raw["days"]))
            first, last = raw.get("first_day"), raw.get("last_day")
            return cls(
                days=days,
                start=time.fromisoformat(str(raw["start"])),
                end=time.fromisoformat("00:00" if str(raw["end"]) == "24:00" else str(raw["end"])),
                reason=raw["reason"],
                decided_on=raw["decided_on"],
                timezone=raw.get("timezone", "Asia/Tokyo"),
                holidays=tuple(date.fromisoformat(str(d)) for d in raw.get("holidays", [])),
                first_day=date.fromisoformat(str(first)) if first else None,
                last_day=date.fromisoformat(str(last)) if last else None,
            )
        except KeyError as exc:
            raise ValueError(
                "a [fetch_window] table needs days, start, end, reason and "
                f"decided_on; missing {exc}"
            ) from exc


@dataclass(frozen=True, slots=True)
class Contact:
    """Who one site's operator should be able to reach, when it is not the default.

    `PT_CONTACT` is the project's address and goes in every User-Agent. 滋賀 is the
    first site where that is the wrong one: the enquiry it answered on 2026-09-18
    was made by a collaborator, so the address the
    secretariat has on file — and would reply to if the crawl troubled them — is
    theirs, not this project's.

    Writing it into the site config rather than exporting a different `PT_CONTACT`
    for that run is the same decision as `FetchWindow`: the third undertaking in
    that letter was 「User-Agent に研究用である旨と当方の連絡先を明記します」, and an
    undertaking someone has to remember to re-export is one that will be wrong on
    a Tuesday afternoon with nothing to show for it.
    """

    address: str
    """What goes in the User-Agent — an address the operator can actually reach."""

    note: str = ""
    """Why this site differs: whose enquiry it was, and when it was answered."""

    def __post_init__(self) -> None:
        if "@" not in self.address and not self.address.startswith("http"):
            raise ValueError(
                f"a site contact must be an address an operator can use, got {self.address!r}"
            )

    @classmethod
    def from_toml(cls, raw: Mapping[str, Any]) -> Contact | None:
        """Read a `[contact]` table from a site config; None when there is none."""
        if not raw:
            return None
        try:
            return cls(address=raw["address"], note=raw.get("note", ""))
        except KeyError as exc:
            raise ValueError(f"a [contact] table needs an address; missing {exc}") from exc


@dataclass(frozen=True, slots=True)
class Notice:
    """An operator who asked to be told *before* a run, and what we last told them.

    栃木県議会事務局 permitted collection on 2026-09-24 and asked for the timing in
    advance. That obligation cannot be met by the crawler — somebody has to send
    an email — but it can be made impossible to forget: the config records when
    we last told them and what period we said we would run in, and a run outside
    that period refuses to start.

    It is the same shape as `RobotsExemption` and `FetchWindow`, for the same
    reason: an undertaking that lives in someone's memory is an undertaking that
    will be broken on a Tuesday afternoon with nothing to show for it.
    """

    who: str
    """Who was told, in their own words — 「栃木県議会事務局 議事課」."""

    last_sent: str = ""
    """ISO date the notice went out. Empty means **promised and not yet sent**:
    the table exists so that a config for an operator who asked to be told
    cannot be written without it — leaving `[notice]` out would let the run go
    ahead unannounced, which is the failure this class exists to prevent."""

    covers_until: str = ""
    """ISO date the notice said we would be finished by. Past it, this refuses."""

    what: str = ""
    """What the notice said, so the next person can send the same thing again."""

    def __post_init__(self) -> None:
        if not self.who.strip():
            raise ValueError("a notice must record who was told")
        if not self.last_sent and not self.covers_until:
            return  # owed, not sent: covers nothing
        for field_name, value in (
            ("last_sent", self.last_sent),
            ("covers_until", self.covers_until),
        ):
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"notice {field_name} must be YYYY-MM-DD, got {value!r}") from exc
        if date.fromisoformat(self.covers_until) < date.fromisoformat(self.last_sent):
            raise ValueError("a notice cannot cover a period before it was sent")

    @property
    def sent(self) -> bool:
        return bool(self.last_sent)

    def covers(self, when: date) -> bool:
        if not self.sent:
            return False
        return date.fromisoformat(self.last_sent) <= when <= date.fromisoformat(self.covers_until)

    def describe(self) -> str:
        if not self.sent:
            return f"{self.who} is owed notice before any run, and none has been sent"
        return f"told {self.who} on {self.last_sent}, covering until {self.covers_until}"

    @classmethod
    def from_toml(cls, raw: Mapping[str, Any]) -> Notice | None:
        """Read a `[notice]` table from a site config; None when there is none."""
        if not raw:
            return None
        try:
            return cls(
                who=raw["who"],
                last_sent=str(raw.get("last_sent", "")),
                covers_until=str(raw.get("covers_until", "")),
                what=raw.get("what", ""),
            )
        except KeyError as exc:
            raise ValueError(
                f"a [notice] table needs who (and last_sent, covers_until once sent); missing {exc}"
            ) from exc
