"""
Stress Test Suite — Ranking & Retrieval
=========================================
Probes extreme, adversarial, and pathological inputs to find bugs.

Run:  python3 stress_tests.py

Categories:
    1. Extreme numeric values  (very large TF, huge corpus, tiny corpus)
    2. Adversarial W2 data     (df > total_docs, mismatched dicts, empty sub-dicts)
    3. NaN / Inf / float       (IEEE 754 edge cases in scores and inputs)
    4. Large scale             (1000 docs, 500 query terms)
    5. Boundary conditions     (k=−1, doc_length=0, all-zero TF)
    6. Consistency checks      (same input → same output every time)
    7. Mathematical invariants (cosine ∈ [0,1], scores monotone w.r.t. TF)
"""

import math
import sys
import time
import traceback
import os

sys.path.insert(0, os.path.dirname(__file__))

from wl3.ranking.tfidf import TFIDFScorer
from wl3.ranking.bm25 import BM25Scorer
from wl3.ranking.vector import VectorScorer
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever, ScoredDocument

# ─────────────────────────────────────────────────────────────────────────────
# Test infrastructure
# ─────────────────────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0
BUGS = []

def check(label, condition, note=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅  {label}")
    else:
        FAIL += 1
        msg = f"  ❌  {label}"
        if note:
            msg += f"\n      → {note}"
        print(msg)
        BUGS.append((label, note))

def check_no_exception(label, fn):
    global PASS, FAIL
    try:
        result = fn()
        PASS += 1
        print(f"  ✅  {label}")
        return result
    except Exception as e:
        FAIL += 1
        tb = traceback.format_exc().strip().splitlines()[-1]
        print(f"  ❌  {label}\n      → EXCEPTION: {tb}")
        BUGS.append((label, str(e)))
        return None

def section(title):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")

# ─────────────────────────────────────────────────────────────────────────────
# Scorers
# ─────────────────────────────────────────────────────────────────────────────

tfidf  = TFIDFScorer()
bm25   = BM25Scorer()
vector = VectorScorer()
ranker = Ranker()

# ─────────────────────────────────────────────────────────────────────────────
# 1. Extreme Numeric Values
# ─────────────────────────────────────────────────────────────────────────────

section("1. EXTREME NUMERIC VALUES")

# 1a. Very large TF
s = check_no_exception("TF-IDF: tf=1_000_000 does not crash",
    lambda: tfidf.score({"word": 1_000_000}, {"word": 1}, 100, ["word"]))
if s is not None:
    check("TF-IDF: tf=1_000_000 gives finite score", math.isfinite(s),
          f"got {s}")

# 1b. Very large corpus
s = check_no_exception("TF-IDF: total_docs=10_000_000",
    lambda: tfidf.score({"word": 5}, {"word": 3}, 10_000_000, ["word"]))
if s is not None:
    check("TF-IDF: large corpus score is finite", math.isfinite(s), f"got {s}")

# 1c. df > total_docs — should NOT give negative score (invalid W2 data)
s = check_no_exception("TF-IDF: df > total_docs (invalid W2 data)",
    lambda: tfidf.score({"word": 3}, {"word": 15}, 10, ["word"]))
if s is not None:
    # log10(10/15) = log10(0.666) = -0.176  → negative IDF → negative score
    # This is a BUG: score goes negative when df > total_docs
    check("TF-IDF: df > total_docs → score should be >= 0",
          s >= 0.0, f"got {s} (NEGATIVE SCORE — df > total_docs not clamped)")

# 1d. BM25 very large TF saturation
s = check_no_exception("BM25: tf=1_000_000 saturation",
    lambda: bm25.score({"word": 1_000_000}, {"word": 1}, 100, 50, 50.0, ["word"]))
if s is not None:
    check("BM25: tf=1_000_000 gives finite score", math.isfinite(s), f"got {s}")
    # Asymptote when doc_length == avg_doc_length (length_norm = 1):
    # limit as tf→∞ = (k1+1)×IDF = 2.5 × IDF
    # We can't use b=0.75 doc_len=50 avg=50 directly; it reduces length_norm=1:
    asym = (1.5 + 1) * math.log10(100 / 1)
    check("BM25: tf=1M below or near asymptote",
          s <= asym * 1.001, f"got {s}, asymptote={asym:.4f}")

# 1e. BM25 df > total_docs
s = check_no_exception("BM25: df > total_docs (invalid W2 data)",
    lambda: bm25.score({"word": 3}, {"word": 15}, 10, 20, 45.0, ["word"]))
if s is not None:
    # BM25 IDF = log10((N-df+0.5)/(df+0.5) + 1)
    #          = log10((10-15+0.5)/(15+0.5) + 1)
    #          = log10(-4.5/15.5 + 1) = log10(0.71) = -0.149 → negative IDF
    check("BM25: df > total_docs → score should be >= 0",
          s >= 0.0, f"got {s} (NEGATIVE IDF — df > total_docs not clamped)")

# 1f. Very small corpus: total_docs=2
s = check_no_exception("TF-IDF: total_docs=2, df=1",
    lambda: tfidf.score({"rare": 1}, {"rare": 1}, 2, ["rare"]))
if s is not None:
    check("TF-IDF: total_docs=2 gives positive score", s > 0, f"got {s}")

# 1g. doc_length=0 for BM25
s = check_no_exception("BM25: doc_length=0",
    lambda: bm25.score({"word": 1}, {"word": 3}, 10, 0, 45.0, ["word"]))
if s is not None:
    check("BM25: doc_length=0 gives finite score", math.isfinite(s), f"got {s}")
    # length_norm = 1 - b + b*(0/45) = 1 - 0.75 = 0.25, denominator = 1 + 1.5*0.25 = 1.375 > 0 → OK

# ─────────────────────────────────────────────────────────────────────────────
# 2. Adversarial W2 Data
# ─────────────────────────────────────────────────────────────────────────────

section("2. ADVERSARIAL / MISMATCHED W2 DATA")

# 2a. Term in doc_tf but not in doc_freq
s = check_no_exception("TF-IDF: term in doc_tf but missing from doc_freq",
    lambda: tfidf.score({"ghost": 5}, {}, 10, ["ghost"]))
if s is not None:
    check("TF-IDF: missing doc_freq term → 0.0", s == 0.0, f"got {s}")

# 2b. Negative TF (corrupted data)
s = check_no_exception("TF-IDF: negative tf (corrupted data)",
    lambda: tfidf.score({"word": -3}, {"word": 3}, 10, ["word"]))
if s is not None:
    # tf=-3 × IDF=0.52 = -1.56 → negative score — should we clamp?
    check("TF-IDF: negative tf → score >= 0 (should clamp tf)",
          s >= 0.0, f"got {s} (NEGATIVE SCORE from negative TF)")

# 2c. BM25: doc_id in candidates but not in doc_lengths (Person 4 passes wrong dict)
result = check_no_exception("BM25: doc_id missing from doc_lengths",
    lambda: ranker.rank(RankingMode.BM25,
                        {99: {"word": 3}}, {"word": 3}, 10, ["word"],
                        avg_doc_length=45.0,
                        doc_lengths={}))  # 99 not in doc_lengths
if result is not None:
    check("BM25: missing doc_id in doc_lengths → still produces score",
          99 in result, f"got keys={list(result.keys())}")
    if 99 in result:
        check("BM25: missing doc_length → treated as doc_length=0 (finite score)",
              math.isfinite(result[99]), f"got {result[99]}")

# 2d. VECTOR: doc_id in candidates but not in doc_terms_full
result = check_no_exception("VECTOR: doc_id missing from doc_terms_full",
    lambda: ranker.rank(RankingMode.VECTOR,
                        {99: {"word": 3}}, {"word": 3}, 10, ["word"],
                        doc_terms_full={}))  # 99 not in doc_terms_full
if result is not None:
    check("VECTOR: missing doc_terms_full entry → score=0.0 (graceful)",
          result.get(99, -1) == 0.0, f"got {result.get(99)}")

# 2e. All query terms have tf=0 in all documents
candidates = {0: {"a": 0, "b": 0, "c": 0},
              1: {"a": 0, "b": 0}}
s_map = check_no_exception("TF-IDF: all TFs = 0 across all candidates",
    lambda: ranker.rank(RankingMode.TFIDF, candidates, {"a": 2, "b": 2, "c": 1},
                        10, ["a", "b", "c"]))
if s_map is not None:
    check("TF-IDF: all TF=0 → all scores = 0.0",
          all(v == 0.0 for v in s_map.values()), f"got {s_map}")

# 2f. Query term not in ANY doc_freq (typo in query)
s = check_no_exception("TF-IDF: query term completely absent from corpus",
    lambda: tfidf.score({"xyzzy": 5}, {}, 100, ["xyzzy"]))
if s is not None:
    check("TF-IDF: unknown query term → 0.0", s == 0.0, f"got {s}")

# 2g. avg_doc_length = 0 for BM25
s = check_no_exception("BM25: avg_doc_length=0 (degenerate corpus)",
    lambda: bm25.score({"word": 3}, {"word": 3}, 10, 20, 0.0, ["word"]))
if s is not None:
    check("BM25: avg_doc_length=0 → finite score (no ZeroDivisionError)",
          math.isfinite(s), f"got {s}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. NaN / Inf / Float Edge Cases
# ─────────────────────────────────────────────────────────────────────────────

section("3. NaN / Inf / FLOAT EDGE CASES")

# 3a. NaN scores in TopKRetriever — known Python heapq issue with NaN
scores_with_nan = {0: float('nan'), 1: 2.0, 2: 3.0}
result = check_no_exception("TopK: NaN score in candidates — does not crash",
    lambda: TopKRetriever.get_top_k(scores_with_nan, k=2))
if result is not None:
    result_ids = [r.doc_id for r in result]
    check("TopK: NaN doc excluded or handled gracefully (no NaN in top-k)",
          not any(math.isnan(r.score) for r in result),
          f"got {[(r.doc_id, r.score) for r in result]}")

# 3b. Inf scores
scores_inf = {0: float('inf'), 1: 2.0, 2: 1.0}
result = check_no_exception("TopK: Inf score in candidates — does not crash",
    lambda: TopKRetriever.get_top_k(scores_inf, k=2))
if result is not None:
    check("TopK: Inf doc appears first",
          result[0].doc_id == 0, f"got {[(r.doc_id, r.score) for r in result]}")

# 3c. All NaN scores
all_nan = {i: float('nan') for i in range(5)}
result = check_no_exception("TopK: All NaN scores — does not crash",
    lambda: TopKRetriever.get_top_k(all_nan, k=3))
# Just checking no crash — ordering of NaN is undefined

# 3d. VectorScorer: IDF formula with df=total_docs → log10(1) = 0 → zero weight
s = check_no_exception("Vector: all query terms have IDF=0 (df=N)",
    lambda: vector.score(["common"], {"common": 5, "other": 2},
                         {"common": 10, "other": 3}, 10))
if s is not None:
    # "common" has df=10=N, IDF=log10(1)=0 → weight=0 → not in query_vec → cosine=0
    check("Vector: IDF=0 term → cosine=0.0", s == 0.0, f"got {s}")

# 3e. Score of exactly 0.0 for a valid term
s = check_no_exception("TF-IDF: tf=0 in doc_tf dict (explicitly zero)",
    lambda: tfidf.score({"word": 0}, {"word": 3}, 10, ["word"]))
if s is not None:
    check("TF-IDF: tf=0 explicit → 0.0", s == 0.0, f"got {s}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Large Scale Performance
# ─────────────────────────────────────────────────────────────────────────────

section("4. LARGE SCALE PERFORMANCE")

# 4a. 10,000 candidate documents, 20 query terms
N_DOCS = 10_000
N_TERMS = 20
big_candidates = {
    i: {f"term{j}": (i % (j + 1)) + 1 for j in range(N_TERMS)}
    for i in range(N_DOCS)
}
big_doc_freq = {f"term{j}": N_DOCS // (j + 2) + 1 for j in range(N_TERMS)}
big_query = [f"term{j}" for j in range(N_TERMS)]

t0 = time.perf_counter()
result = check_no_exception(f"TF-IDF: rank {N_DOCS:,} docs × {N_TERMS} terms",
    lambda: ranker.rank(RankingMode.TFIDF, big_candidates, big_doc_freq,
                        N_DOCS, big_query))
elapsed = time.perf_counter() - t0
if result is not None:
    check(f"TF-IDF: {N_DOCS:,} docs scored in < 1s (got {elapsed:.3f}s)",
          elapsed < 1.0, f"too slow: {elapsed:.3f}s")
    check(f"TF-IDF: all {N_DOCS:,} docs got a score",
          len(result) == N_DOCS, f"got {len(result)}")

# 4b. Top-K from 10,000 docs
t0 = time.perf_counter()
top10 = check_no_exception("TopK: get_top_k from 10,000 candidates",
    lambda: TopKRetriever.get_top_k(result or {}, k=10))
elapsed = time.perf_counter() - t0
if top10 is not None:
    check(f"TopK: 10,000→top10 in < 0.1s (got {elapsed:.4f}s)",
          elapsed < 0.1, f"too slow: {elapsed:.4f}s")
    check("TopK: exactly 10 results", len(top10) == 10, f"got {len(top10)}")

# 4c. BM25 at scale
big_doc_lengths = {i: (i % 100) + 10 for i in range(N_DOCS)}
t0 = time.perf_counter()
result_bm = check_no_exception(f"BM25: rank {N_DOCS:,} docs",
    lambda: ranker.rank(RankingMode.BM25, big_candidates, big_doc_freq,
                        N_DOCS, big_query,
                        avg_doc_length=55.0,
                        doc_lengths=big_doc_lengths))
elapsed = time.perf_counter() - t0
if result_bm is not None:
    check(f"BM25: {N_DOCS:,} docs in < 2s (got {elapsed:.3f}s)",
          elapsed < 2.0, f"too slow: {elapsed:.3f}s")

# 4d. Very long query (500 terms, many repeated)
long_query = [f"term{i % N_TERMS}" for i in range(500)]
s = check_no_exception("TF-IDF: 500-term query (many repeats)",
    lambda: tfidf.score(
        {f"term{j}": j + 1 for j in range(N_TERMS)},
        big_doc_freq, N_DOCS, long_query))
if s is not None:
    check("TF-IDF: 500-term query → finite score", math.isfinite(s), f"got {s}")

# 4e. 1000 docs, MMR pool
scores_large = {i: float(N_DOCS - i) for i in range(N_DOCS)}
t0 = time.perf_counter()
pool = check_no_exception("TopK: MMR pool from 10,000 docs",
    lambda: TopKRetriever.get_top_k_for_mmr(scores_large, pool_size=20))
elapsed = time.perf_counter() - t0
if pool is not None:
    check(f"TopK: MMR pool in < 0.1s (got {elapsed:.4f}s)",
          elapsed < 0.1, f"too slow: {elapsed:.4f}s")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Boundary Conditions
# ─────────────────────────────────────────────────────────────────────────────

section("5. BOUNDARY CONDITIONS")

# 5a. k = -1 for TopK
result = check_no_exception("TopK: k=-1",
    lambda: TopKRetriever.get_top_k({0: 1.0, 1: 2.0}, k=-1))
if result is not None:
    check("TopK: k=-1 → empty list", result == [], f"got {result}")

# 5b. k = sys.maxsize
result = check_no_exception("TopK: k=sys.maxsize",
    lambda: TopKRetriever.get_top_k({0: 1.0, 1: 2.0}, k=sys.maxsize))
if result is not None:
    check("TopK: k=maxsize → all docs returned", len(result) == 2, f"got {len(result)}")

# 5c. total_docs = 1
s = check_no_exception("TF-IDF: total_docs=1, df=1",
    lambda: tfidf.score({"word": 5}, {"word": 1}, 1, ["word"]))
if s is not None:
    # IDF = log10(1/1) = 0 → score = 0
    check("TF-IDF: total_docs=1, df=1 → score=0 (IDF=0)", s == 0.0, f"got {s}")

# 5d. Empty candidates for Ranker (all modes)
for mode in RankingMode:
    result = check_no_exception(f"Ranker: empty candidates ({mode.value})",
        lambda m=mode: ranker.rank(m, {}, {}, 10, [],
                                    avg_doc_length=45.0,
                                    doc_lengths={},
                                    doc_terms_full={}))
    if result is not None:
        check(f"Ranker: empty candidates ({mode.value}) → {{}}", result == {}, f"got {result}")

# 5e. Query with duplicate terms in different cases (case sensitivity)
# W2 should normalize, but let's see what happens with "Machine" vs "machine"
s = check_no_exception("TF-IDF: case mismatch 'Machine' vs 'machine' in doc",
    lambda: tfidf.score({"machine": 3}, {"machine": 3, "Machine": 1}, 10, ["Machine"]))
if s is not None:
    # "Machine" TF in doc is 0 (key is "machine"), doc_freq["Machine"]=1
    # This may produce 0 score if doc_tf doesn't have "Machine"
    # Correct: W2 should normalize, this tests that it doesn't crash
    check("TF-IDF: case mismatch doesn't crash", math.isfinite(s), f"got {s}")

# 5f. Single document, single term
s = check_no_exception("TF-IDF: corpus of 1 doc, 1 unique term",
    lambda: tfidf.score({"unique": 1}, {"unique": 1}, 1, ["unique"]))
# IDF = log10(1/1) = 0, so score = 0 — this is correct behavior
if s is not None:
    check("TF-IDF: 1-doc corpus, df=1 → 0.0 (expected: IDF=log10(1)=0)",
          s == 0.0, f"got {s}")

# 5g. BM25 with b=0.0 and k1=0.0 (degenerate — only IDF matters)
sc = BM25Scorer(k1=0.0, b=0.0)
s = check_no_exception("BM25: k1=0, b=0 (TF ignored, IDF only)",
    lambda: sc.score({"word": 5}, {"word": 3}, 10, 20, 45.0, ["word"]))
if s is not None:
    check("BM25: k1=0 → finite score", math.isfinite(s), f"got {s}")
    # With k1=0: numerator = tf*(0+1) = tf, denominator = tf + 0*(1-0+0) = tf
    # → component = IDF × 1 regardless of TF
    s2 = sc.score({"word": 100}, {"word": 3}, 10, 20, 45.0, ["word"])
    check("BM25: k1=0 → score same regardless of TF",
          abs(s - s2) < 1e-9, f"tf=5 score={s}, tf=100 score={s2}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. Consistency / Determinism
# ─────────────────────────────────────────────────────────────────────────────

section("6. CONSISTENCY & DETERMINISM")

doc_tf = {"machine": 3, "learning": 4}
doc_freq = {"machine": 3, "learning": 4}

# 6a. Same input → same output every time
scores_run1 = [tfidf.score(doc_tf, doc_freq, 10, ["machine", "learning"]) for _ in range(100)]
check("TF-IDF: 100 identical calls → identical results",
      len(set(scores_run1)) == 1, f"got {len(set(scores_run1))} distinct values")

# 6b. Ranker ordering is stable on equal scores
equal_scores = {i: 1.0 for i in range(100)}
top10_a = TopKRetriever.get_top_k(equal_scores, k=10)
top10_b = TopKRetriever.get_top_k(equal_scores, k=10)
check("TopK: equal scores → stable order across runs",
      [r.doc_id for r in top10_a] == [r.doc_id for r in top10_b],
      f"run1={[r.doc_id for r in top10_a[:5]]}, run2={[r.doc_id for r in top10_b[:5]]}")

# 6c. Cosine symmetry: cosine(a, b) == cosine(b, a)
va = {"x": 1.5, "y": 2.0, "z": 0.5}
vb = {"y": 1.0, "z": 2.0, "w": 3.0}
sim_ab = VectorScorer.cosine_similarity(va, vb)
sim_ba = VectorScorer.cosine_similarity(vb, va)
check("Vector: cosine(a,b) == cosine(b,a) (symmetry)",
      abs(sim_ab - sim_ba) < 1e-12, f"got {sim_ab} vs {sim_ba}")

# ─────────────────────────────────────────────────────────────────────────────
# 7. Mathematical Invariants
# ─────────────────────────────────────────────────────────────────────────────

section("7. MATHEMATICAL INVARIANTS")

# 7a. TF-IDF: score is monotone increasing with TF (same IDF)
scores_by_tf = [
    tfidf.score({"word": tf}, {"word": 3}, 10, ["word"])
    for tf in [1, 2, 5, 10, 100]
]
check("TF-IDF: score monotone increasing with TF",
      all(scores_by_tf[i] < scores_by_tf[i+1] for i in range(len(scores_by_tf)-1)),
      f"scores = {[round(s,4) for s in scores_by_tf]}")

# 7b. BM25: score sub-linear in TF (saturation)
scores_bm25_tf = [
    bm25.score({"word": tf}, {"word": 3}, 10, 20, 45.0, ["word"])
    for tf in [1, 2, 5, 10, 100, 1000]
]
diffs = [scores_bm25_tf[i+1] - scores_bm25_tf[i] for i in range(len(scores_bm25_tf)-1)]
check("BM25: score increments overall shrink with TF (first diff >> last diff)",
      diffs[0] > diffs[-1],
      f"diffs = {[round(d,4) for d in diffs]}")

# 7c. Cosine is always in [0, 1]
import random
random.seed(42)
all_in_range = True
for _ in range(200):
    n = random.randint(1, 20)
    va = {f"t{i}": random.uniform(0.01, 10.0) for i in random.sample(range(50), n)}
    vb = {f"t{i}": random.uniform(0.01, 10.0) for i in random.sample(range(50), n)}
    sim = VectorScorer.cosine_similarity(va, vb)
    if not (0.0 <= sim <= 1.0):
        all_in_range = False
        check("Vector: cosine in [0,1] for random vectors", False, f"got {sim}")
        break
if all_in_range:
    check("Vector: cosine in [0,1] for 200 random vector pairs", True)

# 7d. TopK results are always sorted descending
for _ in range(50):
    n = random.randint(5, 100)
    scored = {i: random.uniform(-10, 100) for i in range(n)}
    k = random.randint(1, n)
    results = TopKRetriever.get_top_k(scored, k)
    sc = [r.score for r in results]
    if sc != sorted(sc, reverse=True):
        check("TopK: always sorted descending (50 random tests)", False,
              f"got unsorted: {sc[:5]}")
        break
else:
    check("TopK: always sorted descending (50 random tests)", True)

# 7e. BM25 score increases then saturates as doc_length decreases (below avgdl)
# Shorter doc → higher score (b=0.75)
scores_by_len = [
    bm25.score({"word": 3}, {"word": 3}, 100, dl, 50.0, ["word"])
    for dl in [200, 100, 50, 25, 1]
]
check("BM25: score increases as doc_length decreases below avg",
      all(scores_by_len[i] < scores_by_len[i+1] for i in range(len(scores_by_len)-1)),
      f"scores = {[round(s,4) for s in scores_by_len]}")

# 7f. TF-IDF: IDF decreases as df increases
idfs = []
for df in [1, 2, 5, 10, 50, 99]:
    s = tfidf.score({"word": 1}, {"word": df}, 100, ["word"])
    idfs.append(s)  # s = 1 × IDF, so s IS the IDF
check("TF-IDF: IDF strictly decreases as df increases",
      all(idfs[i] > idfs[i+1] for i in range(len(idfs)-1)),
      f"IDFs = {[round(v,4) for v in idfs]}")

# ─────────────────────────────────────────────────────────────────────────────
# 8. VectorScorer Specific Stress Tests
# ─────────────────────────────────────────────────────────────────────────────

section("8. VECTOR SCORER SPECIFIC")

# 8a. Very high-dimensional sparse vector (500 unique terms)
big_terms = {f"w{i}": (i % 5) + 1 for i in range(500)}
big_df = {f"w{i}": 10 for i in range(500)}
s = check_no_exception("Vector: 500-dimensional sparse vector",
    lambda: vector.score([f"w{i}" for i in range(0, 50)], big_terms, big_df, 100))
if s is not None:
    check("Vector: 500-dim result in [0,1]", 0.0 <= s <= 1.0, f"got {s}")

# 8b. Single overlapping term only
s = check_no_exception("Vector: single shared term only",
    lambda: vector.score(["a"], {"a": 5, "b": 3, "c": 2}, {"a": 2, "b": 3, "c": 5}, 10))
if s is not None:
    check("Vector: single shared term → 0 < cosine <= 1", 0 < s <= 1, f"got {s}")

# 8c. build_tfidf_vector: all terms have df=0 → empty vector
vec = check_no_exception("Vector: build_tfidf_vector all df=0",
    lambda: VectorScorer.build_tfidf_vector({"a": 3, "b": 2}, {}, 10))
if vec is not None:
    check("Vector: build_tfidf_vector all df=0 → empty dict", vec == {}, f"got {vec}")

# ─────────────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────────────────────

total = PASS + FAIL
print(f"\n{'═'*60}")
print(f"  STRESS TEST RESULTS: {PASS}/{total} passed, {FAIL} failed")
print(f"{'═'*60}")

if BUGS:
    print(f"\n  🐛 BUGS FOUND ({len(BUGS)}):")
    for i, (label, note) in enumerate(BUGS, 1):
        print(f"  {i}. {label}")
        if note:
            print(f"     {note}")
else:
    print("\n  No bugs found! ✅")

sys.exit(0 if FAIL == 0 else 1)
