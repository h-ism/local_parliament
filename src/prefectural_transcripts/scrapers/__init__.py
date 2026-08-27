"""Scraper registry.

A scraper is a TOML file in `prefectural_transcripts/sites/`. Files beginning
with `_` are templates and are not registered.

Most sites are selectors, so a config drives `GenericScraper` and that is the
default. A config may instead name a `scraper =` for a site that genuinely cannot
be expressed that way — see `kensakusystem.py` for the one case so far, and the
reasons it earned an exception.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path

from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import GenericScraper, SiteConfig
from prefectural_transcripts.scrapers.kensakusystem import (
    KensakuConfig,
    KensakuSystemScraper,
)

SITES_DIR = Path(__file__).resolve().parent.parent / "sites"

__all__ = [
    "BaseScraper",
    "GenericScraper",
    "KensakuConfig",
    "KensakuSystemScraper",
    "SiteConfig",
    "available_sites",
    "load_scraper",
]


def _generic(path: Path) -> BaseScraper:
    return GenericScraper(SiteConfig.from_toml(path))


def _kensakusystem(path: Path) -> BaseScraper:
    return KensakuSystemScraper(KensakuConfig.from_toml(path))


SCRAPERS: dict[str, Callable[[Path], BaseScraper]] = {
    "generic": _generic,
    "kensakusystem": _kensakusystem,
}


def available_sites(sites_dir: Path | None = None) -> dict[str, Path]:
    """Map scraper name -> config path, sorted by name."""
    directory = sites_dir or SITES_DIR
    if not directory.is_dir():
        return {}
    return {p.stem: p for p in sorted(directory.glob("*.toml")) if not p.name.startswith("_")}


def load_scraper(name: str, sites_dir: Path | None = None) -> BaseScraper:
    sites = available_sites(sites_dir)
    if name not in sites:
        known = ", ".join(sites) or "(none configured)"
        raise KeyError(f"no scraper named {name!r}; available: {known}")
    path = sites[name]
    kind = tomllib.loads(path.read_text(encoding="utf-8")).get("scraper", "generic")
    if kind not in SCRAPERS:
        raise ValueError(f"{path}: unknown scraper {kind!r}; known: {', '.join(SCRAPERS)}")
    return SCRAPERS[kind](path)
