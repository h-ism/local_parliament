"""The 滋賀・石川 committee sample: spread over years, rotating committees."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from prefectural_transcripts.models import MeetingRef

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from sample_committees import committee_of, spread  # noqa: E402


def _ref(title: str, when: date | None = None, n: int = 0) -> MeetingRef:
    return MeetingRef(prefecture="滋賀県", url=f"https://e.invalid/{n}", date=when, title=title)


def test_the_committee_is_read_past_a_padded_date_and_a_session() -> None:
    assert committee_of(_ref("平成２４年　９月１２日政策・土木交通常任委員会 09月12日-01号")) == (
        "政策・土木交通常任委員会"
    )
    assert committee_of(_ref("令和　８年　２月定例会議 予算特別委員会 03月05日-01号")) == (
        "予算特別委員会"
    )


def test_every_year_is_sampled_and_no_committee_is_the_sample() -> None:
    refs = [
        _ref(f"平成{y}年 {c}委員会 x", date(y, 6, i + 1), n=y * 100 + ord(c) * 10 + i)
        for y in (2001, 2002, 2003)
        for c in "ABC"
        for i in range(3)
    ]
    picked = spread(refs, per_year=2)
    assert sorted({r.date.year for r in picked if r.date}) == [2001, 2002, 2003]
    assert sorted(committee_of(r) for r in picked) == sorted(["A委員会", "B委員会", "C委員会"] * 2)
    # The same listing gives the same sample, so a run cut short resumes it.
    assert [r.url for r in spread(refs, per_year=2)] == [r.url for r in picked]
