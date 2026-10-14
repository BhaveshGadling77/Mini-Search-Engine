"""QueryEngine tests: pipeline, cache, persistence, feedback, MMR, threads."""

import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from wl3.engine import QueryEngine, RankedResult, parse_ranking_mode
from wl3.integration.mock_worklet2 import InMemoryWorklet2
from wl3.integration.worklet2_adapter import Worklet2Adapter
from wl3.ranking.ranker import RankingMode

DOCS = [
    {"id": 0, "title": "ML intro", "url": "u0", "text": "machine learning machine learning models data"},
    {"id": 1, "title": "ML deep", "url": "u1", "text": "machine learning neural networks neural networks layers"},
    {"id": 2, "title": "Databases", "url": "u2", "text": "database index query storage table"},
    {"id": 3, "title": "Neural", "url": "u3", "text": "neural networks backpropagation layers neural activation"},
    {"id": 4, "title": "Cooking", "url": "u4", "text": "recipe cooking pasta sauce kitchen"},
    {"id": 5, "title": "Learning", "url": "u5", "text": "learning theory learning students school"},
]


class CountingBackend(InMemoryWorklet2):
    """InMemoryWorklet2 that counts calls, to prove cache hits skip W2."""

    def __init__(self, docs):
        super().__init__(docs)
        self.resolve_calls = 0

    def resolve_query(self, query_string):
        self.resolve_calls += 1
        return super().resolve_query(query_string)


class EngineTestBase(unittest.TestCase):
    docs = DOCS

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = os.path.join(self._tmp.name, "cache.db")
        self.backend = CountingBackend(self.docs)
        self.adapter = Worklet2Adapter(self.backend)
        self.engine = QueryEngine(self.adapter, cache_db_path=self.db)

    def tearDown(self):
        self._tmp.cleanup()


class TestPipeline(EngineTestBase):
    def test_returns_ranked_results_for_every_mode(self):
        for mode in ("tfidf", "bm25", "vector"):
            results = self.engine.search("machine learning", None, mode, 3)
            self.assertTrue(results)
            self.assertTrue(all(isinstance(r, RankedResult) for r in results))
            scores = [r.score for r in results]
            self.assertEqual(scores, sorted(scores, reverse=True))
            self.assertEqual([r.rank for r in results], list(range(1, len(results) + 1)))
            self.assertEqual(results[0].doc_id in (0, 1), True)

    def test_result_fields_populated(self):
        r = self.engine.search("database", None, "bm25", 1)[0]
        self.assertEqual((r.doc_id, r.title, r.url), (2, "Databases", "u2"))
        self.assertIn("database", r.snippet.lower())

    def test_k_larger_than_matches_returns_all_matches(self):
        self.assertEqual(len(self.engine.search("machine", None, "tfidf", 50)), 2)

    def test_k_limits_results(self):
        self.assertEqual(len(self.engine.search("learning", None, "tfidf", 2)), 2)

    def test_invalid_k_and_empty_query(self):
        self.assertEqual(self.engine.search("learning", None, "bm25", 0), [])
        self.assertEqual(self.engine.search("learning", None, "bm25", -3), [])
        self.assertEqual(self.engine.search("   ", None, "bm25", 5), [])
        self.assertEqual(self.engine.search("AND OR", None, "bm25", 5), [])

    def test_no_match_returns_empty_list(self):
        self.assertEqual(self.engine.search("zzzzqqq", None, "bm25", 5), [])

    def test_mode_parsing(self):
        self.assertIs(parse_ranking_mode("TF-IDF"), RankingMode.TFIDF)
        self.assertIs(parse_ranking_mode("Vector/Cosine"), RankingMode.VECTOR)
        with self.assertRaises(ValueError):
            self.engine.search("learning", None, "pagerank", 3)

    def test_boolean_query_passes_through_to_w2(self):
        ids = {r.doc_id for r in self.engine.search("machine AND neural", None, "bm25", 10)}
        self.assertEqual(ids, {1})


class TestCache(EngineTestBase):
    def test_repeat_query_is_cache_hit_and_skips_w2(self):
        first = self.engine.search("machine learning", None, "bm25", 3)
        calls = self.backend.resolve_calls
        second = self.engine.search("machine learning", None, "bm25", 3)
        self.assertEqual(self.backend.resolve_calls, calls)
        self.assertEqual(self.engine.cache_hits, 1)
        self.assertEqual(first, second)

    def test_equivalent_query_text_shares_entry(self):
        self.engine.search("Machine   Learning", None, "bm25", 3)
        self.engine.search("machine learning", None, "bm25", 3)
        self.assertEqual(self.engine.cache_hits, 1)

    def test_config_changes_do_not_collide(self):
        self.engine.search("machine learning", None, "bm25", 3)
        self.engine.search("machine learning", None, "tfidf", 3)
        self.engine.search("machine learning", None, "bm25", 2)
        self.engine.search("machine learning", None, "bm25", 3, True)
        self.assertEqual(self.engine.cache_hits, 0)
        self.assertEqual(self.engine.stats()["cache_entries"], 4)

    def test_cached_result_equals_fresh_computation(self):
        fresh = self.engine.search("neural networks", None, "vector", 4)
        self.engine.clear_cache()
        again = self.engine.search("neural networks", None, "vector", 4)
        self.assertEqual(fresh, again)

    def test_cold_start_restores_from_sqlite(self):
        expected = self.engine.search("machine learning", None, "bm25", 3)
        restarted = QueryEngine(Worklet2Adapter(self.backend), cache_db_path=self.db)
        calls = self.backend.resolve_calls
        got = restarted.search("machine learning", None, "bm25", 3)
        self.assertEqual(self.backend.resolve_calls, calls)      # served from disk
        self.assertEqual(restarted.cache_hits, 1)
        self.assertEqual(got, expected)

    def test_stale_index_version_not_served(self):
        self.engine.search("machine learning", None, "bm25", 3)
        changed = CountingBackend(self.docs + [
            {"id": 6, "title": "New", "url": "u6", "text": "machine learning brand new document"}])
        engine2 = QueryEngine(Worklet2Adapter(changed), cache_db_path=self.db)
        engine2.search("machine learning", None, "bm25", 3)
        self.assertEqual(engine2.cache_hits, 0)
        self.assertEqual(changed.resolve_calls, 1)

    def test_corrupt_database_does_not_crash(self):
        with open(self.db, "wb") as fh:
            fh.write(b"this is not a sqlite database" * 50)
        engine = QueryEngine(self.adapter, cache_db_path=self.db)
        self.assertTrue(engine.search("machine learning", None, "bm25", 3))

    def test_cache_can_be_disabled(self):
        engine = QueryEngine(self.adapter, cache_db_path=None)
        engine.search("machine", None, "bm25", 3)
        engine.search("machine", None, "bm25", 3)
        self.assertEqual(engine.cache_hits, 0)

    def test_empty_result_is_cached_safely(self):
        self.assertEqual(self.engine.search("zzzz", None, "bm25", 3), [])
        self.assertEqual(self.engine.search("zzzz", None, "bm25", 3), [])
        self.assertEqual(self.engine.cache_hits, 1)


class TestFeedback(EngineTestBase):
    def test_no_feedback_matches_anonymous_ranking(self):
        a = self.engine.search("learning", None, "bm25", 5)
        self.engine.clear_cache()
        b = self.engine.search("learning", "sessionX", "bm25", 5)
        self.assertEqual([r.doc_id for r in a], [r.doc_id for r in b])

    def test_feedback_changes_ranking_for_that_session_only(self):
        base = [r.doc_id for r in self.engine.search("learning", "A", "tfidf", 5)]
        self.assertTrue(self.engine.mark_relevant("A", 1))       # neural networks doc
        boosted = [r.doc_id for r in self.engine.search("learning", "A", "tfidf", 5)]
        other = [r.doc_id for r in self.engine.search("learning", "B", "tfidf", 5)]
        self.assertEqual(other, base)
        self.assertNotEqual(boosted, base)
        self.assertEqual(boosted[0], 1)

    def test_personalised_search_bypasses_shared_cache(self):
        self.engine.search("learning", "A", "bm25", 5)           # cached (no feedback yet)
        entries = self.engine.stats()["cache_entries"]
        hits = self.engine.cache_hits
        self.engine.mark_relevant("A", 1)
        self.engine.search("learning", "A", "bm25", 5)
        self.engine.search("learning", "A", "bm25", 5)
        self.assertEqual(self.engine.cache_hits, hits)           # never served from cache
        self.assertEqual(self.engine.stats()["cache_entries"], entries)  # never stored

    def test_other_session_still_uses_shared_cache(self):
        self.engine.search("learning", "B", "bm25", 5)
        self.engine.mark_relevant("A", 1)
        self.engine.search("learning", "B", "bm25", 5)
        self.assertEqual(self.engine.cache_hits, 1)

    def test_reset_feedback_restores_normal_ranking(self):
        base = [r.doc_id for r in self.engine.search("learning", "A", "tfidf", 5)]
        self.engine.mark_relevant("A", 1)
        self.engine.reset_feedback("A")
        again = [r.doc_id for r in self.engine.search("learning", "A", "tfidf", 5)]
        self.assertEqual(again, base)

    def test_unknown_document_feedback_rejected(self):
        self.assertFalse(self.engine.mark_relevant("A", 9999))
        with self.assertRaises(ValueError):
            self.engine.mark_relevant("", 1)

    def test_feedback_works_with_every_mode_and_mmr(self):
        self.engine.mark_relevant("A", 1)
        for mode in ("tfidf", "bm25", "vector"):
            for mmr in (False, True):
                self.assertTrue(self.engine.search("learning", "A", mode, 3, mmr))


class TestMMR(unittest.TestCase):
    def setUp(self):
        docs = []
        for i in range(4):  # four near-identical "python" docs
            docs.append({"id": i, "title": f"dup{i}", "url": "", "text": "python snake python reptile habitat python"})
        docs.append({"id": 4, "title": "lang", "url": "", "text": "python programming language code python software"})
        docs.append({"id": 5, "title": "comedy", "url": "", "text": "python comedy troupe sketch python show"})
        for i in range(6, 12):
            docs.append({"id": i, "title": f"x{i}", "url": "", "text": f"unrelated filler word{i} text"})
        self.engine = QueryEngine(Worklet2Adapter(InMemoryWorklet2(docs)), cache_db_path=None,
                                  mmr_lambda=0.5)

    def test_mmr_returns_k_unique_docs_in_descending_score_order(self):
        res = self.engine.search("python", None, "bm25", 3, True)
        self.assertEqual(len(res), 3)
        self.assertEqual(len({r.doc_id for r in res}), 3)
        self.assertEqual([r.score for r in res], sorted([r.score for r in res], reverse=True))

    def test_mmr_reduces_near_duplicates(self):
        plain = {r.doc_id for r in self.engine.search("python", None, "bm25", 3, False)}
        diverse = {r.doc_id for r in self.engine.search("python", None, "bm25", 3, True)}
        dup_ids = {0, 1, 2, 3}
        self.assertLess(len(diverse & dup_ids), len(plain & dup_ids))

    def test_mmr_result_scores_are_relevance_scores(self):
        """MMR picks the documents; the reported score is still the BM25 score."""
        plain = {r.doc_id: r.score for r in self.engine.search("python", None, "bm25", 20, False)}
        for r in self.engine.search("python", None, "bm25", 3, True):
            self.assertAlmostEqual(r.score, plain[r.doc_id])


class TestConcurrency(EngineTestBase):
    def test_threads_get_consistent_results(self):
        queries = ["machine learning", "neural networks", "database", "learning", "cooking"]
        expected = {q: self.engine.search(q, None, "bm25", 3) for q in queries}
        self.engine.clear_cache()
        errors = []

        def worker(n):
            try:
                for i in range(40):
                    q = queries[(n + i) % len(queries)]
                    if self.engine.search(q, f"s{n}", "bm25", 3) != expected[q]:
                        errors.append(q)
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
