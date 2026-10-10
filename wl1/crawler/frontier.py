"""URL frontier: enforces BFS ordering and prevents re-fetch loops.

Backed by a FIFO ``collections.deque`` (O(1) popleft) plus a ``set`` of
canonicalized URLs for O(1) membership checks. URLs are normalized through a
five-step pipeline before enqueueing, and an optional ``allowed_domains``
filter keeps the crawl within target sites.
"""

from __future__ import annotations

import collections
from urllib.parse import urlsplit, urlunsplit


class URLFrontier:
    """Breadth-first URL queue with deduplication and normalization."""

    def __init__(
        self,
        seeds: list[str] | None = None,
        allowed_domains: list[str] | set[str] | None = None,
    ) -> None:
        self._queue: collections.deque[str] = collections.deque()
        self._visited: set[str] = set()
        self._allowed_domains: set[str] | None = (
            {d.lower() for d in allowed_domains} if allowed_domains else None
        )
        for seed in seeds or []:
            self.add(seed)

    # --- public API ------------------------------------------------------
    def add(self, url: str) -> str | None:
        """Normalize and enqueue ``url`` if new; return its canonical form.

        Returns ``None`` if the url is invalid, already visited, or outside
        the allowed-domain filter.
        """
        norm = self.normalize(url)
        if norm is None:
            return None
        if norm in self._visited:
            return None
        if self._allowed_domains is not None:
            domain = urlsplit(norm).netloc
            if domain not in self._allowed_domains:
                return None
        self._visited.add(norm)
        self._queue.append(norm)
        return norm

    def pop(self) -> str | None:
        """Remove and return the next URL in FIFO order, or ``None`` if empty."""
        if not self._queue:
            return None
        return self._queue.popleft()

    def empty(self) -> bool:
        return not self._queue

    def __len__(self) -> int:
        return len(self._queue)

    @property
    def visited(self) -> set[str]:
        return self._visited

    # --- normalization ---------------------------------------------------
    @staticmethod
    def normalize(url: str) -> str | None:
        """Canonicalize a URL in five steps; return ``None`` if invalid.

        1. Scheme restricted to ``http``/``https`` (lowercased).
        2. Fragment stripped (``#...``).
        3. Scheme + netloc lowercased.
        4. Default ports (``:80``, ``:443``) removed.
        5. Trailing ``/`` duplicated collapsed; empty path -> ``/``.
        """
        if not url:
            return None
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower()
        if scheme not in ("http", "https"):
            return None

        netloc = parts.netloc.lower()
        if scheme == "http" and netloc.endswith(":80"):
            netloc = netloc[:-3]
        elif scheme == "https" and netloc.endswith(":443"):
            netloc = netloc[:-4]

        path = parts.path
        if path == "":
            path = "/"
        path = path.rstrip("/") or "/"

        # Query is preserved; fragment is dropped (urlsplit already split it).
        return urlunsplit((scheme, netloc, path, parts.query, ""))