"""
Unit tests for TopKRetriever
==============================
Verifies correctness of the min-heap top-K extraction and the
MMR candidate-pool helper.

Edge cases covered:
    - k > number of documents
    - k == 0
    - empty input
    - tied scores (deterministic tiebreak by ascending doc_id)
    - negative scores
    - already sorted vs. scrambled input
"""

import pytest
from wl3.retrieval.top_k import TopKRetriever, ScoredDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ids(results: list[ScoredDocument]) -> list[int]:
    return [r.doc_id for r in results]


def scores(results: list[ScoredDocument]) -> list[float]:
    return [r.score for r in results]


# ---------------------------------------------------------------------------
# Tests — get_top_k
# ---------------------------------------------------------------------------

class TestTopKRetriever:

    def test_basic_top_k(self):
        """Top-3 from 5 candidates returns the correct 3."""
        scored = {0: 3.16, 4: 2.81, 7: 2.43, 1: 0.39, 2: 1.10}
        results = TopKRetriever.get_top_k(scored, k=3)
        assert len(results) == 3
        assert ids(results) == [0, 4, 7]

    def test_results_sorted_descending(self):
        """Results must be ordered from highest to lowest score."""
        scored = {10: 1.0, 20: 5.0, 30: 3.0, 40: 2.0}
        results = TopKRetriever.get_top_k(scored, k=4)
        result_scores = scores(results)
        assert result_scores == sorted(result_scores, reverse=True)

    def test_k_equals_number_of_docs(self):
        """k == len(docs) returns all documents."""
        scored = {0: 1.0, 1: 2.0, 2: 3.0}
        results = TopKRetriever.get_top_k(scored, k=3)
        assert len(results) == 3

    def test_k_greater_than_number_of_docs(self):
        """k > len(docs): return all docs, don't crash."""
        scored = {0: 1.0, 1: 2.0}
        results = TopKRetriever.get_top_k(scored, k=100)
        assert len(results) == 2

    def test_k_is_one(self):
        """k=1 returns only the single highest-scoring document."""
        scored = {0: 1.5, 1: 3.0, 2: 0.8}
        results = TopKRetriever.get_top_k(scored, k=1)
        assert len(results) == 1
        assert results[0].doc_id == 1
        assert results[0].score == 3.0

    def test_k_is_zero(self):
        """k=0 returns an empty list."""
        scored = {0: 1.0, 1: 2.0}
        results = TopKRetriever.get_top_k(scored, k=0)
        assert results == []

    def test_empty_candidates(self):
        """Empty scored_documents → empty result."""
        results = TopKRetriever.get_top_k({}, k=5)
        assert results == []

    def test_tied_scores_deterministic_by_doc_id(self):
        """Tied scores must break ties by ascending doc_id."""
        scored = {5: 2.0, 1: 2.0, 3: 2.0}
        results = TopKRetriever.get_top_k(scored, k=2)
        # Tie at 2.0 → lower doc_id wins: expect doc 1 and 3
        assert ids(results) == [1, 3]

    def test_negative_scores_handled(self):
        """Negative scores must be handled correctly (highest = least negative)."""
        scored = {0: -1.0, 1: -3.0, 2: -0.5}
        results = TopKRetriever.get_top_k(scored, k=2)
        assert ids(results) == [2, 0]   # -0.5 > -1.0 > -3.0

    def test_returns_scored_document_objects(self):
        """Each result must be a ScoredDocument with correct fields."""
        scored = {42: 7.77}
        results = TopKRetriever.get_top_k(scored, k=1)
        assert isinstance(results[0], ScoredDocument)
        assert results[0].doc_id == 42
        assert results[0].score == pytest.approx(7.77)

    def test_single_document_corpus(self):
        """Single-doc corpus → that doc is always top-1."""
        results = TopKRetriever.get_top_k({99: 0.001}, k=5)
        assert len(results) == 1
        assert results[0].doc_id == 99


# ---------------------------------------------------------------------------
# Tests — get_top_k_for_mmr
# ---------------------------------------------------------------------------

class TestTopKForMMR:

    def test_mmr_pool_larger_than_k(self):
        """get_top_k_for_mmr returns pool_size candidates (> final k)."""
        scored = {i: float(i) for i in range(50)}
        pool = TopKRetriever.get_top_k_for_mmr(scored, pool_size=20)
        assert len(pool) == 20

    def test_mmr_pool_default_size(self):
        """Default pool_size is 20."""
        scored = {i: float(i) for i in range(100)}
        pool = TopKRetriever.get_top_k_for_mmr(scored)
        assert len(pool) == 20

    def test_mmr_pool_sorted_descending(self):
        """MMR pool must be sorted highest-first so MMR sees best candidates."""
        scored = {i: float(100 - i) for i in range(30)}
        pool = TopKRetriever.get_top_k_for_mmr(scored, pool_size=10)
        pool_scores = scores(pool)
        assert pool_scores == sorted(pool_scores, reverse=True)

    def test_mmr_pool_when_fewer_docs_than_pool(self):
        """If fewer docs than pool_size, return all of them."""
        scored = {0: 1.0, 1: 2.0}
        pool = TopKRetriever.get_top_k_for_mmr(scored, pool_size=20)
        assert len(pool) == 2
