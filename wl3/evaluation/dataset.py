"""
wl3/evaluation/dataset.py
==========================
Labelled evaluation dataset for ranking quality measurement.

Provides a small hand-labelled query set (~30–50 queries) following the
SRS FR-9 requirement.  Each entry specifies a query and the set of doc_ids
that a human assessor has judged as relevant.

The dataset is intentionally kept as a plain Python constant (no database,
no CSV) so it requires zero dependencies and can be run offline during
development before the real W2/W1 corpus is available.

Format
------
Each entry is a dict with:
    "query"        : str              — the query string
    "relevant_docs": list[int]        — doc_ids judged relevant by a human
    "description"  : str (optional)  — notes for the assessor

Usage
-----
    from wl3.evaluation.dataset import LABELLED_QUERIES, get_queries

    for entry in get_queries():
        query        = entry["query"]
        relevant_ids = set(entry["relevant_docs"])
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Hand-labelled query set
# Target: 30–50 queries per SRS §3.4.4
# Current: 30 sample queries using a simulated corpus of ~200 documents.
# Replace relevant_docs with real doc_ids once the W1/W2 corpus is built.
# ---------------------------------------------------------------------------

LABELLED_QUERIES: list[dict] = [
    # --- Machine Learning & AI ---
    {
        "query": "machine learning",
        "relevant_docs": [0, 4, 7, 12, 18, 23],
        "description": "General ML overview articles",
    },
    {
        "query": "deep learning neural networks",
        "relevant_docs": [1, 5, 9, 14, 20],
        "description": "Deep learning / neural net focused docs",
    },
    {
        "query": "supervised learning classification",
        "relevant_docs": [0, 6, 11, 17],
        "description": "Supervised learning and classification tasks",
    },
    {
        "query": "unsupervised learning clustering",
        "relevant_docs": [3, 8, 15, 22],
        "description": "Unsupervised learning and clustering methods",
    },
    {
        "query": "reinforcement learning reward",
        "relevant_docs": [7, 13, 19, 25],
        "description": "Reinforcement learning basics",
    },
    {
        "query": "convolutional neural network image recognition",
        "relevant_docs": [2, 9, 16, 21],
        "description": "CNN for image classification",
    },
    {
        "query": "natural language processing text",
        "relevant_docs": [10, 24, 30, 35],
        "description": "NLP / text processing",
    },
    {
        "query": "recurrent neural network LSTM",
        "relevant_docs": [5, 14, 27, 33],
        "description": "RNNs and LSTM networks",
    },
    {
        "query": "gradient descent optimization",
        "relevant_docs": [1, 6, 18, 28],
        "description": "Gradient descent and training optimization",
    },
    {
        "query": "overfitting regularization dropout",
        "relevant_docs": [4, 11, 20, 31],
        "description": "Overfitting prevention techniques",
    },
    # --- Data Science & Statistics ---
    {
        "query": "data preprocessing normalization",
        "relevant_docs": [3, 8, 22, 34],
        "description": "Data cleaning and preprocessing",
    },
    {
        "query": "feature engineering selection",
        "relevant_docs": [6, 12, 23, 36],
        "description": "Feature selection and engineering",
    },
    {
        "query": "cross validation training test split",
        "relevant_docs": [0, 7, 17, 29],
        "description": "Model evaluation methodologies",
    },
    {
        "query": "precision recall F1 score",
        "relevant_docs": [10, 24, 37, 42],
        "description": "Classification evaluation metrics",
    },
    {
        "query": "principal component analysis dimensionality reduction",
        "relevant_docs": [3, 15, 26, 38],
        "description": "PCA and dimensionality reduction",
    },
    {
        "query": "random forest decision tree ensemble",
        "relevant_docs": [6, 13, 21, 32],
        "description": "Tree-based ensemble methods",
    },
    {
        "query": "support vector machine kernel",
        "relevant_docs": [2, 11, 19, 30],
        "description": "SVM and kernel methods",
    },
    {
        "query": "k-means clustering algorithm",
        "relevant_docs": [8, 15, 22, 40],
        "description": "K-means and centroid clustering",
    },
    # --- Computer Science Fundamentals ---
    {
        "query": "binary search tree data structure",
        "relevant_docs": [50, 55, 61, 68],
        "description": "BST operations and use cases",
    },
    {
        "query": "hash table collision resolution",
        "relevant_docs": [51, 57, 63, 70],
        "description": "Hash maps and collision handling",
    },
    {
        "query": "graph traversal breadth first depth first",
        "relevant_docs": [52, 58, 64, 71],
        "description": "BFS/DFS graph traversal",
    },
    {
        "query": "dynamic programming memoization",
        "relevant_docs": [53, 59, 65, 72],
        "description": "DP and memoization techniques",
    },
    {
        "query": "sorting algorithm merge sort quicksort",
        "relevant_docs": [54, 60, 66, 73],
        "description": "Comparison-based sorting",
    },
    {
        "query": "time complexity big O notation",
        "relevant_docs": [50, 56, 62, 74],
        "description": "Algorithmic complexity analysis",
    },
    # --- Information Retrieval ---
    {
        "query": "inverted index term frequency",
        "relevant_docs": [80, 84, 89, 95],
        "description": "IR index structures",
    },
    {
        "query": "BM25 ranking relevance scoring",
        "relevant_docs": [81, 85, 90, 96],
        "description": "BM25 and relevance ranking",
    },
    {
        "query": "cosine similarity document vector",
        "relevant_docs": [82, 86, 91, 97],
        "description": "Vector space model and cosine scoring",
    },
    {
        "query": "search engine query processing",
        "relevant_docs": [83, 87, 92, 98],
        "description": "End-to-end search pipeline",
    },
    {
        "query": "precision recall information retrieval evaluation",
        "relevant_docs": [84, 88, 93, 99],
        "description": "IR evaluation methodology",
    },
    {
        "query": "LRU cache eviction policy",
        "relevant_docs": [85, 89, 94, 100],
        "description": "LRU caching and eviction",
    },
]


def get_queries() -> list[dict]:
    """
    Return the full labelled query set.

    Returns
    -------
    list[dict]
        Each dict has keys: 'query' (str), 'relevant_docs' (list[int]),
        and optionally 'description' (str).
    """
    return LABELLED_QUERIES


def get_query_by_text(query: str) -> dict | None:
    """
    Retrieve a labelled entry by exact query string (case-insensitive).

    Returns
    -------
    dict or None
    """
    query_lower = query.strip().lower()
    for entry in LABELLED_QUERIES:
        if entry["query"].lower() == query_lower:
            return entry
    return None
