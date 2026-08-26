"""Scraper registry.

A scraper is a TOML file in `prefectural_transcripts/sites/`. Files beginning
with `_` are templates and are not registered.
"""

from __future__ import annotations

from pathlib import Path

from prefectural_transcripts.scrapers.base import BaseScraper
from prefectural_transcripts.scrapers.generic import GenericScraper, SiteConfig

SITES_DIR = Path(__file__).resolve().parent.parent / "sites"

__all__ = ["BaseScraper", "GenericScraper", "SiteConfig", "available_sites", "load_scraper"]


def available_sites(sites_dir: Path | None = None) -> dict[str, Path]:
    """Map scraper name -> config path, sorted by name."""
    directory = sites_dir or SITES_DIR
    if not directory.is_dir():
        return {}
    return {p.stem: p for p in sorted(directory.glob("*.toml")) if not p.name.startswith("_")}


def load_scraper(name: str, sites_dir: Path | None = None) -> GenericScraper:
    sites = available_sites(sites_dir)
    if name not in sites:
        known = ", ".join(sites) or "(none configured)"
        raise KeyError(f"no scraper named {name!r}; available: {known}")
    return GenericScraper(SiteConfig.from_toml(sites[name]))
