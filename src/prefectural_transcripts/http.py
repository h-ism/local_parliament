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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from charset_normalizer import from_bytes

from prefectural_transcripts.config import Settings

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


class ResponseCache:
    """Content-addressed cache of raw response bodies under `cache_dir`."""

    def __init__(self, cache_dir: Path) -> None:
        self.dir = cache_dir

    def _paths(self, url: str) -> tuple[Path, Path]:
        digest = hashlib.sha256(url.encode()).hexdigest()
        sub = self.dir / digest[:2]
        return sub / f"{digest}.body", sub / f"{digest}.json"

    def get(self, url: str) -> Page | None:
        body_path, meta_path = self._paths(url)
        if not (body_path.exists() and meta_path.exists()):
            return None
        meta = json.loads(meta_path.read_text())
        body = body_path.read_bytes()
        return Page(
            url=url,
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

    def put(self, page: Page) -> None:
        body_path, meta_path = self._paths(page.url)
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
        self, settings: Settings | None = None, client: httpx.Client | None = None
    ) -> None:
        self.settings = settings or Settings()
        self.cache = ResponseCache(self.settings.cache_dir)
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
        self._load_robots(url)
        state = self._state(urlparse(url).netloc)
        if state.robots and not state.robots.can_fetch(self.settings.user_agent, url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

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
        page = self._get_with_retries(url)
        # Written even when the cache is switched off for reading: `use_cache=False`
        # means "don't hand me a stale copy", not "throw away what you just paid a
        # request for". Discarding it makes the next run re-fetch a page we already
        # have, which is the opposite of polite.
        self.cache.put(page)
        return page

    def _get_with_retries(self, url: str) -> Page:
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            self._throttle(host)
            try:
                resp = self._client.get(url)
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
