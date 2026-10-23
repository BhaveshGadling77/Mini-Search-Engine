"""
Integration test: WL3 QueryEngine on top of the REAL C++ Worklet 2 (wl2bridge).

Skipped automatically when the extension has not been built
(``python -m pip install pybind11 && make pybind``) or no corpus is present.
"""

from __future__ import annotations

import glob
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORPUS = os.path.join(ROOT, "data", "crawler.json")

if not glob.glob(os.path.join(ROOT, "build", "wl2bridge*")):
    pytest.skip("wl2bridge not built (run `make pybind`)", allow_module_level=True)
if not os.path.isfile(CORPUS):
    pytest.skip("data/crawler.json missing", allow_module_level=True)

from wl3.engine.factory import build_engine  # noqa: E402
from wl3.integration.wl2_backend import create_backend  # noqa: E402
from wl3.integration.worklet2_adapter import Worklet2Adapter  # noqa: E402


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("cache") / "cache.db")
    return build_engine(
        backend_spec="wl3.integration.wl2_backend:create_backend",
        cache_db_path=db,
    )


def test_backend_satisfies_adapter_contract():
    adapter = Worklet2Adapter(create_backend(CORPUS))
    stats = adapter.get_corpus_stats()
    assert stats["total_docs"] > 0 and stats["avg_doc_length"] > 0
    assert adapter.get_index_version()
    cands, df = adapter.resolve_query("python")
    assert cands and df.get("python", 0) >= len(cands)


@pytest.mark.parametrize("mode", ["tfidf", "bm25", "vector"])
def test_all_ranking_modes_return_scored_results(engine, mode):
    results = engine.search("python tutorial", ranking_mode=mode, k=5)
    assert results
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(r.url for r in results)


def test_cache_hit_on_repeat(engine):
    engine.search("decorator", k=3)
    hits = engine.cache_hits
    engine.search("decorator", k=3)
    assert engine.cache_hits == hits + 1


def test_feedback_and_mmr_work_end_to_end(engine):
    first = engine.search("python tutorial", session_id="it", k=5)
    engine.mark_relevant("it", first[0].doc_id)
    assert engine.search("python tutorial", session_id="it", k=5, use_mmr=True)
