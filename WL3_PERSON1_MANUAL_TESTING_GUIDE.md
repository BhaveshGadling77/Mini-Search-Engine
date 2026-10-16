# Worklet 3 — Person 1: Manual Testing & Verification Guide

This guide walks through:
1. How to run the automated tests ( and ).
2. How to manually input custom test cases via Python.
3. Easy, step-by-step test cases with hand calculations.

---

## 1. How to Run the Code

Open your terminal and run:

```bash
cd "/media/aa/New Volume/E/Abhyas kara/TY Study Material/Btech Project/Implementation/Mini-Search-Engine"

# Run the 94 unit tests
python3 run_tests.py

# Run the stress test suite you have open
python3 stress_tests.py
```

---

## 2. Easy Manual Test Cases (With Step-by-Step Math)

### Test Case 1: TF-IDF Scoring (Simple 2-Document Corpus)
- **Setup**:
  - Total documents  = 100$.
  - Query: 
  - Document frequency: $	ext{df}("python") = 10$.
  - $	ext{IDF} = \log_{10}(100 / 10) = \log_{10}(10) = 1.0$.
  - **Doc 1**: mentions "python" 3 times ($	ext{tf} = 3$).
  - **Doc 2**: mentions "python" 1 time ($	ext{tf} = 1$).
- **Expected Scores**:
  - Doc 1 score:  	imes 1.0 = 3.0$
  - Doc 2 score:  	imes 1.0 = 1.0$

### Test Case 2: BM25 Length Normalization (Short vs Long Doc)
- **Setup**:
  - Query: 
  - Total docs  = 100$, $	ext{df} = 10$.
  - Average document length = 0$ words.
  - **Doc 1 (Short)**: length = 5$ words, mentions "search" 2 times.
  - **Doc 2 (Long)**: length = 00$ words, mentions "search" 2 times.
- **Expected Outcome**:
  - Doc 1 must score higher than Doc 2 because BM25 penalizes long, dilute documents when term count is identical.

### Test Case 3: Vector Space Cosine Similarity
- **Query Vector**: 
- **Doc 1 Vector**:  (Identical) $ightarrow$ Cosine = .0$
- **Doc 2 Vector**:  (Orthogonal/No overlap) $ightarrow$ Cosine = bash.0$

### Test Case 4: Top-K Retriever with Tie-Breaking
- Scores: 
-  = 2$
- **Expected Output**: 
- *Note*: Doc 5 beats Doc 10 on tie-break because  < 10$.
