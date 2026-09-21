from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from prefectural_transcripts.http import Page, ResponseCache, sniff_encoding


def test_meta_charset_beats_a_wrong_http_header() -> None:
    # Legacy Japanese sites are frequently fronted by a proxy that stamps
    # utf-8 on every response regardless of the real bytes.
    html = '<html><head><meta charset="shift_jis"></head><body>東京都議会</body></html>'
    body = html.encode("shift_jis")
    assert sniff_encoding(body, "utf-8") == "cp932"


def test_falls_back_to_header_when_no_meta_tag() -> None:
    body = "<html><body>大阪府議会</body></html>".encode("euc-jp")
    assert sniff_encoding(body, "euc-jp") == "euc-jp"


def test_sniffs_when_nothing_is_declared() -> None:
    body = "<html><body>北海道議会</body></html>".encode()
    decoded = body.decode(sniff_encoding(body, None))
    assert "北海道議会" in decoded


def test_unusable_declared_charset_is_rejected() -> None:
    # Declared shift_jis, actually utf-8 — decoding must still succeed.
    html = '<html><head><meta charset="shift_jis"></head><body>議会</body></html>'
    body = html.encode()
    encoding = sniff_encoding(body, None)
    assert "議会" in body.decode(encoding, errors="strict")


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path)
    page = Page(
        url="https://example.invalid/a",
        status=200,
        body="<html>本会議</html>".encode(),
        encoding="utf-8",
        fetched_at=datetime.now(UTC),
        from_cache=False,
    )
    assert cache.get(page.url) is None
    cache.put(page)

    restored = cache.get(page.url)
    assert restored is not None
    assert restored.from_cache is True
    assert restored.text == page.text
    assert restored.sha256 == page.sha256


def test_cache_keys_are_per_url(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path)
    for url in ("https://example.invalid/a", "https://example.invalid/b"):
        cache.put(
            Page(
                url=url,
                status=200,
                body=url.encode(),
                encoding="utf-8",
                fetched_at=datetime.now(UTC),
                from_cache=False,
            )
        )
    a = cache.get("https://example.invalid/a")
    b = cache.get("https://example.invalid/b")
    assert a is not None and b is not None
    assert a.body != b.body


def test_shift_jis_is_decoded_as_its_microsoft_superset() -> None:
    # 﨑 (U+FA11) is a NEC/IBM extension: common in names, absent from base
    # Shift_JIS. A page carrying one must not fall back to some other encoding.
    html = '<meta charset="Shift_JIS"><p>○六番（河原﨑　全君）　質問します。</p>'
    body = html.encode("cp932")

    encoding = sniff_encoding(body, "Shift_JIS")

    assert encoding == "cp932"
    assert "河原﨑" in body.decode(encoding)


def test_cached_pages_are_re_sniffed_rather_than_trusting_stored_encoding(
    tmp_path: Path,
) -> None:
    body = '<meta charset="Shift_JIS"><p>○知事（鈴木康友君）　お答えします。</p>'.encode("cp932")
    cache = ResponseCache(tmp_path)
    cache.put(
        Page(
            url="https://example.invalid/1",
            status=200,
            body=body,
            encoding="utf-8",  # a wrong conclusion, as an older run might have stored
            fetched_at=datetime.now(UTC),
            from_cache=False,
        )
    )

    cached = cache.get("https://example.invalid/1")

    assert cached is not None
    assert cached.encoding == "cp932"
    assert "鈴木康友" in cached.text


def test_cache_keeps_the_header_charset_for_pages_with_no_meta_tag(tmp_path: Path) -> None:
    # 静岡's minutes pages declare their charset only in the HTTP header, so a
    # cache that forgets it decodes worse on the second run than on the first.
    body = "<html><body><p>○知事（鈴木康友君）　お答えします。</p></body></html>".encode("cp932")
    cache = ResponseCache(tmp_path)
    cache.put(
        Page(
            url="https://example.invalid/2",
            status=200,
            body=body,
            encoding="cp932",
            fetched_at=datetime.now(UTC),
            from_cache=False,
            header_charset="Shift_JIS",
        )
    )

    cached = cache.get("https://example.invalid/2")

    assert cached is not None
    assert cached.encoding == "cp932"
    assert "鈴木康友" in cached.text


def test_no_cache_still_stores_what_it_fetched(tmp_path: Path) -> None:
    # --no-cache means "don't serve me a stale copy", not "discard the response".
    import httpx

    from prefectural_transcripts.config import Settings
    from prefectural_transcripts.http import PoliteClient

    settings = Settings()
    settings.cache_dir = tmp_path
    settings.use_cache = False
    settings.min_interval = 0.0
    settings.respect_robots = False

    body = "<html><body>会議録</body></html>".encode("cp932")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=body, headers={"Content-Type": "text/html; charset=Shift_JIS"}
        )
    )
    with PoliteClient(settings, client=httpx.Client(transport=transport)) as client:
        client.get("https://example.invalid/page")

    stored = ResponseCache(tmp_path).get("https://example.invalid/page")
    assert stored is not None
    assert stored.encoding == "cp932"
    assert (stored.header_charset or "").lower() == "shift_jis"


# --- POST, and the robots exemption it exists for --------------------------


def test_post_caches_per_request_body(tmp_path: Path) -> None:
    # Every SSP API call goes to one of three URLs and differs only in the body,
    # so a URL-keyed cache would serve one 会議's transcript for all of them.
    import httpx

    from prefectural_transcripts.config import Settings
    from prefectural_transcripts.http import PoliteClient

    settings = Settings()
    settings.cache_dir = tmp_path
    settings.min_interval = 0.0
    settings.respect_robots = False

    seen: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content)
        return httpx.Response(200, json={"echo": request.content.decode()})

    with PoliteClient(settings, client=httpx.Client(transport=httpx.MockTransport(handler))) as c:
        first = c.post("https://example.invalid/api", json={"council_id": 1})
        second = c.post("https://example.invalid/api", json={"council_id": 2})
        again = c.post("https://example.invalid/api", json={"council_id": 1})

    assert len(seen) == 2, "the repeat should have come from the cache"
    assert first.body != second.body
    assert again.from_cache and again.body == first.body


def test_a_robots_exemption_must_say_why_and_when() -> None:
    from prefectural_transcripts.config import RobotsExemption

    with pytest.raises(ValueError, match="record why"):
        RobotsExemption(prefixes=("https://x.invalid/a",), reason="  ", decided_on="2026-09-18")
    with pytest.raises(ValueError, match="decided_on"):
        RobotsExemption(
            prefixes=("https://x.invalid/a",), reason="asked, not refused", decided_on="soon"
        )
    with pytest.raises(ValueError, match="at least one"):
        RobotsExemption(prefixes=(), reason="asked, not refused", decided_on="2026-09-18")
    with pytest.raises(ValueError, match="absolute"):
        RobotsExemption(prefixes=("/dnp/search/",), reason="asked", decided_on="2026-09-18")


def test_an_exemption_covers_its_prefixes_and_nothing_else(tmp_path: Path) -> None:
    # The scoping is the point: SSP's operator disallows /tenant/js/ specifically,
    # and that narrow refusal has to survive an exemption written for the API.
    import httpx

    from prefectural_transcripts.config import RobotsExemption, Settings
    from prefectural_transcripts.http import PoliteClient, RobotsDisallowed

    robots = "User-agent: *\nDisallow: /\nAllow: /tenant/\nDisallow: /tenant/js/\n"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        return httpx.Response(200, text="ok")

    settings = Settings()
    settings.cache_dir = tmp_path
    settings.min_interval = 0.0

    exemption = RobotsExemption(
        prefixes=("https://ssp.invalid/dnp/search/",),
        reason="operator did not refuse when asked",
        decided_on="2026-09-18",
    )
    transport = httpx.MockTransport(handler)

    with (
        PoliteClient(settings, client=httpx.Client(transport=transport)) as plain,
        pytest.raises(RobotsDisallowed),
    ):
        plain.get("https://ssp.invalid/dnp/search/councils/index")

    with PoliteClient(
        settings, client=httpx.Client(transport=transport), robots_exempt=exemption
    ) as client:
        assert client.get("https://ssp.invalid/dnp/search/councils/index").status == 200
        with pytest.raises(RobotsDisallowed):
            client.get("https://ssp.invalid/tenant/js/release/config.js")


def test_offline_refuses_a_miss_instead_of_fetching(tmp_path: Path) -> None:
    # The standing checks are described as costing nothing because everything is
    # cached. That was true by luck until this: a listing page that happened to
    # be missing would have been fetched — and on 滋賀 or 石川 that means a
    # request outside the hours they agreed to, from a script whose whole job is
    # to read what we already hold.
    import httpx

    from prefectural_transcripts.config import Settings
    from prefectural_transcripts.http import FetchError, PoliteClient

    settings = Settings()
    settings.cache_dir = tmp_path
    settings.min_interval = 0.0
    settings.respect_robots = False
    settings.offline = True

    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        return httpx.Response(200, text="should never be reached")

    with (
        PoliteClient(settings, client=httpx.Client(transport=httpx.MockTransport(handler))) as c,
        pytest.raises(FetchError, match="not cached"),
    ):
        c.get("https://example.invalid/never-fetched")
    assert asked == []
