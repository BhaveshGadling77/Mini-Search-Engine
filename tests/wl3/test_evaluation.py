"""
Unit tests for wl3/evaluation/metrics.py and wl3/evaluation/dataset.py
========================================================================
Tests all metric functions with hand-calculated expected values.

Reference example (used across multiple tests)
-----------------------------------------------
    retrieved    = [7, 0, 4, 1, 12, 23, 5, 8, 3, 2]   (10 results)
    relevant_ids = {0, 4, 7, 12, 23}                    (5 relevant docs)

    Top-5:  [7, 0, 4, 1, 12]  → 4 relevant → P@5 = 4/5 = 0.8
    Top-10: [7,0,4,1,12,23,5,8,3,2] → 5 relevant → P@10 = 5/10 = 0.5

    Recall@5 = 4/5 = 0.8   (4 of 5 relevant found)
    Recall@10 = 5/5 = 1.0  (all 5 relevant found)

    First relevant at rank 1 (doc 7) → RR = 1/1 = 1.0

    AP = (1/1 + 2/2 + 3/3 + 0 + 4/5 + 5/6) / 5
       = (1.0 + 1.0 + 1.0 + 0.8 + 0.8333) / 5
       = 4.6333 / 5 ≈ 0.9267
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from wl3.evaluation.metrics import (
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
    average_precision,
    evaluate_ranking,
    aggregate_metrics,
)
from wl3.evaluation.dataset import get_queries, get_query_by_text


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RETRIEVED = [7, 0, 4, 1, 12, 23, 5, 8, 3, 2]
RELEVANT = {0, 4, 7, 12, 23}


# ---------------------------------------------------------------------------
# Precision@k Tests
# ---------------------------------------------------------------------------

class TestPrecisionAtK(unittest.TestCase):

    def test_precision_at_5(self):
        """Hand-calculated: top-5 = [7,0,4,1,12] → 4 hits → 4/5 = 0.8."""
        self.assertAlmostEqual(precision_at_k(RETRIEVED, RELEVANT, 5), 0.8, places=6)

    def test_precision_at_10(self):
        """Hand-calculated: top-10 has 5 hits → 5/10 = 0.5."""
        self.assertAlmostEqual(precision_at_k(RETRIEVED, RELEVANT, 10), 0.5, places=6)

    def test_precision_at_1_relevant(self):
        """First result is relevant → P@1 = 1.0."""
        self.assertAlmostEqual(precision_at_k(RETRIEVED, RELEVANT, 1), 1.0, places=6)

    def test_precision_at_1_irrelevant(self):
        """First result is irrelevant."""
        retrieved = [99, 0, 4]
        self.assertAlmostEqual(precision_at_k(retrieved, RELEVANT, 1), 0.0, places=6)

    def test_precision_k_zero(self):
        """k=0 → 0.0."""
        self.assertEqual(precision_at_k(RETRIEVED, RELEVANT, 0), 0.0)

    def test_precision_k_negative(self):
        """k<0 → 0.0."""
        self.assertEqual(precision_at_k(RETRIEVED, RELEVANT, -1), 0.0)

    def test_precision_empty_retrieved(self):
        self.assertEqual(precision_at_k([], RELEVANT, 5), 0.0)

    def test_precision_empty_relevant(self):
        self.assertEqual(precision_at_k(RETRIEVED, set(), 5), 0.0)

    def test_precision_k_larger_than_results(self):
        """k=50 but only 10 results → use all 10."""
        result = precision_at_k(RETRIEVED, RELEVANT, 50)
        # 5 relevant in 50 positions → 5/50 = 0.1
        self.assertAlmostEqual(result, 0.1, places=6)

    def test_precision_perfect(self):
        """All top-k results relevant → P@k = 1.0."""
        retrieved = list(RELEVANT)
        self.assertAlmostEqual(precision_at_k(retrieved, RELEVANT, 5), 1.0, places=6)

    def test_precision_no_relevant_in_top_k(self):
        """No relevant docs in top-5."""
        retrieved = [99, 98, 97, 96, 95, 0, 4, 7]
        self.assertAlmostEqual(precision_at_k(retrieved, RELEVANT, 5), 0.0, places=6)


# ---------------------------------------------------------------------------
# Recall@k Tests
# ---------------------------------------------------------------------------

class TestRecallAtK(unittest.TestCase):

    def test_recall_at_5(self):
        """4 of 5 relevant in top-5 → 0.8."""
        self.assertAlmostEqual(recall_at_k(RETRIEVED, RELEVANT, 5), 0.8, places=6)

    def test_recall_at_10(self):
        """All 5 relevant in top-10 → 1.0."""
        self.assertAlmostEqual(recall_at_k(RETRIEVED, RELEVANT, 10), 1.0, places=6)

    def test_recall_zero(self):
        """No relevant docs in list."""
        self.assertAlmostEqual(recall_at_k([99, 98, 97], RELEVANT, 3), 0.0, places=6)

    def test_recall_k_zero(self):
        self.assertEqual(recall_at_k(RETRIEVED, RELEVANT, 0), 0.0)

    def test_recall_empty_relevant(self):
        self.assertEqual(recall_at_k(RETRIEVED, set(), 5), 0.0)

    def test_recall_perfect_small(self):
        """All relevant docs retrieved at top-3."""
        rel = {1, 2, 3}
        retrieved = [1, 2, 3, 99, 98]
        self.assertAlmostEqual(recall_at_k(retrieved, rel, 3), 1.0, places=6)


# ---------------------------------------------------------------------------
# Reciprocal Rank Tests
# ---------------------------------------------------------------------------

class TestReciprocalRank(unittest.TestCase):

    def test_first_result_relevant(self):
        """First result relevant → RR = 1.0."""
        self.assertAlmostEqual(reciprocal_rank(RETRIEVED, RELEVANT), 1.0, places=6)

    def test_second_result_first_relevant(self):
        """First result irrelevant, second relevant → RR = 1/2."""
        retrieved = [99, 0, 4]
        rr = reciprocal_rank(retrieved, RELEVANT)
        self.assertAlmostEqual(rr, 0.5, places=6)

    def test_no_relevant_in_list(self):
        """No relevant docs → RR = 0.0."""
        self.assertAlmostEqual(reciprocal_rank([99, 98, 97], RELEVANT), 0.0, places=6)

    def test_fifth_position(self):
        """First relevant at rank 5 → RR = 0.2."""
        retrieved = [99, 98, 97, 96, 7]
        self.assertAlmostEqual(reciprocal_rank(retrieved, RELEVANT), 0.2, places=6)

    def test_empty_retrieved(self):
        self.assertAlmostEqual(reciprocal_rank([], RELEVANT), 0.0, places=6)


# ---------------------------------------------------------------------------
# MRR Tests
# ---------------------------------------------------------------------------

class TestMRR(unittest.TestCase):

    def test_basic_mrr(self):
        """MRR = mean of [1.0, 0.5, 1/3]."""
        results_list = [
            [7, 99, 98],    # first relevant at rank 1 → RR=1.0
            [99, 0, 98],    # first relevant at rank 2 → RR=0.5
            [99, 98, 4],    # first relevant at rank 3 → RR=0.333...
        ]
        relevant_list = [
            {7}, {0}, {4},
        ]
        mrr = mean_reciprocal_rank(results_list, relevant_list)
        expected = (1.0 + 0.5 + 1/3) / 3
        self.assertAlmostEqual(mrr, expected, places=5)

    def test_all_first_relevant(self):
        """All queries find relevant at rank 1 → MRR = 1.0."""
        results_list = [[1], [2], [3]]
        relevant_list = [{1}, {2}, {3}]
        self.assertAlmostEqual(mean_reciprocal_rank(results_list, relevant_list), 1.0, places=6)

    def test_empty_inputs(self):
        self.assertEqual(mean_reciprocal_rank([], []), 0.0)

    def test_mismatched_lengths(self):
        """Mismatched input lengths → 0.0."""
        self.assertEqual(mean_reciprocal_rank([[1, 2]], [{1}, {2}]), 0.0)


# ---------------------------------------------------------------------------
# Average Precision Tests
# ---------------------------------------------------------------------------

class TestAveragePrecision(unittest.TestCase):

    def test_ap_hand_calculated(self):
        """
        retrieved = [7, 0, 4, 1, 12, 23, 5, 8, 3, 2]
        relevant  = {0, 4, 7, 12, 23}

        Ranks of relevant: 1,2,3,5,6
        Cumulative P@rank: 1/1, 2/2, 3/3, 4/5, 5/6
        = 1.0, 1.0, 1.0, 0.8, 0.8333
        AP = (1+1+1+0.8+0.8333) / 5 = 4.6333/5 ≈ 0.9267
        """
        ap = average_precision(RETRIEVED, RELEVANT)
        self.assertAlmostEqual(ap, (1.0 + 1.0 + 1.0 + 0.8 + 5/6) / 5, places=5)

    def test_ap_perfect(self):
        """Perfect ranking → AP = 1.0."""
        retrieved = [7, 0, 4, 12, 23, 99, 98]
        ap = average_precision(retrieved, RELEVANT)
        self.assertAlmostEqual(ap, 1.0, places=6)

    def test_ap_no_relevant(self):
        """No relevant docs → AP = 0.0."""
        self.assertAlmostEqual(average_precision(RETRIEVED, set()), 0.0, places=6)

    def test_ap_empty_retrieved(self):
        self.assertAlmostEqual(average_precision([], RELEVANT), 0.0, places=6)

    def test_ap_last_position_only(self):
        """Only one relevant doc, at last position."""
        retrieved = [99, 98, 97, 96, 7]
        ap = average_precision(retrieved, {7})
        self.assertAlmostEqual(ap, 1/5, places=6)


# ---------------------------------------------------------------------------
# evaluate_ranking Tests
# ---------------------------------------------------------------------------

class TestEvaluateRanking(unittest.TestCase):

    def test_returns_all_keys(self):
        """evaluate_ranking returns precision@5, recall@5, precision@10, recall@10, rr, ap."""
        report = evaluate_ranking(RETRIEVED, RELEVANT, ks=[5, 10])
        for key in ["precision@5", "recall@5", "precision@10", "recall@10", "rr", "ap"]:
            self.assertIn(key, report, f"Missing key: {key}")

    def test_values_match_individual_functions(self):
        """Values must match individually computed metrics."""
        report = evaluate_ranking(RETRIEVED, RELEVANT, ks=[5, 10])
        self.assertAlmostEqual(report["precision@5"], precision_at_k(RETRIEVED, RELEVANT, 5), places=8)
        self.assertAlmostEqual(report["recall@10"], recall_at_k(RETRIEVED, RELEVANT, 10), places=8)
        self.assertAlmostEqual(report["rr"], reciprocal_rank(RETRIEVED, RELEVANT), places=8)

    def test_custom_ks(self):
        """Custom k values produce corresponding keys."""
        report = evaluate_ranking(RETRIEVED, RELEVANT, ks=[3, 7])
        self.assertIn("precision@3", report)
        self.assertIn("recall@7", report)
        self.assertNotIn("precision@5", report)

    def test_all_values_in_valid_range(self):
        """All metric values must be in [0.0, 1.0]."""
        report = evaluate_ranking(RETRIEVED, RELEVANT, ks=[5, 10])
        for key, val in report.items():
            self.assertGreaterEqual(val, 0.0, f"{key}={val} < 0")
            self.assertLessEqual(val, 1.0, f"{key}={val} > 1")

    def test_empty_retrieved(self):
        """Empty retrieved → all zeros."""
        report = evaluate_ranking([], RELEVANT, ks=[5, 10])
        for val in report.values():
            self.assertAlmostEqual(val, 0.0, places=9)


# ---------------------------------------------------------------------------
# aggregate_metrics Tests
# ---------------------------------------------------------------------------

class TestAggregateMetrics(unittest.TestCase):

    def test_mean_of_two_reports(self):
        """Mean of two reports."""
        r1 = {"precision@5": 0.8, "recall@5": 0.6, "rr": 1.0, "ap": 0.9}
        r2 = {"precision@5": 0.4, "recall@5": 0.2, "rr": 0.5, "ap": 0.3}
        agg = aggregate_metrics([r1, r2])
        self.assertAlmostEqual(agg["precision@5"], 0.6, places=6)
        self.assertAlmostEqual(agg["recall@5"], 0.4, places=6)
        self.assertAlmostEqual(agg["mrr"], 0.75, places=6)  # mean of RR = alias

    def test_mrr_alias(self):
        """mrr key is always added as alias of rr."""
        r = {"rr": 0.75, "precision@5": 0.5}
        agg = aggregate_metrics([r])
        self.assertIn("mrr", agg)
        self.assertAlmostEqual(agg["mrr"], 0.75, places=6)

    def test_empty_input(self):
        """Empty list → empty dict."""
        self.assertEqual(aggregate_metrics([]), {})

    def test_single_report_passthrough(self):
        """Single report → values unchanged (mean of one)."""
        r = {"precision@5": 0.72, "rr": 0.89}
        agg = aggregate_metrics([r])
        self.assertAlmostEqual(agg["precision@5"], 0.72, places=6)


# ---------------------------------------------------------------------------
# Dataset Tests
# ---------------------------------------------------------------------------

class TestDataset(unittest.TestCase):

    def test_get_queries_returns_list(self):
        queries = get_queries()
        self.assertIsInstance(queries, list)

    def test_at_least_30_queries(self):
        """SRS requires ~30–50 labelled queries."""
        queries = get_queries()
        self.assertGreaterEqual(len(queries), 30, f"Only {len(queries)} queries — need ≥ 30")

    def test_each_entry_has_required_keys(self):
        for entry in get_queries():
            self.assertIn("query", entry, f"Missing 'query' in {entry}")
            self.assertIn("relevant_docs", entry, f"Missing 'relevant_docs' in {entry}")
            self.assertIsInstance(entry["query"], str)
            self.assertIsInstance(entry["relevant_docs"], list)
            self.assertGreater(len(entry["query"]), 0, "Empty query string")
            self.assertGreater(len(entry["relevant_docs"]), 0, "Empty relevant_docs list")

    def test_get_query_by_text_found(self):
        entry = get_query_by_text("machine learning")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["query"], "machine learning")

    def test_get_query_by_text_case_insensitive(self):
        entry = get_query_by_text("MACHINE LEARNING")
        self.assertIsNotNone(entry)

    def test_get_query_by_text_not_found(self):
        self.assertIsNone(get_query_by_text("xyzzy this query does not exist"))

    def test_no_duplicate_queries(self):
        queries = [e["query"].lower() for e in get_queries()]
        self.assertEqual(len(queries), len(set(queries)), "Duplicate queries found")

    def test_relevant_docs_are_integers(self):
        for entry in get_queries():
            for doc_id in entry["relevant_docs"]:
                self.assertIsInstance(doc_id, int, f"Non-int doc_id: {doc_id}")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
