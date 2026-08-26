from __future__ import annotations

from datetime import UTC, datetime

import pytest

from prefectural_transcripts.http import Page


def make_page(url: str, html: str, encoding: str = "utf-8") -> Page:
    return Page(
        url=url,
        status=200,
        body=html.encode(encoding),
        encoding=encoding,
        fetched_at=datetime.now(UTC),
        from_cache=False,
    )


class FakeClient:
    """Stands in for PoliteClient, serving canned HTML with no network."""

    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    def get(self, url: str, *, force: bool = False) -> Page:
        self.requested.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected request for {url}")
        return make_page(url, self.pages[url])


@pytest.fixture
def fake_client() -> type[FakeClient]:
    return FakeClient
