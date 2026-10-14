"""Tests for the end-to-end evaluator (engine_evaluator) and the synthetic corpus."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from wl3.engine import QueryEngine
from wl3.evaluation.engine_evaluator import Evaluator, format_report, save_report
from wl3.evaluation.synthetic_corpus import build_synthetic_corpus, load_queries
from wl3.integration.mock_worklet2 import InMemoryWorklet2
from wl3.integration.worklet2_adapter import Worklet2Adapter


class TestSyntheticCorpus(unittest.TestCase):
    def test_size_and_determinism(self):
        docs, queries = build_synthetic_corpus()
        self.assertEqual((len(docs), len(queries)), (240, 40))
        self.assertEqual(build_synthetic_corpus()[0][5], docs[5])

    def test_labels_are_valid_doc_ids(self):
        docs, queries = build_synthetic_corpus()
        ids = {d["id"] for d in docs}
        for q in queries:
            self.assertTrue(q["relevant_docs"])
            self.assertTrue(set(q["relevant_docs"]) <= ids)

    def test_load_queries_roundtrip(self):
        _, queries = build_synthetic_corpus()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = os.path.join(tmp, "q.json")
            with open(path, "w") as fh:
                json.dump(queries, fh)
            self.assertEqual(load_queries(path), queries)


class TestEvaluator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs, queries = build_synthetic_corpus()
        adapter = Worklet2Adapter(InMemoryWorklet2(docs))
        evaluator = Evaluator(
            lambda db: QueryEngine(adapter, cache_db_path=db),
            queries[:6], repeats=1, concurrent_sessions=3,
        )
        cls.report = evaluator.run()

    def test_all_modes_reported(self):
        self.assertEqual(set(self.report["modes"]), {"tfidf", "bm25", "vector"})

    def test_quality_metrics_present_and_bounded(self):
        for data in self.report["modes"].values():
            q = data["quality"]
            self.assertEqual({"P@5", "P@10", "R@5", "R@10", "MRR"} <= set(q), True)
            self.assertTrue(all(0.0 <= v <= 1.0 for v in q.values()))
            self.assertGreater(q["P@5"], 0.5)           # synthetic set is easy

    def test_four_latency_categories_measured(self):
        for data in self.report["modes"].values():
            lat = data["latency"]
            self.assertEqual(set(lat), {"cache_miss", "cache_hit", "cold_start", "concurrent"})
            for entry in lat.values():
                self.assertGreater(entry["n"], 0)
            self.assertLess(lat["cache_hit"]["mean_ms"], lat["cache_miss"]["mean_ms"])

    def test_cold_start_served_from_disk(self):
        for data in self.report["modes"].values():
            self.assertEqual(data["latency"]["cold_start"]["served_from_disk"], 6)

    def test_concurrent_access_is_consistent(self):
        for data in self.report["modes"].values():
            c = data["latency"]["concurrent"]
            self.assertEqual(c["inconsistent_results"], 0)
            self.assertLessEqual(c["cache_entries"], c["cache_capacity"])

    def test_heap_benchmark_present(self):
        self.assertIn("heap_ms", self.report["top_k_benchmark"])

    def test_report_formatting_and_saving(self):
        text = format_report(self.report)
        for token in ("P@5", "MRR", "Cache miss", "SQLite cold start", "Top-K benchmark"):
            self.assertIn(token, text)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            save_report(self.report, os.path.join(tmp, "r.json"), os.path.join(tmp, "r.txt"))
            self.assertTrue(os.path.exists(os.path.join(tmp, "r.txt")))


if __name__ == "__main__":
    unittest.main()
