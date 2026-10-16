# Ranking & Retrieval — Technical Documentation

**Module**: `wl3/ranking/` and `wl3/retrieval/`  
**Owner**: Person 1 (Advait)  
**Language**: Python  

---

## Overview

Person 1 implements the **scoring and retrieval layer** of Worklet 3.
Three ranking algorithms are available; all are selected through a single
`Ranker` façade.  After scoring, `TopKRetriever` efficiently extracts the
best K results using a min-heap.

```
W2 Adapter (Person 4)
        │
        ├── resolve_query()   → candidates, doc_freq
        ├── get_corpus_stats() → total_docs, avg_doc_length
        └── get_doc_terms()   → full term vectors per doc
                │
                ▼
            Ranker.rank(mode, ...)
                │
                ├── TFIDF  → TFIDFScorer.score()  per doc
                ├── BM25   → BM25Scorer.score()   per doc
                └── VECTOR → VectorScorer.score() per doc
                │
                ▼
         {doc_id: score}
                │
                ▼
     TopKRetriever.get_top_k(scores, k)
                │
                ▼
     [ScoredDocument(doc_id, score), ...]
```

---

## 1. TF-IDF Scorer

**File**: [`wl3/ranking/tfidf.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/tfidf.py)  
**Class**: `TFIDFScorer`

### Formula

```
Score(q, d) = Σ  tf(t, d)  ×  log₁₀(N / df(t))
              t ∈ q
```

| Symbol | Meaning | Source |
|--------|---------|--------|
| `tf(t, d)` | Raw frequency of term t in document d | `resolve_query()[0][doc_id][term]` |
| `df(t)` | Number of docs containing term t | `resolve_query()[1][term]` |
| `N` | Total documents in corpus | `get_corpus_stats()["total_docs"]` |

### Hand-Calculated Example

Query: `"machine learning"` — Document 0 (`total_docs=10`)

| Term | TF | DF | IDF = log₁₀(10/DF) | TF × IDF |
|------|----|----|---------------------|----------|
| machine | 3 | 3 | log₁₀(3.333) ≈ 0.5229 | 1.5687 |
| learning | 4 | 4 | log₁₀(2.5) ≈ 0.3979 | 1.5916 |
| **Score** | | | | **3.1603** |

### API

```python
scorer = TFIDFScorer()
score = scorer.score(
    doc_tf      = {"machine": 3, "learning": 4},
    doc_freq    = {"machine": 3, "learning": 4},
    total_docs  = 10,
    query_terms = ["machine", "learning"],
)
# → 3.1603
```

### Design Decisions

- **Raw TF** (not log-normalised): matches the project specification "use the TF of the query terms".
- **Log base 10**: specified in the implementation plan.
- Terms with `df=0` are silently skipped (unknown corpus terms).
- Returns `0.0` for empty query or `total_docs=0`.

---

## 2. BM25 Scorer

**File**: [`wl3/ranking/bm25.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/bm25.py)  
**Class**: `BM25Scorer`

### Formula

```
BM25(q, d) = Σ  IDF(t)  ×  ─────────────  tf(t,d) × (k1 + 1)  ─────────────
             t             tf(t,d) + k1 × (1 − b + b × |d|/avgdl)

IDF(t) = log₁₀( (N − df(t) + 0.5) / (df(t) + 0.5)  +  1 )
```

| Parameter | Default | Effect |
|-----------|---------|--------|
| `k1 = 1.5` | — | TF saturation: as `tf → ∞`, component → `(k1+1) × IDF` |
| `b = 0.75` | — | Length normalisation weight: `0` = off, `1` = full |

### IDF Variant

We use the **Robertson–Sparck Jones variant** with `+1` offset.  This ensures
`IDF ≥ 0` even when `df ≈ N` (very common terms), avoiding negative score
contributions.

### Key difference from TF-IDF

BM25 needs the **total token count** of the document (`doc_length`), not
just query-term counts.  This requires `get_doc_terms(doc_ids)`:

```python
doc_terms_full = adapter.get_doc_terms(list(candidates.keys()))
doc_lengths = {did: sum(terms.values()) for did, terms in doc_terms_full.items()}
```

### Hand-Calculated Example

Query: `"machine learning"` — Document 0  
`k1=1.5, b=0.75, doc_length=16, avg_doc_length=45`

| Term | tf | df | IDF | Numerator | Denominator | Component |
|------|----|----|-----|-----------|-------------|-----------|
| machine | 3 | 3 | 0.4974 | 7.50 | 3.775 | **0.9882** |
| learning | 4 | 4 | 0.3882 | 10.00 | 4.775 | **0.8131** |
| **Score** | | | | | | **1.8013** |

### API

```python
scorer = BM25Scorer(k1=1.5, b=0.75)
score = scorer.score(
    doc_tf         = {"machine": 3, "learning": 4},
    doc_freq       = {"machine": 3, "learning": 4},
    total_docs     = 10,
    doc_length     = 16,   # FULL token count from get_doc_terms()
    avg_doc_length = 45.0,
    query_terms    = ["machine", "learning"],
)
# → 1.8013
```

---

## 3. Vector / Cosine Similarity Scorer

**File**: [`wl3/ranking/vector.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/vector.py)  
**Class**: `VectorScorer`

### Formula

```
w(t, x)  = tf(t, x) × log₁₀(N / df(t))          (TF-IDF weight)

q_vec[t] = w(t, query)
d_vec[t] = w(t, document)

cosine(q, d) = (q_vec · d_vec) / (‖q_vec‖ × ‖d_vec‖)
```

Result is in `[0, 1]`.  No pretrained embeddings or sentence-transformers.

### Important: Requires Full Document Vectors

Unlike TF-IDF and BM25 which only need query-term TFs, VectorScorer needs
**all terms** in the document to build the document vector.  This requires
calling `get_doc_terms()`.

### Static Helpers (for Person 3 — MMR and Rocchio)

```python
# Build a sparse TF-IDF vector for any term dict
vec = VectorScorer.build_tfidf_vector(
    terms={"machine": 3, "learning": 4},
    doc_freq={"machine": 3, "learning": 4},
    total_docs=10,
)
# → {"machine": 1.5687, "learning": 1.5916}

# Compute cosine between any two sparse vectors
sim = VectorScorer.cosine_similarity(vec_a, vec_b)
# → float in [0, 1]
```

These are the building blocks Person 3 needs for:
- **MMR**: document-to-document cosine similarity
- **Rocchio**: building query and document vectors for feedback

### API

```python
scorer = VectorScorer()
score = scorer.score(
    query_terms    = ["machine", "learning"],
    doc_terms_full = {"machine": 3, "learning": 4, "subset": 1, ...},
    doc_freq       = {"machine": 3, "learning": 4, ...},
    total_docs     = 10,
)
# → cosine similarity in [0, 1]
```

---

## 4. Ranker (Strategy Pattern Façade)

**File**: [`wl3/ranking/ranker.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/ranker.py)  
**Classes**: `Ranker`, `RankingMode`

### Design

`QueryEngine` (Person 4) never imports `TFIDFScorer`, `BM25Scorer`, or
`VectorScorer` directly.  It only calls `Ranker.rank()` with a `RankingMode`.
This keeps the engine decoupled from scoring internals.

```python
class RankingMode(Enum):
    TFIDF  = "tfidf"
    BM25   = "bm25"
    VECTOR = "vector"
```

### API

```python
ranker = Ranker(bm25_k1=1.5, bm25_b=0.75)

scores: dict[int, float] = ranker.rank(
    ranking_mode   = RankingMode.BM25,
    candidates     = candidates,         # from resolve_query()
    doc_freq       = doc_freq,           # from resolve_query()
    total_docs     = 10,                 # from get_corpus_stats()
    query_terms    = ["machine", "learning"],
    avg_doc_length = 45.0,               # BM25 only
    doc_lengths    = {0: 16, 4: 18, ...},# BM25 only — from get_doc_terms()
    doc_terms_full = {0: {...}, ...},    # VECTOR only — from get_doc_terms()
)
# → {0: 1.80, 4: 1.65, 7: 1.44, 1: 0.33}
```

### Parameter Requirements by Mode

| Mode | `avg_doc_length` | `doc_lengths` | `doc_terms_full` |
|------|:-:|:-:|:-:|
| TFIDF | ✗ | ✗ | ✗ |
| BM25 | ✓ required | ✓ required | ✗ |
| VECTOR | ✗ | ✗ | ✓ required |

Missing required parameters raise `ValueError` with a descriptive message.

---

## 5. Top-K Min-Heap Retriever

**File**: [`wl3/retrieval/top_k.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/retrieval/top_k.py)  
**Classes**: `TopKRetriever`, `ScoredDocument`

### Algorithm

Uses `heapq.nlargest` which maintains a min-heap of size K internally.

```
For each (doc_id, score) in all N candidates:
    If heap.size < K:
        push (score, doc_id)
    Else if score > heap.minimum:
        replace heap minimum
```

**Complexity**: O(N log K) time, O(K) space.
Significantly faster than O(N log N) full sort when K << N.

### Tie-Breaking

Equal scores are broken by **ascending doc_id** for determinism.
This ensures the same query always returns the same ordered list.

### API

```python
# Normal search path
results: list[ScoredDocument] = TopKRetriever.get_top_k(scores, k=10)

# MMR path — get a larger candidate pool
pool: list[ScoredDocument] = TopKRetriever.get_top_k_for_mmr(scores, pool_size=20)
```

```python
@dataclass
class ScoredDocument:
    doc_id: int
    score: float
```

### MMR Integration Path

```
Ranker.rank()          →  {doc_id: score}   (N candidates, e.g. 500)
        │
        ↓
TopKRetriever.get_top_k_for_mmr(pool_size=20)
        │
        ↓
MMR.rerank(pool, query_terms, k=10)   ← Person 3
        │
        ↓
Final K diverse results
```

---

## 6. Integration Guide for Other Team Members

### Person 4 (QueryEngine) — Minimal Calling Template

```python
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever

ranker = Ranker()

def search(query: str, mode: RankingMode, k: int, use_mmr: bool) -> list:
    # 1. W2 calls
    candidates, doc_freq = adapter.resolve_query(query)
    stats = adapter.get_corpus_stats()                    # call once, cache

    # 2. Extra data for BM25 / VECTOR
    doc_terms_full = {}
    doc_lengths = {}
    if mode in (RankingMode.BM25, RankingMode.VECTOR) or use_mmr:
        doc_terms_full = adapter.get_doc_terms(list(candidates.keys()))
        doc_lengths = {did: sum(t.values()) for did, t in doc_terms_full.items()}

    # 3. Score
    scores = ranker.rank(
        ranking_mode   = mode,
        candidates     = candidates,
        doc_freq       = doc_freq,
        total_docs     = stats["total_docs"],
        query_terms    = query.split(),
        avg_doc_length = stats["avg_doc_length"],
        doc_lengths    = doc_lengths or None,
        doc_terms_full = doc_terms_full or None,
    )

    # 4. Retrieve
    if use_mmr:
        pool = TopKRetriever.get_top_k_for_mmr(scores, pool_size=20)
        return mmr.rerank(pool, ...)          # Person 3
    else:
        return TopKRetriever.get_top_k(scores, k)
```

### Person 3 (MMR / Rocchio) — Using the Static Helpers

```python
from wl3.ranking.vector import VectorScorer

# Build TF-IDF vector for a document
doc_vec = VectorScorer.build_tfidf_vector(
    terms=doc_terms_full[doc_id],
    doc_freq=doc_freq,
    total_docs=total_docs,
)

# Compute doc-to-doc cosine similarity for MMR
sim = VectorScorer.cosine_similarity(doc_vec_a, doc_vec_b)
```

---

## 7. Running Tests

```bash
cd /home/aa/Downloads/btech-project-implementation/Mini-Search-Engine

# All Person 1 tests
python -m pytest tests/wl3/test_tfidf.py \
                 tests/wl3/test_bm25.py \
                 tests/wl3/test_vector.py \
                 tests/wl3/test_ranker.py \
                 tests/wl3/test_top_k.py \
                 tests/wl3/test_ranking_integration.py \
                 -v

# Quick run
python -m pytest tests/wl3/ -v --tb=short
```

Expected: **~63 tests**, all passing.

---

## 8. File Index

| File | Purpose |
|------|---------|
| [`wl3/ranking/tfidf.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/tfidf.py) | TFIDFScorer |
| [`wl3/ranking/bm25.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/bm25.py) | BM25Scorer (configurable k1, b) |
| [`wl3/ranking/vector.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/vector.py) | VectorScorer + static cosine/vector helpers |
| [`wl3/ranking/ranker.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/ranker.py) | Ranker façade + RankingMode enum |
| [`wl3/ranking/__init__.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/ranking/__init__.py) | Package re-exports |
| [`wl3/retrieval/top_k.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/retrieval/top_k.py) | TopKRetriever + ScoredDocument |
| [`wl3/retrieval/__init__.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/wl3/retrieval/__init__.py) | Package re-exports |
| [`tests/wl3/test_tfidf.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/tests/wl3/test_tfidf.py) | 11 TF-IDF unit tests |
| [`tests/wl3/test_bm25.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/tests/wl3/test_bm25.py) | 13 BM25 unit tests |
| [`tests/wl3/test_vector.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/tests/wl3/test_vector.py) | 13 Vector/Cosine unit tests |
| [`tests/wl3/test_ranker.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/tests/wl3/test_ranker.py) | 11 Ranker unit tests |
| [`tests/wl3/test_top_k.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/tests/wl3/test_top_k.py) | 15 TopK unit tests |
| [`tests/wl3/test_ranking_integration.py`](file:///home/aa/Downloads/btech-project-implementation/Mini-Search-Engine/tests/wl3/test_ranking_integration.py) | End-to-end pipeline tests |
