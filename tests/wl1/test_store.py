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
    path = os.path.join(tmp_path, "corpus.jsonl")
    doc = Document(
        doc_id="d-test1234",
        url="https://example.com/",
        text="hello world",
        tokens=("hello", "world"),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 11, "status": "ok", "depth": 0},
    )
    with JSONLStore(path) as store:
        store.append(doc)

    with open(path, encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle]

    assert len(lines) == 1
    assert lines[0]["doc_id"] == "d-test1234"
    assert lines[0]["tokens"] == ["hello", "world"]
    assert lines[0]["meta"]["depth"] == 0


def test_to_dict_matches_schema():
    doc = Document(
        doc_id="d-abc12345",
        url="u",
        text="t",
        tokens=(),
        meta={"crawled_at": "2026-09-10T00:00:00Z", "content_length": 1, "status": "ok", "depth": 1},
    )
    record = doc.to_dict()
    assert set(record) == {"doc_id", "url", "text", "tokens", "meta"}
    # tokens serialized as list in JSON, even though stored as tuple
    assert isinstance(record["tokens"], list)


def test_corpus_path_mapped_to_data_dir():
    from crawler import config
    assert os.path.isabs(config.CORPUS_PATH)
    assert os.path.basename(config.CORPUS_PATH) == "corpus.jsonl"
    data_dir = os.path.dirname(config.CORPUS_PATH)
    assert os.path.basename(data_dir) == "data"
    assert os.path.isdir(config.DATA_DIR)
    assert os.path.samefile(data_dir, config.DATA_DIR)

