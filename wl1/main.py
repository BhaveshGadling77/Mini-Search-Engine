"""Command-line entry point for the Mini Search Engine crawler.

Usage:
    python main.py --seeds seeds.txt --max-pages 100 [--allowed-domains example.com ...]
"""

from __future__ import annotations

import argparse
import logging
import os

from crawler import config
from crawler.engine import CrawlEngine
from crawler.store import JSONLStore


def load_seeds(seed_file: str) -> list[str]:
    with open(seed_file, encoding="utf-8") as handle:
        seeds: list[str] = []
        for line in handle:
            cleaned = line.split("#", 1)[0].strip()
            if cleaned:
                seeds.append(cleaned)
        return seeds


def setup_logging(log_path: str) -> None:
    directory = os.path.dirname(log_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mini Search Engine crawler")
    parser.add_argument("--seeds", default=config.SEED_FILE, help="Seed file (one URL per line)")
    parser.add_argument("--max-pages", type=int, default=config.MAX_PAGES, help="Maximum documents to crawl")
    parser.add_argument("--max-depth", type=int, default=getattr(config, "MAX_DEPTH", None), help="Maximum crawl depth")
    parser.add_argument("--max-links-per-page", type=int, default=getattr(config, "MAX_LINKS_PER_PAGE", None), help="Maximum outbound links enqueued per page")
    parser.add_argument("--allowed-domains", nargs="*", default=None, help="Restrict crawl to these domains")
    parser.add_argument("--corpus", default=config.CORPUS_PATH, help="Output JSONL path")
    parser.add_argument("--log", default=config.LOG_PATH, help="Log file path")
    parser.add_argument("--clear-corpus", action="store_true", help="Clear existing corpus before crawling")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.log)

    seeds = load_seeds(args.seeds)
    if not seeds:
        logging.error("No seed URLs found in %s", args.seeds)
        return 1

    if args.clear_corpus and os.path.exists(args.corpus):
        os.remove(args.corpus)

    store = JSONLStore(args.corpus)
    engine = CrawlEngine(
        seeds=seeds,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        max_links_per_page=args.max_links_per_page,
        allowed_domains=args.allowed_domains,
        store=store,
    )

    try:
        stored = engine.run()
    finally:
        engine.close()

    logging.info("Crawl complete: %d documents persisted to %s", stored, args.corpus)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())