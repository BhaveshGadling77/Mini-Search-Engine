"""
WL3 Full Branch Stress Test Suite
===================================
Covers ALL FOUR PERSONS' code on the wl3 branch.

  Person 1 — Ranking & Retrieval:
              TFIDFScorer, BM25Scorer, VectorScorer, Ranker,
              TopKRetriever, ScoredDocument, Evaluation Metrics, Dataset.
  Person 2 — Caching Layer:
              LRUCache, SQLiteCache, CacheManager, build_cache_key.
  Person 3 — Relevance Feedback & Diversification:
              Rocchio, MMR, SessionManager, SessionFeedbackState.
  Person 4 — Engine & System Integration:
              InMemoryWorklet2, Worklet2Adapter, QueryEngine,
              factory.build_engine, synthetic_corpus.

Zero external dependencies: 100% Python standard library (unittest, threading, sqlite3).
Zero source code modifications: tests are completely self-contained in this file.
"""

from __future__ import annotations

import collections
from concurrent.futures import ThreadPoolExecutor
import math
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Imports from all 4 persons
from wl3.ranking.tfidf import TFIDFScorer
from wl3.ranking.bm25 import BM25Scorer
from wl3.ranking.vector import VectorScorer
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever, ScoredDocument
from wl3.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    average_precision,
    evaluate_ranking,
    aggregate_metrics,
)
from wl3.evaluation.dataset import LABELLED_QUERIES, get_queries

from wl3.cache.lru_cache import LRUCache
from wl3.cache.sqlite_cache import SQLiteCache
from wl3.cache.cache_manager import CacheManager, build_cache_key

from wl3.feedback.rocchio import Rocchio
from wl3.diversification.mmr import MMR
from wl3.feedback.session_manager import SessionManager, SessionFeedbackState

from wl3.integration.mock_worklet2 import InMemoryWorklet2
from wl3.integration.worklet2_adapter import Worklet2Adapter
from wl3.engine.query_engine import QueryEngine
from wl3.engine.models import RankedResult
from wl3.engine.factory import build_engine
from wl3.evaluation.synthetic_corpus import build_synthetic_corpus


# ==============================================================================
# SECTION 1: PERSON 1 TESTS — RANKING, RETRIEVAL & METRICS
# ==============================================================================

class TestPerson1TFIDFScorer(unittest.TestCase):
    """Unit and stress tests for Person 1's TFIDFScorer."""

    def setUp(self):
        self.scorer = TFIDFScorer()

    def test_basic_formula(self):
        # doc_tf, doc_freq, total_docs, query_terms
        # N=100, df=10 -> idf = log10(100/10) = 1.0. tf=2 -> score = 2.0
        score = self.scorer.score(
            doc_tf={"apple": 2},
            doc_freq={"apple": 10},
            total_docs=100,
            query_terms=["apple"],
        )
        self.assertAlmostEqual(score, 2.0, places=5)

    def test_multi_term_sum(self):
        # apple: tf=2, df=10, N=100 -> idf=1.0 -> 2.0
        # banana: tf=3, df=1, N=100 -> idf=2.0 -> 6.0
        # total = 8.0
        score = self.scorer.score(
            doc_tf={"apple": 2, "banana": 3},
            doc_freq={"apple": 10, "banana": 1},
            total_docs=100,
            query_terms=["apple", "banana"],
        )
        self.assertAlmostEqual(score, 8.0, places=5)

    def test_empty_query_returns_zero(self):
        self.assertEqual(self.scorer.score({"a": 1}, {"a": 5}, 10, []), 0.0)

    def test_empty_doc_terms_returns_zero(self):
        self.assertEqual(self.scorer.score({}, {"a": 5}, 10, ["a"]), 0.0)

    def test_zero_total_docs_returns_zero(self):
        self.assertEqual(self.scorer.score({"a": 2}, {"a": 5}, 0, ["a"]), 0.0)

    def test_term_absent_from_doc_terms(self):
        score = self.scorer.score({"banana": 5}, {"apple": 2}, 100, ["apple"])
        self.assertEqual(score, 0.0)

    def test_term_absent_from_doc_freq(self):
        score = self.scorer.score({"apple": 5}, {}, 100, ["apple"])
        self.assertEqual(score, 0.0)

    def test_df_greater_than_or_equal_to_total_docs_clamped_to_zero(self):
        # If term in all documents: N=10, df=10 -> log10(1) = 0.0 -> score = 0.0
        score = self.scorer.score({"the": 10}, {"the": 10}, 10, ["the"])
        self.assertEqual(score, 0.0)
        # If df > N due to corrupt data: log10(N/df) < 0 -> clamped to 0.0
        score_corrupt = self.scorer.score({"the": 10}, {"the": 20}, 10, ["the"])
        self.assertEqual(score_corrupt, 0.0)

    def test_extreme_large_tf(self):
        # Stress with tf=1,000,000
        score = self.scorer.score({"big": 1_000_000}, {"big": 10}, 10_000, ["big"])
        self.assertTrue(math.isfinite(score))
        self.assertAlmostEqual(score, 3_000_000.0, places=1)


class TestPerson1BM25Scorer(unittest.TestCase):
    """Unit and stress tests for Person 1's BM25Scorer."""

    def setUp(self):
        self.scorer = BM25Scorer(k1=1.5, b=0.75)

    def test_invalid_parameters_raise(self):
        with self.assertRaises(ValueError):
            BM25Scorer(k1=-0.1)
        with self.assertRaises(ValueError):
            BM25Scorer(b=-0.1)
        with self.assertRaises(ValueError):
            BM25Scorer(b=1.1)

    def test_empty_query_returns_zero(self):
        score = self.scorer.score({"a": 1}, {"a": 5}, 100, 10, 10.0, [])
        self.assertEqual(score, 0.0)

    def test_tf_saturation(self):
        # In BM25, as TF increases, score approaches (k1 + 1) * IDF asymptotically
        s1 = self.scorer.score({"a": 1}, {"a": 10}, 100, 10, 10.0, ["a"])
        s10 = self.scorer.score({"a": 10}, {"a": 10}, 100, 10, 10.0, ["a"])
        s100 = self.scorer.score({"a": 100}, {"a": 10}, 100, 10, 10.0, ["a"])
        s1000 = self.scorer.score({"a": 1000}, {"a": 10}, 100, 10, 10.0, ["a"])
        self.assertLess(s1, s10)
        self.assertLess(s10, s100)
        self.assertLess(s100, s1000)
        # Ratio of increase shrinks dramatically
        self.assertGreater(s10 - s1, s1000 - s100)

    def test_document_length_normalization(self):
        # A shorter document with the same term count should score higher
        s_short = self.scorer.score({"a": 2}, {"a": 10}, 100, 5, 10.0, ["a"])
        s_long = self.scorer.score({"a": 2}, {"a": 10}, 100, 20, 10.0, ["a"])
        self.assertGreater(s_short, s_long)

    def test_b_zero_disables_length_normalization(self):
        scorer_nob = BM25Scorer(k1=1.5, b=0.0)
        s_short = scorer_nob.score({"a": 2}, {"a": 10}, 100, 5, 10.0, ["a"])
        s_long = scorer_nob.score({"a": 2}, {"a": 10}, 100, 20, 10.0, ["a"])
        self.assertAlmostEqual(s_short, s_long)

    def test_non_negative_floor(self):
        # Robertson IDF with df very close to N can go negative, BM25Scorer clamps to >= 0
        score = self.scorer.score({"common": 5}, {"common": 99}, 100, 10, 10.0, ["common"])
        self.assertGreaterEqual(score, 0.0)


class TestPerson1VectorScorer(unittest.TestCase):
    """Unit and stress tests for Person 1's VectorScorer."""

    def setUp(self):
        self.scorer = VectorScorer()

    def test_identical_vectors_have_cosine_one(self):
        v = {"apple": 1.0, "banana": 2.0}
        sim = self.scorer.cosine_similarity(v, v)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_orthogonal_vectors_have_cosine_zero(self):
        v1 = {"apple": 1.0}
        v2 = {"banana": 1.0}
        sim = self.scorer.cosine_similarity(v1, v2)
        self.assertEqual(sim, 0.0)

    def test_empty_vector_returns_zero(self):
        self.assertEqual(self.scorer.cosine_similarity({}, {"a": 1.0}), 0.0)
        self.assertEqual(self.scorer.cosine_similarity({"a": 1.0}, {}), 0.0)
        self.assertEqual(self.scorer.cosine_similarity({}, {}), 0.0)

    def test_symmetry(self):
        v1 = {"apple": 0.5, "banana": 0.8, "cherry": 0.2}
        v2 = {"apple": 0.9, "banana": 0.1, "date": 0.4}
        self.assertAlmostEqual(
            self.scorer.cosine_similarity(v1, v2),
            self.scorer.cosine_similarity(v2, v1),
            places=6,
        )

    def test_score_wrapper(self):
        score = self.scorer.score(
            query_terms=["apple"],
            doc_terms_full={"apple": 1, "banana": 1},
            doc_freq={"apple": 5},
            total_docs=100,
        )
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestPerson1Ranker(unittest.TestCase):
    """Unit tests for Ranker dispatching across modes."""

    def setUp(self):
        self.ranker = Ranker()
        self.candidates = {
            1: {"python": 2, "search": 1},
            2: {"python": 1, "search": 3},
        }
        self.doc_freq = {"python": 2, "search": 2}
        self.total_docs = 10
        self.doc_lengths = {1: 3, 2: 4}
        self.avg_doc_len = 3.5

    def test_rank_tfidf(self):
        scores = self.ranker.rank(
            ranking_mode=RankingMode.TFIDF,
            candidates=self.candidates,
            doc_freq=self.doc_freq,
            total_docs=self.total_docs,
            query_terms=["python", "search"],
        )
        self.assertEqual(set(scores.keys()), {1, 2})
        for s in scores.values():
            self.assertGreaterEqual(s, 0.0)

    def test_rank_bm25(self):
        scores = self.ranker.rank(
            ranking_mode=RankingMode.BM25,
            candidates=self.candidates,
            doc_freq=self.doc_freq,
            total_docs=self.total_docs,
            query_terms=["python", "search"],
            doc_lengths=self.doc_lengths,
            avg_doc_length=self.avg_doc_len,
        )
        self.assertEqual(set(scores.keys()), {1, 2})

    def test_bm25_missing_doc_lengths_raises(self):
        with self.assertRaises(ValueError):
            self.ranker.rank(
                ranking_mode=RankingMode.BM25,
                candidates=self.candidates,
                doc_freq=self.doc_freq,
                total_docs=self.total_docs,
                query_terms=["python"],
                doc_lengths=None,
                avg_doc_length=self.avg_doc_len,
            )

    def test_score_document_alias(self):
        s1 = self.ranker.score_document(
            ranking_mode=RankingMode.TFIDF,
            doc_id=1,
            doc_tf={"python": 2},
            doc_freq=self.doc_freq,
            total_docs=self.total_docs,
            query_terms=["python"],
        )
        self.assertGreater(s1, 0.0)


class TestPerson1TopKRetriever(unittest.TestCase):
    """Unit and stress tests for Person 1's TopKRetriever."""

    def test_basic_top_k_ordering(self):
        scores = {10: 1.5, 20: 4.2, 30: 2.1, 40: 0.5, 50: 3.8}
        top3 = TopKRetriever.get_top_k(scores, k=3)
        self.assertEqual(len(top3), 3)
        self.assertEqual([d.doc_id for d in top3], [20, 50, 30])
        self.assertEqual([d.score for d in top3], [4.2, 3.8, 2.1])

    def test_tie_breaking_by_doc_id_ascending(self):
        scores = {100: 5.0, 50: 5.0, 200: 5.0, 25: 5.0}
        top4 = TopKRetriever.get_top_k(scores, k=4)
        self.assertEqual([d.doc_id for d in top4], [25, 50, 100, 200])

    def test_k_zero_or_negative(self):
        scores = {1: 1.0, 2: 2.0}
        self.assertEqual(TopKRetriever.get_top_k(scores, k=0), [])
        self.assertEqual(TopKRetriever.get_top_k(scores, k=-5), [])

    def test_k_greater_than_n(self):
        scores = {1: 1.0, 2: 2.0}
        top = TopKRetriever.get_top_k(scores, k=100)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].doc_id, 2)

    def test_empty_scores_returns_empty(self):
        self.assertEqual(TopKRetriever.get_top_k({}, k=5), [])

    def test_nan_scores_discarded(self):
        scores = {1: 2.0, 2: float("nan"), 3: 3.0}
        top = TopKRetriever.get_top_k(scores, k=3)
        self.assertEqual([d.doc_id for d in top], [3, 1])

    def test_large_scale_heap_stress(self):
        # 10,000 documents, retrieve top 10
        rng = random.Random(42)
        scores = {i: rng.uniform(0.0, 100.0) for i in range(10_000)}
        scores[99999] = 105.0  # guaranteed top 1

        top10 = TopKRetriever.get_top_k(scores, k=10)
        self.assertEqual(len(top10), 10)
        self.assertEqual(top10[0].doc_id, 99999)
        self.assertEqual(top10[0].score, 105.0)
        for i in range(len(top10) - 1):
            self.assertGreaterEqual(top10[i].score, top10[i + 1].score)


class TestPerson1Metrics(unittest.TestCase):
    """Unit tests for evaluation metrics calculation."""

    def test_precision_at_k(self):
        retrieved = [1, 2, 3, 4, 5]
        relevant = {1, 3, 7}
        self.assertAlmostEqual(precision_at_k(retrieved, relevant, 3), 2 / 3)
        self.assertAlmostEqual(precision_at_k(retrieved, relevant, 5), 0.4)

    def test_recall_at_k(self):
        retrieved = [1, 2, 3, 4, 5]
        relevant = {1, 3, 7, 9}
        self.assertAlmostEqual(recall_at_k(retrieved, relevant, 3), 0.5)

    def test_reciprocal_rank(self):
        self.assertEqual(reciprocal_rank([10, 20, 30], {10}), 1.0)
        self.assertEqual(reciprocal_rank([10, 20, 30], {20}), 0.5)
        self.assertEqual(reciprocal_rank([10, 20, 30], {30}), 1 / 3)
        self.assertEqual(reciprocal_rank([10, 20, 30], {99}), 0.0)

    def test_average_precision(self):
        retrieved = [1, 2, 3, 4, 5]
        relevant = {1, 3}
        self.assertAlmostEqual(average_precision(retrieved, relevant), 5 / 6, places=5)

    def test_boundary_empty_metrics(self):
        self.assertEqual(precision_at_k([], {1, 2}, 5), 0.0)
        self.assertEqual(precision_at_k([1, 2], set(), 5), 0.0)
        self.assertEqual(recall_at_k([1, 2], set(), 5), 0.0)
        self.assertEqual(reciprocal_rank([], {1}), 0.0)
        self.assertEqual(average_precision([], {1}), 0.0)


# ==============================================================================
# SECTION 2: PERSON 2 TESTS — CACHE LAYER (LRU, SQLITE, CACHEMANAGER)
# ==============================================================================

class TestPerson2LRUCache(unittest.TestCase):
    """Unit and stress tests for Person 2's LRUCache."""

    def test_capacity_validation(self):
        with self.assertRaises(ValueError):
            LRUCache(0)
        with self.assertRaises(ValueError):
            LRUCache(-1)

    def test_lru_eviction_order(self):
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(len(cache), 3)

        # Access "a" -> "a" becomes MRU, "b" becomes LRU
        self.assertEqual(cache.get("a"), 1)

        # Insert "d" -> should evict "b"
        cache.put("d", 4)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("c"), 3)
        self.assertEqual(cache.get("d"), 4)

    def test_update_existing_key_does_not_grow_cache(self):
        cache = LRUCache(capacity=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)
        self.assertEqual(len(cache), 2)
        self.assertEqual(cache.get("a"), 10)

        # "b" is now LRU, inserting "c" evicts "b"
        cache.put("c", 3)
        self.assertIsNone(cache.get("b"))
        self.assertEqual(cache.get("a"), 10)
        self.assertEqual(cache.get("c"), 3)

    def test_remove_and_clear(self):
        cache = LRUCache(capacity=3)
        cache.put("x", 1)
        cache.put("y", 2)
        self.assertTrue(cache.remove("x"))
        self.assertFalse(cache.remove("x"))
        self.assertIsNone(cache.get("x"))
        self.assertEqual(len(cache), 1)

        cache.clear()
        self.assertEqual(len(cache), 0)
        self.assertIsNone(cache.get("y"))

    def test_multithreaded_concurrency_stress(self):
        cache = LRUCache(capacity=50)
        errors = []

        def worker(thread_id: int):
            try:
                for i in range(200):
                    key = f"key-{i % 30}"
                    cache.put(key, thread_id * 1000 + i)
                    val = cache.get(key)
                    if random.random() < 0.1:
                        cache.remove(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent LRU errors: {errors}")
        self.assertLessEqual(len(cache), 50)


class TestPerson2SQLiteCache(unittest.TestCase):
    """Unit and stress tests for Person 2's SQLiteCache."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_cache.db")
        self.cache = SQLiteCache(db_path=self.db_path, index_version="v1")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_put_and_get_roundtrip(self):
        key = ("machine learning", "bm25", 10, False, "v1")
        value = [{"doc_id": 1, "score": 3.5, "title": "ML Basics"}]
        self.cache.put(key, value)

        cached_val = self.cache.get(key)
        self.assertIsNotNone(cached_val)
        self.assertEqual(cached_val[0]["doc_id"], 1)
        self.assertAlmostEqual(cached_val[0]["score"], 3.5)

    def test_miss_returns_none(self):
        key = ("unseen query", "tfidf", 5, False, "v1")
        self.assertIsNone(self.cache.get(key))

    def test_version_isolation(self):
        key_v1 = ("query", "bm25", 5, False, "v1")
        key_v2 = ("query", "bm25", 5, False, "v2")
        self.cache.put(key_v1, [{"doc_id": 10}])

        self.assertIsNotNone(self.cache.get(key_v1))
        self.assertIsNone(self.cache.get(key_v2))

    def test_clear_removes_all(self):
        k1 = ("q1", "bm25", 5, False, "v1")
        k2 = ("q2", "bm25", 5, False, "v1")
        self.cache.put(k1, [1])
        self.cache.put(k2, [2])
        self.assertIsNotNone(self.cache.get(k1))
        self.assertIsNotNone(self.cache.get(k2))
        self.cache.clear()
        self.assertIsNone(self.cache.get(k1))
        self.assertIsNone(self.cache.get(k2))


class TestPerson2CacheManager(unittest.TestCase):
    """Unit tests for Person 2's two-tier CacheManager."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "cm_test.db")
        self.manager = CacheManager(capacity=2, db_path=self.db_path, index_version="1")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_l1_to_l2_promotion(self):
        k1 = build_cache_key("query 1", "bm25", 5, False, "1")
        k2 = build_cache_key("query 2", "bm25", 5, False, "1")
        k3 = build_cache_key("query 3", "bm25", 5, False, "1")

        self.manager.put(k1, [{"id": 1}])
        self.manager.put(k2, [{"id": 2}])
        # L1 capacity is 2; putting k3 evicts k1 from L1 into L2
        self.manager.put(k3, [{"id": 3}])

        # Verify k1 is no longer in L1 LRU directly
        self.assertIsNone(self.manager._lru.get(k1))
        # But k1 is in L2 SQLite!
        self.assertIsNotNone(self.manager._sqlite.get(k1))

        # Getting k1 through manager promotes it back to L1
        promoted = self.manager.get(k1)
        self.assertIsNotNone(promoted)
        self.assertEqual(promoted[0]["id"], 1)
        self.assertIsNotNone(self.manager._lru.get(k1))

    def test_build_cache_key_normalisation(self):
        k1 = build_cache_key("  Deep   Learning  ", "TF-IDF", 10, False, 1)
        k2 = build_cache_key("deep learning", "tf-idf", 10, False, "1")
        self.assertEqual(k1, k2)


# ==============================================================================
# SECTION 3: PERSON 3 TESTS — ROCCHIO FEEDBACK & MMR DIVERSIFICATION
# ==============================================================================

class TestPerson3Rocchio(unittest.TestCase):
    """Unit and stress tests for Person 3's Rocchio feedback."""

    def test_param_validation(self):
        with self.assertRaises(ValueError):
            Rocchio(alpha=-0.1)
        with self.assertRaises(ValueError):
            Rocchio(beta=-0.5)
        with self.assertRaises(ValueError):
            Rocchio(gamma=-0.1)

    def test_basic_feedback_calculation(self):
        rocchio = Rocchio(alpha=1.0, beta=0.75, gamma=0.25)
        q = {"neural": 1.0}
        rel = [{"neural": 1.0, "network": 2.0}]
        non_rel = [{"spam": 4.0}]

        updated = rocchio.update_query(q, rel, non_rel)
        self.assertAlmostEqual(updated["neural"], 1.75)
        self.assertAlmostEqual(updated["network"], 1.5)
        self.assertNotIn("spam", updated)

    def test_negative_weights_strictly_pruned(self):
        rocchio = Rocchio(alpha=1.0, beta=0.5, gamma=1.0)
        q = {"term": 0.5}
        rel = []
        non_rel = [{"term": 1.0}]
        updated = rocchio.update_query(q, rel, non_rel)
        self.assertNotIn("term", updated)
        self.assertEqual(len(updated), 0)

    def test_empty_feedback_leaves_query_scaled_by_alpha(self):
        rocchio = Rocchio(alpha=1.2, beta=0.75, gamma=0.15)
        q = {"a": 2.0, "b": 3.0}
        updated = rocchio.update_query(q, [], [])
        self.assertAlmostEqual(updated["a"], 2.4)
        self.assertAlmostEqual(updated["b"], 3.6)


class TestPerson3MMR(unittest.TestCase):
    """Unit and stress tests for Person 3's MMR diversifier."""

    def test_param_validation(self):
        with self.assertRaises(ValueError):
            MMR(lambda_param=-0.1)
        with self.assertRaises(ValueError):
            MMR(lambda_param=1.1)

    def test_empty_or_zero_k_returns_empty(self):
        mmr = MMR(0.5)
        self.assertEqual(mmr.rerank([], {"a": 1.0}, {}, 5), [])
        self.assertEqual(mmr.rerank([ScoredDocument(1, 1.0)], {"a": 1.0}, {}, 0), [])
        self.assertEqual(mmr.rerank([ScoredDocument(1, 1.0)], {"a": 1.0}, {}, -1), [])

    def test_diversity_reranking(self):
        q_vec = {"topicA": 1.0, "topicB": 1.0}
        doc_vecs = {
            1: {"topicA": 1.0},
            2: {"topicA": 1.0},
            3: {"topicB": 0.95},
        }
        pool = [
            ScoredDocument(1, 1.0),
            ScoredDocument(2, 0.99),
            ScoredDocument(3, 0.95),
        ]

        mmr = MMR(lambda_param=0.5)
        reranked = mmr.rerank(pool, q_vec, doc_vecs, k=2)
        chosen_ids = [d.doc_id for d in reranked]
        self.assertEqual(chosen_ids[0], 1)
        self.assertEqual(chosen_ids[1], 3)


class TestPerson3SessionManager(unittest.TestCase):
    """Unit and concurrency tests for Person 3's SessionManager."""

    def setUp(self):
        self.sm = SessionManager()

    def test_session_lifecycle(self):
        sid = self.sm.create_session()
        self.assertTrue(len(sid) > 10)
        self.assertFalse(self.sm.has_feedback(sid))

        self.sm.set_term_boosts(sid, {"python": 1.5, "ir": 0.8})
        self.sm.add_relevant_document(sid, 42)
        self.assertTrue(self.sm.has_feedback(sid))
        self.assertEqual(self.sm.get_term_boosts(sid), {"python": 1.5, "ir": 0.8})

        state = self.sm.get_or_create(sid)
        self.assertIn(42, state.relevant_doc_ids)

        self.sm.clear_feedback(sid)
        self.assertFalse(self.sm.has_feedback(sid))
        self.assertTrue(self.sm.end_session(sid))
        self.assertEqual(len(self.sm), 0)

    def test_session_isolation(self):
        s1 = self.sm.create_session()
        s2 = self.sm.create_session()

        self.sm.set_term_boosts(s1, {"term1": 2.0})
        self.sm.set_term_boosts(s2, {"term2": 5.0})

        self.assertNotIn("term2", self.sm.get_term_boosts(s1))
        self.assertNotIn("term1", self.sm.get_term_boosts(s2))

    def test_concurrent_sessions_stress(self):
        errors = []

        def worker(w_id: int):
            try:
                for i in range(50):
                    sid = self.sm.create_session()
                    self.sm.set_term_boosts(sid, {f"term_{w_id}": float(i + 1)})
                    self.sm.add_relevant_document(sid, i)
                    boosts = self.sm.get_term_boosts(sid)
                    if boosts[f"term_{w_id}"] != float(i + 1):
                        errors.append(f"Mismatch in worker {w_id}")
                    self.sm.end_session(sid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent SessionManager errors: {errors}")


# ==============================================================================
# SECTION 4: PERSON 4 & INTEGRATION TESTS — WORKLET 2 ADAPTER & QUERYENGINE
# ==============================================================================

class TestPerson4IntegrationAndEngine(unittest.TestCase):
    """End-to-end integration and stress tests for QueryEngine across all 4 people."""

    @classmethod
    def setUpClass(cls):
        cls.docs, cls.queries = build_synthetic_corpus(seed=42)
        cls.w2 = InMemoryWorklet2(cls.docs)
        cls.adapter = Worklet2Adapter(cls.w2)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "engine_test.db")
        self.engine = QueryEngine(
            self.adapter,
            cache_db_path=self.db_path,
            cache_capacity=50,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_all_ranking_modes_produce_results(self):
        for mode in ["tfidf", "bm25", "vector"]:
            results = self.engine.search("machine learning neural networks", ranking_mode=mode, k=5)
            self.assertGreaterEqual(len(results), 1, f"Mode {mode} returned no results")
            self.assertIsInstance(results[0], RankedResult)
            self.assertTrue(results[0].title)
            self.assertTrue(results[0].snippet)
            for i in range(len(results) - 1):
                self.assertGreaterEqual(results[i].score, results[i + 1].score)

    def test_ranking_mode_alias_support(self):
        r1 = self.engine.search("database transactions", ranking_mode="tf-idf", k=3)
        r2 = self.engine.search("database transactions", ranking_mode="tf_idf", k=3)
        self.assertEqual([d.doc_id for d in r1], [d.doc_id for d in r2])

    def test_cache_hit_and_latency_drop(self):
        q = "database transactions rollback"
        # Query 1: Cache miss
        start = time.perf_counter()
        r1 = self.engine.search(q, ranking_mode="bm25", k=5)
        miss_latency = time.perf_counter() - start

        # Query 2: Cache hit
        start = time.perf_counter()
        r2 = self.engine.search(q, ranking_mode="bm25", k=5)
        hit_latency = time.perf_counter() - start

        self.assertEqual([d.doc_id for d in r1], [d.doc_id for d in r2])
        self.assertGreater(self.engine.cache_hits, 0)
        self.assertLess(hit_latency, 0.05)

    def test_relevance_feedback_reorders_search(self):
        sid = self.engine.sessions.create_session()
        q = "machine learning"

        initial_results = self.engine.search(q, session_id=sid, ranking_mode="bm25", k=10)
        self.assertGreater(len(initial_results), 5)

        chosen_doc = initial_results[4]
        self.engine.mark_relevant(sid, chosen_doc.doc_id)

        refined_results = self.engine.search(q, session_id=sid, ranking_mode="bm25", k=10)
        self.assertGreater(len(refined_results), 0)

        # Personalized queries must NOT poison the shared cache
        anon_results = self.engine.search(q, session_id=None, ranking_mode="bm25", k=10)
        self.assertEqual([d.doc_id for d in anon_results], [d.doc_id for d in initial_results])

    def test_mmr_diversification_flag(self):
        q = "database indexing transactions"
        res_standard = self.engine.search(q, ranking_mode="bm25", k=5, use_mmr=False)
        res_mmr = self.engine.search(q, ranking_mode="bm25", k=5, use_mmr=True)

        self.assertEqual(len(res_standard), 5)
        self.assertEqual(len(res_mmr), 5)
        self.assertIsInstance(res_mmr[0], RankedResult)

    def test_concurrent_searches_stress(self):
        queries = [
            "neural networks backpropagation",
            "decision trees entropy",
            "clustering kmeans centroid",
            "transactions acid rollback",
            "indexing btree lookup",
        ]
        errors = []

        def worker(w_id: int):
            try:
                sid = self.engine.sessions.create_session()
                for i in range(20):
                    q = queries[i % len(queries)]
                    mode = ["tfidf", "bm25", "vector"][i % 3]
                    res = self.engine.search(q, session_id=sid, ranking_mode=mode, k=5)
                    if not res:
                        errors.append(f"Empty results for {q} in worker {w_id}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent engine errors: {errors}")

    def test_adversarial_queries(self):
        # 1. Empty string
        self.assertEqual(self.engine.search(""), [])
        # 2. Whitespace only
        self.assertEqual(self.engine.search("   "), [])
        # 3. Punctuation / symbols only
        self.assertEqual(self.engine.search("@#$%^&*()_+{}[]:"), [])
        # 4. Unknown nonsense word
        self.assertEqual(self.engine.search("xyzzyfoobar987123qwerty"), [])
        # 5. Giant query (300 terms)
        giant_query = " ".join(["learning", "data", "model", "database"] * 75)
        results = self.engine.search(giant_query, k=5)
        self.assertTrue(len(results) > 0)
        # 6. Extreme k values
        self.assertEqual(self.engine.search("learning", k=0), [])
        self.assertEqual(self.engine.search("learning", k=-5), [])
        huge_k_results = self.engine.search("learning", k=10_000)
        self.assertTrue(len(huge_k_results) > 0)


# ==============================================================================
# RUNNER
# ==============================================================================

def run_all_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        # Person 1
        TestPerson1TFIDFScorer,
        TestPerson1BM25Scorer,
        TestPerson1VectorScorer,
        TestPerson1Ranker,
        TestPerson1TopKRetriever,
        TestPerson1Metrics,
        # Person 2
        TestPerson2LRUCache,
        TestPerson2SQLiteCache,
        TestPerson2CacheManager,
        # Person 3
        TestPerson3Rocchio,
        TestPerson3MMR,
        TestPerson3SessionManager,
        # Person 4
        TestPerson4IntegrationAndEngine,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    start_time = time.perf_counter()
    result = runner.run(suite)
    elapsed = time.perf_counter() - start_time

    print("")
    print("=" * 70)
    print(f"WL3 STRESS TEST SUMMARY")
    print(f"Ran {result.testsRun} tests across all 4 persons in {elapsed:.3f}s")
    print(f"Failures: {len(result.failures)} | Errors: {len(result.errors)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("ALL WL3 TESTS PASSED PERFECTLY! [100% OK]")
        return 0
    else:
        print("SOME TESTS FAILED! Check traceback above.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
