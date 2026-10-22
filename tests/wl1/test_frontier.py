"""Tests for the URL Frontier — BFS queue, normalization, dedup."""

import sys
from pathlib import Path

import pytest

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.frontier import URLFrontier


# ─── Existing Tests (with print output) ──────────────────────────────


def test_seeds_are_enqueued_and_normalized():
    print("\n[TEST] test_seeds_are_enqueued_and_normalized")
    seed = "HTTPS://Example.COM:443/path#frag"
    print(f"  Input:    seed='{seed}'")
    expected = "https://example.com/path"
    f = URLFrontier(seeds=[seed])
    url = f.pop()
    print(f"  Expected: '{expected}'")
    print(f"  Actual:   '{url}'")
    assert url == expected
    print("  Status:   PASS [OK]")


def test_duplicate_urls_are_not_reenqueued():
    print("\n[TEST] test_duplicate_urls_are_not_reenqueued")
    seed = "https://example.com/a"
    print(f"  Input:    seed='{seed}', then add same URL again")
    f = URLFrontier(seeds=[seed])
    result = f.add(seed)
    length = len(f)
    print(f"  Expected: add() returns None, len(frontier) == 1")
    print(f"  Actual:   add() returned {result!r}, len(frontier) == {length}")
    assert result is None
    assert length == 1
    print("  Status:   PASS [OK]")


def test_normalization_strips_fragment_and_port():
    print("\n[TEST] test_normalization_strips_fragment_and_port")
    url = "http://example.com:80/path#section"
    print(f"  Input:    '{url}'")
    expected = "http://example.com/path"
    actual = URLFrontier.normalize(url)
    print(f"  Expected: '{expected}'")
    print(f"  Actual:   '{actual}'")
    assert actual == expected
    print("  Status:   PASS [OK]")


def test_normalization_rejects_non_http_schemes():
    print("\n[TEST] test_normalization_rejects_non_http_schemes")
    ftp_url = "ftp://example.com/file"
    empty_url = ""
    ftp_result = URLFrontier.normalize(ftp_url)
    empty_result = URLFrontier.normalize(empty_url)
    print(f"  Input:    '{ftp_url}' and '{empty_url}'")
    print(f"  Expected: both None")
    print(f"  Actual:   ftp={ftp_result!r}, empty={empty_result!r}")
    assert ftp_result is None
    assert empty_result is None
    print("  Status:   PASS [OK]")


def test_normalization_collapses_trailing_slash():
    print("\n[TEST] test_normalization_collapses_trailing_slash")
    url1 = "https://example.com/"
    url2 = "https://example.com//"
    expected = "https://example.com/"
    r1 = URLFrontier.normalize(url1)
    r2 = URLFrontier.normalize(url2)
    print(f"  Input:    '{url1}' and '{url2}'")
    print(f"  Expected: both '{expected}'")
    print(f"  Actual:   r1='{r1}', r2='{r2}'")
    assert r1 == expected
    assert r2 == expected
    print("  Status:   PASS [OK]")


def test_allowed_domains_filter():
    print("\n[TEST] test_allowed_domains_filter")
    print("  Input:    allowed_domains=['example.com'], add 'other.com' and 'example.com'")
    f = URLFrontier(seeds=["https://example.com"], allowed_domains=["example.com"])
    other_result = f.add("https://other.com/page")
    same_result = f.add("https://example.com/page")
    print(f"  Expected: other.com -> None, example.com -> 'https://example.com/page'")
    print(f"  Actual:   other.com -> {other_result!r}, example.com -> {same_result!r}")
    assert other_result is None
    assert same_result == "https://example.com/page"
    print("  Status:   PASS [OK]")


def test_pop_from_empty_returns_none():
    print("\n[TEST] test_pop_from_empty_returns_none")
    print("  Input:    empty URLFrontier")
    f = URLFrontier()
    result = f.pop()
    is_empty = f.empty()
    print(f"  Expected: pop() -> None, empty() -> True")
    print(f"  Actual:   pop() -> {result!r}, empty() -> {is_empty}")
    assert result is None
    assert is_empty
    print("  Status:   PASS [OK]")


# ─── Additional Tests ────────────────────────────────────────────────


def test_frontier_bfs_order():
    """Enqueue multiple seeds, verify FIFO pop order."""
    print("\n[TEST] test_frontier_bfs_order")
    seeds = ["https://a.com/1", "https://b.com/2", "https://c.com/3"]
    print(f"  Input:    seeds={seeds}")
    f = URLFrontier(seeds=seeds)
    order = [f.pop() for _ in range(3)]
    expected = [URLFrontier.normalize(s) for s in seeds]
    print(f"  Expected: {expected}")
    print(f"  Actual:   {order}")
    assert order == expected
    print("  Status:   PASS [OK]")


def test_visited_property_tracks_all_added():
    """Verify the visited set grows as URLs are added."""
    print("\n[TEST] test_visited_property_tracks_all_added")
    f = URLFrontier(seeds=["https://example.com/a"])
    f.add("https://example.com/b")
    f.add("https://example.com/c")
    visited = f.visited
    print(f"  Input:    added 3 unique URLs")
    print(f"  Expected: len(visited) == 3")
    print(f"  Actual:   len(visited) == {len(visited)}, visited={visited}")
    assert len(visited) == 3
    assert "https://example.com/a" in visited
    assert "https://example.com/b" in visited
    assert "https://example.com/c" in visited
    print("  Status:   PASS [OK]")


def test_normalize_preserves_query_string():
    """Verify that query parameters (?key=val) are preserved."""
    print("\n[TEST] test_normalize_preserves_query_string")
    url = "https://example.com/search?q=hello&lang=en"
    result = URLFrontier.normalize(url)
    print(f"  Input:    '{url}'")
    print(f"  Expected: query string preserved (contains '?q=hello&lang=en')")
    print(f"  Actual:   '{result}'")
    assert "q=hello" in result
    assert "lang=en" in result
    print("  Status:   PASS [OK]")


def test_normalize_handles_whitespace():
    """Leading/trailing spaces should be trimmed."""
    print("\n[TEST] test_normalize_handles_whitespace")
    url = "  https://example.com/page  "
    result = URLFrontier.normalize(url)
    expected = "https://example.com/page"
    print(f"  Input:    '{url}' (with leading/trailing spaces)")
    print(f"  Expected: '{expected}'")
    print(f"  Actual:   '{result}'")
    assert result == expected
    print("  Status:   PASS [OK]")


def test_len_reflects_queue_size():
    """Verify __len__ after adds and pops."""
    print("\n[TEST] test_len_reflects_queue_size")
    f = URLFrontier(seeds=["https://a.com", "https://b.com", "https://c.com"])
    initial_len = len(f)
    f.pop()
    after_pop_len = len(f)
    f.add("https://d.com")
    after_add_len = len(f)
    print(f"  Input:    3 seeds -> pop 1 -> add 1")
    print(f"  Expected: initial=3, after_pop=2, after_add=3")
    print(f"  Actual:   initial={initial_len}, after_pop={after_pop_len}, after_add={after_add_len}")
    assert initial_len == 3
    assert after_pop_len == 2
    assert after_add_len == 3
    print("  Status:   PASS [OK]")
