"""HTTP fetcher: retrieves raw HTML with politeness and resilience.

Uses a `requests.Session` for connection reuse. Never raises to the caller:
malformed URLs, timeouts and HTTP errors are logged and return ``None``.
Transient failures (429/5xx) are retried with exponential backoff.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests

from crawler import config

logger = logging.getLogger(__name__)

_RETRIABLE_STATUS = {429, 500, 502, 503, 504}


class Fetcher:
    """Retrieves raw HTML over HTTP/HTTPS."""

    def __init__(
        self,
        politeness_delay_s: float | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
        respect_robots: bool | None = None,
    ) -> None:
        self.politeness_delay_s = (
            politeness_delay_s if politeness_delay_s is not None
            else config.POLITENESS_DELAY_S
        )
        self.timeout = (
            timeout if timeout is not None
            else config.REQUEST_TIMEOUT_S
        )
        self.respect_robots = (
            config.RESPECT_ROBOTS_TXT if respect_robots is None else respect_robots
        )
        self.max_retries = config.MAX_RETRIES
        self.backoff_s = config.RETRY_BACKOFF_S

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or config.USER_AGENT})

        self._last_request_time: dict[str, float] = {}

        self._robots_cache: dict[str, RobotFileParser | None] = {}

    def fetch(self, url: str) -> str | None:
        """Return the raw HTML for ``url``, or ``None`` on any failure."""
        if not self._robots_allowed(url):
            logger.warning("Robots disallowed (skipping): %s", url)
            return None

        self._wait_politeness(url)

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)

                
                domain = urlsplit(url).netloc
                self._last_request_time[domain] = time.monotonic()

                if resp.status_code == 200:
                    return resp.text
                if resp.status_code in _RETRIABLE_STATUS and attempt < self.max_retries:
                    logger.warning(
                        "HTTP %d on %s (attempt %d/%d), retrying",
                        resp.status_code, url, attempt, self.max_retries,
                    )
                    time.sleep(self.backoff_s * attempt)
                    continue
                logger.warning("HTTP %d on %s (skipping)", resp.status_code, url)
                return None
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    logger.warning(
                        "Request error on %s (attempt %d/%d): %s",
                        url, attempt, self.max_retries, exc,
                    )
                    time.sleep(self.backoff_s * attempt)
                    continue
                logger.warning("Request error on %s (skipping): %s", url, exc)
                return None
        return None

    def close(self) -> None:
        """Close the underlying requests.Session and its connection pool."""
        self.session.close()

    def _wait_politeness(self, url: str) -> None:
        """Sleep if we've hit the same domain too recently."""
        domain = urlsplit(url).netloc
        last = self._last_request_time.get(domain, 0.0)
        elapsed = time.monotonic() - last
        remaining = self.politeness_delay_s - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _robots_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots_cache:
            self._robots_cache[origin] = self._load_robots(origin)
        rp = self._robots_cache[origin]
        if rp is None:
            return True  
        return rp.can_fetch(config.USER_AGENT, url)

    @staticmethod
    def _load_robots(origin: str) -> RobotFileParser | None:
        rp = RobotFileParser()
        rp.set_url(f"{origin}/robots.txt")
        try:
            rp.read()
        except Exception as exc:  
            logger.debug("Could not read robots.txt for %s: %s", origin, exc)
            return None
        return rp