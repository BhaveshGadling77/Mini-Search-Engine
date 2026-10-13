import sys
from pathlib import Path

import pytest

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.frontier import URLFrontier


def test_seeds_are_enqueued_and_normalized():
    f = URLFrontier(seeds=["HTTPS://Example.COM:443/path#frag"])
    url = f.pop()
    assert url == "https://example.com/path"


def test_duplicate_urls_are_not_reenqueued():
    f = URLFrontier(seeds=["https://example.com/a"])
    assert f.add("https://example.com/a") is None
    assert len(f) == 1


def test_normalization_strips_fragment_and_port():
    assert (
        URLFrontier.normalize("http://example.com:80/path#section")
        == "http://example.com/path"
    )


def test_normalization_rejects_non_http_schemes():
    assert URLFrontier.normalize("ftp://example.com/file") is None
    assert URLFrontier.normalize("") is None


def test_normalization_collapses_trailing_slash():
    assert URLFrontier.normalize("https://example.com/") == "https://example.com/"
    assert URLFrontier.normalize("https://example.com//") == "https://example.com/"


def test_allowed_domains_filter():
    f = URLFrontier(seeds=["https://example.com"], allowed_domains=["example.com"])
    assert f.add("https://other.com/page") is None
    assert f.add("https://example.com/page") == "https://example.com/page"


def test_pop_from_empty_returns_none():
    f = URLFrontier()
    assert f.pop() is None
    assert f.empty()
