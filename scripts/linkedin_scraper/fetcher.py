"""
Rate-limited HTTP session for LinkedIn jobs-guest API.

Safety valves:
  - Rotating pool of realistic User-Agent strings (per request)
  - Configurable inter-request delay with jitter
  - Exponential backoff on 429 (5s -> 30s -> 120s)
  - Hard abort after N consecutive 429s

The session is stateless from LinkedIn's perspective: no cookies persisted,
no session tracking. Each request looks like a fresh browser hit. Mirrors the
2026 dev.to reference's "minimum" recommendations.
"""

import random
import time
from dataclasses import dataclass
from typing import Optional

import requests


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
]

BACKOFF_LADDER = [5, 30, 120]
MAX_CONSECUTIVE_429 = 3


@dataclass
class RateLimitError(Exception):
    """Raised when LinkedIn returns repeated 429s and the session aborts."""
    message: str

    def __str__(self) -> str:
        return self.message


class RateLimitedSession:
    """
    Wraps requests.Session with per-request delay, UA rotation, and 429 backoff.

    Usage:
        session = RateLimitedSession(search_delay=3.0, detail_delay=5.0)
        html = session.get_search(url)
        html = session.get_detail(url)
    """

    def __init__(
        self,
        search_delay: float = 3.0,
        detail_delay: float = 5.0,
        jitter_pct: float = 0.25,
        timeout: float = 15.0,
        verbose: bool = False,
    ):
        self.search_delay = search_delay
        self.detail_delay = detail_delay
        self.jitter_pct = jitter_pct
        self.timeout = timeout
        self.verbose = verbose
        self._session = requests.Session()
        self._last_request_at: Optional[float] = None
        self._consecutive_429s = 0

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "close",
        }

    def _sleep(self, base_delay: float) -> None:
        if self._last_request_at is None:
            return
        jitter = base_delay * self.jitter_pct
        delay = base_delay + random.uniform(-jitter, jitter)
        elapsed = time.monotonic() - self._last_request_at
        remaining = delay - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _do_get(self, url: str, base_delay: float) -> str:
        self._sleep(base_delay)
        attempt = 0
        while True:
            try:
                resp = self._session.get(url, headers=self._headers(), timeout=self.timeout)
            except requests.RequestException as exc:
                self._last_request_at = time.monotonic()
                raise RateLimitError(f"Network error fetching {url}: {exc}") from exc
            self._last_request_at = time.monotonic()

            if resp.status_code == 200:
                self._consecutive_429s = 0
                return resp.text

            if resp.status_code == 429:
                self._consecutive_429s += 1
                if self._consecutive_429s >= MAX_CONSECUTIVE_429:
                    raise RateLimitError(
                        f"Aborted after {MAX_CONSECUTIVE_429} consecutive 429s "
                        f"(URL: {url}). LinkedIn is rate-limiting this IP — "
                        f"wait 30+ minutes before retrying."
                    )
                if attempt >= len(BACKOFF_LADDER):
                    raise RateLimitError(
                        f"429 backoff exhausted (URL: {url}). Aborting."
                    )
                wait = BACKOFF_LADDER[attempt]
                if self.verbose:
                    print(f"    429 (attempt {attempt + 1}) — backing off {wait}s")
                time.sleep(wait)
                attempt += 1
                continue

            # 404 is expected for expired/removed jobs — return empty
            if resp.status_code == 404:
                return ""

            raise RateLimitError(
                f"Unexpected HTTP {resp.status_code} for {url} "
                f"(body: {resp.text[:200]})"
            )

    def get_search(self, url: str) -> str:
        return self._do_get(url, self.search_delay)

    def get_detail(self, url: str) -> str:
        return self._do_get(url, self.detail_delay)
