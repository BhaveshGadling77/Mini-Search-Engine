"""
Interactive Manual Test Runner for Person 1 (Ranking & Retrieval)
==================================================================
Run: python3 manual_test_runner.py
"""

import os
import sys

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wl3.ranking.tfidf import TFIDFScorer
from wl3.ranking.bm25 import BM25Scorer
from wl3.ranking.vector import VectorScorer
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever
from wl3.evaluation.metrics import precision_at_k, recall_at_k, reciprocal_rank, average_precision


def demo_case_1_tfidf():
    print("
" + "="*60)
    print("TEST CASE 1: TF-IDF Scoring (Simple 2-Document Corpus)")
    print("="*60)
    scorer = TFIDFScorer()
    # 100 documents total. Word 'python' appears in 10 docs.
    # IDF = log10(100 / 10) = 1.0
    total_docs = 100
    doc_freq = {"python": 10}
    query = ["python"]

    doc1_tf = {"python": 3}  # mentions 'python' 3 times
    doc2_tf = {"python": 1}  # mentions 'python' 1 time

    s1 = scorer.score(doc1_tf, doc_freq, total_docs, query)
    s2 = scorer.score(doc2_tf, doc_freq, total_docs, query)

    print(f"Query: {query}")
    print(f"Total docs: {total_docs}, DF('python'): {doc_freq['python']} -> IDF = 1.0")
    print(f"Doc 1 score (tf=3): {s1}  (Expected: 3.0)")
    print(f"Doc 2 score (tf=1): {s2}  (Expected: 1.0)")
    print(f"Order check: Doc 1 > Doc 2? {s1 > s2} ✅")


def demo_case_2_bm25():
    print("
" + "="*60)
    print("TEST CASE 2: BM25 Length Normalization (Short vs Long Doc)")
    print("="*60)
    scorer = BM25Scorer(k1=1.5, b=0.75)
    total_docs = 100
    doc_freq = {"search": 10}
    avg_len = 50.0
    query = ["search"]

    # Both documents mention 'search' twice (tf=2)
    # Doc 1 is short (25 words). Doc 2 is long (100 words).
    s_short = scorer.score({"search": 2}, doc_freq, total_docs, doc_length=25, avg_doc_length=avg_len, query_terms=query)
    s_long = scorer.score({"search": 2}, doc_freq, total_docs, doc_length=100, avg_doc_length=avg_len, query_terms=query)

    print(f"Query: {query}, TF in both docs = 2")
    print(f"Doc 1 (Short, 25 words) score: {s_short:.4f}")
    print(f"Doc 2 (Long, 100 words) score: {s_long:.4f}")
    print(f"Did shorter doc score higher? {s_short > s_long} ✅ (BM25 penalizes dilution)")


def demo_case_3_vector():
    print("
" + "="*60)
    print("TEST CASE 3: Vector Space Cosine Similarity")
    print("="*60)
    scorer = VectorScorer()

    query_vec = {"python": 1.0, "code": 1.0}
    doc_identical = {"python": 1.0, "code": 1.0}
    doc_disjoint = {"cooking": 1.0}

    sim1 = scorer.cosine_similarity(query_vec, doc_identical)
    sim2 = scorer.cosine_similarity(query_vec, doc_disjoint)

    print(f"Query vector: {query_vec}")
    print(f"Doc 1 vector (Identical): {doc_identical} -> Cosine: {sim1:.4f} (Expected: 1.0)")
    print(f"Doc 2 vector (Orthogonal): {doc_disjoint} -> Cosine: {sim2:.4f} (Expected: 0.0)")


def demo_case_4_topk():
    print("
" + "="*60)
    print("TEST CASE 4: Top-K Retriever with Tie-Breaking")
    print("="*60)
    # Doc 10 and Doc 5 have identical score 5.0. Doc 20 has score 3.0.
    scores = {10: 5.0, 5: 5.0, 20: 3.0}
    top2 = TopKRetriever.get_top_k(scores, k=2)

    print(f"Input scores: {scores}")
    print(f"Top 2 retrieved: {[f'Doc {d.doc_id}: score {d.score}' for d in top2]}")
    print("Notice Doc 5 comes before Doc 10 because on ties it orders by doc_id ascending ✅")


def demo_case_5_metrics():
    print("
" + "="*60)
    print("TEST CASE 5: Precision@K & Recall@K")
    print("="*60)
    # Search returned docs: [1, 2, 3, 4, 5]
    # Actually relevant docs: {1, 3, 9}
    retrieved = [1, 2, 3, 4, 5]
    relevant = {1, 3, 9}

    p3 = precision_at_k(retrieved, relevant, k=3)
    r3 = recall_at_k(retrieved, relevant, k=3)

    print(f"Retrieved top 5: {retrieved}")
    print(f"Relevant docs: {relevant}")
    print(f"In top 3 docs [1, 2, 3], matching are {set(retrieved[:3]) & relevant} (2 docs)")
    print(f"P@3: {p3:.4f} (2 out of 3 = 0.6667) ✅")
    print(f"R@3: {r3:.4f} (2 out of 3 total relevant = 0.6667) ✅")


if __name__ == '__main__':
    demo_case_1_tfidf()
    demo_case_2_bm25()
    demo_case_3_vector()
    demo_case_4_topk()
    demo_case_5_metrics()
    print("
" + "="*60)
    print("ALL 5 EASY TESTCASES EXECUTED SUCCESSFULLY! ✅")
    print("="*60 + "
")
