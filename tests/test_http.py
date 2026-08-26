from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

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
