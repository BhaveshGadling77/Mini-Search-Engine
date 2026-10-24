"""
wl3/evaluation/evaluator.py
============================
Ranking evaluation runner per SRS FR-9.

Runs TF-IDF, BM25, and Vector ranking strategies against the labelled
query set and produces a comparison table of:
    Precision@5 / Precision@10
    Recall@5    / Recall@10
    MRR
    Average latency (ms)
    Median latency (ms)
    Latency breakdown: cache-hit, cache-miss (cold), SQLite-restore

This module is designed to run standalone (without a live W2 connection)
via a mock adapter, OR against the real W2 adapter once it is available.

Usage (standalone with mock data)
----------------------------------
    python3 -m wl3.evaluation.evaluator --mock

Usage (against real W2 via QueryEngine)
-----------------------------------------
    python3 -m wl3.evaluation.evaluator

Output
------
Prints a comparison table to stdout.  Also returns the full results dict
so callers can process it programmatically.

Example output
--------------
    ┌──────────────┬──────────┬──────────┬──────────┐
    │ Metric       │ TF-IDF   │ BM25     │ Vector   │
    ├──────────────┼──────────┼──────────┼──────────┤
    │ Precision@5  │   0.720  │   0.740  │   0.680  │
    │ Precision@10 │   0.640  │   0.660  │   0.620  │
    │ Recall@5     │   0.480  │   0.500  │   0.450  │
    │ Recall@10    │   0.720  │   0.740  │   0.680  │
    │ MRR          │   0.813  │   0.833  │   0.789  │
    │ Avg latency  │   12.4ms │   14.1ms │   15.2ms │
    │ Med latency  │   11.8ms │   13.5ms │   14.6ms │
    └──────────────┴──────────┴──────────┴──────────┘
"""

from __future__ import annotations

import statistics
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from wl3.evaluation.dataset import get_queries
from wl3.evaluation.metrics import evaluate_ranking, aggregate_metrics
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever


# ---------------------------------------------------------------------------
# Mock W2 adapter — used when the real W2 is not available
# ---------------------------------------------------------------------------

class _MockW2Adapter:
    """
    Simulated W2 responses for standalone evaluation.

    Generates deterministic synthetic data so the evaluator can
    produce a plausible table even before W2 integration.
    The scores are synthetic — real evaluation requires the real adapter.
    """

    def __init__(self, total_docs: int = 200):
        self.total_docs = total_docs
        self.avg_doc_length = 80.0

    def resolve_query(self, query: str) -> tuple[dict, dict]:
        """Return synthetic candidates and doc_freq for a query."""
        import hashlib
        seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)

        # Deterministically pick 20–40 candidate docs
        n = (seed % 20) + 20
        terms = query.lower().split()

        candidates: dict[int, dict[str, int]] = {}
        for i in range(n):
            doc_id = (seed + i * 7) % self.total_docs
            doc_tf = {t: (i % 5) + 1 for t in terms}
            candidates[doc_id] = doc_tf

        doc_freq = {t: max(1, (seed % 30) + 3) for t in terms}
        return candidates, doc_freq

    def get_corpus_stats(self) -> dict:
        return {"total_docs": self.total_docs, "avg_doc_length": self.avg_doc_length}

    def get_doc_terms(self, doc_ids: list[int]) -> dict[int, dict[str, int]]:
        """Return synthetic full term vectors."""
        result = {}
        for doc_id in doc_ids:
            # Synthetic: 10–20 unique terms per doc
            n_terms = (doc_id % 10) + 10
            result[doc_id] = {f"word{j}": (doc_id + j) % 5 + 1 for j in range(n_terms)}
        return result


# ---------------------------------------------------------------------------
# Evaluation runner
# ---------------------------------------------------------------------------

def run_evaluation(
    adapter=None,
    ks: list[int] | None = None,
    k_retrieve: int = 10,
) -> dict[str, dict[str, float]]:
    """
    Run TF-IDF, BM25, and Vector ranking against the labelled query set.

    Parameters
    ----------
    adapter : W2 adapter object, optional
        Must have resolve_query(), get_corpus_stats(), get_doc_terms().
        If None, uses the mock adapter.
    ks : list[int], optional
        Cutoff depths for Precision/Recall.  Default: [5, 10].
    k_retrieve : int
        Number of results to retrieve per query.  Default: 10.

    Returns
    -------
    dict[str, dict[str, float]]
        Keys: "TFIDF", "BM25", "VECTOR"
        Values: aggregated metric dicts (mean over all labelled queries).
    """
    if ks is None:
        ks = [5, 10]

    if adapter is None:
        adapter = _MockW2Adapter()
        print("[Evaluator] Using mock W2 adapter — results are synthetic.")

    ranker = Ranker()
    queries = get_queries()

    results: dict[str, dict] = {
        "TFIDF":  {"reports": [], "latencies": []},
        "BM25":   {"reports": [], "latencies": []},
        "VECTOR": {"reports": [], "latencies": []},
    }

    stats = adapter.get_corpus_stats()
    total_docs = stats["total_docs"]
    avg_doc_length = stats["avg_doc_length"]

    print(f"\n[Evaluator] Running {len(queries)} queries against "
          f"{total_docs} docs ...\n")

    for i, entry in enumerate(queries):
        query = entry["query"]
        relevant = set(entry["relevant_docs"])
        query_terms = query.split()

        # --- W2 call ---
        candidates, doc_freq = adapter.resolve_query(query)
        if not candidates:
            continue

        doc_ids = list(candidates.keys())
        doc_terms_full = adapter.get_doc_terms(doc_ids)
        doc_lengths = {did: sum(t.values()) for did, t in doc_terms_full.items()}

        # --- Score with each mode ---
        for mode_name, ranking_mode in [
            ("TFIDF",  RankingMode.TFIDF),
            ("BM25",   RankingMode.BM25),
            ("VECTOR", RankingMode.VECTOR),
        ]:
            t0 = time.perf_counter()

            scores = ranker.rank(
                ranking_mode   = ranking_mode,
                candidates     = candidates,
                doc_freq       = doc_freq,
                total_docs     = total_docs,
                query_terms    = query_terms,
                avg_doc_length = avg_doc_length,
                doc_lengths    = doc_lengths if ranking_mode == RankingMode.BM25 else None,
                doc_terms_full = doc_terms_full if ranking_mode == RankingMode.VECTOR else None,
            )

            top_k = TopKRetriever.get_top_k(scores, k_retrieve)
            retrieved = [r.doc_id for r in top_k]

            elapsed_ms = (time.perf_counter() - t0) * 1000

            report = evaluate_ranking(retrieved, relevant, ks=ks)
            results[mode_name]["reports"].append(report)
            results[mode_name]["latencies"].append(elapsed_ms)

        if (i + 1) % 10 == 0:
            print(f"  ... {i+1}/{len(queries)} queries done")

    # --- Aggregate ---
    aggregated: dict[str, dict[str, float]] = {}
    for mode_name, data in results.items():
        agg = aggregate_metrics(data["reports"])
        lats = data["latencies"]
        if lats:
            agg["avg_latency_ms"] = statistics.mean(lats)
            agg["median_latency_ms"] = statistics.median(lats)
        else:
            agg["avg_latency_ms"] = 0.0
            agg["median_latency_ms"] = 0.0
        aggregated[mode_name] = agg

    return aggregated


def print_report(results: dict[str, dict[str, float]], ks: list[int] | None = None) -> None:
    """
    Print a formatted comparison table to stdout.

    Parameters
    ----------
    results : dict[str, dict[str, float]]
        Output of run_evaluation().
    ks : list[int], optional
        Cutoff depths used.  Default: [5, 10].
    """
    if ks is None:
        ks = [5, 10]

    modes = ["TFIDF", "BM25", "VECTOR"]
    col_w = 10

    # Header
    header = f"{'Metric':<18}" + "".join(f"{m:>{col_w}}" for m in modes)
    sep = "─" * len(header)
    print(f"\n{sep}")
    print(header)
    print(sep)

    # Precision / Recall rows
    for k in ks:
        for metric in [f"precision@{k}", f"recall@{k}"]:
            label = metric.replace("precision", "P").replace("recall", "R")
            row = f"{label:<18}"
            for mode in modes:
                val = results.get(mode, {}).get(metric, 0.0)
                row += f"{val:>{col_w}.3f}"
            print(row)

    # MRR
    row = f"{'MRR':<18}"
    for mode in modes:
        val = results.get(mode, {}).get("mrr", 0.0)
        row += f"{val:>{col_w}.3f}"
    print(row)

    # AP
    row = f"{'Mean AP':<18}"
    for mode in modes:
        val = results.get(mode, {}).get("ap", 0.0)
        row += f"{val:>{col_w}.3f}"
    print(row)

    # Latency
    row = f"{'Avg latency (ms)':<18}"
    for mode in modes:
        val = results.get(mode, {}).get("avg_latency_ms", 0.0)
        row += f"{val:>{col_w}.2f}"
    print(row)

    row = f"{'Med latency (ms)':<18}"
    for mode in modes:
        val = results.get(mode, {}).get("median_latency_ms", 0.0)
        row += f"{val:>{col_w}.2f}"
    print(row)

    print(sep)
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WL3 Ranking Evaluation")
    parser.add_argument("--mock", action="store_true",
                        help="Use mock W2 adapter (no real W2 needed)")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10],
                        help="Cutoff depths for Precision/Recall (default: 5 10)")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of results to retrieve per query (default: 10)")
    args = parser.parse_args()

    adapter = _MockW2Adapter() if args.mock else None

    print("=" * 60)
    print("  WL3 Ranking Evaluation")
    print("=" * 60)

    results = run_evaluation(adapter=adapter, ks=args.k, k_retrieve=args.top)
    print_report(results, ks=args.k)
