"""Tests for the W2 adapter, the in-memory W2, the CLI and the Flask app."""

import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from wl3.cli.main import format_results, main as cli_main
from wl3.engine import QueryEngine, RankedResult
from wl3.engine.text import highlight, make_snippet, tokenize_query
from wl3.integration import Worklet2Adapter, Worklet2Error, create_adapter, load_backend
from wl3.integration.mock_worklet2 import InMemoryWorklet2
from wl3.web.app import create_app

DOCS = [
    {"id": 0, "title": "A", "url": "ua", "text": "apple banana cherry apple"},
    {"id": 1, "title": "B", "url": "ub", "text": "banana cherry date"},
    {"id": 2, "title": "C", "url": "uc", "text": "cherry date elderberry"},
    {"id": 3, "title": "D", "url": "ud", "text": "apricot application apply"},
]


class TestAdapter(unittest.TestCase):
    def test_rejects_incomplete_backend(self):
        class Partial:
            def resolve_query(self, q):
                return {}, {}

        with self.assertRaises(Worklet2Error):
            Worklet2Adapter(Partial())

    def test_normalises_types(self):
        class Loose(InMemoryWorklet2):
            def resolve_query(self, q):
                return {"1": {"apple": "2"}}, {"apple": "3"}

            def get_index_version(self):
                return 42

        adapter = Worklet2Adapter(Loose(DOCS))
        candidates, df = adapter.resolve_query("apple")
        self.assertEqual(candidates, {1: {"apple": 2}})
        self.assertEqual(df, {"apple": 3})
        self.assertEqual(adapter.get_index_version(), "42")

    def test_backend_failure_becomes_worklet2_error(self):
        class Broken(InMemoryWorklet2):
            def resolve_query(self, q):
                raise RuntimeError("boom")

        with self.assertRaises(Worklet2Error):
            Worklet2Adapter(Broken(DOCS)).resolve_query("x")

    def test_corpus_stats_called_once_unless_refreshed(self):
        calls = []

        class Counting(InMemoryWorklet2):
            def get_corpus_stats(self):
                calls.append(1)
                return super().get_corpus_stats()

        adapter = Worklet2Adapter(Counting(DOCS))
        adapter.get_corpus_stats()
        adapter.get_corpus_stats()
        self.assertEqual(len(calls), 1)
        adapter.get_corpus_stats(refresh=True)
        self.assertEqual(len(calls), 2)

    def test_empty_id_lists_short_circuit(self):
        adapter = Worklet2Adapter(InMemoryWorklet2(DOCS))
        self.assertEqual(adapter.get_doc_terms([]), {})
        self.assertEqual(adapter.get_doc_snippet_data([]), {})

    def test_create_adapter_requires_a_source(self):
        with self.assertRaises(Worklet2Error):
            create_adapter()
        self.assertEqual(create_adapter(synthetic=True).get_corpus_stats()["total_docs"], 240)

    def test_load_backend_from_module_spec(self):
        backend = load_backend("wl3.integration.mock_worklet2:InMemoryWorklet2")
        self.assertTrue(callable(backend))      # class given -> factory
        with self.assertRaises(Worklet2Error):
            load_backend("no_such_module_xyz")


class TestInMemoryWorklet2(unittest.TestCase):
    def setUp(self):
        self.w2 = InMemoryWorklet2(DOCS)

    def ids(self, q):
        return set(self.w2.resolve_query(q)[0])

    def test_or_and_not(self):
        self.assertEqual(self.ids("apple date"), {0, 1, 2})
        self.assertEqual(self.ids("banana AND cherry"), {0, 1})
        self.assertEqual(self.ids("cherry NOT apple"), {1, 2})

    def test_prefix_wildcard(self):
        self.assertEqual(self.ids("app*"), {0, 3})

    def test_five_function_contract(self):
        cands, df = self.w2.resolve_query("apple cherry")
        self.assertEqual(cands[0], {"apple": 2, "cherry": 1})
        self.assertEqual(df, {"apple": 1, "cherry": 3})
        self.assertEqual(self.w2.get_corpus_stats()["total_docs"], 4)
        self.assertIsInstance(self.w2.get_index_version(), str)
        self.assertEqual(self.w2.get_doc_snippet_data([1])[1]["title"], "B")
        self.assertEqual(self.w2.get_doc_terms([1])[1]["banana"], 1)

    def test_version_changes_when_corpus_changes(self):
        other = InMemoryWorklet2(DOCS + [{"id": 9, "title": "", "url": "", "text": "new"}])
        self.assertNotEqual(self.w2.get_index_version(), other.get_index_version())


class TestTextHelpers(unittest.TestCase):
    def test_tokenize_query(self):
        self.assertEqual(tokenize_query('"Machine, Learning!" AND data'), ["machine", "learning", "data"])
        self.assertEqual(tokenize_query(""), [])

    def test_snippet_centres_on_hit(self):
        text = "filler " * 100 + "needle" + " filler" * 100
        self.assertIn("needle", make_snippet(text, ["needle"], 80))

    def test_highlight_whole_words_only(self):
        self.assertEqual(highlight("cat concat Cat", ["cat"], "[", "]"), "[cat] concat [Cat]")


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_format_results(self):
        r = RankedResult(1, 2.5, "Title", "http://x", "some neuron text", rank=1)
        out = format_results([r], "neuron", color=False)
        self.assertIn("1. Title", out)
        self.assertIn("URL: http://x", out)
        self.assertIn("Score: 2.5000", out)
        self.assertEqual(format_results([], "q"), "No results.")

    def test_one_shot_query(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["-q", "neuron training", "-k", "2", "--no-color",
                             "--db", os.path.join(self.tmp.name, "c.db")])
        self.assertEqual(code, 0)
        self.assertIn("Score:", buf.getvalue())

    def test_bad_mode_exits_nonzero(self):
        self.assertEqual(cli_main(["--mode", "nope", "-q", "x"]), 2)

    def test_presentation_layers_contain_no_core_logic(self):
        """CLI/Flask must not duplicate ranking, cache, Rocchio or MMR code."""
        root = os.path.join(os.path.dirname(__file__), "..", "..", "wl3")
        banned = re.compile(r"import heapq|from wl3\.(ranking|retrieval|cache|feedback|diversification)")
        for rel in ("cli/main.py", "web/app.py"):
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                code = re.sub(r'""".*?"""', "", fh.read(), flags=re.S)
            self.assertIsNone(banned.search(code), f"core logic referenced in {rel}")


class TestFlask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        engine = QueryEngine(
            Worklet2Adapter(InMemoryWorklet2(DOCS)),
            cache_db_path=os.path.join(self.tmp.name, "w.db"),
        )
        self.engine = engine
        self.app = create_app(engine)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_search_json_and_session_cookie(self):
        r = self.client.get("/api/search?q=cherry&k=2")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json["results"]), 2)
        self.assertEqual(set(r.json["results"][0]), {"rank", "doc_id", "score", "title", "url", "snippet"})
        self.assertIn("wl3_session", r.headers.get("Set-Cookie", ""))

    def test_bad_mode_is_400(self):
        self.assertEqual(self.client.get("/api/search?q=x&mode=zzz").status_code, 400)

    def test_empty_query_returns_empty_list(self):
        self.assertEqual(self.client.get("/api/search?q=").json["results"], [])

    def test_feedback_is_per_browser_session(self):
        a, b = self.app.test_client(), self.app.test_client()
        url = "/api/search?q=banana&mode=tfidf"
        ids = lambda c: [r["doc_id"] for r in c.get(url).json["results"]]
        self.assertEqual(ids(a), [0, 1])                   # tie -> doc id order
        self.assertTrue(a.post("/api/feedback", json={"doc_id": 2}).json["ok"])
        self.assertEqual(ids(a), [1, 0])                   # personalised for browser A
        self.assertEqual(ids(b), [0, 1])                   # browser B unaffected

    def test_feedback_validation_and_reset(self):
        self.assertEqual(self.client.post("/api/feedback", json={"doc_id": "x"}).status_code, 400)
        self.assertTrue(self.client.post("/api/reset").json["ok"])

    def test_html_page_escapes_and_renders(self):
        r = self.client.get("/?q=cherry")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<mark>", r.data)
        self.assertEqual(self.client.get("/?q=%3Cscript%3E").status_code, 200)

    def test_stats_endpoint(self):
        self.client.get("/api/search?q=cherry")
        self.assertEqual(self.client.get("/api/stats").json["total_docs"], 4)


if __name__ == "__main__":
    unittest.main()
