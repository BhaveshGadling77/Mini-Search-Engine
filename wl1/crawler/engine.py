"""Crawl orchestration: the BFS feedback loop.

`CrawlEngine` ties the components together:

    pop URL -> fetch -> parse (text + links) -> tokenize -> persist
             -> enqueue unseen normalized outbound links

It tracks BFS depth per URL and records it in each document's metadata.
"""

from __future__ import annotations

import logging

from crawler import config
from crawler.fetcher import Fetcher
from crawler.frontier import URLFrontier
from crawler.models import Document
from crawler.parser import parse_page
from crawler.store import JSONLStore
from crawler.tokenizer import tokenize

logger = logging.getLogger(__name__)


class CrawlEngine:
    """Runs a BFS crawl from a set of seeds and persists documents."""

    def __init__(
        self,
        seeds: list[str],
        max_pages: int | None = None,
        allowed_domains: list[str] | None = None,
        fetcher: Fetcher | None = None,
        store: JSONLStore | None = None,
    ) -> None:
        self.max_pages = max_pages if max_pages is not None else config.MAX_PAGES
        self.frontier = URLFrontier(
            seeds=seeds, allowed_domains=allowed_domains
        )
        self.fetcher = fetcher or Fetcher()
        self.store = store or JSONLStore(config.CORPUS_PATH)
        self._depth: dict[str, int] = {}
        for seed in seeds:
            normalized = URLFrontier.normalize(seed)
            if normalized is not None:
                self._depth.setdefault(normalized, 0)

    def run(self) -> int:
        """Execute the crawl until `max_pages` documents are stored or the
        frontier is exhausted. Returns the number of documents persisted."""
        stored = 0
        while stored < self.max_pages and not self.frontier.empty():
            url = self.frontier.pop()
            if url is None:
                break
            depth = self._depth.get(url, 0)

            html = self.fetcher.fetch(url)
            if html is None:
                logger.info("Skipped (fetch failed): %s", url)
                continue

            # Parse HTML once — extracts both text and links in a single pass
            text, links = parse_page(html, url)
            tokens = tokenize(text)

            document = Document(
                doc_id=Document.new_doc_id(),
                url=url,
                text=text,
                tokens=tuple(tokens),
                meta={
                    "crawled_at": Document.now_iso(),
                    "content_length": len(html),
                    "status": "ok",
                    "depth": depth,
                },
            )
            self.store.append(document)
            stored += 1
            logger.info("Stored %s (%s)", document.doc_id, url)

            for link in links:
                normalized = self.frontier.add(link)
                if normalized is not None:
                    self._depth[normalized] = depth + 1

        return stored

    def close(self) -> None:
        """Release all resources (store file handle + HTTP session)."""
        self.store.close()
        self.fetcher.close()