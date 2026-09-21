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
    """Half-open [start, end) in `timezone`. `end` of 00:00 means midnight, the day's end."""

    reason: str
    """Whose instruction this is, in their words where possible."""

    decided_on: str
    timezone: str = "Asia/Tokyo"

    def __post_init__(self) -> None:
        if not self.days:
            raise ValueError("a fetch window must name at least one day")
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

    def allows(self, when: datetime) -> bool:
        local = when.astimezone(self.zone)
        if local.weekday() not in self.days:
            return False
        moment = local.time()
        if self.end == time(0, 0):
            return moment >= self.start
        return self.start <= moment < self.end

    def next_open(self, when: datetime) -> datetime:
        """When the window next opens, for a message a person can act on."""
        local = when.astimezone(self.zone)
        for ahead in range(8):
            day = (local + timedelta(days=ahead)).date()
            if day.weekday() not in self.days:
                continue
            opens = datetime.combine(day, self.start, tzinfo=self.zone)
            if opens >= local:
                return opens
            if ahead == 0 and self.allows(local):
                return local
        raise ValueError("a fetch window with no opening in the next week")

    def describe(self) -> str:
        names = [name for name, number in _WEEKDAYS.items() if number in self.days]
        end = "24:00" if self.end == time(0, 0) else self.end.strftime("%H:%M")
        return f"{'/'.join(names)} {self.start.strftime('%H:%M')}-{end} {self.timezone}"

    @classmethod
    def from_toml(cls, raw: Mapping[str, Any]) -> FetchWindow | None:
        """Read a `[fetch_window]` table from a site config; None when there is none."""
        if not raw:
            return None
        try:
            days = tuple(sorted(_WEEKDAYS[str(d).lower()[:3]] for d in raw["days"]))
            return cls(
                days=days,
                start=time.fromisoformat(str(raw["start"])),
                end=time.fromisoformat("00:00" if str(raw["end"]) == "24:00" else str(raw["end"])),
                reason=raw["reason"],
                decided_on=raw["decided_on"],
                timezone=raw.get("timezone", "Asia/Tokyo"),
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
