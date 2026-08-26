from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from prefectural_transcripts.http import Page, ResponseCache, sniff_encoding


def test_meta_charset_beats_a_wrong_http_header() -> None:
    # Legacy Japanese sites are frequently fronted by a proxy that stamps
    # utf-8 on every response regardless of the real bytes.
    html = '<html><head><meta charset="shift_jis"></head><body>東京都議会</body></html>'
    body = html.encode("shift_jis")
    assert sniff_encoding(body, "utf-8") == "shift_jis"


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
