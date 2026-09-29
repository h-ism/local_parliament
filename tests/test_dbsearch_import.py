"""Tests for the DB-Search manual-download importer.

The fixture is the shape of 山梨's 2026-02-03 臨時会 第１号, cut down: both marker
forms, a block with a 説明員 table appended after a 罫線, and a 目次 document.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prefectural_transcripts.importers.dbsearch import (
    DbSearchImporter,
    DocumentResult,
    _parse_header,
    decode,
    page_to_download,
    parse_document,
)

RULE = "　" * 7 + "─" * 20

BODY = f"""令和８年２月臨時会（第１号）　本文 : 2026-02-03
----------------------------------------------------------------
1:
◯議長（渡辺淳也君）ただいまから、令和八年二月山梨県議会臨時会を開会いたします。
　これより、本日の会議を開きます。
{RULE}

2:
◯議長（渡辺淳也君）次に、地方自治法第百二十一条の規定により、出席を求めました。
{RULE}
　　　地方自治法第百二十一条の規定に基づく説明員
　知　事　　長　崎　幸太郎　　副知事　　井　上　弘　之
{RULE}

3:
◯知事（長崎幸太郎君）提出いたしました案件につきまして、御説明申し上げます。

4:
◯水岸富美男君　自由民主党を代表して質問いたします。
　本年一月二十日、甲府地方裁判所において判決が示されました。

5:
◯飯島　修君　リベラル山梨の飯島修です。

6:
◯議長（渡辺淳也君）以上で本臨時会を閉会いたします。
　　　　　　　　　　午後零時二十八分閉会
"""

INDEX = """令和８年２月臨時会　　目次 : 2026-02-03
----------------------------------------------------------------
1:
　　　　　目　　次
　出　席　議　員　……………………………………一
"""


def parse(text: str = BODY, name: str = "20260203.txt") -> DocumentResult:
    return parse_document(text, prefecture="山梨県", source_file=name)


def test_reads_the_header():
    header = _parse_header("令和８年２月臨時会（第１号）　本文 : 2026-02-03")
    assert header.session == "令和８年２月臨時会"
    assert header.number == "第１号"
    assert header.kind == "本文"
    assert header.date.isoformat() == "2026-02-03"


def test_reads_a_header_with_no_number():
    header = _parse_header("令和８年２月臨時会　　目次 : 2026-02-03")
    assert header.session == "令和８年２月臨時会"
    assert header.number is None
    assert header.kind == "目次"


def test_rejects_a_line_that_is_not_a_header():
    with pytest.raises(ValueError, match="not a DB-Search header"):
        _parse_header("◯議長（渡辺淳也君）ただいまから、開会いたします。")


def test_index_documents_are_not_transcripts():
    result = parse(INDEX)
    assert result.meeting is None
    assert result.header.kind == "目次"


def test_splits_on_the_vendors_speech_numbers():
    meeting = parse().meeting
    assert meeting is not None
    assert len(meeting.speeches) == 6
    assert [s.order for s in meeting.speeches] == [0, 1, 2, 3, 4, 5]


def test_reads_the_bracketed_marker_form():
    first = parse().meeting.speeches[0]
    assert first.speaker == "渡辺淳也"
    assert first.role == "議長"
    assert first.text.startswith("ただいまから、")


def test_reads_the_bare_name_marker_form():
    """Both shapes appear in one sitting; a rule that knows one drops the other."""
    bare = parse().meeting.speeches[3]
    assert bare.speaker == "水岸富美男"
    assert bare.role is None
    assert bare.text.startswith("自由民主党")


def test_a_space_inside_a_name_is_not_a_second_speaker():
    assert parse().meeting.speeches[4].speaker == "飯島修"


def test_a_rule_line_ends_the_speech():
    """The 説明員 table after the 罫線 is an appended document, not the speaker."""
    result = parse()
    second = result.meeting.speeches[1]
    assert "説明員" not in second.text
    assert "長　崎" not in second.text
    assert second.text.endswith("出席を求めました。")
    assert result.trimmed >= 1


def test_an_unreadable_marker_costs_a_name_and_not_the_words():
    text = BODY.replace("◯知事（長崎幸太郎君）", "＊知事（長崎幸太郎君）")
    result = parse(text)
    assert len(result.meeting.speeches) == 6
    assert result.meeting.speeches[2].speaker == ""
    assert "＊知事" in result.meeting.speeches[2].text
    assert len(result.unattributed) == 1


def test_a_numeral_circle_is_not_a_speaker():
    """〇 opens a line as the numeral zero; it must not become a name."""
    text = BODY.replace("◯知事（長崎幸太郎君）", "〇〇年度の資料についてですが、")
    result = parse(text)
    assert result.meeting.speeches[2].speaker == ""
    assert len(result.unattributed) == 1


def test_gaps_in_the_speech_numbers_are_reported():
    gaps = parse(BODY.replace("\n4:\n", "\n9:\n")).gaps
    assert gaps
    assert "発言番号" in gaps[0]


def test_the_record_is_identified_by_its_file_not_a_url():
    meeting = parse().meeting
    assert meeting.url is None
    assert meeting.source_file == "20260203.txt"
    assert meeting.key == "file:20260203.txt"


def test_decodes_cp932():
    """The downloads are cp932; base Shift_JIS cannot hold 﨑 or 髙."""
    assert decode(BODY.encode("cp932")).startswith("令和８年２月臨時会")
    assert "河原﨑" in decode("河原﨑".encode("cp932"))


def test_crlf_line_endings_survive():
    meeting = parse(BODY.replace("\n", "\r\n")).meeting
    assert len(meeting.speeches) == 6
    assert "\r" not in meeting.speeches[0].text


def test_importer_skips_what_is_already_collected(tmp_path: Path):
    (tmp_path / "a.txt").write_bytes(BODY.encode("cp932"))
    importer = DbSearchImporter("山梨県")
    assert len(importer.import_paths([tmp_path / "a.txt"]).meetings) == 1
    outcome = importer.import_paths([tmp_path / "a.txt"], skip={"file:a.txt"})
    assert outcome.meetings == []


def test_importer_counts_index_documents_as_skipped(tmp_path: Path):
    (tmp_path / "body.txt").write_bytes(BODY.encode("cp932"))
    (tmp_path / "index.txt").write_bytes(INDEX.encode("cp932"))
    outcome = DbSearchImporter("山梨県").import_paths(sorted(tmp_path.glob("*.txt")))
    assert len(outcome.meetings) == 1
    assert outcome.skipped == {"目次": 1}
    assert "1 documents, 6 speeches" in outcome.summary()[0]


# -- 茨城: the same product, fetched as a page ---------------------------------

IBARAKI_PAGE = """<html><body>
<h1 class="logo"><img alt="茨城県議会"></h1>
<h1>令和８年土木企業立地推進常任委員会　  本文 2026-06-10</h1>
<h1>:</h1>
<ul>
<li class="voice-block voice_block d-none" data-voice_code="1"><div class="voice">
<div class="voice__detail">1:</div>
<p class="voice__text">　　　　　　　　　　　　　　　　午前10時29分開議<br/>
◯坂本委員長　ただいまから、土木企業立地推進委員会を開会いたします。<br/>
　　　　　───────────────────────────────<br/>
</p></div></li>
<li class="voice-block voice_block d-none" data-voice_code="2"><div class="voice">
<div class="voice__detail">2:</div>
<p class="voice__text">◯森田委員　二,三人じゃきかないですよ。パッと数えてもたくさんいる。<br/></p>
</div></li>
<li class="voice-block voice_block d-none" data-voice_code="3"><div class="voice">
<div class="voice__detail">3:</div>
<p class="voice__text">◯24番江尻加那議員　日本共産党の江尻加那です。<br/></p>
</div></li>
<li class="voice-block voice_block d-none" data-voice_code="4"><div class="voice">
<div class="voice__detail">4:</div>
<p class="voice__text">◯小野瀬書記<br/>　朗読いたします。<br/></p>
</div></li>
<li class="voice-block voice_block d-none" data-voice_code="5"><div class="voice">
<div class="voice__detail">5:</div>
<p class="voice__text">◯江尻委員今の知事の説明を多くの県民の皆さんが聞いています。<br/></p>
</div></li>
</ul></body></html>"""


def ibaraki() -> DocumentResult:
    return parse_document(page_to_download(IBARAKI_PAGE), prefecture="茨城県", source_file="x")


def test_a_fetched_page_reads_like_a_download():
    result = ibaraki()
    assert result.header.kind == "本文"
    assert result.header.date.isoformat() == "2026-06-10"
    assert result.header.session == "令和８年土木企業立地推進常任委員会"
    assert len(result.meeting.speeches) == 5


def test_a_bare_office_ends_at_the_space_and_not_at_the_next_honorific():
    # The honorific branch once read 「森田委員二,三人じゃ…たく」 as a speaker.
    speeches = ibaraki().meeting.speeches
    assert speeches[1].speaker == "森田委員"
    assert speeches[1].text.startswith("二,三人")


def test_the_chairs_first_words_are_not_lost_to_the_heading_above_them():
    first = ibaraki().meeting.speeches[0]
    assert first.speaker == "坂本委員長"
    assert "開議" not in first.text
    assert first.text.startswith("ただいまから")


def test_a_seat_number_is_the_role_not_a_reason_to_drop_the_name():
    third = ibaraki().meeting.speeches[2]
    assert (third.role, third.speaker) == ("24番", "江尻加那議員")


def test_a_marker_alone_on_its_line_still_names_the_speaker():
    assert ibaraki().meeting.speeches[3].speaker == "小野瀬書記"


def test_a_marker_with_no_space_costs_a_name_rather_than_inventing_one():
    result = ibaraki()
    last = result.meeting.speeches[4]
    assert last.speaker == ""
    assert "今の知事の説明" in last.text
    assert len(result.unattributed) == 1


def test_a_long_office_is_not_cut_off_by_a_length_bound():
    office = "木名瀬グローバル戦略チームリーダー兼Ｇ20貿易・デジタル経済大臣会合推進チームリーダー"
    page = IBARAKI_PAGE.replace("◯小野瀬書記<br/>", f"◯{office}　説明します。<br/>")
    speech = parse_document(
        page_to_download(page), prefecture="茨城県", source_file="x"
    ).meeting.speeches[3]
    assert speech.speaker.startswith("木名瀬グローバル戦略")
