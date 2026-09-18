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

    def __init__(self, pages: dict[str, str], encoding: str = "utf-8") -> None:
        self.pages = pages
        self.encoding = encoding
        """Some sites are cp932 and a scraper may decode the raw body itself."""
        self.requested: list[str] = []

    def get(self, url: str, *, force: bool = False) -> Page:
        self.requested.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected request for {url}")
        return make_page(url, self.pages[url], self.encoding)


class FakeApiClient:
    """Stands in for PoliteClient on a POST-only JSON API, with no network.

    SSP has no pages to can: every listing and every transcript is a POST to one
    of three URLs, told apart only by the body. So responses are keyed by the
    endpoint's last path segment and the payload fields that select the document.
    """

    def __init__(self, responses: dict[tuple[str, ...], str]) -> None:
        self.responses = responses
        self.requested: list[tuple[str, ...]] = []

    @staticmethod
    def key(url: str, payload: dict[str, object]) -> tuple[str, ...]:
        endpoint = url.rstrip("/").rsplit("/", 1)[-1]
        ids = tuple(
            str(payload[field]) for field in ("council_id", "schedule_id") if field in payload
        )
        return (endpoint, *ids)

    def post(
        self,
        url: str,
        *,
        json: dict[str, object] | None = None,
        data: dict[str, str] | None = None,
        force: bool = False,
    ) -> Page:
        key = self.key(url, json or {})
        self.requested.append(key)
        if key not in self.responses:
            raise AssertionError(f"unexpected request {key}; have {sorted(self.responses)}")
        return make_page(url, self.responses[key])

    def get(self, url: str, *, force: bool = False) -> Page:
        raise AssertionError(f"this API is POST-only; something asked to GET {url}")


@pytest.fixture
def fake_client() -> type[FakeClient]:
    return FakeClient


@pytest.fixture
def fake_api_client() -> type[FakeApiClient]:
    return FakeApiClient
