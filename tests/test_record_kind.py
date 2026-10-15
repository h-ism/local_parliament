"""Records that are not verbatim are kept, as what they are (decided 2026-10-15).

A 要点筆記 or 要点記録 attributes words to a person without being that person's
words. These tests pin the three things that keep it from being counted as speech:
the passage says what it is, a record made of nothing else says so too, and the
store files such a record apart from the transcripts.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from prefectural_transcripts.models import Meeting, Speech
from prefectural_transcripts.scrapers.generic import split_speeches
from prefectural_transcripts.scrapers.ssp import SspConfig, SspScraper, parse_committee_record
from prefectural_transcripts.storage import SpeechCsvWriter, TranscriptStore, read_meetings


def _config() -> SspConfig:
    return SspConfig(
        prefecture="秋田県",
        tenant="prefakita",
        tenant_id=1,
        base_url="https://ssp.kaigiroku.net/",
    )


def _meeting(url: str, *kinds: str) -> Meeting:
    return Meeting(
        prefecture="和歌山県",
        url=url,
        speeches=[
            Speech(order=i, speaker="玄素", text="開会します。", kind=kind)  # type: ignore[arg-type]
            for i, kind in enumerate(kinds)
        ],
        retrieved_at=datetime.now(UTC),
    )


def test_a_record_is_a_summary_only_when_every_passage_is() -> None:
    assert _meeting("https://example.invalid/1", "summary", "summary").kind == "summary"
    # 兵庫: the chair's 「発言の概要」 inside a sitting that is otherwise verbatim.
    assert _meeting("https://example.invalid/2", "verbatim", "summary").kind == "verbatim"
    assert _meeting("https://example.invalid/3").kind == "verbatim"


def test_kind_survives_a_round_trip_and_cannot_disagree_with_the_passages() -> None:
    record = json.loads(_meeting("https://example.invalid/1", "summary").model_dump_json())
    assert record["kind"] == "summary"
    assert record["speeches"][0]["kind"] == "summary"

    # Written before the field existed: everything reads back as verbatim.
    del record["kind"], record["speeches"][0]["kind"]
    assert Meeting.model_validate(record).kind == "verbatim"


def test_a_summary_record_is_stored_apart_from_the_transcripts(tmp_path: Path) -> None:
    with TranscriptStore(tmp_path, "和歌山県") as store:
        store.write(_meeting("https://example.invalid/1", "verbatim"))
        store.write(_meeting("https://example.invalid/2", "summary"))

    assert store.summary == tmp_path / "summary" / "和歌山県.jsonl"
    assert [str(m.url) for m in read_meetings(store.path)] == ["https://example.invalid/1"]
    assert [str(m.url) for m in read_meetings(store.summary)] == ["https://example.invalid/2"]
    assert store.written == {"verbatim": 1, "summary": 1}
    # Resume must see both, or a summary would be fetched again on every run.
    assert TranscriptStore(tmp_path, "和歌山県").seen_keys() == {
        "https://example.invalid/1",
        "https://example.invalid/2",
    }


def test_the_csv_follows_the_jsonl_and_says_what_each_row_is(tmp_path: Path) -> None:
    with SpeechCsvWriter(tmp_path, "兵庫県") as writer:
        writer.write(_meeting("https://example.invalid/1", "verbatim", "summary"))
        writer.write(_meeting("https://example.invalid/2", "summary"))

    with writer.path.open(encoding="utf-8-sig") as fh:
        assert [row["kind"] for row in csv.DictReader(fh)] == ["verbatim", "summary"]
    with writer.summary.open(encoding="utf-8-sig") as fh:
        assert [row["kind"] for row in csv.DictReader(fh)] == ["summary"]


# 和歌山's committees: 要点筆記 markers, and a transcript marker the same site
# uses for 令和8年's 総括質疑.
WAKAYAMA = r"""(?xm)
  ^ (?: ●  (?P<speaker>[^\n]{0,24}?) (?:説明)? $
      | (?P<role2>[ＱＡ]) [^\S\n]+ (?P<speaker2>[^\n]{1,30}?) $
      | ○  (?P<speaker3>[^\n 　]{1,20}?) [ 　]
    )"""


def test_a_summary_marker_marks_its_passage_and_nothing_else() -> None:
    text = (
        "●玄素委員長\n◎開会宣告\n"
        "Ｑ　谷口委員\n防災対策について伺う。\n"
        "Ａ　平田人事委員会委員長\n検討している。\n"
        "○濱口委員長　山家委員。\n"
    )
    speeches = split_speeches(text, WAKAYAMA, summary="^[●ＱＡ]")

    assert [(s.speaker, s.kind) for s in speeches] == [
        ("玄素委員長", "summary"),
        ("谷口委員", "summary"),
        ("平田人事委員会委員長", "summary"),
        ("浜口委員長", "verbatim"),  # 常用漢字, as every speaker is
    ]
    assert all(s.kind == "verbatim" for s in split_speeches(text, WAKAYAMA))


# 秋田's 議会運営委員会: no speech block, a 要点記録 in 議題 blocks.
def _block(code: int, title: str, body: str) -> dict[str, object]:
    return {"minute_type_code": code, "title": title, "body": f"<pre>{body}</pre>"}


def test_a_sitting_recorded_only_as_a_yoten_kiroku_becomes_a_summary_record() -> None:
    blocks = [
        _block(2, "（名簿）", "議会運営委員会会議録（第１７回）\n◯協議事項\n　１　条例案について"),
        _block(
            3,
            "協議事項",
            "△協議事項　\n１　条例案について\n　　総務課長から資料１により説明があり、了承された。",
        ),
        _block(3, "その他", "△その他　\n　・　日程について\n　　委員長が諮り、了承された。"),
    ]
    passages = SspScraper(_config())._summary_record(blocks)

    assert [p.kind for p in passages] == ["summary", "summary"]
    assert passages[0].speaker == ""
    assert passages[0].text.startswith("△協議事項")


def test_an_order_paper_is_not_a_summary() -> None:
    # 秋田's 予算特別委員会 that only refers bills to 分科会: a list, no sentence.
    blocks = [_block(3, "議題", "△議案第１号\n　令和６年度秋田県一般会計補正予算（第５号）")]
    scraper = SspScraper(_config())

    assert scraper._summary_record(blocks) == []
    assert scraper.outcome.summary_documents == 0


def test_a_record_indented_with_ascii_spaces_is_still_read() -> None:
    # 神奈川's 平成17年 決算特別委員会: a 36,520-character 意見発表 that read as no
    # speech at all, because its lines open with two ASCII spaces, not U+3000.
    record = (
        "４　意見発表\n\nしきだ委員\n"
        "  私は、賛成の立場から意見を述べさせていただきます。\n"
        "  平成15年度の本県財政については、\n"
    )
    assert parse_committee_record(record) == [
        (
            "しきだ委員",
            "私は、賛成の立場から意見を述べさせていただきます。\n平成15年度の本県財政については、",
        )
    ]
