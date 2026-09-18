"""Runtime settings.

Defaults are deliberately conservative: these are small public-sector servers and
a research crawl has no reason to be fast.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

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
