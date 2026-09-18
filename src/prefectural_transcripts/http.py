"""A deliberately polite HTTP client.

Three things matter for this crawl and none of them are the default anywhere:

1. **Rate limiting per host.** Prefectural assembly sites are small. We serialise
   requests per host and sleep between them, honouring robots.txt `Crawl-delay`.
2. **Caching to disk.** Re-parsing is common while selectors are being tuned;
   re-downloading is not acceptable. Every response body is stored under its URL
   hash so a second run is free and offline.
3. **Encoding.** Many of these pages are Shift_JIS or EUC-JP and say so only in a
   `<meta>` tag, or lie in the HTTP header. We sniff rather than trust.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import urllib.robotparser
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from charset_normalizer import from_bytes

from prefectural_transcripts.config import RobotsExemption, Settings

log = logging.getLogger(__name__)

_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-]+)""", re.I)

RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})


class FetchError(RuntimeError):
    """Raised when a URL could not be retrieved after retries."""


class RobotsDisallowed(FetchError):
    """Raised when robots.txt forbids the URL for our user-agent."""


@dataclass(slots=True)
class Page:
    """A fetched page, already decoded to text."""

    url: str
    status: int
    body: bytes
    encoding: str
    fetched_at: datetime
    from_cache: bool
    header_charset: str | None = None
    """What the HTTP header claimed, kept so a cached body can be re-sniffed.

    Some of these pages carry no `<meta charset>` at all, and the header is then
    the only signal there is — dropping it on the way into the cache would make
    a cached page decode worse than a freshly fetched one.
    """

    @property
    def text(self) -> str:
        return self.body.decode(self.encoding, errors="replace")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


def sniff_encoding(body: bytes, header_charset: str | None) -> str:
    """Best-effort charset detection for legacy Japanese pages.

    The `<meta>` tag is checked before the HTTP header because these sites are
    frequently served by a proxy that stamps a wrong `charset=` on everything.
    """
    if m := _META_CHARSET.search(body[:4096]):
        candidate = m.group(1).decode("ascii", errors="ignore")
        if _is_usable(body, candidate):
            return _normalise(candidate)
    if header_charset and _is_usable(body, header_charset):
        return _normalise(header_charset)
    if best := from_bytes(body).best():
        return _normalise(best.encoding)
    return "utf-8"


# A page that declares Shift_JIS almost always contains cp932, Microsoft's
# superset of it. The NEC/IBM extension characters cp932 adds are not
# exotic here: they are the ones Japanese personal names use — 﨑, 髙, 桒 — so a
# single member's name is enough to make the base codec fail on a whole sitting.
# Decoding as cp932 is safe (it is a strict extension of Shift_JIS) and is what
# every browser does with these pages.
_ALIASES = {
    "shift-jis": "cp932",
    "shift_jis": "cp932",
    "sjis": "cp932",
    "x-sjis": "cp932",
    "windows-31j": "cp932",
    "ms_kanji": "cp932",
    # EUC-JP has the same problem and no equivalent fix here: CPython ships no
    # MS-extended EUC codec, so a EUC-JP page carrying those characters still
    # falls through to charset-normalizer. Left alone until a real page needs it.
}


def _normalise(enc: str) -> str:
    key = enc.lower().strip()
    return _ALIASES.get(key, key)


def _is_usable(body: bytes, enc: str) -> bool:
    try:
        body.decode(_normalise(enc))
    except (UnicodeDecodeError, LookupError):
        return False
    return True


def _canonical_request(payload: Mapping[str, Any]) -> str:
    """A stable text form of a request body, for the cache key and the log.

    Sorted keys so that two identical requests written in a different order are
    one cache entry rather than two requests to someone else's server.
    """
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class ResponseCache:
    """Content-addressed cache of raw response bodies under `cache_dir`.

    The key is the URL for a GET. A POST needs the request body in the key too —
    every SSP API call goes to one of six URLs and differs only in what is sent —
    so `key` is separable from the URL the page came from.
    """

    def __init__(self, cache_dir: Path) -> None:
        self.dir = cache_dir

    def _paths(self, key: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(key.encode()).hexdigest()
        sub = self.dir / digest[:2]
        return sub / f"{digest}.body", sub / f"{digest}.json"

    def get(self, key: str, *, url: str | None = None) -> Page | None:
        body_path, meta_path = self._paths(key)
        if not (body_path.exists() and meta_path.exists()):
            return None
        meta = json.loads(meta_path.read_text())
        body = body_path.read_bytes()
        return Page(
            url=url or meta.get("url") or key,
            status=meta["status"],
            body=body,
            # The bytes are the truth; the encoding is a conclusion drawn from
            # them. Re-deriving it on read means a fix to `sniff_encoding` reaches
            # everything already cached, instead of only pages fetched afterwards.
            # Entries written before `header_charset` existed fall back to the
            # encoding they concluded at the time, which is re-validated anyway.
            encoding=sniff_encoding(body, meta.get("header_charset") or meta.get("encoding")),
            header_charset=meta.get("header_charset"),
            fetched_at=datetime.fromisoformat(meta["fetched_at"]),
            from_cache=True,
        )

    def put(self, page: Page, *, key: str | None = None, request: str | None = None) -> None:
        body_path, meta_path = self._paths(key or page.url)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_bytes(page.body)
        meta_path.write_text(
            json.dumps(
                {
                    "url": page.url,
                    "status": page.status,
                    "encoding": page.encoding,
                    "header_charset": page.header_charset,
                    "fetched_at": page.fetched_at.isoformat(),
                    # What was asked, for a POST — otherwise the cache holds an
                    # answer to a question nobody can read back.
                    **({"request": request} if request is not None else {}),
                },
                ensure_ascii=False,
            )
        )


@dataclass(slots=True)
class _HostState:
    next_allowed: float = 0.0
    crawl_delay: float | None = None
    robots: urllib.robotparser.RobotFileParser | None = None
    robots_loaded: bool = False


class PoliteClient:
    """Rate-limited, caching, robots-aware HTTP client.

    Use as a context manager; it owns an `httpx.Client`.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        robots_exempt: RobotsExemption | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.cache = ResponseCache(self.settings.cache_dir)
        self.robots_exempt = robots_exempt
        """Scoped exception to robots.txt, from the site config. See `RobotsExemption`."""
        self._exemptions_logged: set[str] = set()
        self._hosts: dict[str, _HostState] = {}
        self._lock = threading.Lock()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            follow_redirects=True,
            timeout=self.settings.timeout,
            headers={"User-Agent": self.settings.user_agent},
        )

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # -- politeness -----------------------------------------------------

    def _state(self, host: str) -> _HostState:
        with self._lock:
            return self._hosts.setdefault(host, _HostState())

    def _load_robots(self, url: str) -> None:
        parsed = urlparse(url)
        state = self._state(parsed.netloc)
        if state.robots_loaded:
            return
        robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            resp = self._client.get(robots_url)
            parser.parse(resp.text.splitlines() if resp.status_code == 200 else [])
        except httpx.HTTPError as exc:
            log.warning("could not fetch %s (%s); assuming allowed", robots_url, exc)
            parser.parse([])
        state.robots = parser
        state.robots_loaded = True
        delay = parser.crawl_delay(self.settings.user_agent)
        if delay is not None:
            state.crawl_delay = float(delay)
            log.info("%s advertises Crawl-delay: %ss", parsed.netloc, delay)

    def _check_robots(self, url: str) -> None:
        if not self.settings.respect_robots:
            return
        if self.robots_exempt and self.robots_exempt.covers(url):
            self._announce_exemption(url)
            return
        self._load_robots(url)
        state = self._state(urlparse(url).netloc)
        if state.robots and not state.robots.can_fetch(self.settings.user_agent, url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

    def _announce_exemption(self, url: str) -> None:
        """Say once, per prefix and per run, that robots.txt was set aside here.

        At WARNING deliberately. Every run log that fetched an exempted URL then
        carries the reason and the date the researcher decided it, so the record
        does not live only in a config file nobody re-reads.
        """
        for prefix in self.robots_exempt.prefixes if self.robots_exempt else ():
            if url.startswith(prefix) and prefix not in self._exemptions_logged:
                self._exemptions_logged.add(prefix)
                assert self.robots_exempt is not None
                log.warning(
                    "robots.txt set aside for %s by decision of %s: %s",
                    prefix,
                    self.robots_exempt.decided_on,
                    self.robots_exempt.reason,
                )

    def _throttle(self, host: str) -> None:
        state = self._state(host)
        interval = max(self.settings.min_interval, state.crawl_delay or 0.0)
        with self._lock:
            wait = state.next_allowed - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            state.next_allowed = time.monotonic() + interval

    # -- fetching -------------------------------------------------------

    def get(self, url: str, *, force: bool = False) -> Page:
        """Fetch `url`, returning a cached copy unless `force` is set."""
        if self.settings.use_cache and not force and (cached := self.cache.get(url)):
            log.debug("cache hit %s", url)
            return cached

        self._check_robots(url)
        page = self._send_with_retries("GET", url)
        # Written even when the cache is switched off for reading: `use_cache=False`
        # means "don't hand me a stale copy", not "throw away what you just paid a
        # request for". Discarding it makes the next run re-fetch a page we already
        # have, which is the opposite of polite.
        self.cache.put(page)
        return page

    def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        data: Mapping[str, str] | None = None,
        force: bool = False,
    ) -> Page:
        """POST `url` and cache the response under URL + request body.

        Needed for one product so far: SSP (Discuss Net Premium) has no
        server-rendered route at all — every listing and every transcript comes
        back from a POST to `/dnp/search/…`, and the URL alone does not say what
        was asked. Everything else — rate limiting, retries, the cache, the
        robots check — is the same path a GET takes.
        """
        if json is not None and data is not None:
            raise ValueError("post() takes json= or data=, not both")
        body = _canonical_request(json if json is not None else data or {})
        kind = "json" if json is not None else "form"
        key = f"{url}#{kind}:{hashlib.sha256(body.encode()).hexdigest()}"

        if self.settings.use_cache and not force and (cached := self.cache.get(key, url=url)):
            log.debug("cache hit %s %s", url, body)
            return cached

        self._check_robots(url)
        page = self._send_with_retries("POST", url, json=json, data=data)
        self.cache.put(page, key=key, request=body)
        return page

    def _send_with_retries(
        self,
        method: str,
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> Page:
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            self._throttle(host)
            try:
                resp = self._client.request(method, url, json=json, data=data)
            except httpx.HTTPError as exc:
                last = exc
                log.warning(
                    "attempt %d/%d failed for %s: %s",
                    attempt,
                    self.settings.max_retries,
                    url,
                    exc,
                )
            else:
                if resp.status_code in RETRYABLE_STATUSES:
                    last = FetchError(f"HTTP {resp.status_code} for {url}")
                    self._honour_retry_after(host, resp)
                    log.warning(
                        "attempt %d/%d got HTTP %d for %s",
                        attempt,
                        self.settings.max_retries,
                        resp.status_code,
                        url,
                    )
                elif resp.status_code >= 400:
                    raise FetchError(f"HTTP {resp.status_code} for {url}")
                else:
                    body = resp.content
                    return Page(
                        url=str(resp.url),
                        status=resp.status_code,
                        body=body,
                        encoding=sniff_encoding(body, resp.charset_encoding),
                        header_charset=resp.charset_encoding,
                        fetched_at=datetime.now(UTC),
                        from_cache=False,
                    )
            time.sleep(min(2.0**attempt, 60.0))
        raise FetchError(f"giving up on {url} after {self.settings.max_retries} attempts") from last

    def _honour_retry_after(self, host: str, resp: httpx.Response) -> None:
        raw = resp.headers.get("Retry-After")
        if not raw:
            return
        try:
            seconds = float(raw)
        except ValueError:
            return
        state = self._state(host)
        with self._lock:
            state.next_allowed = max(state.next_allowed, time.monotonic() + seconds)
