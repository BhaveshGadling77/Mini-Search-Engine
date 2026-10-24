"""Stopword-only queries: Worklet 2 returns the first 10 docs plus doc id -1."""

from __future__ import annotations

import pytest

from wl3.cli.main import format_results
from wl3.engine.models import STOPWORD_NOTICE
from wl3.engine.query_engine import QueryEngine
from wl3.integration.mock_worklet2 import InMemoryWorklet2
from wl3.integration.worklet2_adapter import STOPWORD_ONLY_DOC_ID, Worklet2Adapter
from wl3.web.app import create_app

DOCS = [
    {"id": i, "title": f"Doc {i}", "url": f"https://x.test/{i}",
     "text": f"python tutorial number {i} about decorators and generators"}
    for i in range(1, 16)
]


class SentinelBackend(InMemoryWorklet2):
    """Mimics the C++ contract exactly (candidates for ids 1..10 plus -1)."""

    def resolve_query(self, query_string):
        if query_string.strip().lower() in {"the", "the of and"}:
            return {**{i: {} for i in range(1, 11)}, -1: {}}, {}
        return super().resolve_query(query_string)


@pytest.fixture()
def engine():
    return QueryEngine(Worklet2Adapter(SentinelBackend(DOCS)), cache_db_path=None)


@pytest.mark.parametrize("query", ["the", "the of and"])
def test_sentinel_is_stripped_and_notice_set(engine, query):
    results = engine.search(query, k=10)
    assert results.notice == STOPWORD_NOTICE
    ids = [r.doc_id for r in results]
    assert STOPWORD_ONLY_DOC_ID not in ids
    assert ids == list(range(1, 11))
    assert [r.rank for r in results] == list(range(1, 11))
    assert all(r.url and r.score == 0.0 for r in results)


def test_k_limits_stopword_results(engine):
    assert len(engine.search("the", k=3)) == 3
    assert len(engine.search("the", k=50)) == 10


@pytest.mark.parametrize("mode", ["tfidf", "bm25", "vector"])
def test_every_mode_and_mmr_handle_it(engine, mode):
    assert engine.search("the", ranking_mode=mode, use_mmr=True).notice == STOPWORD_NOTICE


def test_normal_query_has_no_notice_and_is_cached(tmp_path):
    eng = QueryEngine(Worklet2Adapter(SentinelBackend(DOCS)),
                      cache_db_path=str(tmp_path / "c.db"))
    first = eng.search("python tutorial", k=3)
    again = eng.search("python tutorial", k=3)
    assert first.notice == again.notice == ""
    assert eng.cache_hits == 1


def test_stopword_answers_are_not_cached(tmp_path):
    eng = QueryEngine(Worklet2Adapter(SentinelBackend(DOCS)),
                      cache_db_path=str(tmp_path / "c.db"))
    eng.search("the", k=5)
    assert eng.search("the", k=5).notice == STOPWORD_NOTICE   # still has notice on repeat
    assert eng.cache_hits == 0


def test_stopword_query_with_feedback_session(engine):
    first = engine.search("python tutorial", session_id="s", k=3)
    engine.mark_relevant("s", first[0].doc_id)
    assert engine.search("the", session_id="s", k=5).notice == STOPWORD_NOTICE


def test_mock_backend_follows_same_contract():
    eng = QueryEngine(Worklet2Adapter(InMemoryWorklet2(DOCS)), cache_db_path=None)
    results = eng.search("the of and", k=10)
    assert results.notice == STOPWORD_NOTICE and len(results) == 10
    assert eng.search("the python", k=5).notice == ""        # mixed query is normal
    assert eng.search("AND", k=5) == []                       # operator-only: nothing


def test_cli_shows_notice(engine):
    text = format_results(engine.search("the", k=2), "the", color=False)
    assert text.startswith(STOPWORD_NOTICE)
    assert "1. Doc 1" in text


def test_flask_json_and_html_show_notice(engine):
    client = create_app(engine).test_client()
    body = client.get("/api/search?q=the&k=4").get_json()
    assert body["notice"] == STOPWORD_NOTICE
    assert [r["doc_id"] for r in body["results"]] == [1, 2, 3, 4]
    page = client.get("/?q=the&k=4").get_data(as_text=True)
    assert STOPWORD_NOTICE in page and "No results." not in page
    assert client.get("/api/search?q=python").get_json()["notice"] == ""
