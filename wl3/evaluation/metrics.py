"""
wl3/evaluation/metrics.py
===========================
Ranking quality metrics per SRS FR-9.

Implements:
    precision_at_k(retrieved, relevant, k)
    recall_at_k(retrieved, relevant, k)
    reciprocal_rank(retrieved, relevant)
    mean_reciprocal_rank(results_list, relevant_list)
    average_precision(retrieved, relevant)
    evaluate_ranking(retrieved, relevant, ks)

All functions operate on plain Python lists/sets — no external
libraries required.

Definitions (binary relevance judgements)
------------------------------------------
    Precision@k  = |relevant ∩ top-k retrieved| / k
    Recall@k     = |relevant ∩ top-k retrieved| / |relevant|
    RR           = 1 / rank_of_first_relevant  (0 if none found)
    MRR          = mean(RR) over a query set
    AP           = average of Precision@k over all ranks k where
                   the k-th result is relevant

Usage
-----
    from wl3.evaluation.metrics import evaluate_ranking

    retrieved    = [7, 0, 4, 1, 12, 23, 5, 8, 3, 2]   # ranked doc_ids
    relevant_ids = {0, 4, 7, 12, 23}

    report = evaluate_ranking(retrieved, relevant_ids, ks=[5, 10])
    # → {"precision@5": 0.8, "recall@5": 0.8, "precision@10": 0.5,
    #    "recall@10": 1.0, "rr": 1.0, "ap": 0.9067}
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Core metric functions
# ---------------------------------------------------------------------------

def precision_at_k(
    retrieved: list[int],
    relevant: set[int],
    k: int,
) -> float:
    """
    Compute Precision@k.

    Precision@k = (# relevant documents in the top-k results) / k

    Parameters
    ----------
    retrieved : list[int]
        Ranked list of doc_ids in descending relevance order.
    relevant : set[int]
        Set of doc_ids judged relevant for this query.
    k : int
        Cutoff depth.  Must be > 0.

    Returns
    -------
    float in [0.0, 1.0]
        0.0 if k <= 0 or retrieved is empty.
    """
    if k <= 0 or not retrieved or not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / k


def recall_at_k(
    retrieved: list[int],
    relevant: set[int],
    k: int,
) -> float:
    """
    Compute Recall@k.

    Recall@k = (# relevant documents in the top-k results) / |relevant|

    Parameters
    ----------
    retrieved : list[int]
        Ranked list of doc_ids in descending relevance order.
    relevant : set[int]
        Set of doc_ids judged relevant for this query.
    k : int
        Cutoff depth.  Must be > 0.

    Returns
    -------
    float in [0.0, 1.0]
        0.0 if relevant is empty or k <= 0.
    """
    if k <= 0 or not retrieved or not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / len(relevant)


def reciprocal_rank(
    retrieved: list[int],
    relevant: set[int],
) -> float:
    """
    Compute the Reciprocal Rank (RR) for a single query.

    RR = 1 / rank_of_first_relevant_result
         0.0 if no relevant result appears in the list.

    Parameters
    ----------
    retrieved : list[int]
        Ranked list of doc_ids (1-indexed positions implied).
    relevant : set[int]
        Set of relevant doc_ids for this query.

    Returns
    -------
    float in (0.0, 1.0]
    """
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(
    results_list: list[list[int]],
    relevant_list: list[set[int]],
) -> float:
    """
    Compute Mean Reciprocal Rank (MRR) over a query set.

    MRR = (1 / |Q|) × Σ RR(q)  for each query q in Q

    Parameters
    ----------
    results_list : list[list[int]]
        One ranked list per query.
    relevant_list : list[set[int]]
        One relevant-doc set per query (same order).

    Returns
    -------
    float in [0.0, 1.0]
    """
    if not results_list or len(results_list) != len(relevant_list):
        return 0.0
    rr_sum = sum(
        reciprocal_rank(retrieved, relevant)
        for retrieved, relevant in zip(results_list, relevant_list)
    )
    return rr_sum / len(results_list)


def average_precision(
    retrieved: list[int],
    relevant: set[int],
) -> float:
    """
    Compute Average Precision (AP) for a single query.

    AP = (1 / |relevant|) × Σ  Precision@k  for each k where
         retrieved[k-1] ∈ relevant

    Parameters
    ----------
    retrieved : list[int]
        Ranked list of doc_ids.
    relevant : set[int]
        Set of relevant doc_ids.

    Returns
    -------
    float in [0.0, 1.0]
        0.0 if relevant is empty.
    """
    if not relevant or not retrieved:
        return 0.0

    hits = 0
    ap_sum = 0.0
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            hits += 1
            ap_sum += hits / rank

    return ap_sum / len(relevant)


# ---------------------------------------------------------------------------
# Composite evaluation report
# ---------------------------------------------------------------------------

def evaluate_ranking(
    retrieved: list[int],
    relevant: set[int],
    ks: list[int] | None = None,
) -> dict[str, float]:
    """
    Compute the full set of ranking metrics for a single query.

    Metrics computed:
        precision@k     — for each k in ks
        recall@k        — for each k in ks
        rr              — Reciprocal Rank
        ap              — Average Precision

    Parameters
    ----------
    retrieved : list[int]
        Ranked doc_ids returned by the search system.
    relevant : set[int]
        Doc_ids judged relevant by a human assessor.
    ks : list[int], optional
        Cutoff depths.  Default: [5, 10].

    Returns
    -------
    dict[str, float]
        Keys: "precision@5", "recall@5", "precision@10", "recall@10",
              "rr", "ap"  (plus any additional k-values requested).

    Example
    -------
    >>> retrieved    = [7, 0, 4, 1, 12, 23, 5, 8, 3, 2]
    >>> relevant_ids = {0, 4, 7, 12, 23}
    >>> evaluate_ranking(retrieved, relevant_ids, ks=[5, 10])
    {'precision@5': 0.8, 'recall@5': 0.8, 'precision@10': 0.5,
     'recall@10': 1.0, 'rr': 1.0, 'ap': ...}
    """
    if ks is None:
        ks = [5, 10]

    report: dict[str, float] = {}

    for k in ks:
        report[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
        report[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)

    report["rr"] = reciprocal_rank(retrieved, relevant)
    report["ap"] = average_precision(retrieved, relevant)

    return report


def aggregate_metrics(per_query_reports: list[dict[str, float]]) -> dict[str, float]:
    """
    Average per-query metric reports across a query set.

    Computes the mean of each metric key.  MRR is the mean of per-query RR.

    Parameters
    ----------
    per_query_reports : list[dict[str, float]]
        One report dict per query (output of evaluate_ranking).

    Returns
    -------
    dict[str, float]
        Keys are the same as the input dicts but values are means.
        An extra "mrr" key is added = mean of "rr" values.
    """
    if not per_query_reports:
        return {}

    keys = per_query_reports[0].keys()
    aggregated: dict[str, float] = {}
    n = len(per_query_reports)

    for key in keys:
        aggregated[key] = sum(r.get(key, 0.0) for r in per_query_reports) / n

    # Alias: MRR = mean of per-query RR values
    if "rr" in aggregated:
        aggregated["mrr"] = aggregated["rr"]

    return aggregated
