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
