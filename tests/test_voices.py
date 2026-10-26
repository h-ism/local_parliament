"""gijiroku VOICES (滋賀・石川・栃木): frames, the whole-sitting page, and its markers.

Fixtures copy the shapes of the reconnaissance caches of 2026-10-10/11 and (栃木)
2026-10-24, trimmed.
"""

from __future__ import annotations

from datetime import date

from conftest import FakeClient, make_page
from prefectural_transcripts.models import MeetingRef
from prefectural_transcripts.scrapers.voices import (
    VoicesConfig,
    VoicesScraper,
    rows_on,
    shown_year,
    sitting_date,
    speaker_of,
    split_session,
)

BASE = "https://example.jp/voices/"
INDEX = BASE + "g08v_viewh.asp"
WRAP = BASE + "g08v_viewh.asp?Sflg=11&FYY=2020&TYY=2020"
LIST = BASE + "cgi/voiweb.exe?ACT=100&KTYP=0,1,2,3&FYY=2020&TYY=2020&KGTP=1,2"
SET_MOKUJI = BASE + "cgi/voiweb.exe?ACT=200&FINO=2507&UNID=K1"
SET_01 = BASE + "cgi/voiweb.exe?ACT=200&FINO=2508&UNID=K2"
HAT_01 = BASE + "cgi/voiweb.exe?ACT=203&FINO=2508&HUID=191963&STYLE=0"

INDEX_HTML = f"""<html><body>
<a href="{INDEX}?Sflg=10">本会議をすべて表示</a>
<a href="g08v_viewh.asp?Sflg=11&FYY=2020&TYY=2020">令和2年</a>
<a href="g07_Shitsumon.asp">発言通告一覧</a>
</body></html>"""

WRAP_HTML = (
    '<html><body><iframe src="cgi/voiweb.exe?ACT=100&amp;KTYP=0,1,2,3&amp;FYY=2020'
    '&amp;TYY=2020&amp;KGTP=1,2"></iframe></body></html>'
)


def _row(title: str, fino: int, unid: str, label: str) -> str:
    return (
        '<TR><TD NOWRAP COLSPAN=3>\n<A HREF="voiweb.exe?ACT=100&FINO=1"><IMG SRC="f.gif"></A>\n'
        f'{title},<A HREF="javascript:;"  TARGET="HLD_WIN" onClick="winopen('
        f"'voiweb.exe?ACT=200&FINO={fino}&UNID={unid}');\">{label}</A>\n</TD></TR>"
    )


TITLE = "令和　２年１１月定例会議（第17号～第23号）"
LIST_HTML = (
    "<html><body><TABLE><TR><TD>2件の日程がヒットしました。</TD></TR></TABLE><TABLE>"
    + _row(TITLE, 2507, "K1", "11月27日-目次")
    + _row(TITLE, 2508, "K2", "12月10日-06号")
    + "</TABLE></body></html>"
)

FRAMESET_HTML = """<FRAMESET ROWS="103,*"><FRAME SRC="voiweb.exe?ACT=201&FINO=2508" NAME="header">
<FRAME SRC="voiweb.exe?ACT=202&FINO=2508#191963" NAME="sidebar">
<FRAME SRC="voiweb.exe?ACT=203&FINO=2508&HUID=191963&STYLE=0#HUID191963" NAME="hat">
</FRAMESET>"""

SITTING_HTML = (
    "<BODY><SCRIPT>var hitp = -1;</SCRIPT>"
    '<A NAME="HUID191963"></A>令和　２年１１月定例会議（第17号～第23号）<BR><BR>'
    "　　令和２年11月定例会議会議録（第22号）<BR>　　令和２年12月10日（木曜日）<BR>"
    "議事日程　第６号<BR><P>"
    '<A NAME="HUID191964"></A>○議長（細江正人）　これより本日の会議を開きます。<BR>'
    "　　　────────────────<BR><P>"
    '<A NAME="HUID191965"></A>△議第164号から議第197号まで<BR><P>'
    '<A NAME="HUID191966"></A>◆11番（黄野瀬明子議員）　（登壇、拍手）おはようございます。<BR>'
    "〇総務・企画常任委員会<BR>　早速ですけれども。<BR><P>"
    '<A NAME="HUID191967"></A>◎20番（目片信悟議員［総務・企画常任委員長］）　報告します。<BR><P>'
    '<A NAME="HUID191968"></A>◎20番（総務企画常任委員長黒川治君）　去る13日。<BR><P>'
    '<A NAME="HUID191969"></A>（拍手）とだけ書かれた行<BR><P>'
    '<A NAME="HUID191970"></A>○議長（細江正人）　本日はこれをもって散会いたします。<BR>'
    "　　午後５時１分　散会<BR>会議録署名議員<BR>議　長　細　江　正　人<BR>"
    "<SCRIPT>function init_h(){}</SCRIPT></BODY>"
)


def _scraper() -> VoicesScraper:
    return VoicesScraper(VoicesConfig(prefecture="滋賀県", index_url=INDEX))


def _client(sitting: str = SITTING_HTML) -> FakeClient:
    return FakeClient(
        {
            INDEX: INDEX_HTML,
            WRAP: WRAP_HTML,
            LIST: LIST_HTML,
            SET_01: FRAMESET_HTML,
            HAT_01: sitting,
        }
    )


def test_rows_carry_title_label_and_the_winopen_url() -> None:
    rows = rows_on(LIST_HTML, LIST)
    assert [r.label for r in rows] == ["11月27日-目次", "12月10日-06号"]
    assert rows[1].title == TITLE
    assert rows[1].url == SET_01


def test_listing_follows_year_links_and_skips_the_mokuji() -> None:
    scraper = _scraper()
    client = _client()
    refs = list(scraper.list_meetings(client))  # type: ignore[arg-type]
    assert [str(r.url) for r in refs] == [SET_01]
    assert refs[0].date == date(2020, 12, 10)
    assert SET_MOKUJI not in client.requested
    assert "1 目次 document(s) listed and skipped" in scraper.report()


def test_a_list_shorter_than_its_hit_count_is_reported() -> None:
    scraper = _scraper()
    client = _client()
    client.pages[LIST] = LIST_HTML.replace("2件の日程", "3件の日程")
    list(scraper.list_meetings(client))  # type: ignore[arg-type]
    assert any("3 listed, 2 read" in line for line in scraper.report())


def test_a_sitting_is_the_frameset_then_its_hat_frame() -> None:
    scraper = _scraper()
    client = _client()
    meetings = list(scraper.scrape(client))  # type: ignore[arg-type]
    assert client.requested[-2:] == [SET_01, HAT_01]
    (m,) = meetings
    assert m.date == date(2020, 12, 10)
    assert m.session == "令和2年11月定例会議"
    got = [(s.speaker, s.role) for s in m.speeches]
    assert got == [
        ("細江正人", "議長"),
        ("黄野瀬明子", "11番"),
        ("目片信悟", "20番　総務・企画常任委員長"),
        ("黒川治", "20番　総務企画常任委員長"),
        ("", None),  # a block whose marker cannot be read: kept, no name
        ("細江正人", "議長"),
    ]
    # The rule line goes; an inner 〇 line naming a committee stays as text.
    assert m.speeches[0].text == "これより本日の会議を開きます。"
    assert "〇総務・企画常任委員会" in m.speeches[1].text
    # The signatures after 閉会 / 散会 are not the chair's words.
    assert m.speeches[-1].text.endswith("散会")
    report = "\n".join(scraper.report())
    assert "△ heading 1" in report
    assert "1 speech(es) whose marker was not read" in report


def test_a_printed_date_that_disagrees_with_the_label_is_reported() -> None:
    scraper = _scraper()
    client = _client(
        SITTING_HTML.replace("令和２年12月10日（木曜日）", "令和２年12月11日（金曜日）")
    )
    list(scraper.scrape(client))  # type: ignore[arg-type]
    assert any("printed 2020-12-11" in line for line in scraper.report())


def test_ishikawa_prints_month_and_day_in_kanji_and_that_is_checked_too() -> None:
    scraper = _scraper()
    client = _client(SITTING_HTML.replace("令和２年12月10日（木曜日）", "十二月九日（水曜日）"))
    list(scraper.scrape(client))  # type: ignore[arg-type]
    assert any("printed (12, 9)" in line for line in scraper.report())


def test_marker_shapes_from_both_sites() -> None:
    cases = {
        "○議長（岡本秀康君）　これより": ("岡本秀康", "議長"),
        "◆９番（野村政夫君）　（登壇、拍手）": ("野村政夫", "9番"),
        "◎知事（三日月大造）　お答え": ("三日月大造", "知事"),
        "◆北村茂男君　「ひいては": ("北村茂男", None),
        "◆（櫻井廣明君）　若かりし": ("櫻井広明", None),  # 廣 -> 広, normalize_speaker
        "◎矢田富郎君　ただいま": ("矢田富郎", None),
    }
    for line, want in cases.items():
        speaker, role, _ = speaker_of(line)
        assert (speaker, role) == want, line


def test_words_after_a_circle_are_not_a_speaker() -> None:
    for line in (
        "◆ただいま議題となりました議案について",
        "○３　閉会中の継続調査事件",
        "〇七年版ですが",
    ):
        assert speaker_of(line)[0] == "", line


def test_dates_from_session_and_label() -> None:
    assert sitting_date("平成　４年　２月第　１回定例会", "03月04日-03号") == date(1992, 3, 4)
    assert sitting_date("平成31年・令和元年", "05月01日-01号") is None
    assert sitting_date("令和元年１２月定例会議", "12月10日-01号") == date(2019, 12, 10)
    # A December session that runs into January is in the next year.
    assert sitting_date("令和　７年１２月定例会議", "01月08日-05号") == date(2026, 1, 8)


def test_a_session_has_one_name_whatever_the_padding() -> None:
    assert split_session("令和　２年１１月定例会議（第17号～第23号）") == "令和2年11月定例会議"
    assert split_session("平成　４年　２月第　１回定例会") == "平成4年2月第1回定例会"
    assert split_session("令和　８年　１月臨時会議（第22号）") == "令和8年1月臨時会議"


def test_reparse_without_a_listing_keeps_the_ref_date() -> None:
    scraper = _scraper()
    ref = MeetingRef(prefecture="滋賀県", url=SET_01, date=date(2020, 12, 10), title="x")  # type: ignore[arg-type]
    m = scraper.parse_meeting(ref, make_page(HAT_01, SITTING_HTML))
    assert m.date == date(2020, 12, 10)


# 栃木: a fiscal-year wrapper, whose list shows one calendar year per page.
TG_WRAP = BASE + "g08v_viewh.asp?Sflg=11&FYY=2015&FMM=4&TYY=2016&TMM=3"
TG_LIST = BASE + "cgi/voiweb.exe?ACT=100&KTYP=0,1,2,3&FYY=2015&FMM=4&TYY=2016&TMM=3&KGTP=1"
TG_2015 = BASE + "cgi/voiweb.exe?ACT=100&KGTP=1&FYY=2015&FMM=4&TYY=2016&TMM=3&YEAR=2015"
TG_2016 = BASE + "cgi/voiweb.exe?ACT=100&KGTP=1&FYY=2015&FMM=4&TYY=2016&TMM=3&YEAR=2016"
TG_TITLE = "平成２７年度栃木県議会第３３３回通常会議"


def _bar(shown: str, linked: str, year: int) -> str:
    return (
        '<TABLE><TR><TD BGCOLOR="#E6E6FA">'
        f'{shown} <A HREF="voiweb.exe?ACT=100&KGTP=1&FYY=2015&FMM=4&TYY=2016&TMM=3'
        f'&YEAR={year}">{linked}</A> </TD></TR></TABLE>'
    )


def _bar_linked_first(linked: str, shown: str, year: int) -> str:
    return (
        '<TABLE><TR><TD BGCOLOR="#E6E6FA">'
        f'<A HREF="voiweb.exe?ACT=100&KGTP=1&FYY=2015&FMM=4&TYY=2016&TMM=3'
        f'&YEAR={year}">{linked}</A> {shown} </TD></TR></TABLE>'
    )


def _tochigi_client() -> FakeClient:
    expand = (
        '<A HREF="voiweb.exe?ACT=100&KGTP=1&FYY=2015&FMM=4&TYY=2016&TMM=3'
        '&TITL_SUBT=x&YEAR=2015">平成　27年</A>'
    )
    return FakeClient(
        {
            INDEX: '<html><body><a href="g08v_viewh.asp?Sflg=11&FYY=2015&FMM=4&TYY=2016&TMM=3">'
            "平成27年度</a></body></html>",
            TG_WRAP: '<html><body><iframe src="cgi/voiweb.exe?ACT=100&amp;KTYP=0,1,2,3&amp;'
            'FYY=2015&amp;FMM=4&amp;TYY=2016&amp;TMM=3&amp;KGTP=1"></iframe></body></html>',
            TG_LIST: "<html><body><TABLE><TR><TD>2件の日程がヒットしました。</TD></TR></TABLE>"
            + _bar("平成　28年", "平成　27年", 2015)
            + "<TABLE>"
            + _row(TG_TITLE, 1953, "T1", "03月24日-06号")
            + "</TABLE>"
            + expand
            + "</body></html>",
            TG_2015: "<html><body>"
            + _bar_linked_first("平成　28年", "平成　27年", 2016)
            + "<TABLE>"
            + _row("平成２７年度栃木県議会第３３２回通常会議", 1900, "T2", "12月01日-02号")
            + "</TABLE></body></html>",
        }
    )


def test_tochigi_the_year_is_the_one_the_bar_does_not_link() -> None:
    assert shown_year(_bar("平成　28年", "平成　27年", 2015)) == 2016
    assert shown_year(_bar_linked_first("平成　28年", "平成　27年", 2016)) == 2015
    assert shown_year(LIST_HTML) is None  # 滋賀・石川: no bar


def test_tochigi_a_fiscal_year_is_two_pages_and_each_dates_its_rows() -> None:
    scraper = VoicesScraper(VoicesConfig(prefecture="栃木県", index_url=INDEX))
    client = _tochigi_client()
    refs = list(scraper.list_meetings(client))  # type: ignore[arg-type]
    assert [r.date for r in refs] == [date(2016, 3, 24), date(2015, 12, 1)]
    # The year already read is not asked for again, and a session's expansion
    # (TITL_SUBT=) lists speeches, not sittings.
    assert TG_2016 not in client.requested
    assert not any("TITL_SUBT" in u for u in client.requested)
    assert not any("listed," in line for line in scraper.report())


def test_tochigi_titles_have_no_month_so_the_page_year_dates_them() -> None:
    assert sitting_date(TG_TITLE, "02月19日-01号") is None
    assert sitting_date(TG_TITLE, "02月19日-01号", 2016) == date(2016, 2, 19)
    assert sitting_date("平成２１年第３００回（第４号）定例会", "12月14日-05号", 2009) == date(
        2009, 12, 14
    )
    # Where the title has a month (滋賀・石川) the page year changes nothing.
    assert sitting_date("令和　７年１２月定例会議", "01月08日-05号", 2026) == date(2026, 1, 8)


def test_tochigi_name_then_office_markers() -> None:
    cases = {
        "○関谷暢之　議長　ただいまから本日の会議を開きます。": ("関谷暢之", "議長"),
        "◎小林基予子　事務局長　出席議員数を報告いたします。": ("小林基予子", "事務局長"),
        "◎福田富一　知事": ("福田富一", "知事"),
        "◆50番（螺良昭人議員）　とちぎ自民党議員会の": ("螺良昭人", "50番"),
    }
    for line, want in cases.items():
        speaker, role, rest = speaker_of(line)
        assert (speaker, role) == want, line
    assert speaker_of("○関谷暢之　議長　ただいまから")[2] == "　ただいまから"


def test_tochigi_a_bullet_before_the_printed_date_is_not_a_digit() -> None:
    scraper = _scraper()
    client = _client(SITTING_HTML.replace("令和２年12月10日（木曜日）", "〇十二月十日（木曜日）"))
    list(scraper.scrape(client))  # type: ignore[arg-type]
    assert not any("printed" in line for line in scraper.report())


def test_tochigi_a_committee_report_is_the_chair_not_the_committee() -> None:
    # 2014-11-27: 「○県政経営委員会　岩崎信委員長　」, six times — six "speakers"
    # that were committees.
    line = "○県政経営委員会　岩崎信委員長　県政経営委員会が取り組みました"
    assert speaker_of(line)[:2] == ("岩崎信", "県政経営委員会委員長")
    # A roster line inside a speech keeps its old reading; it never opens a turn.
    assert speaker_of("○県政経営委員会（定数九人）")[:2] == ("定数九人", "県政経営委員会")
    # A form's placeholder is not a name.
    assert speaker_of("○○議会議長○○　○○")[0] == ""


def test_tochigi_a_turn_with_no_anchor_is_split_out() -> None:
    # 令和4年2〜3月: the vice-chair's turns carry no anchor and sat inside the
    # member's speech before them — 93 of them, credited to the member.
    sitting = SITTING_HTML.replace(
        "〇総務・企画常任委員会<BR>　早速ですけれども。<BR>",
        "〇総務・企画常任委員会<BR>　早速ですけれども。<BR>"
        "○佐藤良　副議長　福田富一知事。<BR>（福田富一知事登壇）<BR>"
        "○県政経営委員会（定数九人）<BR>",
    )
    scraper = _scraper()
    (m,) = list(scraper.scrape(_client(sitting)))  # type: ignore[arg-type]
    got = [(s.speaker, s.role) for s in m.speeches]
    assert got[1:3] == [("黄野瀬明子", "11番"), ("佐藤良", "副議長")]
    assert m.speeches[1].text.endswith("早速ですけれども。")
    assert m.speeches[2].text == "福田富一知事。\n（福田富一知事登壇）\n○県政経営委員会（定数九人）"
    assert "turn with no anchor 1" in "\n".join(scraper.report())
