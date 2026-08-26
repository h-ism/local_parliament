from datetime import date

import pytest

from prefectural_transcripts.dates import parse_japanese_date


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("令和7年6月10日", date(2025, 6, 10)),
        ("令和元年5月1日", date(2019, 5, 1)),
        ("平成31年4月30日", date(2019, 4, 30)),
        ("昭和64年1月7日", date(1989, 1, 7)),
        ("R7.6.10", date(2025, 6, 10)),
        ("2025年6月10日", date(2025, 6, 10)),
        ("2025-06-10", date(2025, 6, 10)),
        ("開会 令和7年 6月 10日 午前十時", date(2025, 6, 10)),
    ],
)
def test_parses_known_forms(text: str, expected: date) -> None:
    assert parse_japanese_date(text) == expected


@pytest.mark.parametrize("text", ["", "第2回定例会", "令和7年13月45日"])
def test_returns_none_when_no_valid_date(text: str) -> None:
    assert parse_japanese_date(text) is None


def test_wareki_is_preferred_over_a_stray_number() -> None:
    # A page header often carries both an era date and an unrelated 4-digit id.
    assert parse_japanese_date("議案1234 令和6年12月3日") == date(2024, 12, 3)
