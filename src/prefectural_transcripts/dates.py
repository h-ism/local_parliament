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
# Minutes printed before roughly the mid-2000s set their dates in 漢数字 —
# 「平成十二年十二月八日（金曜日）」 — and the same page numbers its sittings 「第二号」.
# 和歌山's archive switches form partway through, so both are needed for one site.
_KANJI_DIGITS = "〇零一二三四五六七八九十"
_WAREKI_KANJI = re.compile(
    rf"(令和|平成|昭和|大正|明治)\s*(元|[{_KANJI_DIGITS}]{{1,4}})\s*年"
    rf"\s*([{_KANJI_DIGITS}]{{1,3}})\s*月\s*([{_KANJI_DIGITS}]{{1,3}})\s*日"
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

    Handles 「令和7年6月10日」, 「平成十二年十二月八日」, 「R7.6.10」, 「2025年6月10日」,
    「2025-06-10」 and Domino's 「06/23/2025」 (month first). Full-width digits are
    matched by `\\d` and converted by `int`, so they need no separate pattern.
    """
    if not text:
        return None

    if m := _WAREKI.search(text):
        era, era_year, month, day = m.groups()
        year = 1 if era_year == "元" else int(era_year)
        return _safe_date(ERA_BASE[era] + year, int(month), int(day))

    if m := _WAREKI_KANJI.search(text):
        era, era_year, month, day = m.groups()
        year = 1 if era_year == "元" else kanji_to_int(era_year)
        parsed = _safe_date(ERA_BASE[era] + year, kanji_to_int(month), kanji_to_int(day))
        if parsed:
            return parsed

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


_KANJI_VALUE = dict(zip("〇一二三四五六七八九", range(10), strict=True)) | {"零": 0}


def kanji_to_int(text: str) -> int:
    """Read a 漢数字 in the range these dates use (1–99).

    Handles the positional 「十」 forms that actually occur — 十二 = 12,
    二十 = 20, 二十八 = 28 — and the digit-strung 「二〇二五」 form. Anything
    outside that raises, rather than returning a plausible wrong year.
    """
    text = text.strip()
    if not text:
        raise ValueError("empty 漢数字")
    if "十" not in text:
        # 「二〇二五」 — positionless digits, read left to right.
        return int("".join(str(_KANJI_VALUE[c]) for c in text))
    tens, _, units = text.partition("十")
    return (kanji_to_int(tens) if tens else 1) * 10 + (kanji_to_int(units) if units else 0)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
