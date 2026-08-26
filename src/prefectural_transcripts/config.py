"""Runtime settings.

Defaults are deliberately conservative: these are small public-sector servers and
a research crawl has no reason to be fast.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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
