"""
Standalone test runner — no pytest required.
Run with:  python3 run_tests.py

Implements all tests from the 5 test files using Python's built-in
unittest framework.  Results match what pytest would report.
"""

import math
import sys
import unittest

# ---------------------------------------------------------------------------
# Make sure wl3 is importable from project root
# ---------------------------------------------------------------------------
import os
sys.path.insert(0, os.path.dirname(__file__))

from wl3.ranking.tfidf import TFIDFScorer
from wl3.ranking.bm25 import BM25Scorer
from wl3.ranking.vector import VectorScorer
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever, ScoredDocument


def approx(a, b, rel=1e-4, abs_=1e-9):
    """pytest.approx equivalent."""
    if abs(b) < 1e-10:
        return abs(a - b) <= abs_
    return abs(a - b) / max(abs(b), 1e-10) <= rel


# ===========================================================================
# TF-IDF Tests
# ===========================================================================

class TestTFIDFScorer(unittest.TestCase):

    def setUp(self):
        self.scorer = TFIDFScorer()
        self.doc_freq = {"machine": 3, "learning": 4, "data": 2, "neural": 2}
        self.doc0 = {"machine": 3, "learning": 4}
        self.doc1 = {"machine": 0, "learning": 1}
        self.doc7 = {"machine": 2, "learning": 3}

    def test_basic_scoring(self):
        score = self.scorer.score(self.doc0, self.doc_freq, 10, ["machine", "learning"])
        expected = 3 * math.log10(10/3) + 4 * math.log10(10/4)
        self.assertAlmostEqual(score, expected, places=4)

    def test_ordering(self):
        s0 = self.scorer.score(self.doc0, self.doc_freq, 10, ["machine", "learning"])
        s7 = self.scorer.score(self.doc7, self.doc_freq, 10, ["machine", "learning"])
        s1 = self.scorer.score(self.doc1, self.doc_freq, 10, ["machine", "learning"])
        self.assertGreater(s0, s7)
        self.assertGreater(s7, s1)

    def test_single_term_query(self):
        score = self.scorer.score(self.doc0, self.doc_freq, 10, ["machine"])
        self.assertAlmostEqual(score, 3 * math.log10(10/3), places=4)

    def test_zero_tf_contributes_zero(self):
        doc_tf = {"learning": 4}
        score = self.scorer.score(doc_tf, self.doc_freq, 10, ["machine", "learning"])
        expected = 4 * math.log10(10/4)
        self.assertAlmostEqual(score, expected, places=4)

    def test_term_in_all_docs_zero_idf(self):
        score = self.scorer.score({"common": 10}, {"common": 10}, 10, ["common"])
        self.assertAlmostEqual(score, 0.0, places=9)

    def test_rare_term_max_idf(self):
        score = self.scorer.score({"unique": 1}, {"unique": 1}, 10, ["unique"])
        self.assertAlmostEqual(score, math.log10(10), places=4)

    def test_empty_query_returns_zero(self):
        self.assertEqual(self.scorer.score(self.doc0, self.doc_freq, 10, []), 0.0)

    def test_empty_doc_tf_returns_zero(self):
        self.assertEqual(self.scorer.score({}, self.doc_freq, 10, ["machine"]), 0.0)

    def test_unknown_term_skipped(self):
        self.assertEqual(self.scorer.score({"ghost": 5}, {}, 10, ["ghost"]), 0.0)

    def test_non_negative_score(self):
        score = self.scorer.score(self.doc0, self.doc_freq, 10, ["machine", "learning"])
        self.assertGreaterEqual(score, 0.0)

    def test_total_docs_zero_returns_zero(self):
        self.assertEqual(self.scorer.score(self.doc0, self.doc_freq, 0, ["machine"]), 0.0)


# ===========================================================================
# BM25 Tests
# ===========================================================================

class TestBM25Scorer(unittest.TestCase):

    def setUp(self):
        self.scorer = BM25Scorer(k1=1.5, b=0.75)
        self.doc_freq = {"machine": 3, "learning": 4}
        self.doc0 = {"machine": 3, "learning": 4}
        self.N = 10
        self.avgdl = 45.0
        self.doc0_len = 16

    def test_basic_scoring(self):
        score = self.scorer.score(self.doc0, self.doc_freq, self.N,
                                   self.doc0_len, self.avgdl, ["machine", "learning"])
        self.assertAlmostEqual(score, 1.8013, places=2)

    def test_ordering(self):
        doc7 = {"machine": 2, "learning": 3}
        s0 = self.scorer.score(self.doc0, self.doc_freq, self.N, self.doc0_len, self.avgdl, ["machine", "learning"])
        s7 = self.scorer.score(doc7, self.doc_freq, self.N, self.doc0_len, self.avgdl, ["machine", "learning"])
        self.assertGreater(s0, s7)

    def test_short_doc_scores_higher(self):
        s_short = self.scorer.score(self.doc0, self.doc_freq, self.N, 16, self.avgdl, ["machine", "learning"])
        s_long = self.scorer.score(self.doc0, self.doc_freq, self.N, 100, self.avgdl, ["machine", "learning"])
        self.assertGreater(s_short, s_long)

    def test_b_zero_no_length_effect(self):
        sc = BM25Scorer(k1=1.5, b=0.0)
        s1 = sc.score(self.doc0, self.doc_freq, self.N, 16, self.avgdl, ["machine", "learning"])
        s2 = sc.score(self.doc0, self.doc_freq, self.N, 100, self.avgdl, ["machine", "learning"])
        self.assertAlmostEqual(s1, s2, places=6)

    def test_tf_saturation(self):
        sc = BM25Scorer(k1=1.5, b=0.0)
        s10 = sc.score({"machine": 10}, {"machine": 3}, self.N, 16, self.avgdl, ["machine"])
        s100 = sc.score({"machine": 100}, {"machine": 3}, self.N, 16, self.avgdl, ["machine"])
        self.assertLess(s100 / s10, 1.15)

    def test_empty_query_zero(self):
        self.assertEqual(self.scorer.score(self.doc0, self.doc_freq, self.N,
                                            self.doc0_len, self.avgdl, []), 0.0)

    def test_invalid_k1_raises(self):
        with self.assertRaises(ValueError):
            BM25Scorer(k1=-1.0)

    def test_invalid_b_raises(self):
        with self.assertRaises(ValueError):
            BM25Scorer(b=1.5)

    def test_non_negative_score(self):
        score = self.scorer.score(self.doc0, self.doc_freq, self.N,
                                   self.doc0_len, self.avgdl, ["machine", "learning"])
        self.assertGreaterEqual(score, 0.0)


# ===========================================================================
# Vector Tests
# ===========================================================================

class TestVectorScorer(unittest.TestCase):

    def setUp(self):
        self.scorer = VectorScorer()
        self.doc_freq = {
            "machine": 3, "learning": 4, "subset": 1, "artificial": 2,
            "intelligence": 2, "is": 5, "a": 6, "of": 5,
        }
        self.doc0_full = {
            "machine": 3, "learning": 4, "subset": 1, "artificial": 2,
            "intelligence": 2, "is": 2, "a": 1, "of": 1,
        }

    def test_identical_vector(self):
        # Build query_tf to exactly match doc0_full proportions.
        # We use build_tfidf_vector directly so both vectors are identical.
        vec = VectorScorer.build_tfidf_vector(self.doc0_full, self.doc_freq, 10)
        score = VectorScorer.cosine_similarity(vec, vec)
        self.assertAlmostEqual(score, 1.0, places=5)

    def test_orthogonal_vectors(self):
        score = self.scorer.score(["python"], {"java": 3}, {"python": 1, "java": 1}, 10)
        self.assertAlmostEqual(score, 0.0, places=9)

    def test_partial_overlap(self):
        score = self.scorer.score(["machine", "learning"], self.doc0_full, self.doc_freq, 10)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_result_in_range(self):
        score = self.scorer.score(["machine", "learning"], self.doc0_full, self.doc_freq, 10)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_empty_query_zero(self):
        self.assertEqual(self.scorer.score([], self.doc0_full, self.doc_freq, 10), 0.0)

    def test_empty_doc_zero(self):
        self.assertEqual(self.scorer.score(["machine"], {}, self.doc_freq, 10), 0.0)

    def test_build_tfidf_vector(self):
        vec = VectorScorer.build_tfidf_vector({"machine": 3}, {"machine": 3}, 10)
        expected = 3 * math.log10(10/3)
        self.assertAlmostEqual(vec["machine"], expected, places=4)

    def test_cosine_identical(self):
        v = {"a": 1.5, "b": 2.0}
        self.assertAlmostEqual(VectorScorer.cosine_similarity(v, v), 1.0, places=5)

    def test_cosine_orthogonal(self):
        va = {"apple": 1.0}
        vb = {"mango": 1.0}
        self.assertAlmostEqual(VectorScorer.cosine_similarity(va, vb), 0.0, places=9)

    def test_cosine_empty_zero(self):
        self.assertEqual(VectorScorer.cosine_similarity({}, {"a": 1.0}), 0.0)


# ===========================================================================
# Ranker Tests
# ===========================================================================

class TestRanker(unittest.TestCase):

    def setUp(self):
        self.ranker = Ranker()
        self.candidates = {0: {"machine": 3, "learning": 4},
                           4: {"machine": 1, "learning": 5},
                           7: {"machine": 2, "learning": 3},
                           1: {"machine": 0, "learning": 1}}
        self.doc_freq = {"machine": 3, "learning": 4}
        self.query = ["machine", "learning"]
        self.doc_lengths = {0: 16, 4: 18, 7: 14, 1: 20}
        self.doc_terms_full = {
            0: {"machine": 3, "learning": 4, "subset": 1, "artificial": 2,
                "intelligence": 2, "is": 2, "a": 1, "of": 1},
            4: {"deep": 3, "learning": 5, "uses": 1, "neural": 2, "networks": 2, "layers": 2, "machine": 1},
            7: {"reinforcement": 2, "learning": 3, "machine": 2, "type": 1},
            1: {"neural": 3, "networks": 2, "computing": 1, "learning": 1},
        }

    def test_tfidf_returns_all(self):
        s = self.ranker.rank(RankingMode.TFIDF, self.candidates, self.doc_freq, 10, self.query)
        self.assertEqual(set(s.keys()), {0, 4, 7, 1})

    def test_tfidf_ordering(self):
        s = self.ranker.rank(RankingMode.TFIDF, self.candidates, self.doc_freq, 10, self.query)
        self.assertGreater(s[0], s[7])
        self.assertGreater(s[7], s[1])

    def test_bm25_returns_all(self):
        s = self.ranker.rank(RankingMode.BM25, self.candidates, self.doc_freq, 10, self.query,
                              avg_doc_length=45.0, doc_lengths=self.doc_lengths)
        self.assertEqual(set(s.keys()), {0, 4, 7, 1})

    def test_bm25_missing_doc_lengths_raises(self):
        with self.assertRaises(ValueError):
            self.ranker.rank(RankingMode.BM25, self.candidates, self.doc_freq, 10, self.query,
                              avg_doc_length=45.0, doc_lengths=None)

    def test_vector_returns_all(self):
        s = self.ranker.rank(RankingMode.VECTOR, self.candidates, self.doc_freq, 10, self.query,
                              doc_terms_full=self.doc_terms_full)
        self.assertEqual(set(s.keys()), {0, 4, 7, 1})

    def test_vector_missing_full_terms_raises(self):
        with self.assertRaises(ValueError):
            self.ranker.rank(RankingMode.VECTOR, self.candidates, self.doc_freq, 10, self.query,
                              doc_terms_full=None)

    def test_empty_candidates(self):
        for mode in RankingMode:
            s = self.ranker.rank(mode, {}, self.doc_freq, 10, self.query,
                                  avg_doc_length=45.0, doc_lengths={}, doc_terms_full={})
            self.assertEqual(s, {})

    def test_enum_values(self):
        self.assertEqual(RankingMode.TFIDF.value, "tfidf")
        self.assertEqual(RankingMode.BM25.value, "bm25")
        self.assertEqual(RankingMode.VECTOR.value, "vector")

    def test_all_modes_non_negative(self):
        for mode in RankingMode:
            s = self.ranker.rank(mode, self.candidates, self.doc_freq, 10, self.query,
                                  avg_doc_length=45.0, doc_lengths=self.doc_lengths,
                                  doc_terms_full=self.doc_terms_full)
            for doc_id, score in s.items():
                self.assertGreaterEqual(score, 0.0, f"{mode} gave negative score for doc {doc_id}")


# ===========================================================================
# Top-K Tests
# ===========================================================================

class TestTopKRetriever(unittest.TestCase):

    def test_basic_top_k(self):
        scored = {0: 3.16, 4: 2.81, 7: 2.43, 1: 0.39, 2: 1.10}
        results = TopKRetriever.get_top_k(scored, k=3)
        self.assertEqual(len(results), 3)
        self.assertEqual([r.doc_id for r in results], [0, 4, 7])

    def test_sorted_descending(self):
        scored = {10: 1.0, 20: 5.0, 30: 3.0, 40: 2.0}
        results = TopKRetriever.get_top_k(scored, k=4)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_k_equals_n(self):
        scored = {0: 1.0, 1: 2.0, 2: 3.0}
        self.assertEqual(len(TopKRetriever.get_top_k(scored, k=3)), 3)

    def test_k_greater_than_n(self):
        self.assertEqual(len(TopKRetriever.get_top_k({0: 1.0, 1: 2.0}, k=100)), 2)

    def test_k_is_one(self):
        results = TopKRetriever.get_top_k({0: 1.5, 1: 3.0, 2: 0.8}, k=1)
        self.assertEqual(results[0].doc_id, 1)

    def test_k_zero_empty(self):
        self.assertEqual(TopKRetriever.get_top_k({0: 1.0}, k=0), [])

    def test_empty_input_empty(self):
        self.assertEqual(TopKRetriever.get_top_k({}, k=5), [])

    def test_tie_by_doc_id(self):
        results = TopKRetriever.get_top_k({5: 2.0, 1: 2.0, 3: 2.0}, k=2)
        self.assertEqual([r.doc_id for r in results], [1, 3])

    def test_negative_scores(self):
        results = TopKRetriever.get_top_k({0: -1.0, 1: -3.0, 2: -0.5}, k=2)
        self.assertEqual([r.doc_id for r in results], [2, 0])

    def test_returns_scored_document(self):
        results = TopKRetriever.get_top_k({42: 7.77}, k=1)
        self.assertIsInstance(results[0], ScoredDocument)
        self.assertEqual(results[0].doc_id, 42)
        self.assertAlmostEqual(results[0].score, 7.77)

    def test_mmr_pool_size(self):
        scored = {i: float(i) for i in range(50)}
        pool = TopKRetriever.get_top_k_for_mmr(scored, pool_size=20)
        self.assertEqual(len(pool), 20)

    def test_mmr_default_pool_20(self):
        scored = {i: float(i) for i in range(100)}
        self.assertEqual(len(TopKRetriever.get_top_k_for_mmr(scored)), 20)

    def test_mmr_sorted_descending(self):
        scored = {i: float(100 - i) for i in range(30)}
        pool = TopKRetriever.get_top_k_for_mmr(scored, pool_size=10)
        sc = [r.score for r in pool]
        self.assertEqual(sc, sorted(sc, reverse=True))


# ===========================================================================
# Integration Tests
# ===========================================================================

class TestIntegration(unittest.TestCase):

    def setUp(self):
        self.ranker = Ranker()
        self.candidates = {0: {"machine": 3, "learning": 4},
                           4: {"machine": 1, "learning": 5},
                           7: {"machine": 2, "learning": 3},
                           1: {"machine": 0, "learning": 1}}
        self.doc_freq = {"machine": 3, "learning": 4}
        self.query_terms = ["machine", "learning"]
        self.N = 10
        self.avgdl = 45.0
        self.doc_terms_full = {
            0: {"machine": 3, "learning": 4, "subset": 1, "artificial": 2,
                "intelligence": 2, "is": 2, "a": 1, "of": 1},
            4: {"deep": 3, "learning": 5, "uses": 1, "neural": 2,
                "networks": 2, "layers": 2, "machine": 1},
            7: {"reinforcement": 2, "learning": 3, "machine": 2, "type": 1},
            1: {"neural": 3, "networks": 2, "computing": 1, "learning": 1},
        }
        self.doc_lengths = {did: sum(t.values()) for did, t in self.doc_terms_full.items()}

    def test_tfidf_top3(self):
        scores = self.ranker.rank(RankingMode.TFIDF, self.candidates, self.doc_freq, self.N, self.query_terms)
        top3_ids = {r.doc_id for r in TopKRetriever.get_top_k(scores, k=3)}
        self.assertEqual(top3_ids, {0, 4, 7})

    def test_bm25_full_pipeline(self):
        scores = self.ranker.rank(RankingMode.BM25, self.candidates, self.doc_freq, self.N,
                                   self.query_terms, avg_doc_length=self.avgdl,
                                   doc_lengths=self.doc_lengths)
        results = TopKRetriever.get_top_k(scores, k=4)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r.score >= 0 for r in results))

    def test_vector_scores_in_range(self):
        scores = self.ranker.rank(RankingMode.VECTOR, self.candidates, self.doc_freq, self.N,
                                   self.query_terms, doc_terms_full=self.doc_terms_full)
        for did, s in scores.items():
            self.assertGreaterEqual(s, 0.0, f"doc {did} cosine < 0")
            self.assertLessEqual(s, 1.0, f"doc {did} cosine > 1")

    def test_all_modes_same_doc_set(self):
        s_tf = self.ranker.rank(RankingMode.TFIDF, self.candidates, self.doc_freq, self.N, self.query_terms)
        s_bm = self.ranker.rank(RankingMode.BM25, self.candidates, self.doc_freq, self.N, self.query_terms,
                                 avg_doc_length=self.avgdl, doc_lengths=self.doc_lengths)
        s_vc = self.ranker.rank(RankingMode.VECTOR, self.candidates, self.doc_freq, self.N, self.query_terms,
                                 doc_terms_full=self.doc_terms_full)
        self.assertEqual(set(s_tf.keys()), set(s_bm.keys()))
        self.assertEqual(set(s_tf.keys()), set(s_vc.keys()))

    def test_mmr_pool_superset_of_top5(self):
        big = {i: {"machine": i % 5 + 1, "learning": i % 4 + 1} for i in range(30)}
        big_df = {"machine": 15, "learning": 20}
        scores = self.ranker.rank(RankingMode.TFIDF, big, big_df, 30, self.query_terms)
        pool = TopKRetriever.get_top_k_for_mmr(scores, pool_size=20)
        top5 = TopKRetriever.get_top_k(scores, k=5)
        pool_ids = {r.doc_id for r in pool}
        top5_ids = {r.doc_id for r in top5}
        self.assertTrue(top5_ids.issubset(pool_ids))


# ===========================================================================
# Main runner
# ===========================================================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestTFIDFScorer,
        TestBM25Scorer,
        TestVectorScorer,
        TestRanker,
        TestTopKRetriever,
        TestIntegration,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} tests passed", end="")
    if failed:
        print(f", {failed} FAILED ❌")
    else:
        print(" ✅")
    print(f"{'='*60}")

    sys.exit(0 if result.wasSuccessful() else 1)
