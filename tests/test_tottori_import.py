"""鳥取's 本会議 delivery (2026-10-14): the export and the secretariat's own files.

Fixtures copy the shapes of the delivered files, trimmed, written as cp932 the
way they arrived. Offline: nothing here reads beyond tmp_path.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

from prefectural_transcripts.importers.tottori import (
    import_tree,
    rtf_text,
    speaker_of,
    split_speeches,
)

EXPORT = """2007年02月19日：平成19年２月定例会（第２号）　本文

　　　　　　　午前10時02分開議
◯議長（山根英明君）おはようございます。
　これより、代表質問を行っていただきます。
　35番中尾享議員


◯35番（中尾享君）（登壇、拍手）皆さんおはようございます。
　───────────────────────────────────────────────────────────
　次に、関西広域連合についてお尋ねします。


◯議長（山根英明君）暫時休憩いたします。
　　　　　　　午前11時50分休憩
　　　────────────────
　　　　　　　午後１時00分再開


◯議長（山根英明君）議席は、お手元に配付の議席表のとおり指定いたします。
　　　────────────────
〔参照〕
　１番　興　治　英　夫
　　　────────────────
　次に、会議録署名議員の指名をいたします。


◯副議長（斉木正一君）暫時休憩をいたします。
　　　────────────────
　皆様に申し上げます。
　黙祷。


◯議長（野田修君）


◯知事（平井伸治君）（登壇）お答えします。
　これをもって散会いたします。
　　　　　　　午後４時17分散会
　　　────────────────
"""

HANDMADE = """平成１５年６月定例\t鳥取県議会会議録\t第２号　　１０

平成１５年６月１２日（木曜日）
　出席議員（３７名）
\t１　番\t興　治　英　夫\t

午前１０時０３分開議
○議長（前田宏君）ただいまから本日の会議を開きます。
○３６番　（小谷茂君）知事、なるほど説明はよくわかりました。
　これをもって散会いたします。
午後５時１０分散会
"""

COMBINED = (
    "平成１８年\n鳥取県議会会議録　目　　次\n●１１月２７日（第１号）\n"
    "平成１８年\n１１月定例\n鳥取県議会会議録\n第　１　号\n平成１８年１１月２７日（月曜日）\n"
    "○議長（鉄永幸紀君）ただいまから開会いたします。\n午前１０時３０分散会\n"
    "平成１８年\n１１月定例\n鳥取県議会会議録\n第　２　号\n平成１８年１１月２９日（水曜日）\n"
    "○知事（片山善博君）（登壇）これより、" + "あ" * 60 + "御説明いたし\n"
    "ます。\n"
    "○議長（鉄永幸紀君）散会いたします。\n午後３時００分散会\n"
)

WRAPPED = (
    "        　　　　　　　午前11時16分\n"
    "        ○臨時議長（浜崎芳宏君）ただいま、御紹介にあずかりました浜崎でござい\n"
    "        ます。\n"
    "        　何とぞよろしくお願い申し上げます。\n"
)


def _cocoa_rtf(paragraphs: list[str]) -> bytes:
    """What TextEdit saves: \\uN for every non-ASCII character, U+2028 inside a paragraph."""

    def esc(t: str) -> str:
        return "".join(c if ord(c) < 128 else f"\\u{ord(c)} " for c in t)

    head = (
        "{\\rtf1\\ansi\\ansicpg932\\cocoartf2869\n"
        "{\\fonttbl\\f0\\froman\\fcharset0 Times-Roman;}\n"
        "{\\colortbl;\\red255\\green255\\blue255;}\n"
        "{\\*\\expandedcolortbl;;\\cssrgb\\c0\\c0\\c0;}\n"
        "\\pard\\pardeftab720\\partightenfactor0\n\n\\f0\\fs24 \\cf0 \\uc0"
    )
    body = "\\\n\\pard\\pardeftab720\\partightenfactor0\n\\cf3 \\strokec3 \\\n\\cf0 ".join(
        esc(x) for x in paragraphs
    )
    return (head + body + "\\\n}").encode("ascii")


RTF = [
    "午前10時00分開会\u2028◯議長（野田修君）ただいまから開会いたします。",
    "◯知事（平井伸治君）（登壇）本定例県議会に提案いたしました。\u2028\u3000よろしくお願いします。",
    "◯議長（野田修君）これをもって散会いたします。\u2028\u3000\u3000午前10時19分散会"
    "\u2028\u3000\u3000\u3000────────────────",
]


DOWNLOAD = """令和７年９月定例会（第２号）　本文 : 2025-09-16
----------------------------------------------------------------
1:
　　　　　　　午前10時00分開議
◯議長（福田俊史君）ただいまから本日の会議を開きます。
　11番鳥羽喜一議員

2:
◯11番（鳥羽喜一君）（登壇・演壇、拍手）おはようございます。
　まず、参議院議員選挙を経てについてです。

3:
◯知事（平井伸治君）（登壇）鳥羽議員の御質問にお答え申し上げます。
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("cp932"))


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "鳥取県"
    _write(root / "export" / "20070219_平成19年2月定例会_第2号.txt", EXPORT)
    _write(
        root / "export" / "20080605_平成20年5月定例会_第4号.txt",
        "2008年06月05日：平成20年５月定例会（第４号）　本文\n\n発言が指定されていません。\n",
    )
    old = root / "H15-H18" / "H15"
    _write(old / "H15.06定例会議事録" / "第２号.txt", HANDMADE)
    _write(old / "H15.06定例会議事録" / "目次.txt", "目次\n○議長（前田宏君）\n")
    _write(old / "H15.05臨時会議事録" / "15・５・９　鳥取県議会５月臨時会（校正後）.txt", WRAPPED)
    h18 = root / "H15-H18" / "H18" / "H18.11定例会議事録" / "確定版"
    _write(h18 / "第1～4号.txt", COMBINED)
    _write(
        h18 / "第1号.txt",
        "平成１８年\n１１月定例\n鳥取県議会会議録\n第　１　号\n平成１８年１１月２７日（月曜日）\n"
        "○議長（鉄永幸紀君）ただいまから開会いたします。\n午前１０時３０分散会\n",
    )
    _write(
        root / "H15-H18" / "H17" / "H17.06定例会議事録" / "鳥取県議会６月定例会　校正後_170621.TXT",
        "午前10時04分開議\n○議長（前田宏君）ただいまから本日の会議を開きます。\n\x1a",
    )
    rtf = root / "rtf"
    rtf.mkdir()
    (rtf / "鳥取県議会H27年2月定例会_1_270212.rtf").write_bytes(_cocoa_rtf(RTF))
    (rtf / "鳥取県議会H17年6月定例会_170616.rtf").write_bytes(_cocoa_rtf(RTF))
    download = root / "download"
    _write(download / "20250916_令和7年9月定例会_第2号.txt", DOWNLOAD)
    # The same day as an RTF already imported, sent again in the new shape.
    _write(
        download / "20150212_平成27年2月定例会_第1号.txt",
        "平成27年２月定例会（第１号）　本文 : 2015-02-12\n" + "-" * 64 + "\n1:\n"
        "◯議長（野田修君）ただいまから開会いたします。\n",
    )
    return root


def test_rtf_text_reads_what_textedit_writes() -> None:
    lines = rtf_text(_cocoa_rtf(RTF)).split("\n")
    assert lines[:3] == ["午前10時00分開会", "◯議長（野田修君）ただいまから開会いたします。", ""]
    assert "　よろしくお願いします。" in lines
    # \\'hh bytes are the code page's, two to a cp932 character.
    assert rtf_text(b"{\\rtf1\\ansi\\ansicpg932 \\'8e\\'73}") == "市"
    # With \\uc1 the character after \\uN is a fallback for readers without Unicode.
    assert rtf_text(b"{\\rtf1\\uc1 \\u24066 ?x}") == "市x"


def test_export_speeches_and_what_a_rule_ends() -> None:
    lines = EXPORT.split("\n")[1:]
    split = split_speeches(lines)
    got = [(s.speaker, s.role, s.text.split("\n")[0]) for s in split.speeches]
    assert got == [
        ("山根英明", "議長", "おはようございます。"),
        ("中尾享", "35番", "（登壇、拍手）皆さんおはようございます。"),
        ("山根英明", "議長", "暫時休憩いたします。"),
        ("山根英明", "議長", "議席は、お手元に配付の議席表のとおり指定いたします。"),
        ("斉木正一", "副議長", "暫時休憩をいたします。"),
        ("", None, "皆様に申し上げます。"),
        ("平井伸治", "知事", "（登壇）お答えします。"),
    ]
    # A long rule stands where words were struck; the speech goes on after it.
    assert split.speeches[1].text.endswith("次に、関西広域連合についてお尋ねします。")
    # After a 〔参照〕 insert the chair carries on with no marker of its own.
    assert split.speeches[3].text.endswith("次に、会議録署名議員の指名をいたします。")
    assert "興" not in split.speeches[3].text
    # 再開 stamps go; the 休憩 stamp before the rule is the chair's paragraph.
    assert "再開" not in split.speeches[2].text
    assert split.resumed == 1
    assert split.silent == 1
    assert split.unattributed == ["(after a rule) 皆様に申し上げます。"]


def test_markers_of_both_circles() -> None:
    assert speaker_of("○３６番　（小谷茂君）知事")[:2] == ("小谷茂", "36番")
    assert speaker_of("◯議長（山根英明君）おはよう")[:2] == ("山根英明", "議長")
    assert speaker_of("○ただいまから")[0] == ""


def test_the_tree(tmp_path: Path) -> None:
    out = import_tree(_tree(tmp_path))
    by_file = {m.source_file: m for m in out.meetings}

    export = by_file["export/20070219_平成19年2月定例会_第2号.txt"]
    assert export.date == dt.date(2007, 2, 19)
    assert export.session == "平成19年2月定例会"
    assert export.title == "平成19年2月定例会（第2号）"

    # The failed export is reported and not written, so a re-sent file is read.
    assert out.skipped["empty export (発言が指定されていません。)"] == [
        "export/20080605_平成20年5月定例会_第4号.txt"
    ]
    assert len(out.skipped["not a transcript (目次・付録 by name)"]) == 1

    h15 = by_file["H15-H18/H15/H15.06定例会議事録/第２号.txt"]
    assert (h15.date, h15.session, h15.title) == (
        dt.date(2003, 6, 12),
        "平成15年6月定例会",
        "平成15年6月定例会（第2号）",
    )
    assert [s.speaker for s in h15.speeches] == ["前田宏", "小谷茂"]

    # Mid-word wraps are joined; the eight-space indent goes.
    wrapped = next(m for m in out.meetings if m.session == "平成15年5月臨時会")
    assert wrapped.date == dt.date(2003, 5, 9)
    assert wrapped.speeches[0].text.startswith("ただいま、御紹介にあずかりました浜崎でございます。")

    # No printed date: the file name's, and no 号 is invented.
    h17 = next(m for m in out.meetings if m.source_file.endswith("_170621.TXT"))
    assert (h17.date, h17.title) == (dt.date(2005, 6, 21), "平成17年6月定例会")
    assert h17.speeches[-1].text == "ただいまから本日の会議を開きます。"

    # Several sittings in one file, split at the printed date; 第1号 twice.
    nov29 = by_file["H15-H18/H18/H18.11定例会議事録/確定版/第1～4号.txt#2006-11-29"]
    assert nov29.title == "平成18年11月定例会（第2号）"
    assert [s.speaker for s in nov29.speeches] == ["片山善博", "鉄永幸紀"]
    assert out.duplicates and out.duplicates[0].startswith("2006-11-27: kept ")
    assert sum(m.date == dt.date(2006, 11, 27) for m in out.meetings) == 1
    assert any("平成17年6月定例会: 2 sitting(s) with no 号" in n for n in out.numbering)

    # Re-sent as RTF: dated and numbered by the file name alone.
    rtf = by_file["rtf/鳥取県議会H27年2月定例会_1_270212.rtf"]
    assert (rtf.date, rtf.title) == (dt.date(2015, 2, 12), "平成27年2月定例会（第1号）")
    assert [(s.speaker, s.role) for s in rtf.speeches] == [
        ("野田修", "議長"),
        ("平井伸治", "知事"),
        ("野田修", "議長"),
    ]
    assert rtf.speeches[1].text.endswith("提案いたしました。\nよろしくお願いします。")
    opening = by_file["rtf/鳥取県議会H17年6月定例会_170616.rtf"]
    assert (opening.date, opening.title) == (dt.date(2005, 6, 16), "平成17年6月定例会")

    # The download shape: 発言番号 dropped, markers split it, numbering checks it.
    dl = by_file["download/20250916_令和7年9月定例会_第2号.txt"]
    assert (dl.date, dl.session, dl.title) == (
        dt.date(2025, 9, 16),
        "令和7年9月定例会",
        "令和7年9月定例会（第2号）",
    )
    assert [s.speaker for s in dl.speeches] == ["福田俊史", "鳥羽喜一", "平井伸治"]
    assert dl.speeches[1].text.endswith("まず、参議院議員選挙を経てについてです。")
    assert not any("1:" in s.text or "---" in s.text for s in dl.speeches)
    assert not any("download/20250916" in n for n in out.numbering)

    # Sent again: what was imported first stays, and the later copy is compared.
    assert "download/20150212_平成27年2月定例会_第1号.txt" not in by_file
    assert any(
        d.startswith("2015-02-12: kept rtf/") and "TEXT DIFFERS" in d for d in out.duplicates
    )


def test_a_download_whose_blocks_and_markers_disagree_is_reported(tmp_path: Path) -> None:
    root = tmp_path / "鳥取県"
    # Block 2's marker lost its circle: two numbers, one speech.
    _write(
        root / "download" / "20250916_令和7年9月定例会_第2号.txt",
        DOWNLOAD.replace("◯11番", "11番"),
    )
    out = import_tree(root)
    assert "download/20250916_令和7年9月定例会_第2号.txt: 3 numbered blocks, 2 speeches" in (
        out.numbering
    )


def test_a_record_already_written_is_skipped(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    key = "file:export/20070219_平成19年2月定例会_第2号.txt"
    out = import_tree(root, skip={key})
    assert key[5:] not in {m.source_file for m in out.meetings}


def test_receive_undoes_the_mangled_names(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "tottori_receive", Path(__file__).resolve().parent.parent / "scripts" / "tottori_receive.py"
    )
    assert spec and spec.loader
    receive = importlib.util.module_from_spec(spec)
    sys.modules["tottori_receive"] = receive
    spec.loader.exec_module(receive)

    mangled = "H19年".encode("cp932").decode("cp437")
    assert mangled == "H19öN"
    assert receive.unmangle(mangled) == "H19年"
    assert receive.unmangle("H15") == "H15"

    src = tmp_path / "data"
    _write(src / mangled / mangled / "document (1).txt", EXPORT)
    _write(src / "H15" / "H15.06定例会議事録".encode("cp932").decode("cp437") / "x.txt", "x")
    target = receive.target_of(src / mangled / mangled / "document (1).txt", src)
    assert target == Path("export/20070219_平成19年2月定例会_第2号.txt")
    old = receive.target_of(
        src / "H15" / "H15.06定例会議事録".encode("cp932").decode("cp437") / "x.txt", src
    )
    assert old == Path("H15-H18/H15/H15.06定例会議事録/x.txt")

    _write(src / "R7(9~11)" / "download (1).txt", DOWNLOAD)
    target = receive.target_of(src / "R7(9~11)" / "download (1).txt", src)
    assert target == Path("download/20250916_令和7年9月定例会_第2号.txt")


def test_a_file_wrapped_at_150_columns_is_rejoined() -> None:
    from prefectural_transcripts.importers.tottori import _rejoin, _wrap_width

    full = "あ" * 75  # 150 columns, the width of 平成18年11月定例会's combined files
    lines = ["○知事（片山善博君）" + "い" * 65, "ます。", "　次の段落。"] + [full] * 50
    assert _wrap_width(lines) == 150
    joined = _rejoin(lines, 150)
    assert joined[0].endswith("います。")
    assert joined[1] == "　次の段落。"  # a paragraph opens with 　 and is never joined
