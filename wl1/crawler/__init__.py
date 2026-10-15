"""This package contains the core components of the web crawler, 
including the fetcher, parser, tokenizer, and storage mechanisms. 
It provides the necessary functionality to crawl web pages, extract relevant 
information, and store it for further processing.
"""

from crawler.models import Document
from crawler.frontier import URLFrontier
from crawler.fetcher import Fetcher
from crawler.parser import parse_html, extract_links, parse_page
from crawler.tokenizer import tokenize
from crawler.store import JSONLStore
from crawler.engine import CrawlEngine

__all__ = [
    "Document",
    "URLFrontier",
    "Fetcher",
    "parse_html",
    "extract_links",
    "parse_page",
    "tokenize",
    "JSONLStore",
    "CrawlEngine",
]