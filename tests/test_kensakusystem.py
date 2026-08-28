"""Offline tests for the `kensakusystem.jp` scraper.

Every URL here is the shape the live site actually serves; the point of the
fixtures is the awkward parts — a tree navigated through `onClick` with a
cp932-encoded label, a transcript assembled from character offsets, and a body
that is plain text rather than HTML.
"""

from __future__ import annotations

from datetime import date

from conftest import FakeClient
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

YEAR_R8 = """<html><body>
<A onClick="document.viewtree.treedepth.value='令和 8年'">令和 8年</A>
<A onClick="document.viewtree.treedepth.value='令和 7年'">令和 7年</A>
<A onClick="document.viewtree.treedepth.value='令和 8年 第395回定例会 '">第395回定例会</A>
<A onClick="document.viewtree.treedepth.value='令和 8年 建設委員会 '">建設委員会</A>
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
