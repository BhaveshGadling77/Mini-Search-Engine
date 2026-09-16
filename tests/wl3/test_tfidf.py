"""
Unit tests for TFIDFScorer
===========================
All expected values are hand-calculated in the implementation plan
using the sample 10-document corpus.

Sample corpus constants:
    total_docs = 10
    doc_freq   = {"machine": 3, "learning": 4, "data": 2, "neural": 2}

    doc_tf for doc 0 = {"machine": 3, "learning": 4}
    doc_tf for doc 1 = {"machine": 0, "learning": 1}
    doc_tf for doc 7 = {"machine": 2, "learning": 3}

Hand-calculated score for doc 0 ("machine learning" query):
    IDF("machine") = log10(10/3) ≈ 0.5229
    IDF("learning") = log10(10/4) ≈ 0.3979
    Score = 3×0.5229 + 4×0.3979 ≈ 3.1603
"""

import math
import pytest
from wl3.ranking.tfidf import TFIDFScorer


# ---------------------------------------------------------------------------
# Fixtures — shared sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def scorer() -> TFIDFScorer:
    return TFIDFScorer()


@pytest.fixture
def sample_doc_freq() -> dict:
    return {"machine": 3, "learning": 4, "data": 2, "neural": 2}


@pytest.fixture
def doc0_tf() -> dict:
    """doc 0: 'machine' appears 3×, 'learning' 4×."""
    return {"machine": 3, "learning": 4}


@pytest.fixture
def doc1_tf() -> dict:
    """doc 1: no 'machine', 'learning' appears 1×."""
    return {"machine": 0, "learning": 1}


@pytest.fixture
def doc7_tf() -> dict:
    """doc 7: 'machine' 2×, 'learning' 3×."""
    return {"machine": 2, "learning": 3}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTFIDFScorer:

    def test_basic_scoring(self, scorer, doc0_tf, sample_doc_freq):
        """Hand-calculated score for doc0 must match within tolerance."""
        score = scorer.score(
            doc_tf=doc0_tf,
            doc_freq=sample_doc_freq,
            total_docs=10,
            query_terms=["machine", "learning"],
        )
        expected = 3 * math.log10(10 / 3) + 4 * math.log10(10 / 4)
        assert score == pytest.approx(expected, rel=1e-6)

    def test_ordering_multiple_docs(self, scorer, doc0_tf, doc7_tf, doc1_tf, sample_doc_freq):
        """doc0 (higher TF) must rank above doc7, which ranks above doc1."""
        score0 = scorer.score(doc0_tf, sample_doc_freq, 10, ["machine", "learning"])
        score7 = scorer.score(doc7_tf, sample_doc_freq, 10, ["machine", "learning"])
        score1 = scorer.score(doc1_tf, sample_doc_freq, 10, ["machine", "learning"])
        assert score0 > score7 > score1

    def test_single_term_query(self, scorer, doc0_tf, sample_doc_freq):
        """Single-term query uses only that term's contribution."""
        score = scorer.score(doc0_tf, sample_doc_freq, 10, ["machine"])
        expected = 3 * math.log10(10 / 3)
        assert score == pytest.approx(expected, rel=1e-6)

    def test_zero_tf_term_contributes_zero(self, scorer, sample_doc_freq):
        """A query term absent from the document must contribute 0."""
        doc_tf = {"learning": 4}  # no 'machine'
        score = scorer.score(doc_tf, sample_doc_freq, 10, ["machine", "learning"])
        expected = 4 * math.log10(10 / 4)  # only 'learning' contributes
        assert score == pytest.approx(expected, rel=1e-6)

    def test_term_in_all_docs_gives_zero_idf(self, scorer):
        """When df == N, IDF = log10(1) = 0, so contribution = 0."""
        doc_tf = {"common": 10}
        doc_freq = {"common": 10}          # appears in ALL 10 docs
        score = scorer.score(doc_tf, doc_freq, total_docs=10, query_terms=["common"])
        assert score == pytest.approx(0.0, abs=1e-9)

    def test_rare_term_has_highest_idf(self, scorer):
        """A term in only 1 doc has IDF = log10(N/1) = log10(N), maximum."""
        doc_tf = {"unique": 1}
        doc_freq = {"unique": 1}
        score = scorer.score(doc_tf, doc_freq, total_docs=10, query_terms=["unique"])
        expected = 1 * math.log10(10 / 1)
        assert score == pytest.approx(expected, rel=1e-6)

    def test_empty_query_returns_zero(self, scorer, doc0_tf, sample_doc_freq):
        """Empty query_terms list must return 0.0."""
        score = scorer.score(doc0_tf, sample_doc_freq, 10, query_terms=[])
        assert score == 0.0

    def test_empty_doc_tf_returns_zero(self, scorer, sample_doc_freq):
        """Empty doc_tf (document has no terms) must return 0.0."""
        score = scorer.score({}, sample_doc_freq, 10, query_terms=["machine"])
        assert score == 0.0

    def test_term_not_in_corpus_skipped(self, scorer):
        """Query term with df=0 (unknown term) must be silently skipped."""
        doc_tf = {"ghost": 5}
        doc_freq = {}          # 'ghost' has no DF record
        score = scorer.score(doc_tf, doc_freq, 10, ["ghost"])
        assert score == 0.0

    def test_score_is_non_negative(self, scorer, doc0_tf, sample_doc_freq):
        """TF-IDF score must always be non-negative."""
        score = scorer.score(doc0_tf, sample_doc_freq, 10, ["machine", "learning"])
        assert score >= 0.0

    def test_total_docs_zero_returns_zero(self, scorer, doc0_tf, sample_doc_freq):
        """Pathological total_docs=0 must return 0.0 without raising."""
        score = scorer.score(doc0_tf, sample_doc_freq, total_docs=0, query_terms=["machine"])
        assert score == 0.0

    def test_repeated_query_term_sums_correctly(self, scorer):
        """Repeated term in query list should sum its contribution twice."""
        # query = ["data", "data"] — same as asking for 'data' in both positions
        # Both positions use the SAME tf in the doc, so score is just regular scoring.
        # The scorer iterates query_terms — if "data" appears twice it counts twice.
        doc_tf = {"data": 2}
        doc_freq = {"data": 2}
        score_once = scorer.score(doc_tf, doc_freq, 10, ["data"])
        score_twice = scorer.score(doc_tf, doc_freq, 10, ["data", "data"])
        # score_twice = 2 × score_once  (term iterated twice)
        assert score_twice == pytest.approx(2 * score_once, rel=1e-6)
