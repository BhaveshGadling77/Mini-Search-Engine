import json
import os
import sys
from pathlib import Path

# Link tests to wl1/crawler
_wl1_dir = Path(__file__).resolve().parents[2] / "wl1"
if str(_wl1_dir) not in sys.path:
    sys.path.insert(0, str(_wl1_dir))

from crawler.models import Document
from crawler.store import JSONLStore


def test_append_writes_json_line(tmp_path):
    path = os.path.join(tmp_path, "crawler.json")
    doc = Document(
        doc_id="000001",
        url="https://example.com/",
        text="hello world",
        tokens=("hello", "world"),
        token_segments=(("hello", "world"),),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 11, "status": "ok", "depth": 0},
    )
    with JSONLStore(path) as store:
        store.append(doc)

    with open(path, encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle]

    assert len(lines) == 1
    assert lines[0]["doc_id"] == "000001"
    assert lines[0]["tokens"] == ["hello", "world"]
    assert lines[0]["meta"]["depth"] == 0


def test_to_dict_matches_schema():
    doc = Document(
        doc_id="000001",
        url="u",
        text="t",
        tokens=(),
        token_segments=(),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 1, "status": "ok", "depth": 1},
    )
    record = doc.to_dict()
    assert set(record) == {"doc_id", "url", "text", "tokens", "token_segments", "meta"}
    # tokens serialized as list in JSON, even though stored as tuple
    assert isinstance(record["tokens"], list)


def test_corpus_path_mapped_to_data_dir():
    from crawler import config
    assert os.path.isabs(config.CORPUS_PATH)
    assert os.path.basename(config.CORPUS_PATH) == "crawler.json"
    data_dir = os.path.dirname(config.CORPUS_PATH)
    assert os.path.basename(data_dir) == "data"
    assert os.path.isdir(config.DATA_DIR)
    assert os.path.samefile(data_dir, config.DATA_DIR)


def test_new_doc_id_sequential_formatting():
    assert Document.new_doc_id(1) == "000001"
    assert Document.new_doc_id(2) == "000002"
    assert Document.new_doc_id(42) == "000042"
    assert Document.new_doc_id(100) == "000100"
    assert Document.new_doc_id(500) == "000500"


def test_crawl_engine_sequential_doc_ids(tmp_path):
    from unittest.mock import MagicMock
    from crawler.engine import CrawlEngine

    path = os.path.join(tmp_path, "crawler.json")
    mock_fetcher = MagicMock()
    mock_fetcher.fetch.side_effect = [
        "<html><body><p>Page 1</p><a href='/p2'>link</a></body></html>",
        "<html><body><p>Page 2</p></body></html>",
    ]

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

    assert len(lines) == 2
    assert lines[0]["doc_id"] == "000001"
    assert lines[1]["doc_id"] == "000002"



