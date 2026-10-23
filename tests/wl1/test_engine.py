"""Tests for the CrawlEngine — mocked fetcher + temp store (no network required).

Each test prints its input, expected, and actual values so a full run
produces a self-describing, recordable output (see run_wl1_tests.py).
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.engine import CrawlEngine
from crawler.store import JSONLStore


def _page(body: str) -> str:
    """Wrap ``body`` in a minimal HTML document."""
    return f"<html><body>{body}</body></html>"


def _crawl(tmp_path, pages, *, seeds, **engine_kwargs):
    """Crawl a fake in-memory web (``pages`` maps url -> html) with a mocked fetcher.

    Unknown URLs "fail" (fetch returns None) and are skipped, just like a
    real crawl. Returns (stored_count, list_of_document_dicts).
    """
    fetcher = MagicMock()
    fetcher.fetch.side_effect = lambda url: pages.get(url)
    corpus = os.path.join(tmp_path, "crawler.json")
    with JSONLStore(corpus) as store:
        engine = CrawlEngine(seeds=seeds, fetcher=fetcher, store=store, **engine_kwargs)
        stored = engine.run()
    with open(corpus, encoding="utf-8") as handle:
        docs = [json.loads(line) for line in handle]
    return stored, docs


# ─── Crawl Engine Tests ──────────────────────────────────────────────


def test_engine_crawls_linked_pages_in_bfs_order(tmp_path):
    """A seed page's outbound links are crawled after the seed itself."""
    print("\n[TEST] test_engine_crawls_linked_pages_in_bfs_order")
    pages = {
        "https://example.com/p1": _page("<p>Page 1</p><a href='/p2'>next</a>"),
        "https://example.com/p2": _page("<p>Page 2</p><a href='/p3'>next</a>"),
        "https://example.com/p3": _page("<p>Page 3</p>"),
    }
    print("  Input:    chain p1 -> p2 -> p3, seeds=['https://example.com/p1'], max_pages=10")
    stored, docs = _crawl(tmp_path, pages, seeds=["https://example.com/p1"], max_pages=10)
    urls = [d["url"] for d in docs]
    expected = ["https://example.com/p1", "https://example.com/p2", "https://example.com/p3"]
    print(f"  Expected: stored=3, urls={expected}")
    print(f"  Actual:   stored={stored}, urls={urls}")
    assert stored == 3
    assert urls == expected
    print("  Status:   PASS [OK]")


def test_engine_respects_max_pages(tmp_path):
    """Crawling stops once max_pages documents have been stored."""
    print("\n[TEST] test_engine_respects_max_pages")
    pages = {
        "https://example.com/p1": _page("<p>Page 1</p><a href='/p2'>next</a>"),
        "https://example.com/p2": _page("<p>Page 2</p><a href='/p3'>next</a>"),
        "https://example.com/p3": _page("<p>Page 3</p>"),
    }
    print("  Input:    3-page chain, seeds=['https://example.com/p1'], max_pages=2")
    stored, docs = _crawl(tmp_path, pages, seeds=["https://example.com/p1"], max_pages=2)
    urls = [d["url"] for d in docs]
    print(f"  Expected: stored=2, p3 not crawled")
    print(f"  Actual:   stored={stored}, urls={urls}")
    assert stored == 2
    assert "https://example.com/p3" not in urls
    print("  Status:   PASS [OK]")


def test_engine_respects_max_depth(tmp_path):
    """Links beyond max_depth are discovered but never crawled."""
    print("\n[TEST] test_engine_respects_max_depth")
    pages = {
        "https://example.com/p1": _page("<p>Page 1</p><a href='/p2'>next</a>"),
        "https://example.com/p2": _page("<p>Page 2</p><a href='/p3'>next</a>"),
        "https://example.com/p3": _page("<p>Page 3</p>"),
    }
    print("  Input:    chain p1 -> p2 -> p3, seeds=['https://example.com/p1'], max_depth=1")
    stored, docs = _crawl(
        tmp_path, pages, seeds=["https://example.com/p1"], max_pages=10, max_depth=1
    )
    urls = [d["url"] for d in docs]
    print(f"  Expected: stored=2 (p1 depth=0, p2 depth=1), p3 not crawled")
    print(f"  Actual:   stored={stored}, urls={urls}")
    assert stored == 2
    assert "https://example.com/p3" not in urls
    print("  Status:   PASS [OK]")


def test_engine_respects_max_links_per_page(tmp_path):
    """At most max_links_per_page outbound links are enqueued per page."""
    print("\n[TEST] test_engine_respects_max_links_per_page")
    link_html = "".join(f"<a href='/l{i}'>L{i}</a>" for i in range(1, 6))
    pages = {
        "https://example.com/hub": _page(f"<p>Hub</p>{link_html}"),
        **{f"https://example.com/l{i}": _page(f"<p>Leaf {i}</p>") for i in range(1, 6)},
    }
    print("  Input:    hub with 5 outbound links, seeds=['https://example.com/hub'], max_links_per_page=2")
    stored, docs = _crawl(
        tmp_path,
        pages,
        seeds=["https://example.com/hub"],
        max_pages=10,
        max_links_per_page=2,
    )
    urls = [d["url"] for d in docs]
    print(f"  Expected: only hub + l1 + l2 crawled (l3..l5 never enqueued)")
    print(f"  Actual:   stored={stored}, urls={urls}")
    assert "https://example.com/l1" in urls
    assert "https://example.com/l2" in urls
    assert "https://example.com/l3" not in urls
    assert "https://example.com/l4" not in urls
    assert "https://example.com/l5" not in urls
    assert stored == 3
    print("  Status:   PASS [OK]")


def test_engine_skips_failed_fetches(tmp_path):
    """URLs whose fetch fails are skipped and do not consume a doc id."""
    print("\n[TEST] test_engine_skips_failed_fetches")
    pages = {"https://example.com/p2": _page("<p>Alive</p>")}
    print(
        "  Input:    seeds=['https://example.com/p1' (fetch fails), "
        "'https://example.com/p2' (ok)]"
    )
    stored, docs = _crawl(
        tmp_path, pages, seeds=["https://example.com/p1", "https://example.com/p2"], max_pages=10
    )
    urls = [d["url"] for d in docs]
    print(f"  Expected: stored=1, urls=['https://example.com/p2'], doc_id='000001'")
    print(f"  Actual:   stored={stored}, urls={urls}, doc_id={docs[0]['doc_id']}")
    assert stored == 1
    assert urls == ["https://example.com/p2"]
    assert docs[0]["doc_id"] == "000001"
    print("  Status:   PASS [OK]")


def test_engine_crawls_shared_link_only_once(tmp_path):
    """A URL discovered by two pages is crawled exactly once."""
    print("\n[TEST] test_engine_crawls_shared_link_only_once")
    shared = "<a href='/shared'>shared</a>"
    pages = {
        "https://example.com/a": _page(f"<p>A</p>{shared}"),
        "https://example.com/b": _page(f"<p>B</p>{shared}"),
        "https://example.com/shared": _page("<p>Shared</p>"),
    }
    print("  Input:    seeds=['.../a', '.../b'], both pages link to '.../shared'")
    stored, docs = _crawl(
        tmp_path, pages, seeds=["https://example.com/a", "https://example.com/b"], max_pages=10
    )
    urls = [d["url"] for d in docs]
    shared_count = urls.count("https://example.com/shared")
    print(f"  Expected: stored=3, '.../shared' crawled exactly once")
    print(f"  Actual:   stored={stored}, urls={urls}, shared_count={shared_count}")
    assert stored == 3
    assert shared_count == 1
    print("  Status:   PASS [OK]")


def test_engine_allowed_domains_restricts_crawl(tmp_path):
    """Links outside allowed_domains are filtered out before enqueueing."""
    print("\n[TEST] test_engine_allowed_domains_restricts_crawl")
    pages = {
        "https://example.com/p1": _page(
            "<p>P1</p><a href='https://external.com/x'>ext</a>"
        ),
        "https://external.com/x": _page("<p>External</p>"),
    }
    print("  Input:    seed on example.com links to external.com, allowed_domains=['example.com']")
    stored, docs = _crawl(
        tmp_path,
        pages,
        seeds=["https://example.com/p1"],
        max_pages=10,
        allowed_domains=["example.com"],
    )
    urls = [d["url"] for d in docs]
    print(f"  Expected: stored=1, only 'https://example.com/p1' crawled")
    print(f"  Actual:   stored={stored}, urls={urls}")
    assert stored == 1
    assert urls == ["https://example.com/p1"]
    print("  Status:   PASS [OK]")


def test_engine_records_depth_status_and_length_in_meta(tmp_path):
    """Each stored document's meta carries depth, status and content length."""
    print("\n[TEST] test_engine_records_depth_status_and_length_in_meta")
    pages = {
        "https://example.com/p1": _page("<p>Page 1</p><a href='/p2'>next</a>"),
        "https://example.com/p2": _page("<p>Page 2</p><a href='/p3'>next</a>"),
        "https://example.com/p3": _page("<p>Page 3</p>"),
    }
    print("  Input:    chain p1 -> p2 -> p3, seeds=['https://example.com/p1'], max_pages=10")
    stored, docs = _crawl(tmp_path, pages, seeds=["https://example.com/p1"], max_pages=10)
    depths = {d["url"]: d["meta"]["depth"] for d in docs}
    statuses = {d["url"]: d["meta"]["status"] for d in docs}
    lengths_ok = all(d["meta"]["content_length"] == len(pages[d["url"]]) for d in docs)
    expected_depths = {
        "https://example.com/p1": 0,
        "https://example.com/p2": 1,
        "https://example.com/p3": 2,
    }
    print(f"  Expected: depths={expected_depths}, all statuses 'ok', content_length matches html")
    print(f"  Actual:   depths={depths}, statuses={set(statuses.values())}, lengths_ok={lengths_ok}")
    assert depths == expected_depths
    assert all(s == "ok" for s in statuses.values())
    assert lengths_ok
    print("  Status:   PASS [OK]")


def test_engine_persists_token_segments(tmp_path):
    """Section breaks survive the full pipeline: two blocks -> two segments."""
    print("\n[TEST] test_engine_persists_token_segments")
    pages = {
        "https://example.com/p1": _page("<p>Alpha</p><p>Beta</p>"),
    }
    print("  Input:    page with two <p> blocks ('Alpha' and 'Beta'), max_pages=1")
    stored, docs = _crawl(tmp_path, pages, seeds=["https://example.com/p1"], max_pages=1)
    tokens = docs[0]["tokens"]
    segments = docs[0]["token_segments"]
    print(f"  Expected: tokens=['alpha', 'beta'], token_segments=[['alpha'], ['beta']]")
    print(f"  Actual:   tokens={tokens}, token_segments={segments}")
    assert tokens == ["alpha", "beta"]
    assert segments == [["alpha"], ["beta"]]
    print("  Status:   PASS [OK]")


def test_engine_start_seq_controls_first_doc_id(tmp_path):
    """start_seq offsets the sequential doc ids (resume support)."""
    print("\n[TEST] test_engine_start_seq_controls_first_doc_id")
    pages = {
        "https://example.com/p1": _page("<p>Page 1</p>"),
        "https://example.com/p2": _page("<p>Page 2</p>"),
    }
    print("  Input:    seeds=['.../p1', '.../p2'], start_seq=5")
    stored, docs = _crawl(
        tmp_path, pages, seeds=["https://example.com/p1", "https://example.com/p2"],
        max_pages=10, start_seq=5,
    )
    ids = [d["doc_id"] for d in docs]
    print(f"  Expected: ids=['000005', '000006']")
    print(f"  Actual:   ids={ids}")
    assert ids == ["000005", "000006"]
    print("  Status:   PASS [OK]")
