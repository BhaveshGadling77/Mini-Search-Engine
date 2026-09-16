"""
Unit tests for BM25Scorer
===========================
All expected values are hand-calculated in the implementation plan.

Hand-calculated BM25 score for doc0 ("machine learning" query):
    k1=1.5, b=0.75, doc_length=16, avg_doc_length=45.0, total_docs=10

    "machine": tf=3, df=3
        IDF = log10((10-3+0.5)/(3+0.5) + 1) = log10(7.5/3.5 + 1) = log10(3.1429) ≈ 0.4974
        numerator = 3 × 2.5 = 7.5
        length_norm = 1 - 0.75 + 0.75 × (16/45) ≈ 0.5167
        denominator = 3 + 1.5 × 0.5167 ≈ 3.775
        component ≈ 0.4974 × (7.5/3.775) ≈ 0.9882

    "learning": tf=4, df=4
        IDF = log10((10-4+0.5)/(4+0.5) + 1) = log10(6.5/4.5 + 1) = log10(2.4444) ≈ 0.3882
        numerator = 4 × 2.5 = 10
        denominator = 4 + 1.5 × 0.5167 ≈ 4.775
        component ≈ 0.3882 × (10/4.775) ≈ 0.8131

    Total ≈ 1.8013
"""

import math
import pytest
from wl3.ranking.bm25 import BM25Scorer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scorer() -> BM25Scorer:
    return BM25Scorer(k1=1.5, b=0.75)


@pytest.fixture
def doc0_tf() -> dict:
    return {"machine": 3, "learning": 4}


@pytest.fixture
def doc_freq() -> dict:
    return {"machine": 3, "learning": 4}


TOTAL_DOCS = 10
AVG_DOC_LENGTH = 45.0
DOC0_LENGTH = 16  # sum of all tokens in doc 0
DOC_LONG_LENGTH = 100  # a long document


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBM25Scorer:

    def test_basic_scoring(self, scorer, doc0_tf, doc_freq):
        """Hand-calculated BM25 score must match within tolerance."""
        score = scorer.score(
            doc_tf=doc0_tf,
            doc_freq=doc_freq,
            total_docs=TOTAL_DOCS,
            doc_length=DOC0_LENGTH,
            avg_doc_length=AVG_DOC_LENGTH,
            query_terms=["machine", "learning"],
        )
        assert score == pytest.approx(1.8013, rel=0.001)

    def test_ordering_doc0_vs_doc7(self, scorer, doc_freq):
        """doc0 (tf=3,4) must outscore doc7 (tf=2,3) at equal doc lengths."""
        doc7_tf = {"machine": 2, "learning": 3}
        score0 = scorer.score(doc0_tf := {"machine": 3, "learning": 4}, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        score7 = scorer.score(doc7_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        assert score0 > score7

    def test_short_doc_scores_higher_than_long_doc_same_raw_tf(self, scorer, doc0_tf, doc_freq):
        """
        A shorter document should score higher than a longer document with
        the exact same raw TF, because the length penalty is lower.
        """
        score_short = scorer.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        score_long = scorer.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC_LONG_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        # doc0_length(16) < avg(45), so short gets a boost; long(100) gets penalised
        assert score_short > score_long

    def test_length_normalization_disabled(self, doc0_tf, doc_freq):
        """With b=0, different document lengths must produce identical scores."""
        scorer_no_len = BM25Scorer(k1=1.5, b=0.0)
        score_short = scorer_no_len.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        score_long = scorer_no_len.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC_LONG_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        assert score_short == pytest.approx(score_long, rel=1e-9)

    def test_full_length_normalization(self, doc0_tf, doc_freq):
        """With b=1, length normalization is applied at maximum weight."""
        scorer_full_len = BM25Scorer(k1=1.5, b=1.0)
        score_short = scorer_full_len.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        score_avg = scorer_full_len.score(doc0_tf, doc_freq, TOTAL_DOCS, int(AVG_DOC_LENGTH), AVG_DOC_LENGTH, ["machine", "learning"])
        score_long = scorer_full_len.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC_LONG_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        # short < avg → short gets boost (positive), long gets penalised
        assert score_short > score_avg > score_long

    def test_tf_saturation(self, scorer, doc_freq):
        """BM25 term-frequency saturation: tf=100 must score only modestly more than tf=10."""
        tf_10 = {"machine": 10}
        tf_100 = {"machine": 100}
        score_10 = scorer.score(tf_10, {"machine": 3}, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine"])
        score_100 = scorer.score(tf_100, {"machine": 3}, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine"])
        # With k1=1.5 the asymptote is (k1+1) × IDF.
        # score_100 should be only marginally above score_10
        ratio = score_100 / score_10
        assert ratio < 1.15, f"Expected TF saturation, got ratio={ratio:.3f}"

    def test_custom_k1_b(self, doc0_tf, doc_freq):
        """Custom k1/b must differ from default."""
        default = BM25Scorer(k1=1.5, b=0.75)
        custom = BM25Scorer(k1=1.2, b=0.5)
        score_default = default.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        score_custom = custom.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        assert score_default != pytest.approx(score_custom, abs=1e-4)

    def test_zero_tf_term_contributes_zero(self, scorer, doc_freq):
        """Term with tf=0 in the document must contribute 0."""
        doc_tf = {"learning": 4}  # no 'machine'
        score = scorer.score(doc_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        score_learning_only = scorer.score(doc_tf, {"learning": 4}, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["learning"])
        assert score == pytest.approx(score_learning_only, rel=1e-6)

    def test_empty_query_returns_zero(self, scorer, doc0_tf, doc_freq):
        """Empty query must return 0.0."""
        assert scorer.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, []) == 0.0

    def test_single_doc_corpus(self, scorer):
        """N=1 edge case: df=1, total_docs=1 should still produce valid score."""
        doc_tf = {"python": 5}
        doc_freq = {"python": 1}
        score = scorer.score(doc_tf, doc_freq, total_docs=1, doc_length=10, avg_doc_length=10.0, query_terms=["python"])
        # IDF = log10((1-1+0.5)/(1+0.5) + 1) = log10(0.5/1.5 + 1) = log10(1.333) ≈ 0.1249
        assert score > 0.0

    def test_invalid_k1_raises(self):
        """Negative k1 must raise ValueError at construction time."""
        with pytest.raises(ValueError, match="k1"):
            BM25Scorer(k1=-1.0)

    def test_invalid_b_raises(self):
        """b outside [0, 1] must raise ValueError at construction time."""
        with pytest.raises(ValueError, match="b"):
            BM25Scorer(b=1.5)

    def test_score_is_non_negative(self, scorer, doc0_tf, doc_freq):
        """BM25 score must always be non-negative."""
        score = scorer.score(doc0_tf, doc_freq, TOTAL_DOCS, DOC0_LENGTH, AVG_DOC_LENGTH, ["machine", "learning"])
        assert score >= 0.0
