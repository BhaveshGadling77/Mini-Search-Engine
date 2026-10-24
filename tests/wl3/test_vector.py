"""
Unit tests for VectorScorer
=============================
Tests both the primary score() method and the static helpers
build_tfidf_vector() and cosine_similarity() that Person 3 (MMR/Rocchio)
will use.

Key properties verified:
    - Identical documents → cosine ≈ 1.0
    - Orthogonal documents (no shared terms) → cosine = 0.0
    - Partial overlap → 0 < cosine < 1
    - Empty input → 0.0
    - Result is always in [0, 1]
"""

import math
import pytest
from wl3.ranking.vector import VectorScorer


TOTAL_DOCS = 10


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scorer() -> VectorScorer:
    return VectorScorer()


@pytest.fixture
def ml_doc_freq() -> dict:
    """DF for ML corpus (used across multiple tests)."""
    return {
        "machine": 3, "learning": 4, "subset": 1, "artificial": 2,
        "intelligence": 2, "is": 5, "a": 6, "of": 5, "deep": 2,
        "neural": 2, "networks": 2, "layers": 1, "uses": 1,
    }


@pytest.fixture
def doc0_full_terms() -> dict:
    """Full term vector for doc 0 (ML intro article)."""
    return {
        "machine": 3, "learning": 4, "subset": 1, "artificial": 2,
        "intelligence": 2, "is": 2, "a": 1, "of": 1,
    }


@pytest.fixture
def doc4_full_terms() -> dict:
    """Full term vector for doc 4 (Deep Learning article)."""
    return {
        "deep": 3, "learning": 5, "uses": 1, "neural": 2,
        "networks": 2, "layers": 2, "machine": 1,
    }


# ---------------------------------------------------------------------------
# Tests — primary score() method
# ---------------------------------------------------------------------------

class TestVectorScorerScore:

    def test_identical_vectors(self, scorer, doc0_full_terms, ml_doc_freq):
        """Same TF-IDF vector compared with itself → cosine = 1.0."""
        vec = VectorScorer.build_tfidf_vector(doc0_full_terms, ml_doc_freq, TOTAL_DOCS)
        score = VectorScorer.cosine_similarity(vec, vec)
        assert score == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self, scorer, ml_doc_freq):
        """No shared terms → cosine = 0.0."""
        query_terms = ["python", "programming"]
        doc_terms = {"database": 3, "sql": 2}
        doc_freq = {**ml_doc_freq, "python": 1, "programming": 1, "database": 1, "sql": 1}
        score = scorer.score(query_terms, doc_terms, doc_freq, TOTAL_DOCS)
        assert score == pytest.approx(0.0, abs=1e-9)

    def test_partial_overlap(self, scorer, doc0_full_terms, ml_doc_freq):
        """Partial term overlap → score strictly between 0 and 1."""
        query_terms = ["machine", "learning"]
        score = scorer.score(query_terms, doc0_full_terms, ml_doc_freq, TOTAL_DOCS)
        assert 0.0 < score < 1.0

    def test_more_relevant_doc_scores_higher(self, scorer, doc0_full_terms, doc4_full_terms, ml_doc_freq):
        """
        For query 'machine learning':
        doc0 (has both 'machine' and 'learning' with high TF)
        should score higher than a doc with only 'learning'.
        """
        query_terms = ["machine", "learning"]
        score0 = scorer.score(query_terms, doc0_full_terms, ml_doc_freq, TOTAL_DOCS)
        # doc5: a document with no 'machine' at all
        doc_no_machine = {"learning": 1, "data": 2}
        doc_freq_partial = {**ml_doc_freq, "data": 3}
        score_no_machine = scorer.score(query_terms, doc_no_machine, doc_freq_partial, TOTAL_DOCS)
        assert score0 > score_no_machine

    def test_empty_query_returns_zero(self, scorer, doc0_full_terms, ml_doc_freq):
        """Empty query_terms → 0.0."""
        score = scorer.score([], doc0_full_terms, ml_doc_freq, TOTAL_DOCS)
        assert score == 0.0

    def test_empty_document_returns_zero(self, scorer, ml_doc_freq):
        """Empty doc_terms_full → 0.0."""
        score = scorer.score(["machine"], {}, ml_doc_freq, TOTAL_DOCS)
        assert score == 0.0

    def test_result_in_zero_one_range(self, scorer, doc0_full_terms, ml_doc_freq):
        """Cosine result must always be in [0, 1]."""
        query_terms = ["machine", "learning", "neural"]
        score = scorer.score(query_terms, doc0_full_terms, ml_doc_freq, TOTAL_DOCS)
        assert 0.0 <= score <= 1.0

    def test_unknown_doc_terms_ignored(self, scorer, ml_doc_freq):
        """Unknown doc terms (not in doc_freq) contribute 0 to the doc vector."""
        doc_terms = {"machine": 3, "unknownxyz": 100}
        query_terms = ["machine"]
        score_with_unknown = scorer.score(query_terms, doc_terms, ml_doc_freq, TOTAL_DOCS)
        doc_terms_clean = {"machine": 3}
        score_clean = scorer.score(query_terms, doc_terms_clean, ml_doc_freq, TOTAL_DOCS)
        # Unknown term builds zero weight so doc vector is the same
        assert score_with_unknown == pytest.approx(score_clean, rel=1e-6)


# ---------------------------------------------------------------------------
# Tests — static helpers
# ---------------------------------------------------------------------------

class TestBuildTfidfVector:

    def test_basic_vector_construction(self, ml_doc_freq):
        """build_tfidf_vector returns correct weights for known terms."""
        terms = {"machine": 3, "learning": 4}
        vec = VectorScorer.build_tfidf_vector(terms, ml_doc_freq, TOTAL_DOCS)
        expected_machine = 3 * math.log10(10 / 3)
        expected_learning = 4 * math.log10(10 / 4)
        assert vec["machine"] == pytest.approx(expected_machine, rel=1e-6)
        assert vec["learning"] == pytest.approx(expected_learning, rel=1e-6)

    def test_unknown_terms_omitted(self, ml_doc_freq):
        """Terms not in doc_freq must be excluded from the vector."""
        terms = {"ghost": 5}
        vec = VectorScorer.build_tfidf_vector(terms, ml_doc_freq, TOTAL_DOCS)
        assert "ghost" not in vec
        assert len(vec) == 0

    def test_empty_terms_returns_empty(self, ml_doc_freq):
        """Empty input terms → empty vector."""
        vec = VectorScorer.build_tfidf_vector({}, ml_doc_freq, TOTAL_DOCS)
        assert vec == {}


class TestCosineSimilarity:

    def test_identical_vectors_return_one(self):
        """Cosine of a vector with itself = 1.0."""
        vec = {"a": 1.5, "b": 2.0, "c": 0.5}
        assert VectorScorer.cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors_return_zero(self):
        """Vectors with no shared terms → cosine = 0.0."""
        vec_a = {"apple": 1.0, "banana": 2.0}
        vec_b = {"cat": 1.0, "dog": 2.0}
        assert VectorScorer.cosine_similarity(vec_a, vec_b) == 0.0

    def test_empty_vector_returns_zero(self):
        """Either empty vector → 0.0."""
        assert VectorScorer.cosine_similarity({}, {"a": 1.0}) == 0.0
        assert VectorScorer.cosine_similarity({"a": 1.0}, {}) == 0.0

    def test_result_clamped_to_one(self):
        """Result must never exceed 1.0 due to floating point."""
        vec = {"x": 1.0}
        result = VectorScorer.cosine_similarity(vec, vec)
        assert result <= 1.0

    def test_partial_overlap_between_zero_and_one(self):
        """Partial overlap → result strictly between 0 and 1."""
        vec_a = {"a": 1.0, "b": 1.0}
        vec_b = {"b": 1.0, "c": 1.0}
        result = VectorScorer.cosine_similarity(vec_a, vec_b)
        assert 0.0 < result < 1.0
