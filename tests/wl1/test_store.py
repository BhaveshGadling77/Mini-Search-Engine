"""Tests for Document model, JSONLStore, and CrawlEngine integration."""

import json
import os
import re
import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.models import Document
from crawler.store import JSONLStore


# ─── Existing Tests (with print output) ──────────────────────────────


def test_append_writes_json_line(tmp_path):
    print("\n[TEST] test_append_writes_json_line")
    path = os.path.join(tmp_path, "crawler.json")
    doc = Document(
        doc_id="000001",
        url="https://example.com/",
        title="",
        text="hello world",
        tokens=("hello", "world"),
        token_segments=(("hello", "world"),),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 11, "status": "ok", "depth": 0},
    )
    print(f"  Input:    Document(doc_id='000001', url='https://example.com/', tokens=('hello','world'))")
    with JSONLStore(path) as store:
        store.append(doc)

    with open(path, encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle]

    print(f"  Expected: 1 JSON line with doc_id='000001', tokens=['hello','world'], depth=0")
    print(f"  Actual:   {len(lines)} line(s), doc_id={lines[0]['doc_id']!r}, tokens={lines[0]['tokens']}, depth={lines[0]['meta']['depth']}")
    assert len(lines) == 1
    assert lines[0]["doc_id"] == "000001"
    assert lines[0]["tokens"] == ["hello", "world"]
    assert lines[0]["meta"]["depth"] == 0
    print("  Status:   PASS [OK]")


def test_to_dict_matches_schema():
    print("\n[TEST] test_to_dict_matches_schema")
    doc = Document(
        doc_id="000001",
        url="u",
        title="",
        text="t",
        tokens=(),
        token_segments=(),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 1, "status": "ok", "depth": 1},
    )
    record = doc.to_dict()
    keys = set(record)
    expected_keys = {"doc_id", "url", "title", "text", "tokens", "token_segments", "meta"}
    tokens_type = type(record["tokens"]).__name__
    print(f"  Input:    Document with empty tokens")
    print(f"  Expected: keys={expected_keys}, tokens type=list")
    print(f"  Actual:   keys={keys}, tokens type={tokens_type}")
    assert keys == expected_keys
    assert isinstance(record["tokens"], list)
    print("  Status:   PASS [OK]")


def test_corpus_path_mapped_to_data_dir():
    print("\n[TEST] test_corpus_path_mapped_to_data_dir")
    from crawler import config
    is_abs = os.path.isabs(config.CORPUS_PATH)
    basename = os.path.basename(config.CORPUS_PATH)
    data_dir = os.path.dirname(config.CORPUS_PATH)
    data_basename = os.path.basename(data_dir)
    dir_exists = os.path.isdir(config.DATA_DIR)
    print(f"  Input:    config.CORPUS_PATH = {config.CORPUS_PATH!r}")
    print(f"  Expected: absolute path, basename='crawler.json', parent='data', DATA_DIR exists")
    print(f"  Actual:   is_abs={is_abs}, basename={basename!r}, parent_dir={data_basename!r}, exists={dir_exists}")
    assert is_abs
    assert basename == "crawler.json"
    assert data_basename == "data"
    assert dir_exists
    assert os.path.samefile(data_dir, config.DATA_DIR)
    print("  Status:   PASS [OK]")


def test_new_doc_id_sequential_formatting():
    print("\n[TEST] test_new_doc_id_sequential_formatting")
    test_cases = [(1, "000001"), (2, "000002"), (42, "000042"), (100, "000100"), (500, "000500")]
    print(f"  Input:    seq values {[tc[0] for tc in test_cases]}")
    results = [(seq, Document.new_doc_id(seq)) for seq, _ in test_cases]
    all_pass = all(actual == expected for (seq, actual), (_, expected) in zip(results, test_cases))
    print(f"  Expected: {[tc[1] for tc in test_cases]}")
    print(f"  Actual:   {[r[1] for r in results]}")
    for (seq, actual), (_, expected) in zip(results, test_cases):
        assert actual == expected
    print("  Status:   PASS [OK]")


def test_crawl_engine_sequential_doc_ids(tmp_path):
    print("\n[TEST] test_crawl_engine_sequential_doc_ids")
    from unittest.mock import MagicMock
    from crawler.engine import CrawlEngine

    path = os.path.join(tmp_path, "crawler.json")
    mock_fetcher = MagicMock()
    mock_fetcher.fetch.side_effect = [
        "<html><body><p>Page 1</p><a href='/p2'>link</a></body></html>",
        "<html><body><p>Page 2</p></body></html>",
    ]
    print("  Input:    2 mock pages, seeds=['https://example.com/p1'], max_pages=2")

    with JSONLStore(path) as store:
        engine = CrawlEngine(
            seeds=["https://example.com/p1"],
            max_pages=2,
            fetcher=mock_fetcher,
            store=store,
        )
        engine.run()

    with open(path, encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle]

    ids = [line["doc_id"] for line in lines]
    print(f"  Expected: 2 docs with ids ['000001', '000002']")
    print(f"  Actual:   {len(lines)} docs with ids {ids}")
    assert len(lines) == 2
    assert lines[0]["doc_id"] == "000001"
    assert lines[1]["doc_id"] == "000002"
    print("  Status:   PASS [OK]")


# ─── Additional Tests ────────────────────────────────────────────────


def test_document_is_frozen():
    """Verify Document is immutable (assigning to field raises)."""
    print("\n[TEST] test_document_is_frozen")
    doc = Document(
        doc_id="000001", url="u", title="", text="t", tokens=(), token_segments=(),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 1, "status": "ok", "depth": 0},
    )
    print("  Input:    Document(frozen=True), attempt to set doc.url = 'new'")
    raised = False
    try:
        doc.url = "new"  # type: ignore
    except AttributeError:
        raised = True
    print(f"  Expected: AttributeError raised = True")
    print(f"  Actual:   AttributeError raised = {raised}")
    assert raised
    print("  Status:   PASS [OK]")


def test_now_iso_format():
    """Verify Document.now_iso() returns valid ISO 8601 string."""
    print("\n[TEST] test_now_iso_format")
    ts = Document.now_iso()
    # Pattern: 2026-09-10T12:34:56Z
    pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    matches = bool(re.match(pattern, ts))
    print(f"  Input:    Document.now_iso()")
    print(f"  Expected: ISO 8601 format matching '{pattern}'")
    print(f"  Actual:   '{ts}', matches={matches}")
    assert matches
    print("  Status:   PASS [OK]")


def test_store_appends_multiple_documents(tmp_path):
    """Write 3 docs, verify all 3 lines present."""
    print("\n[TEST] test_store_appends_multiple_documents")
    path = os.path.join(tmp_path, "crawler.json")
    docs = []
    for i in range(1, 4):
        docs.append(Document(
            doc_id=Document.new_doc_id(i), url=f"https://example.com/p{i}",
            title="", text=f"page {i}", tokens=(f"page", f"{i}"), token_segments=((f"page", f"{i}"),),
            meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 6, "status": "ok", "depth": 0},
        ))
    print(f"  Input:    3 Documents with ids ['000001', '000002', '000003']")
    with JSONLStore(path) as store:
        for doc in docs:
            store.append(doc)

    with open(path, encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle]

    ids = [line["doc_id"] for line in lines]
    print(f"  Expected: 3 lines with ids ['000001', '000002', '000003']")
    print(f"  Actual:   {len(lines)} lines with ids {ids}")
    assert len(lines) == 3
    assert ids == ["000001", "000002", "000003"]
    print("  Status:   PASS [OK]")


def test_to_dict_token_segments_serialization():
    """Verify token_segments becomes list of lists in to_dict()."""
    print("\n[TEST] test_to_dict_token_segments_serialization")
    doc = Document(
        doc_id="000001", url="u", title="", text="t",
        tokens=("hello", "world"),
        token_segments=(("hello",), ("world",)),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 1, "status": "ok", "depth": 0},
    )
    record = doc.to_dict()
    segs = record["token_segments"]
    is_list = isinstance(segs, list)
    inner_lists = all(isinstance(s, list) for s in segs)
    print(f"  Input:    token_segments=(('hello',), ('world',))")
    print(f"  Expected: list of lists: [['hello'], ['world']]")
    print(f"  Actual:   {segs}, outer_is_list={is_list}, inner_are_lists={inner_lists}")
    assert is_list
    assert inner_lists
    assert segs == [["hello"], ["world"]]
    print("  Status:   PASS [OK]")


def test_store_creates_parent_directory(tmp_path):
    """Write to a nested path, verify dir is created."""
    print("\n[TEST] test_store_creates_parent_directory")
    path = os.path.join(tmp_path, "sub", "dir", "crawler.json")
    print(f"  Input:    path='{path}' (nested, non-existent)")
    doc = Document(
        doc_id="000001", url="u", title="", text="t", tokens=(), token_segments=(),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 1, "status": "ok", "depth": 0},
    )
    with JSONLStore(path) as store:
        store.append(doc)
    parent_exists = os.path.isdir(os.path.dirname(path))
    file_exists = os.path.isfile(path)
    print(f"  Expected: parent dir created, file written")
    print(f"  Actual:   parent_exists={parent_exists}, file_exists={file_exists}")
    assert parent_exists
    assert file_exists
    print("  Status:   PASS [OK]")
