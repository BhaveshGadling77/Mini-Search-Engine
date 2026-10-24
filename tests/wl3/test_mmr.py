import pytest

from wl3.diversification.mmr import MMR
from wl3.retrieval.top_k import ScoredDocument


def test_mmr_returns_k_results():
    query = {"ai": 1.0}
    vectors = {
        1: {"ai": 1.0},
        2: {"ai": 0.9, "robotics": 0.1},
        3: {"robotics": 1.0},
    }
    pool = [
        ScoredDocument(1, 3.0),
        ScoredDocument(2, 2.0),
        ScoredDocument(3, 1.0),
    ]

    results = MMR().rerank(pool, query, vectors, 2)

    assert len(results) == 2
    assert results[0].doc_id == 1
    assert len({doc.doc_id for doc in results}) == 2


def test_mmr_handles_empty_pool_and_nonpositive_k():
    mmr = MMR()

    assert mmr.rerank([], {"ai": 1.0}, {}, 5) == []
    assert mmr.rerank([ScoredDocument(1, 1.0)], {"ai": 1.0}, {}, 0) == []


def test_mmr_rejects_invalid_lambda():
    with pytest.raises(ValueError):
        MMR(lambda_param=1.5)


def test_mmr_removes_duplicate_document_ids():
    pool = [ScoredDocument(1, 2.0), ScoredDocument(1, 1.0)]
    results = MMR().rerank(pool, {"ai": 1.0}, {1: {"ai": 1.0}}, 5)

    assert len(results) == 1
    assert results[0].doc_id == 1
