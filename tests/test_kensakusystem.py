"""Offline tests for the `kensakusystem.jp` scraper.

Every URL here is the shape the live site actually serves; the point of the
fixtures is the awkward parts — a tree navigated through `onClick` with a
cp932-encoded label, a transcript assembled from character offsets, and a body
that is plain text rather than HTML.
"""

from __future__ import annotations

from datetime import date

from conftest import FakeClient
from prefectural_transcripts.scrapers import SITES_DIR
from prefectural_transcripts.scrapers.kensakusystem import (
    KensakuConfig,
    KensakuSystemScraper,
    _cp932,
    date_from_filename,
)

BASE = "https://www.kensakusystem.jp/ehime/"
CGI = BASE + "cgi-bin3/"
CODE = "e7c7rvxas7fwx1belp"

INDEX = f"""<html><body>
<a href="cgi-bin3/See.exe?Code={CODE}">会議録の閲覧</a>
</body></html>"""

ROOT = """<html><body>
<A HREF="javascript:document.viewtree.submit()"
   onClick="document.viewtree.treedepth.value='令和 8年'">令和 8年</A>
<A HREF="javascript:document.viewtree.submit()"
   onClick="document.viewtree.treedepth.value='平成30年'">平成27年～平成30年</A>
</body></html>"""

# The year lists its own node among its children, and its documents beside them —
# so opening the year *as a session* yields every sitting a second time.
YEAR_R8 = f"""<html><body>
<A onClick="document.viewtree.treedepth.value='令和 8年'">令和 8年</A>
<A onClick="document.viewtree.treedepth.value='令和 7年'">令和 7年</A>
<A onClick="document.viewtree.treedepth.value='令和 8年 第395回定例会 '">第395回定例会</A>
<A onClick="document.viewtree.treedepth.value='令和 8年 建設委員会 '">建設委員会</A>
<A href="ResultFrame.exe?Code={CODE}&fileName=R080225A&startPos=0">（第1号 2月25日）</A>
</body></html>"""

YEAR_EMPTY = """<html><body>
<A onClick="document.viewtree.treedepth.value='平成30年'">平成30年</A>
</body></html>"""

SESSION = f"""<html><body>
<A onClick="document.viewtree.treedepth.value='令和 8年 第395回定例会 '">第395回定例会</A>
<OL>
<A href="ResultFrame.exe?Code={CODE}&fileName=R080225A&startPos=0">
<IMG SRC="/ehime/image/r2.gif" WIDTH="12">（第1号 2月25日）</A><BR>
<A href="ResultFrame.exe?Code={CODE}&fileName=R080302A&startPos=0">
<IMG SRC="/ehime/image/r2.gif" WIDTH="12">（第2号 3月 2日）</A><BR>
</OL>
</body></html>"""

SPEAKERS = """<html><body>
<TITLE>会議録の閲覧と検索</TITLE>
<FORM NAME="download" ACTION="/ehime/cgi-bin3/GetPerson.exe" METHOD="POST">
<INPUT type="checkbox" name="downloadPos" value="81" >
<INPUT type="checkbox" name="downloadPos" value="3199" >
</FORM></body></html>"""

# What GetPerson.exe returns: plain text, CRLF, printed-page markers, and section
# headings that are *not* speeches — 「○議事日程」 has no brackets and
# 「〇出席議員」 uses 〇 (U+3007) rather than ○ (U+25CB).
TRANSCRIPT = (
    "○議事日程\r\n"
    "〇出席議員　45名\r\n"
    "〇欠　　員　２名\r\n"
    '<PAGE="2">\r\n'
    "○（福羅浩一議長）　ただいまから第395回愛媛県議会定例会を開会いたします。\r\n"
    "○（中村時広知事）　今議会招集の挨拶を申し上げます。\r\n"
)


def _pages() -> dict[str, str]:
    year_r8 = f"{CGI}See.exe?Code={CODE}&treedepth={_cp932('令和 8年')}"
    year_r7 = f"{CGI}See.exe?Code={CODE}&treedepth={_cp932('令和 7年')}"
    year_h30 = f"{CGI}See.exe?Code={CODE}&treedepth={_cp932('平成30年')}"
    session = f"{CGI}See.exe?Code={CODE}&treedepth={_cp932('令和 8年 第395回定例会 ')}"
    pages = {
        BASE + "index.html": INDEX,
        f"{CGI}See.exe?Code={CODE}": ROOT,
        year_r8: YEAR_R8,
        year_r7: YEAR_EMPTY,
        year_h30: YEAR_EMPTY,
        session: SESSION,
    }
    committee = f"{CGI}See.exe?Code={CODE}&treedepth={_cp932('令和 8年 建設委員会 ')}"
    pages[committee] = f"""<html><body>
<A href="ResultFrame.exe?Code={CODE}&fileName=R080610B04&startPos=0">
<IMG SRC="/ehime/image/r2.gif" WIDTH="12">（ 6月10日）</A><BR>
</body></html>"""
    for name in ("R080225A", "R080302A"):
        pages[f"{CGI}r_Speakers.exe?{CODE}/{name}/0/0//10/1/1073741823:2097151/0/1//0/0/0"] = (
            SPEAKERS
        )
        pages[f"{CGI}GetPerson.exe?Code={CODE}&fileName={name}&downloadPos=81&downloadPos=3199"] = (
            TRANSCRIPT
        )
    return pages


def _scraper(**kw: object) -> KensakuSystemScraper:
    return KensakuSystemScraper(
        KensakuConfig(prefecture="愛媛県", base_url=BASE, name="ehime", **kw)  # type: ignore[arg-type]
    )


def test_filename_carries_the_date() -> None:
    """`fileName=R080225A` is 令和8年2月25日 — which is why --since/--until can
    prune this crawl before a transcript is fetched."""
    assert date_from_filename("R080225A") == date(2026, 2, 25)
    assert date_from_filename("H310129B") == date(2019, 1, 29)
    assert date_from_filename("S610331A") == date(1986, 3, 31)
    assert date_from_filename("nonsense") is None


def test_a_long_sitting_still_yields_a_valid_ref() -> None:
    """A 一般質問 day has ~100 speeches; the download URL for one exceeds the
    2,083-character limit pydantic puts on a URL, which is why the ref points at
    the index instead."""
    pages = _pages()
    many = "".join(f'<INPUT name="downloadPos" value="{i * 977}" >' for i in range(120))
    committee = f"{CGI}See.exe?Code={CODE}&treedepth={_cp932('令和 8年 建設委員会 ')}"
    pages[committee] = f"""<html><body>
<A href="ResultFrame.exe?Code={CODE}&fileName=R080610B04&startPos=0">
<IMG SRC="/ehime/image/r2.gif" WIDTH="12">（ 6月10日）</A><BR>
</body></html>"""
    for name in ("R080225A", "R080302A"):
        pages[f"{CGI}r_Speakers.exe?{CODE}/{name}/0/0//10/1/1073741823:2097151/0/1//0/0/0"] = (
            f"<html><body><FORM>{many}</FORM></body></html>"
        )
    client = FakeClient(pages)
    refs = list(_scraper().list_meetings(client))
    assert len(str(refs[0].url)) < 200


def test_the_code_is_read_from_the_landing_page() -> None:
    """Pinning it in the config would let a rotation fail quietly on every
    request instead of loudly on the first."""
    client = FakeClient(_pages())
    scraper = _scraper()
    assert scraper._session_token(client) == ("cgi-bin3", CODE)


def test_walks_the_tree_and_composes_the_download_url() -> None:
    client = FakeClient(_pages())
    refs = list(_scraper().list_meetings(client))

    assert [r.date for r in refs] == [date(2026, 2, 25), date(2026, 3, 2)]
    assert [r.title for r in refs] == [
        "令和8年第395回定例会（第1号 2月25日）",
        "令和8年第395回定例会（第2号 3月 2日）",
    ]
    # A ref points at the speaker index; the download URL is composed later,
    # because on a busy sitting it runs past pydantic's 2,083-character limit.
    assert str(refs[0].url).endswith(
        "?e7c7rvxas7fwx1belp/R080225A/0/0//10/1/1073741823:2097151/0/1//0/0/0"
    )
    # Listing costs nothing per document, so --since/--until prunes before either fetch.
    assert not any("r_Speakers" in u or "GetPerson" in u for u in client.requested)


def test_committees_are_left_out_by_default() -> None:
    """The same tree carries every 委員会, which would multiply the crawl."""
    client = FakeClient(_pages())
    list(_scraper().list_meetings(client))
    assert not any("建設委員会" in _cp932_decoded(u) for u in client.requested)


def _cp932_decoded(url: str) -> str:
    from urllib.parse import unquote_to_bytes

    return unquote_to_bytes(url).decode("cp932", errors="replace")


def test_years_scopes_which_sessions_are_opened() -> None:
    """A date filter prunes the sittings a walk finds, not the walk itself, so
    `years` is the knob that scopes a crawl.

    Every *tab* is still opened, because that is the only way to learn which years
    exist — a year that is not itself a tab (令和 2年, 平成31年) is reachable no
    other way. What `years` decides is which years get opened for their sessions.
    """
    client = FakeClient(_pages())
    list(_scraper(years=["令和 8年"]).list_meetings(client))
    session = _cp932("令和 8年 第395回定例会 ")
    assert any(session in u for u in client.requested)
    # 平成30年 is a tab, so it is opened to enumerate years...
    assert any(_cp932("平成30年") in u for u in client.requested)
    # ...but no session under it is ever requested.
    assert not any("%95%BD%90%AC30%94N%20" in u for u in client.requested)


def test_an_unreachable_year_is_reported_not_ignored(caplog) -> None:
    """Naming a year the tree does not have used to fail silently."""
    client = FakeClient(_pages())
    with caplog.at_level("WARNING"):
        list(_scraper(years=["令和 9年"]).list_meetings(client))
    assert "令和 9年" in caplog.text  # 平成


def test_plain_text_is_split_on_the_bracketed_marker() -> None:
    client = FakeClient(_pages(), encoding="cp932")
    scraper = _scraper()
    ref = next(iter(scraper.list_meetings(client)))
    meeting = scraper.parse_meeting(ref, scraper.fetch_meeting(ref, client))

    # 「○議事日程」 has no brackets and 「〇出席議員」 is a different circle: neither
    # is a speech, and both sit above the first real marker.
    assert [s.speaker for s in meeting.speeches] == ["福羅浩一議長", "中村時広知事"]
    assert meeting.session == "令和8年第395回定例会"
    assert meeting.date == date(2026, 2, 25)
    assert '<PAGE="2">' not in meeting.speeches[0].text
    # The stored URL is the short index, not the multi-kilobyte download URL.
    assert "downloadPos" not in str(meeting.url)
    # Name and office are one run with no delimiter, so the split is not guessed.
    assert all(s.role is None for s in meeting.speeches)


def test_gannen_is_a_year_node() -> None:
    """「令和元年」 sits in the tree beside 「平成31年」 and covers 2019-05 onwards.
    `\\d{1,2}` does not match 元, and the miss is silent: the node is simply never
    walked and nothing warns."""
    from prefectural_transcripts.scrapers.kensakusystem import _YEAR_NODE, _year_key

    assert _YEAR_NODE.match("令和元年")
    assert _YEAR_NODE.match("平成31年")
    assert not _YEAR_NODE.match("令和元年 第363回定例会 ")
    # 平成31年 must sort before 令和元年, which string order gets backwards.
    assert _year_key("平成31年") < _year_key("令和元年")


# --- 兵庫: the same product, two generations apart -----------------------------
#
# Every fixture below is the shape hyogopref actually serves. Read only the older
# markup and 兵庫 yields nothing at all — which looks exactly like a year the tree
# does not have, and warns about nothing.

HYOGO = "https://www.kensakusystem.jp/hyogopref/"
HCGI = HYOGO + "cgi-bin3/"
HCODE = "rpo2cq1zucjm5gwgk4"

HYOGO_INDEX = f"""<html><body>
<a href="cgi-bin3/See.exe?Code={HCODE}">会議録の閲覧</a>
</body></html>"""

# `data-depth` rather than `onClick="…treedepth.value='…'"`.
HYOGO_ROOT = """<html><body>
<A HREF="#" class="js-tree-submit" data-depth="令和 7年"><IMG ALT="令和 2年～"></A>
</body></html>"""

HYOGO_YEAR = """<html><body>
<A HREF="#" class="js-tree-submit" data-depth="令和 7年"></A>
<A HREF="#" class="js-tree-submit" data-depth="令和 7年  2月第370回定例会 ">2月第370回定例会</A>
<A HREF="#" class="js-tree-submit" data-depth="令和 7年 総務常任委員会 ">総務常任委員会</A>
</body></html>"""

# The 決議案・請願・意見書 the year level lists beside its sittings. Their names
# carry an extension, and `fileName=([A-Za-z0-9]+)` used to take them with the
# `.html` cut off — a request that 404s one hop later.
HYOGO_SESSION = f"""<html><body>
<A href="ResultFrame.exe?Code={HCODE}&fileName=R070225A&startPos=0">
<IMG SRC="/hyogopref/image/r.gif">（第3日 2月25日）</A><BR>
<A href="ResultFrame.exe?Code={HCODE}&fileName=R07060004KETS.html">
<IMG SRC="/hyogopref/image/r.gif">令和 7年 6月決議案第4号</A><BR>
</body></html>"""

# `GetText3.exe?…&FUNC=PRINT_ALL` — HTML, one `<BR>` per line, whole sitting.
# 「○議事日程（第３号）」 has the exact shape of a marker and is not a speech; the
# space after the bracket is what separates them.
HYOGO_TRANSCRIPT = """<html><body>
開催日：令和 7年 2月25日<BR>
○議事日程（第３号）<BR>
○議長（浜田知昭）　　ただいまから本日の会議を開きます。<BR>
○（北野　実議員）　　おはようございます。姫路市選出の北野実です。<BR>
○知事（齋藤元彦）　　北野実議員のご質問にお答えをします。<BR>
</body></html>"""

HYOGO_SPLIT = r"(?m)^○(?P<role>[^（(\n]{0,24})[（(](?P<speaker>[^）)\n]{1,24}?)(?:議員)?[）)][ 　]"


def _hyogo_pages() -> dict[str, str]:
    doc = (
        f"{HCGI}GetText3.exe?Code={HCODE}&fileName=R070225A"
        "&startPos=0&keyMode=10&searchMode=1&FUNC=PRINT_ALL"
    )
    return {
        HYOGO + "index.html": HYOGO_INDEX,
        f"{HCGI}See.exe?Code={HCODE}": HYOGO_ROOT,
        f"{HCGI}See.exe?Code={HCODE}&treedepth={_cp932('令和 7年')}": HYOGO_YEAR,
        f"{HCGI}See.exe?Code={HCODE}&treedepth={_cp932('令和 7年  2月第370回定例会 ')}": (
            HYOGO_SESSION
        ),
        doc: HYOGO_TRANSCRIPT,
    }


def _hyogo() -> KensakuSystemScraper:
    return KensakuSystemScraper(
        KensakuConfig(
            prefecture="兵庫県",
            base_url=HYOGO,
            name="hyogo",
            download="printall",
            speech_split=HYOGO_SPLIT,
        )
    )


def test_the_newer_tree_markup_is_read_too() -> None:
    """兵庫 carries its labels in `data-depth`, not in an `onClick` assignment."""
    client = FakeClient(_hyogo_pages())
    refs = list(_hyogo().list_meetings(client))
    assert [r.date for r in refs] == [date(2025, 2, 25)]
    assert refs[0].title == "令和7年2月第370回定例会（第3日 2月25日）"


def test_documents_that_are_not_sittings_are_left_out(caplog) -> None:
    """兵庫 lists 決議案・請願・意見書 on the same pages as its minutes."""
    client = FakeClient(_hyogo_pages())
    with caplog.at_level("WARNING"):
        refs = list(_hyogo().list_meetings(client))
    assert len(refs) == 1
    assert "KETS" not in str(refs[0].url)
    # A known kind is dropped quietly; an unknown shape would be reported.
    assert not caplog.text


def test_the_older_serial_suffix_is_a_sitting_too() -> None:
    """三重's 平成 archive numbers a continued sitting `H010518A01`.

    The first version of the shape rule allowed one letter and no digits, and
    rejected 52 real sittings. They were reported rather than dropped in silence,
    which is the only reason this is a test and not a hole in the corpus.
    """
    from prefectural_transcripts.scrapers.kensakusystem import _SITTING

    assert _SITTING.match("H010518A01")
    assert _SITTING.match("S610222A")
    # 目次・名簿・議案 are not sittings, with or without their extension.
    assert not _SITTING.match("R080119MOKU")
    assert not _SITTING.match("H070515MEIB.html")


def test_an_unknown_document_shape_is_reported(caplog) -> None:
    """The one thing this project cannot afford is dropping a sitting in silence."""
    pages = _hyogo_pages()
    pages[f"{HCGI}See.exe?Code={HCODE}&treedepth={_cp932('令和 7年  2月第370回定例会 ')}"] = (
        f'<A href="ResultFrame.exe?Code={HCODE}&fileName=R07UNSEENSHAPE">（第3日）</A>'
    )
    client = FakeClient(pages)
    with caplog.at_level("WARNING"):
        list(_hyogo().list_meetings(client))
    assert "R07UNSEENSHAPE" in caplog.text


def test_printall_is_one_request_and_html() -> None:
    """No speaker index, no offsets: 全文表示 hands back the whole sitting."""
    client = FakeClient(_hyogo_pages(), encoding="cp932")
    scraper = _hyogo()
    ref = next(iter(scraper.list_meetings(client)))
    before = len(client.requested)
    meeting = scraper.parse_meeting(ref, scraper.fetch_meeting(ref, client))

    assert len(client.requested) == before + 1
    assert [(s.role, s.speaker) for s in meeting.speeches] == [
        ("議長", "浜田知昭"),
        (None, "北野　実"),
        ("知事", "齋藤元彦"),
    ]
    # 「○議事日程（第３号）」 has a marker's shape and is not a speech.
    assert all("議事日程" not in s.speaker for s in meeting.speeches)


# --- the URL limit that ate three sittings -------------------------------------


def test_a_long_sitting_is_fetched_in_chunks() -> None:
    """`GetPerson.exe` 404s past ~2,110 characters of URL, and `scrape()` logs a
    FetchError and moves on — so the sitting is simply absent afterwards. Three
    愛媛 sittings were lost that way, all of them 3月 days with ~120 speeches.
    """
    from prefectural_transcripts.scrapers.kensakusystem import MAX_URL

    pages = _pages()
    positions = [str(i * 977) for i in range(120)]
    many = "".join(f'<INPUT name="downloadPos" value="{p}" >' for p in positions)
    index = f"{CGI}r_Speakers.exe?{CODE}/R080225A/0/0//10/1/1073741823:2097151/0/1//0/0/0"
    pages[index] = f"<html><body><FORM>{many}</FORM></body></html>"

    stem = f"{CGI}GetPerson.exe?Code={CODE}&fileName=R080225A"
    chunks, current, length = [], [], len(stem)
    for p in positions:
        field = len(f"&downloadPos={p}")
        if current and length + field > MAX_URL:
            chunks.append(current)
            current, length = [], len(stem)
        current.append(p)
        length += field
    chunks.append(current)
    assert len(chunks) > 1, "the fixture must be long enough to need splitting"

    head = "開催日：令和 8年 2月25日\r\n会議名：令和 8年定例会（第1号 2月25日）\r\n\r\n"
    for i, chunk in enumerate(chunks):
        url = stem + "".join(f"&downloadPos={p}" for p in chunk)
        assert len(url) <= MAX_URL
        pages[url] = f"{head}○（{i}番議員）　発言{i}。\r\n"

    client = FakeClient(pages, encoding="cp932")
    scraper = _scraper()
    ref = next(iter(scraper.list_meetings(client)))
    meeting = scraper.parse_meeting(ref, scraper.fetch_meeting(ref, client))

    # Every chunk arrived...
    assert [s.speaker for s in meeting.speeches] == [f"{i}番議員" for i in range(len(chunks))]
    # ...and the header the CGI repeats on each response did not land inside a speech.
    assert all("開催日" not in s.text for s in meeting.speeches)


# --- the marker rule, and the three documents that shaped its bounds -----------


def _shipped_split(name: str) -> str:
    """The rule as it ships, so these tests guard the file the crawl reads."""
    return KensakuConfig.from_toml(SITES_DIR / f"{name}.toml").speech_split


UNIFIED_SPLIT = _shipped_split("ehime")


def test_the_three_tenants_share_one_rule() -> None:
    """They are one rule on purpose, and each divergence has cost a corpus.

    Keeping them equal is also what makes the counts in every comment here
    comparable: a change measured on 兵庫's archive is a change to 三重's too.
    """
    assert _shipped_split("mie") == UNIFIED_SPLIT
    assert _shipped_split("hyogo") == UNIFIED_SPLIT


def test_the_marker_rule_takes_every_form_these_sites_write() -> None:
    """One rule for 愛媛・三重・兵庫, each bound paid for by a real document.

    Every line here is the shape one of the three actually serves; the ones that
    must *not* match are headings that wear a marker's exact shape.
    """
    from prefectural_transcripts.scrapers.generic import split_speeches

    text = "\n".join(
        [
            "○議事日程（第３号）",  # a heading: ends its line
            "〇出席議員　45名",  # a roster, and the other circle
            "○知事（一見勝之）　三重は役職を外に書く。",
            "○（三宅浩正議長）　愛媛の現行はすべて括弧の中。",
            "○（北野　実議員）　兵庫の議員は議員付き。",
            "○47番（岡田己宜君）（拍手）平成の愛媛は拍手で始まる。",
            "○（毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長）　29文字の実在の話者。",
            "○（大北秀特命担当部長(会計管理者)）　名前の中に半角括弧がある。",
        ]
    )
    got = [(s.role, s.speaker) for s in split_speeches(text, UNIFIED_SPLIT)]

    assert got == [
        ("知事", "一見勝之"),
        (None, "三宅浩正議長"),
        (None, "北野　実"),
        ("47番", "岡田己宜"),  # 「君」 goes in _clean_speaker
        (None, "毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長"),
        (None, "大北秀特命担当部長(会計管理者)"),
    ]


def test_the_marker_rule_takes_the_committee_forms_too() -> None:
    """委員会 write the same marker three more ways, and each one parsed to zero.

    兵庫 leaves the marker alone on its line — with the office outside the
    brackets and with it inside — and 三重 drops the brackets altogether. Every
    line below is one of the three tenants' actual markup, and the headings among
    them are the ones that wear a marker's exact shape.
    """
    from prefectural_transcripts.scrapers.generic import split_speeches

    text = "\n".join(
        [
            "○（議事日程）",  # 兵庫 委員会 heading: no office, ends its line
            "○（１　諸　報　告）",
            "○（部外局関係）",
            "○議事日程（第７号）",  # 本会議 heading: office outside, ends its line
            "○委員長（門間雄司）",
            "　　ただいまから総務常任委員会を開会します。",
            "○ＳＤＧｓ推進課長（佐城永修）",
            "　　資料に沿ってご説明します。",
            "○（庄本えつこ委員）",
            "　　１点お伺いします。",
            "○（内藤兵衛委員長発言の概要）",
            "　　運営について申し合わせたとおりです。",
            "○議事日程　　",  # 三重 委員会 heading: nothing follows on the line
            "○小島委員長　　ただいまの報告に対し、御質疑はありませんか。",
            "○宮本課長　　まず、今回の改正というのが、",
        ]
    )
    got = [(s.role, s.speaker) for s in split_speeches(text, UNIFIED_SPLIT)]

    assert got == [
        ("委員長", "門間雄司"),
        ("ＳＤＧｓ推進課長", "佐城永修"),
        ("委員", "庄本えつこ"),
        ("委員長発言の概要", "内藤兵衛"),
        (None, "小島委員長"),
        (None, "宮本課長"),
    ]


def test_a_heading_that_ends_its_line_is_not_a_speaker() -> None:
    """The two guards that let the committee branches exist at all.

    「○議事日程（第７号）」 has branch 2's exact shape and 「○（議事日程）」 branch 3's.
    A digit inside the brackets is what separates the first — a sitting has no
    speaker called 第７号 — and the office suffix separates the second, which is
    和歌山's 「君」 trick under another name.
    """
    import re

    for heading in ("○議事日程（第７号）", "○（議事日程）", "○（２　閉会中の継続調査事件）"):
        assert not re.match(UNIFIED_SPLIT, heading), heading
    for marker in ("○委員長（門間雄司）", "○（庄本えつこ委員）"):
        assert re.match(UNIFIED_SPLIT, marker), marker


def test_a_committee_sitting_records_which_committee() -> None:
    """`committee` is what separates 本会議 from 委員会 once both are in one file."""
    from prefectural_transcripts.scrapers.kensakusystem import _committee

    assert _committee("令和7年総務常任委員会") == "総務常任委員会"
    # 兵庫 names a budget committee for the year it examines, and the two years
    # are genuinely different bodies — so only the leading one comes off.
    assert _committee("令和8年令和8年度予算特別委員会") == "令和8年度予算特別委員会"
    assert _committee("令和6年県庁舎等再整備協議会") == "県庁舎等再整備協議会"
    assert _committee("令和8年第395回定例会") is None
    # 兵庫's truncated 「第198回定」 is a 定例会 whose label does not say so. An
    # "everything that is not 定例会 is a committee" rule would file it as one.
    assert _committee("昭和61年第198回定") is None
    assert _committee(None) is None


def test_the_year_node_is_not_one_of_its_own_sessions() -> None:
    """The tree repeats the year among its children; opening it walks in circles.

    It cost nothing while `sessions` named the kinds of session wanted. With
    `sessions = '.'` — which is what collects the committees — the year label
    matches like anything else.
    """
    client = FakeClient(_pages())
    refs = list(_scraper(sessions=".").list_meetings(client))

    assert [r.title for r in refs] == [
        "令和8年第395回定例会（第1号 2月25日）",
        "令和8年第395回定例会（第2号 3月 2日）",
        "令和8年建設委員会（ 6月10日）",
    ]
    # 「令和8年第395回定例会（第1号 2月25日）」 appears once. The year page lists that
    # sitting too, so opening the year as a session would collect it twice.
    assert len(refs) == len({str(r.url) for r in refs})


def test_a_label_truncated_by_the_site_is_still_opened() -> None:
    """兵庫's tree carries 「昭和61年 第198回定 」, cut off mid-word by whoever typed
    it, and the sitting of 1986-06-05 hangs underneath. `定例会|臨時会` skipped the
    node and nothing warned — a node that is never opened has no smoke test. This
    is why all three tenants now say `sessions = '.'`."""
    pages = _hyogo_pages()
    truncated = "令和 7年 第198回定 "
    pages[f"{HCGI}See.exe?Code={HCODE}&treedepth={_cp932('令和 7年')}"] = HYOGO_YEAR.replace(
        "総務常任委員会 ", "第198回定 "
    )
    pages[f"{HCGI}See.exe?Code={HCODE}&treedepth={_cp932(truncated)}"] = (
        f'<A href="ResultFrame.exe?Code={HCODE}&fileName=R070605A">（第3日 6月 5日）</A>'
    )
    client = FakeClient(pages)

    scraper = KensakuSystemScraper(
        KensakuConfig(
            prefecture="兵庫県",
            base_url=HYOGO,
            name="hyogo",
            download="printall",
            speech_split=HYOGO_SPLIT,
            sessions=".",
        )
    )
    assert date(2025, 6, 5) in [r.date for r in scraper.list_meetings(client)]


# --- 愛媛's rosters, which are the delimiter its markers do not have -----------

ROSTER = """〇出席議員　44名
　　１番　　井　川　　　剛
　　９番　　三　宅　浩　正

〇出席理事者
　知事　　　　　　　　　　中　村　時　広
　デジタル変革担当部長　　大　内　康　夫
　　観光スポーツ文化部長　金　子　浩　一
　財政課長　　　　　　　　知　念　良　輝

〇出席事務局職員
　事務局長　　　　　　　　須　藤　達　也
"""


def test_the_roster_is_read_off_the_sitting_itself() -> None:
    from prefectural_transcripts.scrapers.kensakusystem import roster_names, roster_offices

    names = roster_names(ROSTER)
    assert {"三宅浩正", "中村時広", "大内康夫", "知念良輝", "須藤達也"} <= names
    # The padding between office and name is two spaces on most rows and **one**
    # on some — 「　　観光スポーツ文化部長　金　子　浩　一」 — so the name rule reads
    # nothing there and the office rule has to.
    assert "金子浩一" not in names
    assert "観光スポーツ文化部長" in roster_offices(ROSTER)


def test_a_name_and_an_office_are_split_only_where_the_roster_says_so() -> None:
    """「○（三宅浩正議長）」 is one run with nothing to split on, and leaving it that
    way made 「中畑保一」 and 「中畑保一議長」 two speakers — 38 people counted twice,
    every one of them someone who held an office."""
    from prefectural_transcripts.scrapers.kensakusystem import (
        roster_names,
        roster_offices,
        split_on_roster,
    )

    names, offices = roster_names(ROSTER), roster_offices(ROSTER)

    assert split_on_roster("三宅浩正議長", names, offices) == ("三宅浩正", "議長")
    assert split_on_roster("大内康夫デジタル変革担当部長", names, offices) == (
        "大内康夫",
        "デジタル変革担当部長",
    )
    # Read off the office side, because the name side cannot parse that row.
    assert split_on_roster("金子浩一観光スポーツ文化部長", names, offices) == (
        "金子浩一",
        "観光スポーツ文化部長",
    )
    # 「○（財政課長）」 names nobody. The roster does say who holds the post, and
    # attaching them would be attributing a speech the record does not attribute.
    assert split_on_roster("財政課長", names, offices) == ("財政課長", None)
    # A speaker the roster has never heard of is left exactly as printed.
    assert split_on_roster("山田太郎参考人", names, offices) == ("山田太郎参考人", None)


def test_the_split_is_off_unless_a_config_asks_for_it() -> None:
    """三重 and 兵庫 print name and office separately; only 愛媛 needs this, and a
    surname-only marker like 三重's 「○小島委員長」 must not be cut down to 「小島」."""
    assert not KensakuConfig(prefecture="三重県", base_url=BASE).roster_split
    assert KensakuConfig.from_toml(SITES_DIR / "ehime.toml").roster_split
    assert not KensakuConfig.from_toml(SITES_DIR / "mie.toml").roster_split
    assert not KensakuConfig.from_toml(SITES_DIR / "hyogo.toml").roster_split
