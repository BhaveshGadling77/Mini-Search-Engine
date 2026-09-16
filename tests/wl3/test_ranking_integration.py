"""
End-to-end integration tests for the Ranking & Retrieval pipeline
===================================================================
Simulates the complete flow:

    W2 mock data (resolve_query + get_corpus_stats + get_doc_terms)
        ↓
    Ranker.rank()  (TFIDF / BM25 / VECTOR)
        ↓
    TopKRetriever.get_top_k()
        ↓
    Final ranked ScoredDocument list

All three ranking modes are exercised end-to-end.
Also tests the MMR candidate-pool path.

These tests use the same sample corpus defined in the implementation plan
so results can be hand-verified.
"""

import pytest
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever, ScoredDocument


# ===========================================================================
# Mock W2 response data — mirrors exactly what W2 would return
# ===========================================================================

def mock_resolve_query(query_string: str) -> tuple[dict, dict]:
    """Simulated W2.resolve_query() for 'machine learning' query."""
    candidates = {
        0: {"machine": 3, "learning": 4},
        4: {"machine": 1, "learning": 5},
        7: {"machine": 2, "learning": 3},
        1: {"machine": 0, "learning": 1},
    }
    doc_freq = {"machine": 3, "learning": 4}
    return candidates, doc_freq


def mock_get_corpus_stats() -> dict:
    """Simulated W2.get_corpus_stats()."""
    return {"total_docs": 10, "avg_doc_length": 45.0}


def mock_get_doc_terms(doc_ids: list[int]) -> dict[int, dict[str, int]]:
    """Simulated W2.get_doc_terms() — returns full term vectors."""
    full_store = {
        0: {"machine": 3, "learning": 4, "subset": 1, "artificial": 2,
            "intelligence": 2, "is": 2, "a": 1, "of": 1},          # len 16
        4: {"deep": 3, "learning": 5, "uses": 1, "neural": 2,
            "networks": 2, "layers": 2, "machine": 1},              # len 16 → but we treat as 18
        7: {"reinforcement": 2, "learning": 3, "machine": 2, "type": 1},  # len 8
        1: {"neural": 3, "networks": 2, "computing": 1, "learning": 1},   # len 7
    }
    return {doc_id: full_store[doc_id] for doc_id in doc_ids if doc_id in full_store}


QUERY = "machine learning"
QUERY_TERMS = ["machine", "learning"]


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def ranker() -> Ranker:
    return Ranker()


@pytest.fixture
def candidates_and_freq():
    return mock_resolve_query(QUERY)


@pytest.fixture
def corpus_stats():
    return mock_get_corpus_stats()


@pytest.fixture
def doc_terms_full(candidates_and_freq):
    candidates, _ = candidates_and_freq
    return mock_get_doc_terms(list(candidates.keys()))


@pytest.fixture
def doc_lengths(doc_terms_full):
    return {did: sum(terms.values()) for did, terms in doc_terms_full.items()}


# ===========================================================================
# Integration tests
# ===========================================================================

class TestTFIDFPipeline:

    def test_produces_scores_for_all_candidates(self, ranker, candidates_and_freq, corpus_stats):
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(
            ranking_mode=RankingMode.TFIDF,
            candidates=candidates,
            doc_freq=doc_freq,
            total_docs=corpus_stats["total_docs"],
            query_terms=QUERY_TERMS,
        )
        assert set(scores.keys()) == {0, 4, 7, 1}

    def test_top3_contains_correct_docs(self, ranker, candidates_and_freq, corpus_stats):
        """After TF-IDF ranking, top-3 must be docs 0, 4, 7 in some order."""
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(RankingMode.TFIDF, candidates, doc_freq,
                             corpus_stats["total_docs"], QUERY_TERMS)
        top3 = TopKRetriever.get_top_k(scores, k=3)
        top3_ids = {r.doc_id for r in top3}
        assert top3_ids == {0, 4, 7}

    def test_doc1_not_in_top3(self, ranker, candidates_and_freq, corpus_stats):
        """doc1 (only 'learning', no 'machine') must be excluded from top-3."""
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(RankingMode.TFIDF, candidates, doc_freq,
                             corpus_stats["total_docs"], QUERY_TERMS)
        top3 = TopKRetriever.get_top_k(scores, k=3)
        assert 1 not in {r.doc_id for r in top3}

    def test_results_in_descending_order(self, ranker, candidates_and_freq, corpus_stats):
        """Top-k result list must be sorted highest→lowest score."""
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(RankingMode.TFIDF, candidates, doc_freq,
                             corpus_stats["total_docs"], QUERY_TERMS)
        results = TopKRetriever.get_top_k(scores, k=4)
        result_scores = [r.score for r in results]
        assert result_scores == sorted(result_scores, reverse=True)


class TestBM25Pipeline:

    def test_produces_scores_for_all_candidates(self, ranker, candidates_and_freq,
                                                 corpus_stats, doc_lengths):
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(
            ranking_mode=RankingMode.BM25,
            candidates=candidates,
            doc_freq=doc_freq,
            total_docs=corpus_stats["total_docs"],
            query_terms=QUERY_TERMS,
            avg_doc_length=corpus_stats["avg_doc_length"],
            doc_lengths=doc_lengths,
        )
        assert set(scores.keys()) == {0, 4, 7, 1}

    def test_bm25_top_results_all_non_negative(self, ranker, candidates_and_freq,
                                                corpus_stats, doc_lengths):
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(RankingMode.BM25, candidates, doc_freq,
                             corpus_stats["total_docs"], QUERY_TERMS,
                             avg_doc_length=corpus_stats["avg_doc_length"],
                             doc_lengths=doc_lengths)
        results = TopKRetriever.get_top_k(scores, k=4)
        assert all(r.score >= 0.0 for r in results)

    def test_bm25_doc_lengths_computed_from_full_terms(self, ranker, candidates_and_freq,
                                                        corpus_stats, doc_terms_full):
        """doc_lengths computed via sum(full_terms.values()) must be used."""
        candidates, doc_freq = candidates_and_freq
        doc_lengths = {did: sum(t.values()) for did, t in doc_terms_full.items()}
        scores = ranker.rank(RankingMode.BM25, candidates, doc_freq,
                             corpus_stats["total_docs"], QUERY_TERMS,
                             avg_doc_length=corpus_stats["avg_doc_length"],
                             doc_lengths=doc_lengths)
        # Shorter docs (e.g. doc7 len=8, doc1 len=7) may score higher per token
        assert scores[7] > 0.0


class TestVectorPipeline:

    def test_produces_scores_for_all_candidates(self, ranker, candidates_and_freq,
                                                 corpus_stats, doc_terms_full):
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(
            ranking_mode=RankingMode.VECTOR,
            candidates=candidates,
            doc_freq=doc_freq,
            total_docs=corpus_stats["total_docs"],
            query_terms=QUERY_TERMS,
            doc_terms_full=doc_terms_full,
        )
        assert set(scores.keys()) == {0, 4, 7, 1}

    def test_vector_scores_in_zero_one_range(self, ranker, candidates_and_freq,
                                              corpus_stats, doc_terms_full):
        """Cosine similarity must always be in [0, 1]."""
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(RankingMode.VECTOR, candidates, doc_freq,
                             corpus_stats["total_docs"], QUERY_TERMS,
                             doc_terms_full=doc_terms_full)
        for doc_id, s in scores.items():
            assert 0.0 <= s <= 1.0, f"doc {doc_id} cosine = {s}"

    def test_vector_top1_is_most_relevant(self, ranker, candidates_and_freq,
                                           corpus_stats, doc_terms_full):
        """Vector top-1 should be one of the two ML-focused docs."""
        candidates, doc_freq = candidates_and_freq
        scores = ranker.rank(RankingMode.VECTOR, candidates, doc_freq,
                             corpus_stats["total_docs"], QUERY_TERMS,
                             doc_terms_full=doc_terms_full)
        top1 = TopKRetriever.get_top_k(scores, k=1)[0]
        assert top1.doc_id in {0, 4}  # both are strong ML docs


class TestMMRPoolPath:

    def test_mmr_pool_returns_20_candidates(self, ranker, candidates_and_freq, corpus_stats):
        """MMR pool path: get_top_k_for_mmr returns up to pool_size docs."""
        # Use a bigger fake corpus for this test
        big_candidates = {i: {"machine": i % 5 + 1, "learning": i % 3 + 1} for i in range(50)}
        big_doc_freq = {"machine": 30, "learning": 40}
        scores = ranker.rank(RankingMode.TFIDF, big_candidates, big_doc_freq, 50, QUERY_TERMS)
        pool = TopKRetriever.get_top_k_for_mmr(scores, pool_size=20)
        assert len(pool) == 20

    def test_mmr_pool_is_superset_of_top5(self, ranker, candidates_and_freq, corpus_stats):
        """The MMR pool must contain at least the top-5 final results."""
        big_candidates = {i: {"machine": i % 5 + 1, "learning": i % 4 + 1} for i in range(30)}
        big_doc_freq = {"machine": 15, "learning": 20}
        scores = ranker.rank(RankingMode.TFIDF, big_candidates, big_doc_freq, 30, QUERY_TERMS)
        pool = TopKRetriever.get_top_k_for_mmr(scores, pool_size=20)
        top5 = TopKRetriever.get_top_k(scores, k=5)
        pool_ids = {r.doc_id for r in pool}
        top5_ids = {r.doc_id for r in top5}
        assert top5_ids.issubset(pool_ids)


class TestCrossModePipeline:

    def test_all_modes_same_candidate_set(self, ranker, candidates_and_freq,
                                          corpus_stats, doc_terms_full, doc_lengths):
        """All 3 modes must score the exact same set of doc_ids."""
        candidates, doc_freq = candidates_and_freq
        N = corpus_stats["total_docs"]

        scores_tf = ranker.rank(RankingMode.TFIDF, candidates, doc_freq, N, QUERY_TERMS)
        scores_bm = ranker.rank(RankingMode.BM25, candidates, doc_freq, N, QUERY_TERMS,
                                 avg_doc_length=corpus_stats["avg_doc_length"], doc_lengths=doc_lengths)
        scores_vc = ranker.rank(RankingMode.VECTOR, candidates, doc_freq, N, QUERY_TERMS,
                                 doc_terms_full=doc_terms_full)

        assert set(scores_tf.keys()) == set(scores_bm.keys()) == set(scores_vc.keys())

    def test_modes_may_produce_different_top1(self, ranker, candidates_and_freq,
                                               corpus_stats, doc_terms_full, doc_lengths):
        """Different modes are not required to agree on top-1 (they often don't)."""
        candidates, doc_freq = candidates_and_freq
        N = corpus_stats["total_docs"]

        scores_tf = ranker.rank(RankingMode.TFIDF, candidates, doc_freq, N, QUERY_TERMS)
        scores_vc = ranker.rank(RankingMode.VECTOR, candidates, doc_freq, N, QUERY_TERMS,
                                 doc_terms_full=doc_terms_full)

        top1_tf = TopKRetriever.get_top_k(scores_tf, k=1)[0].score
        top1_vc = TopKRetriever.get_top_k(scores_vc, k=1)[0].score

        # Scores are on different scales (TF-IDF vs cosine) — just verify both positive
        assert top1_tf > 0
        assert top1_vc > 0
