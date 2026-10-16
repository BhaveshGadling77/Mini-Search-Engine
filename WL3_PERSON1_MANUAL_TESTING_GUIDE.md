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
- **Doc 1 Vector**:  (Identical) $
ightarrow$ Cosine = .0$
- **Doc 2 Vector**:  (Orthogonal/No overlap) $
ightarrow$ Cosine = bash.0$

### Test Case 4: Top-K Retriever with Tie-Breaking
- Scores: 
-  = 2$
- **Expected Output**: 
- *Note*: Doc 5 beats Doc 10 on tie-break because  < 10$.

Here is the complete explanation of **what output Person 1 provides to the next person in Worklet 3**, **how to run it to see that output**, and **how to edit and see your changes in `manual_test_runner.py`**.

---

## 1. What Output Does Person 1 Give to the Next Worklet/Person?

Person 1 is responsible for **Ranking & Retrieval**. In the collaborative pipeline, Person 1 takes candidate documents from Worklet 2 and hands off data to Person 2, Person 3, and Person 4:

```
[Worklet 2 Index]
       │
       ▼ (candidates & doc frequencies)
┌────────────────────────────────────────────────────────┐
│  PERSON 1: Ranker + TopKRetriever                      │
│                                                        │
│  1. Ranker.rank(...)                                   │
│     Output: dict[int, float]  -->  {101: 4.82, 102: 2.15, ...}
│                                                        │
│  2. TopKRetriever.get_top_k_for_mmr(...)               │
│     Output: list[ScoredDocument] (Candidate pool of 20) │
│                                                        │
│  3. TopKRetriever.get_top_k(...)                       │
│     Output: list[ScoredDocument] (Final top K)         │
└────────────────────────────────────────────────────────┘
       │                                     │
       ▼                                     ▼
 [Person 3: MMR Diversifier]       [Person 2 & 4: Cache & CLI/Web Engine]
 Receives the candidate pool       Receives the ranked documents to cache
 to diversify search results       and display titles/snippets to the user
```

### The 2 Exact Output Formats You Hand Off:
1. **Raw Scored Dictionary**: `{doc_id: score}`
   ```python
   {1: 3.4521, 2: 1.8904, 5: 0.7612}
   ```
2. **Ranked ScoredDocument Objects**: `list[ScoredDocument]`
   ```python
   [
       ScoredDocument(doc_id=1, score=3.4521),
       ScoredDocument(doc_id=2, score=1.8904),
       ScoredDocument(doc_id=5, score=0.7612)
   ]
   ```

---

## 2. How to Run Your Code to Show This Hand-Off Output

You can run your code in two ways:

### Method A: See the Person 1 Hand-Off Directly (Python One-Liner / REPL)
Run this command in your terminal to see Person 1 process sample Worklet 2 candidates and produce the exact hand-off for Person 3 and Person 4:

```bash
python3 -c "
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.retrieval.top_k import TopKRetriever

ranker = Ranker()

# 1. Input received from Worklet 2:
candidates = {
    101: {'machine': 3, 'learning': 2},
    102: {'learning': 1},
    103: {'machine': 1, 'learning': 4}
}
doc_freq = {'machine': 2, 'learning': 3}
total_docs = 100
query = ['machine', 'learning']

# 2. Person 1 computes scores (Hand-off 1):
scores = ranker.rank(RankingMode.TFIDF, candidates, doc_freq, total_docs, query)
print('--- OUTPUT 1: Handed to Cache / Scoring Dict ---')
print(scores)

# 3. Person 1 extracts Top-K (Hand-off 2, given to Person 3 MMR & Person 4):
top_docs = TopKRetriever.get_top_k(scores, k=2)
print('\n--- OUTPUT 2: Handed to Person 3 MMR / Person 4 Results ---')
for rank, doc in enumerate(top_docs, start=1):
    print(f'Rank {rank} -> Doc ID: {doc.doc_id}, Score: {doc.score:.4f}')
"
```

**Output Produced:**
```text
--- OUTPUT 1: Handed to Cache / Scoring Dict ---
{101: 8.1362, 102: 1.5229, 103: 7.7891}

--- OUTPUT 2: Handed to Person 3 MMR / Person 4 Results ---
Rank 1 -> Doc ID: 101, Score: 8.1362
Rank 2 -> Doc ID: 103, Score: 7.7891
```

---

### Method B: See Your Code Running Inside the Whole Worklet 3 Search Engine
Because all 4 persons are integrated on this branch, you can run the full interactive search engine CLI. When you run this, **your Person 1 Ranker is the engine scoring the documents**:

```bash
# Search using your BM25 scorer:
python3 -m wl3.cli.main --query "machine learning neural networks" --mode bm25 --k 3

# Search using your TF-IDF scorer:
python3 -m wl3.cli.main --query "database transactions" --mode tfidf --k 3
```

**Output Produced in Terminal:**
```text
Search results for 'machine learning neural networks' (bm25, k=3):
  [1] Doc 4 (score: 6.1726) - Machine Learning: Neural Networks (note 5)
      ...activation of a system relates closely to backpropagation and activation...
  [2] Doc 0 (score: 5.5328) - Machine Learning: Neural Networks (note 1)
      ...prediction and learning are central to data. backpropagation and perceptron...
  [3] Doc 1 (score: 5.4855) - Machine Learning: Neural Networks (note 2)
      ...typical discussion of layers covers neuron together with rigging...
```

---

## 3. How to Change Testcases in `manual_test_runner.py` & See Changes

You currently have `manual_test_runner.py` open in your editor. Here is how you can customize any testcase:

### Step 1: Open `manual_test_runner.py` and modify values

In lines 28–34:
```python
# CURRENT CODE:
total_docs = 100
doc_freq = {"python": 10}
query = ["python"]

doc1_tf = {"python": 3}  # mentions 'python' 3 times
doc2_tf = {"python": 1}  # mentions 'python' 1 time
```

Change it to whatever you want to test! For example, test a multi-word query with 3 documents:
```python
# YOUR CUSTOM TEST:
total_docs = 500
doc_freq = {"neural": 20, "network": 5}
query = ["neural", "network"]

doc1_tf = {"neural": 4, "network": 2}
doc2_tf = {"neural": 1, "network": 0}
doc3_tf = {"neural": 0, "network": 5}
```
And calculate/print `s3` alongside `s1` and `s2`:
```python
s1 = scorer.score(doc1_tf, doc_freq, total_docs, query)
s2 = scorer.score(doc2_tf, doc_freq, total_docs, query)
s3 = scorer.score(doc3_tf, doc_freq, total_docs, query)

print(f"Doc 1 score: {s1:.4f}")
print(f"Doc 2 score: {s2:.4f}")
print(f"Doc 3 score: {s3:.4f}")
```

### Step 2: Save the file
Press <kbd>Ctrl</kbd> + <kbd>S</kbd> to save `manual_test_runner.py`.

### Step 3: Run the file in the terminal
In your terminal, execute:
```bash
python3 manual_test_runner.py
```

### How the Changes Reflect:
1. Python reads the updated file directly from your disk.
2. The `TFIDFScorer`, `BM25Scorer`, or `TopKRetriever` will immediately execute with your new numbers.
3. The terminal prints the updated scores and shows whether your assertions passed or failed.