"""Date parsing for Japanese assembly pages.

These sites almost always print dates in 和暦 (era years) — 「令和7年6月10日」 —
and occasionally in western years. Both forms show up on the same site, so parsing
is centralised here rather than duplicated into every site config.
"""

from __future__ import annotations

import re
from datetime import date

# First year of each era, so 令和N年 == 2018 + N.
ERA_BASE = {
    "令和": 2018,
    "平成": 1988,
    "昭和": 1925,
    "大正": 1911,
    "明治": 1867,
    "R": 2018,
    "H": 1988,
    "S": 1925,
}

_WAREKI = re.compile(
    r"(令和|平成|昭和|大正|明治|[RHS])\s*(元|\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)
_WAREKI_NUMERIC = re.compile(r"([RHS])\s*(\d{1,2})[./-](\d{1,2})[./-](\d{1,2})")
_SEIREKI = re.compile(r"(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?")
# Lotus Domino prints its date fields as MM/DD/YYYY (静岡 does this). Tried last,
# after the year-first forms, so it can never steal a match from them. Day-first
# readings are NOT accepted: a site that means DD/MM would need its own pattern,
# because the two are indistinguishable for the first twelve days of a month.
_US_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def parse_japanese_date(text: str) -> date | None:
    """Extract the first date found in `text`, or None.

    Handles 「令和7年6月10日」, 「R7.6.10」, 「2025年6月10日」, 「2025-06-10」 and
    Domino's 「06/23/2025」 (month first).
    """
    if not text:
        return None

    if m := _WAREKI.search(text):
        era, era_year, month, day = m.groups()
        year = 1 if era_year == "元" else int(era_year)
        return _safe_date(ERA_BASE[era] + year, int(month), int(day))

    if m := _WAREKI_NUMERIC.search(text):
        era, era_year, month, day = m.groups()
        return _safe_date(ERA_BASE[era] + int(era_year), int(month), int(day))

    if m := _SEIREKI.search(text):
        western, month, day = m.groups()
        return _safe_date(int(western), int(month), int(day))

    if m := _US_SLASH.search(text):
        month, day, western = m.groups()
        return _safe_date(int(western), int(month), int(day))

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
