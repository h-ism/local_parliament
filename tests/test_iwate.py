"""岩手: a sitting is every page from one 第N号 up to the next."""

from __future__ import annotations

from datetime import date

from conftest import FakeClient
from prefectural_transcripts.scrapers.generic import split_speeches
from prefectural_transcripts.scrapers.iwate import (
    DEFAULT_SPEECH_SPLIT,
    IwateConfig,
    IwateScraper,
    sittings_on,
    split_heading,
)

ROOT = "https://www3.pref.iwate.jp/gikai/user/www/Zenbun/"

INDEX = """<html><body><ul>
<li><a href="#">平成19年9月定例会</a><ul>
  <li><a href="/gikai/user/www/Zenbun/mokuji/2"><span>本会議</span></a></li>
</ul></li>
<li><a href="#">令和8年2月定例会</a><ul>
  <li><a href="/gikai/user/www/Zenbun/mokuji/351"><span>予算特別委員会</span></a></li>
</ul></li>
</ul></body></html>"""

MOKUJI_2 = """<html><body><table><tr>
<td align="center">平成19年9月定例会　第３回岩手県議会定例会会議録</td></tr></table>
<a href="/gikai/user/www/Zenbun/page/2/376282/376296">第２号（10月４日）</a>
<a href="/gikai/user/www/Zenbun/page/2/376297/376314">佐々木（博）議員</a>
<a href="/gikai/user/www/Zenbun/page/2/376315/376331">柳村議員</a>
<a href="/gikai/user/www/Zenbun/page/2/376348/376362">第３号（10月５日）</a>
<a href="/gikai/user/www/Zenbun/furoku/f190901.html">１　定例会日程</a>
<a href="/gikai/user/www/Zenbun/">戻る</a>
</body></html>"""

MOKUJI_351 = """<html><body><table><tr>
<td align="center">令和8年2月定例会　予算特別委員会会議記録</td></tr></table>
<a href="/gikai/user/www/Zenbun/page/351/1172774/1173098">第１号　　３月４日（水）</a>
<a href="/gikai/user/www/Zenbun/furoku/fY3080201.html">予算特別委員長報告</a>
</body></html>"""


def _page(lines: list[str]) -> str:
    body = "<br>".join(lines)
    return f"""<html><body><center>
<table><tr><td align="center">見出し</td></tr></table>
<table><tr><td><a href="#">前へ</a></td><td><a href="#">次へ</a></td></tr></table>
<table><tr><td><div style="width:600px;">{body}</div></td></tr></table>
</center></body></html>"""


PAGES = {
    ROOT: INDEX,
    ROOT + "mokuji/2": MOKUJI_2,
    ROOT + "mokuji/351": MOKUJI_351,
    ROOT + "page/2/376282/376296": _page(
        [
            "第３回岩手県議会定例会会議録（第２号）",
            "平成19年10月４日（木曜日）",
            "出席議員（48名）",
            "〇議長（渡辺幸貫君）　これより本日の会議を開きます。",
            "〔32番佐々木博君登壇〕（拍手）",
        ]
    ),
    ROOT + "page/2/376297/376314": _page(
        [
            "〇32番（佐々木博君）　民主・県民会議の佐々木博でございます。",
            "〇知事（達増拓也君）　佐々木博議員の御質問にお答えいたします。",
        ]
    ),
    ROOT + "page/2/376315/376331": _page(
        [
            "〇議長（渡辺幸貫君）　次に、柳村岩見君。",
            "〇36番（柳村岩見君）　自由民主クラブの柳村岩見です。",
        ]
    ),
    ROOT + "page/2/376348/376362": _page(
        ["平成19年10月５日（金曜日）", "〇議長（渡辺幸貫君）　開きます。"]
    ),
    ROOT + "page/351/1172774/1173098": _page(
        [
            "令和８年３月４日（水）",
            "１開会　午前10時２分",
            "〇坊良議会事務局長　委員長が互選されるまでの間、",
            "〇千葉伝年長委員　ただいま御紹介ありました千葉伝です。",
            "〇菊池（雄）委員　質問いたします。",
        ]
    ),
}


def _scraper() -> IwateScraper:
    return IwateScraper(IwateConfig(prefecture="岩手県", index_url=ROOT))


def test_a_sitting_runs_from_one_dai_n_go_to_the_next() -> None:
    heading, sittings, orphans = sittings_on(MOKUJI_2, ROOT + "mokuji/2")
    assert heading.startswith("平成19年9月定例会")
    assert [s.label for s in sittings] == ["第２号（10月４日）", "第３号（10月５日）"]
    assert [len(s.pages) for s in sittings] == [3, 1]
    assert orphans == []


def test_a_gap_in_the_page_ranges_is_counted() -> None:
    # 376297/376314 followed by 376348: the pages between are not linked.
    gappy = MOKUJI_2.replace(
        '<a href="/gikai/user/www/Zenbun/page/2/376315/376331">柳村議員</a>', ""
    ).replace("第３号（10月５日）", "谷藤議員")
    _, sittings, _ = sittings_on(gappy, ROOT + "mokuji/2")
    assert sittings[0].gaps == 1


def test_pages_before_the_first_sitting_are_returned_not_dropped() -> None:
    html = MOKUJI_2.replace("第２号（10月４日）", "会議録")
    _, sittings, orphans = sittings_on(html, ROOT + "mokuji/2")
    assert len(orphans) == 3
    assert [s.label for s in sittings] == ["第３号（10月５日）"]


def test_heading_gives_session_and_committee() -> None:
    assert split_heading("令和8年2月定例会　予算特別委員会会議記録") == (
        "令和8年2月定例会",
        "予算特別委員会",
    )
    assert split_heading("平成7年12月定例会　決算特別委員会（企業会計）会議録") == (
        "平成7年12月定例会",
        "決算特別委員会（企業会計）",
    )
    assert split_heading("平成19年9月定例会　第３回岩手県議会定例会会議録") == (
        "平成19年9月定例会",
        None,
    )


def test_scrape_joins_the_pages_of_a_sitting() -> None:
    client = FakeClient(PAGES)
    scraper = _scraper()
    meetings = list(scraper.scrape(client))  # type: ignore[arg-type]
    assert len(meetings) == 3

    second = meetings[0]
    assert second.date == date(2007, 10, 4)
    assert second.session == "平成19年9月定例会"
    assert second.committee is None
    # Four pages of text, one record, in the 目次's order.
    assert [s.speaker for s in second.speeches] == [
        "渡辺幸貫",
        "佐々木博",
        "達増拓也",
        "渡辺幸貫",
        "柳村岩見",
    ]
    assert second.speeches[1].role == "32番"
    # The first page's last line runs on into the member page's speech.
    assert "〔32番佐々木博君登壇〕" in second.speeches[0].text

    committee = meetings[2]
    assert committee.date == date(2026, 3, 4)
    assert committee.committee == "予算特別委員会"
    assert [s.speaker for s in committee.speeches] == [
        "坊良議会事務局長",
        "千葉伝年長委員",
        "菊池(雄)委員",
    ]
    assert scraper.report() == []


def test_a_date_that_disagrees_with_the_mokuji_is_reported() -> None:
    pages = dict(PAGES)
    pages[ROOT + "page/2/376348/376362"] = pages[ROOT + "page/2/376348/376362"].replace(
        "10月５日", "10月６日"
    )
    scraper = _scraper()
    list(scraper.scrape(FakeClient(pages)))  # type: ignore[arg-type]
    assert any("disagreeing" in line for line in scraper.report())


def test_the_marker_rule_keeps_numerals_and_headings_out() -> None:
    text = "\n".join(
        [
            "〇議長（渡辺幸貫君）　これより会議を開きます。",
            "〇七年度の予算について、",  # 〇 as zero, no full-width space after a name
            "日程第１　一般質問",
            "〇高校教育課学校支援推進官兼義務教育課学校支援推進官　お答えします。",
        ]
    )
    speeches = split_speeches(text, DEFAULT_SPEECH_SPLIT)
    assert [s.speaker for s in speeches] == [
        "渡辺幸貫",
        "高校教育課学校支援推進官兼義務教育課学校支援推進官",
    ]
    assert "〇七年度" in speeches[0].text


def test_shapes_found_on_the_first_night() -> None:
    text = "\n".join(
        [
            # 令和3年: no space after the bracket. Five sittings parsed to nothing.
            "〇議長（関根敏伸君）これより本日の会議を開きます。",
            # ○ U+25CB rather than 〇 U+3007.
            "○保健福祉部長（野原勝君）　お答えします。",
            # Half-width brackets.
            "〇2番(畠山茂君)　希望いわての畠山茂です。",
            # The closing bracket missing in the source.
            "〇２番（畠山茂君　それぞれ丁寧な御答弁をいただきました。",
            # A speaker resuming — not a person named 続.
            "〇高田一郎委員（続）　続けます。",
            # A committee marker alone on its line.
            "〇小澤首席社会教育主事兼生涯学習文化財課総括課長",
            "お答えいたします。",
        ]
    )
    speeches = split_speeches(text, DEFAULT_SPEECH_SPLIT)
    assert [(s.role, s.speaker) for s in speeches] == [
        ("議長", "関根敏伸"),
        ("保健福祉部長", "野原勝"),
        ("2番", "畠山茂"),
        ("２番", "畠山茂"),
        (None, "高田一郎委員"),
        # 澤 -> 沢: `normalize_speaker`'s 常用漢字 table, as on every site.
        (None, "小沢首席社会教育主事兼生涯学習文化財課総括課長"),
    ]
    assert speeches[-1].text == "お答えいたします。"


def test_a_bracket_without_kun_and_without_a_space_is_not_a_marker() -> None:
    text = "〇議長（渡辺幸貫君）　予算について、\n〇七年度の予算（案）について説明します。"
    speeches = split_speeches(text, DEFAULT_SPEECH_SPLIT)
    assert len(speeches) == 1
    assert "〇七年度" in speeches[0].text
