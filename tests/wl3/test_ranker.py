"""
Unit tests for Ranker
=======================
Verifies that the Ranker facade correctly delegates to each scorer
and enforces parameter requirements.
"""

import pytest
from wl3.ranking.ranker import Ranker, RankingMode


# ---------------------------------------------------------------------------
# Shared sample data (mirrors the W2 mock contract)
# ---------------------------------------------------------------------------

TOTAL_DOCS = 10
AVG_DOC_LEN = 45.0

CANDIDATES = {
    0: {"machine": 3, "learning": 4},
    4: {"machine": 1, "learning": 5},
    7: {"machine": 2, "learning": 3},
    1: {"machine": 0, "learning": 1},
}

DOC_FREQ = {"machine": 3, "learning": 4}

QUERY_TERMS = ["machine", "learning"]

DOC_LENGTHS = {0: 16, 4: 18, 7: 14, 1: 20}

DOC_TERMS_FULL = {
    0: {"machine": 3, "learning": 4, "subset": 1, "artificial": 2,
        "intelligence": 2, "is": 2, "a": 1, "of": 1},
    4: {"deep": 3, "learning": 5, "uses": 1, "neural": 2,
        "networks": 2, "layers": 2, "machine": 1},
    7: {"reinforcement": 2, "learning": 3, "machine": 2, "type": 1},
    1: {"neural": 3, "networks": 2, "computing": 1, "learning": 1},
}


@pytest.fixture
def ranker() -> Ranker:
    return Ranker(bm25_k1=1.5, bm25_b=0.75)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRanker:

    def test_tfidf_mode_returns_scores_for_all_docs(self, ranker):
        """TFIDF mode: all candidates receive a score."""
        scores = ranker.rank(
            ranking_mode=RankingMode.TFIDF,
            candidates=CANDIDATES,
            doc_freq=DOC_FREQ,
            total_docs=TOTAL_DOCS,
            query_terms=QUERY_TERMS,
        )
        assert set(scores.keys()) == set(CANDIDATES.keys())
        assert all(isinstance(s, float) for s in scores.values())

    def test_tfidf_ordering(self, ranker):
        """TFIDF: doc0 (highest TF) should rank above doc7 above doc1."""
        scores = ranker.rank(RankingMode.TFIDF, CANDIDATES, DOC_FREQ, TOTAL_DOCS, QUERY_TERMS)
        assert scores[0] > scores[7] > scores[1]

    def test_bm25_mode_returns_scores_for_all_docs(self, ranker):
        """BM25 mode: all candidates receive a score."""
        scores = ranker.rank(
            ranking_mode=RankingMode.BM25,
            candidates=CANDIDATES,
            doc_freq=DOC_FREQ,
            total_docs=TOTAL_DOCS,
            query_terms=QUERY_TERMS,
            avg_doc_length=AVG_DOC_LEN,
            doc_lengths=DOC_LENGTHS,
        )
        assert set(scores.keys()) == set(CANDIDATES.keys())

    def test_bm25_requires_doc_lengths(self, ranker):
        """BM25 without doc_lengths must raise ValueError."""
        with pytest.raises(ValueError, match="doc_lengths"):
            ranker.rank(
                ranking_mode=RankingMode.BM25,
                candidates=CANDIDATES,
                doc_freq=DOC_FREQ,
                total_docs=TOTAL_DOCS,
                query_terms=QUERY_TERMS,
                avg_doc_length=AVG_DOC_LEN,
                doc_lengths=None,  # explicitly missing
            )

    def test_vector_mode_returns_scores_for_all_docs(self, ranker):
        """VECTOR mode: all candidates receive a score."""
        scores = ranker.rank(
            ranking_mode=RankingMode.VECTOR,
            candidates=CANDIDATES,
            doc_freq=DOC_FREQ,
            total_docs=TOTAL_DOCS,
            query_terms=QUERY_TERMS,
            doc_terms_full=DOC_TERMS_FULL,
        )
        assert set(scores.keys()) == set(CANDIDATES.keys())

    def test_vector_requires_doc_terms_full(self, ranker):
        """VECTOR mode without doc_terms_full must raise ValueError."""
        with pytest.raises(ValueError, match="doc_terms_full"):
            ranker.rank(
                ranking_mode=RankingMode.VECTOR,
                candidates=CANDIDATES,
                doc_freq=DOC_FREQ,
                total_docs=TOTAL_DOCS,
                query_terms=QUERY_TERMS,
                doc_terms_full=None,
            )

    def test_all_modes_produce_non_negative_scores(self, ranker):
        """All modes must produce non-negative scores."""
        for mode in RankingMode:
            kwargs = dict(
                ranking_mode=mode,
                candidates=CANDIDATES,
                doc_freq=DOC_FREQ,
                total_docs=TOTAL_DOCS,
                query_terms=QUERY_TERMS,
                avg_doc_length=AVG_DOC_LEN,
                doc_lengths=DOC_LENGTHS,
                doc_terms_full=DOC_TERMS_FULL,
            )
            scores = ranker.rank(**kwargs)
            for doc_id, s in scores.items():
                assert s >= 0.0, f"Mode {mode} gave negative score for doc {doc_id}"

    def test_ranking_mode_enum_values(self):
        """RankingMode enum must have expected string values."""
        assert RankingMode.TFIDF.value == "tfidf"
        assert RankingMode.BM25.value == "bm25"
        assert RankingMode.VECTOR.value == "vector"

    def test_empty_candidates_returns_empty(self, ranker):
        """Empty candidates dict → empty scores dict for all modes."""
        for mode in RankingMode:
            scores = ranker.rank(
                ranking_mode=mode,
                candidates={},
                doc_freq=DOC_FREQ,
                total_docs=TOTAL_DOCS,
                query_terms=QUERY_TERMS,
                avg_doc_length=AVG_DOC_LEN,
                doc_lengths={},
                doc_terms_full={},
            )
            assert scores == {}

    def test_modes_produce_different_scores(self, ranker):
        """Different modes generally produce different scores (not accidentally equal)."""
        tfidf_scores = ranker.rank(RankingMode.TFIDF, CANDIDATES, DOC_FREQ, TOTAL_DOCS, QUERY_TERMS)
        bm25_scores = ranker.rank(RankingMode.BM25, CANDIDATES, DOC_FREQ, TOTAL_DOCS, QUERY_TERMS,
                                   avg_doc_length=AVG_DOC_LEN, doc_lengths=DOC_LENGTHS)
        # They will numerically differ for doc 0
        assert tfidf_scores[0] != pytest.approx(bm25_scores[0], rel=0.01)

    def test_unknown_ranking_mode_raises(self, ranker):
        """An unknown string mode (if somehow bypassing enum) must raise ValueError."""
        with pytest.raises((ValueError, AttributeError)):
            ranker.rank(
                ranking_mode="unknown_mode",
                candidates=CANDIDATES,
                doc_freq=DOC_FREQ,
                total_docs=TOTAL_DOCS,
                query_terms=QUERY_TERMS,
            )
