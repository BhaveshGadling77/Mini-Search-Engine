"""
End-to-end evaluation runner (W3 SRS FR-9 / 3.4).

Unlike ``evaluator.py`` (a quick offline scorer over a mock adapter), this
runner drives the real ``QueryEngine`` so that cache hits, cache misses, the
SQLite cold start and concurrent access are measured on the actual pipeline.

Runs TF-IDF, BM25 and Vector ranking on the same labelled queries and reports

* quality  : Precision@5/10, Recall@5/10, MRR
* latency  : mean / median (ms) for
              - cache MISS        (cache cleared before every query)
              - cache HIT         (query repeated after a warm-up)
              - SQLite COLD START (fresh engine process-state, entries restored
                                   from disk)
              - CONCURRENT access (many simulated browser sessions at once)
* a heap-vs-full-sort Top-K micro benchmark (SRS 3.4.1).

The evaluator receives an *engine factory* so it can create a second engine
on the same SQLite file to simulate an application restart.
"""

from __future__ import annotations

import json
import os
import random
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from wl3.engine.query_engine import QueryEngine
from wl3.evaluation.metrics import aggregate_metrics, evaluate_ranking
from wl3.retrieval.top_k import TopKRetriever

MODES = ("tfidf", "bm25", "vector")
K_VALUES = (5, 10)


def _ms(seconds: float) -> float:
    return seconds * 1000.0


def _summary(samples_s: list[float]) -> dict:
    if not samples_s:
        return {"mean_ms": 0.0, "median_ms": 0.0, "n": 0}
    return {
        "mean_ms": _ms(statistics.fmean(samples_s)),
        "median_ms": _ms(statistics.median(samples_s)),
        "n": len(samples_s),
    }


class Evaluator:
    """
    Parameters
    ----------
    engine_factory : callable ``(db_path) -> QueryEngine``
        Must build an engine whose SQLite cache lives at ``db_path``.
    queries : list[dict]   # {"query": str, "relevant_docs": [doc_ids]}
    repeats : int
        Timing repetitions per query (latency is averaged over them).
    """

    def __init__(
        self,
        engine_factory: Callable[[str], QueryEngine],
        queries: list[dict],
        repeats: int = 3,
        concurrent_sessions: int = 8,
    ) -> None:
        self.engine_factory = engine_factory
        self.queries = queries
        self.repeats = max(1, repeats)
        self.concurrent_sessions = concurrent_sessions

    # ------------------------------------------------------------------
    # Quality
    # ------------------------------------------------------------------

    def evaluate_quality(self, engine: QueryEngine, mode: str) -> dict:
        reports = []
        for item in self.queries:
            engine.clear_cache()
            ranked = [r.doc_id for r in engine.search(item["query"], None, mode, 10, False)]
            reports.append(evaluate_ranking(ranked, set(item["relevant_docs"]), ks=list(K_VALUES)))
        agg = aggregate_metrics(reports)
        return {
            "P@5": agg["precision@5"], "P@10": agg["precision@10"],
            "R@5": agg["recall@5"], "R@10": agg["recall@10"],
            "MRR": agg["mrr"], "MAP": agg["ap"],
        }

    # ------------------------------------------------------------------
    # Latency
    # ------------------------------------------------------------------

    def measure_miss(self, engine: QueryEngine, mode: str) -> dict:
        samples = []
        for _ in range(self.repeats):
            for item in self.queries:
                engine.clear_cache()
                start = time.perf_counter()
                engine.search(item["query"], None, mode, 10, False)
                samples.append(time.perf_counter() - start)
        return _summary(samples)

    def measure_hit(self, engine: QueryEngine, mode: str) -> dict:
        for item in self.queries:                       # warm-up fills the cache
            engine.search(item["query"], None, mode, 10, False)
        samples = []
        for _ in range(self.repeats):
            for item in self.queries:
                start = time.perf_counter()
                engine.search(item["query"], None, mode, 10, False)
                samples.append(time.perf_counter() - start)
        return _summary(samples)

    def measure_cold_start(self, mode: str) -> dict:
        """Persist entries, 'restart' (new engine, empty LRU), time first hits."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = os.path.join(tmp, "cold.db")
            first = self.engine_factory(db)
            for item in self.queries:
                first.search(item["query"], None, mode, 10, False)
            del first

            restarted = self.engine_factory(db)
            restarted.reset_counters()
            samples = []
            for item in self.queries:
                start = time.perf_counter()
                restarted.search(item["query"], None, mode, 10, False)
                samples.append(time.perf_counter() - start)
            result = _summary(samples)
            result["served_from_disk"] = restarted.cache_hits
            return result

    def measure_concurrent(self, mode: str) -> dict:
        """Many simulated browser sessions hitting one shared engine."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            engine = self.engine_factory(os.path.join(tmp, "conc.db"))
            reference = {
                item["query"]: [r.doc_id for r in engine.search(item["query"], None, mode, 10, False)]
                for item in self.queries
            }
            engine.clear_cache()
            engine.reset_counters()

            rng = random.Random(1)
            workload = [
                (f"session-{s}", rng.choice(self.queries)["query"])
                for s in range(self.concurrent_sessions)
                for _ in range(len(self.queries))
            ]

            def one_request(args):
                session_id, query = args
                start = time.perf_counter()
                ranked = [r.doc_id for r in engine.search(query, session_id, mode, 10, False)]
                return time.perf_counter() - start, query, ranked

            wall_start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=self.concurrent_sessions) as pool:
                outcomes = list(pool.map(one_request, workload))
            wall = time.perf_counter() - wall_start

            inconsistent = sum(1 for _, q, ranked in outcomes if ranked != reference[q])
            summary = _summary([t for t, _, _ in outcomes])
            summary.update(
                {
                    "requests": len(outcomes),
                    "wall_time_s": wall,
                    "throughput_rps": len(outcomes) / wall if wall else 0.0,
                    "inconsistent_results": inconsistent,
                    "cache_entries": len(engine.cache),
                    "cache_capacity": engine.cache.capacity if hasattr(engine.cache, "capacity") else engine.cache_capacity,
                }
            )
            return summary

    # ------------------------------------------------------------------
    # Heap vs full sort
    # ------------------------------------------------------------------

    @staticmethod
    def benchmark_top_k(n: int = 50_000, k: int = 10, trials: int = 5) -> dict:
        rng = random.Random(0)
        scores = {i: rng.random() for i in range(n)}
        heap_t, sort_t = [], []
        for _ in range(trials):
            start = time.perf_counter()
            TopKRetriever.get_top_k(scores, k)
            heap_t.append(time.perf_counter() - start)
            start = time.perf_counter()
            sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
            sort_t.append(time.perf_counter() - start)
        return {
            "n": n,
            "k": k,
            "heap_ms": _ms(statistics.median(heap_t)),
            "full_sort_ms": _ms(statistics.median(sort_t)),
        }

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------

    def run(self, modes: tuple[str, ...] = MODES) -> dict:
        report: dict = {"queries": len(self.queries), "modes": {}}
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            engine = self.engine_factory(os.path.join(tmp, "eval.db"))
            report["total_docs"] = engine.total_docs
            for mode in modes:
                report["modes"][mode] = {
                    "quality": self.evaluate_quality(engine, mode),
                    "latency": {
                        "cache_miss": self.measure_miss(engine, mode),
                        "cache_hit": self.measure_hit(engine, mode),
                        "cold_start": self.measure_cold_start(mode),
                        "concurrent": self.measure_concurrent(mode),
                    },
                }
        report["top_k_benchmark"] = self.benchmark_top_k()
        return report


# ----------------------------------------------------------------------
# Report formatting
# ----------------------------------------------------------------------

def format_report(report: dict) -> str:
    modes = list(report["modes"])
    names = {"tfidf": "TF-IDF", "bm25": "BM25", "vector": "Vector"}
    head = f"{'':<26}" + "".join(f"{names[m]:>14}" for m in modes)
    lines = [
        f"Evaluation: {report['queries']} labelled queries over {report['total_docs']} documents",
        "",
        "Ranking quality",
        head,
    ]
    for metric in ("P@5", "P@10", "R@5", "R@10", "MRR", "MAP"):
        lines.append(
            f"{metric:<26}" + "".join(f"{report['modes'][m]['quality'][metric]:>14.3f}" for m in modes)
        )

    lines += ["", "Latency (ms): mean / median", head]
    for label, key in (
        ("Cache miss", "cache_miss"),
        ("Cache hit", "cache_hit"),
        ("SQLite cold start", "cold_start"),
        ("Concurrent (per request)", "concurrent"),
    ):
        cells = ""
        for m in modes:
            lat = report["modes"][m]["latency"][key]
            cells += f"{lat['mean_ms']:>6.3f}/{lat['median_ms']:<6.3f}"
        lines.append(f"{label:<26}{cells}")

    lines += ["", "Concurrent access detail"]
    for m in modes:
        c = report["modes"][m]["latency"]["concurrent"]
        lines.append(
            f"  {names[m]:<7} {c['requests']} requests, {c['throughput_rps']:.0f} req/s, "
            f"inconsistent results: {c['inconsistent_results']}, "
            f"cache entries {c['cache_entries']}/{c['cache_capacity']}"
        )
    b = report["top_k_benchmark"]
    lines += [
        "",
        f"Top-K benchmark (n={b['n']}, k={b['k']}): heap {b['heap_ms']:.2f} ms "
        f"vs full sort {b['full_sort_ms']:.2f} ms",
    ]
    return "\n".join(lines)


def save_report(report: dict, json_path: str, text_path: str | None = None) -> None:
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    if text_path:
        with open(text_path, "w", encoding="utf-8") as fh:
            fh.write(format_report(report) + "\n")


def main(argv: list[str] | None = None) -> int:
    import argparse

    from wl3.evaluation.synthetic_corpus import build_synthetic_corpus, load_queries
    from wl3.integration.mock_worklet2 import InMemoryWorklet2
    from wl3.integration.worklet2_adapter import Worklet2Adapter, create_adapter

    parser = argparse.ArgumentParser(description="Evaluate TF-IDF / BM25 / Vector ranking")
    parser.add_argument("--backend", help="real Worklet 2 backend, 'module[:attr]'")
    parser.add_argument("--corpus", help="JSON corpus for the in-memory Worklet 2")
    parser.add_argument("--queries", help="labelled queries JSON (default: synthetic set)")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", help="save the report here (.json, plus a .txt next to it); default: print only")
    args = parser.parse_args(argv)

    if args.backend or args.corpus:
        adapter = create_adapter(args.backend, args.corpus)
        if not args.queries:
            parser.error("--queries is required when using a real/custom corpus")
        queries = load_queries(args.queries)
    else:
        documents, synthetic_queries = build_synthetic_corpus()
        adapter = Worklet2Adapter(InMemoryWorklet2(documents))
        queries = load_queries(args.queries) if args.queries else synthetic_queries

    evaluator = Evaluator(
        lambda db: QueryEngine(adapter, cache_db_path=db), queries, repeats=args.repeats
    )
    report = evaluator.run()
    print(format_report(report))
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        save_report(report, args.out, os.path.splitext(args.out)[0] + ".txt")
        print(f"\nSaved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
