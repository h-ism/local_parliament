from datetime import date

import pytest

from prefectural_transcripts.dates import kanji_to_int, parse_japanese_date


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


def test_parses_domino_month_first_slashes() -> None:
    # 静岡's minutes app prints its 質問日 field this way.
    assert parse_japanese_date("質問日： 06/23/2025") == date(2025, 6, 23)
    assert parse_japanese_date("12/01/1999") == date(1999, 12, 1)


def test_year_first_forms_still_win_over_slashes() -> None:
    assert parse_japanese_date("2025/6/10") == date(2025, 6, 10)
    assert parse_japanese_date("令和7年6月10日（06/10/2025）") == date(2025, 6, 10)


def test_impossible_month_first_date_is_rejected() -> None:
    assert parse_japanese_date("23/06/2025") is None


def test_parses_kanji_numeral_wareki_dates() -> None:
    """Minutes printed before the mid-2000s set dates in 漢数字 (和歌山's archive)."""
    assert parse_japanese_date("平成十二年十二月八日（金曜日）") == date(2000, 12, 8)
    assert parse_japanese_date("平成十二年十二月一日") == date(2000, 12, 1)
    # 兵庫's archive starts here, so the era arithmetic matters beyond 平成.
    assert parse_japanese_date("昭和六十一年三月三十一日") == date(1986, 3, 31)
    assert parse_japanese_date("令和元年五月一日") == date(2019, 5, 1)


def test_kanji_dates_do_not_displace_arabic_ones() -> None:
    """The 漢数字 pattern is tried after the ordinary one and must not steal it."""
    assert parse_japanese_date("令和7年6月10日") == date(2025, 6, 10)
    # Full-width digits need no pattern of their own: `\d` matches them.
    assert parse_japanese_date("令和６年６月19日（水曜日）") == date(2024, 6, 19)


def test_kanji_to_int_reads_the_positional_forms() -> None:
    assert [kanji_to_int(s) for s in ("十", "十二", "二十", "二十八", "三十一", "六十一")] == [
        10,
        12,
        20,
        28,
        31,
        61,
    ]
    # 「二〇二五」 — digits strung positionlessly, which older headers also use.
    assert kanji_to_int("二〇二五") == 2025
