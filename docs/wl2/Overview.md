# Worklet 2 — Inverted Index & Query Processing
### Design & Data-Flow Overview

## 1. Scope

Worklet 2 turns the normalized token streams produced by Worklet 1 into index structures that can answer four kinds of queries — **boolean, phrase, prefix, and wildcard** — without scanning every document at query time. It sits in the middle of the pipeline: it reads what Worklet 1 stored, and it hands Worklet 3 everything needed to rank, cache, and serve results.

```
 Worklet 1                    Worklet 2                               Worklet 3
 ──────────                   ──────────                              ──────────
 Crawl → Parse → Tokenize --> Inverted index --> Positional index --> Ranking (TF-IDF / BM25)
 Store Document records       Boolean query engine (AND/OR/NOT)       Top-k via min-heap
 (doc_id, tokens, metadata)   Trie (prefix / wildcard)                LRU cache
                               Optimized postings merge (skip ptrs)    CLI / REPL + evaluation
```

## 2. Interface A — Input Received from Worklet 1

| Field | Type | Notes |
|---|---|---|
| `doc_id` | int / str | Unique per crawled page; the primary key used throughout the index |
| `tokens` | `List[str]` | Normalized (lowercased, punctuation stripped, stop-words removed); **order must be preserved** — Step 2 needs token positions |
| `url` | str | Carried through for display/citation; not used by indexing itself |
| `title` | str | Optional, used later for result display |
| `text` | str | Optional clean text, useful for snippet/highlight generation |
| `metadata` | dict | e.g. crawl timestamp; passed through, not indexed |

This arrives via Worklet 1's file-based store — one record per crawled page. Worklet 2 reads the store once, at index-build time, and does not re-fetch or re-parse anything; cleaning and tokenization are entirely Worklet 1's job.

## 3. The Five Processing Steps

### Step 1 — Inverted Index Construction

Builds the core term → postings mapping that every later step reads from.

| Aspect | Details |
|---|---|
| Input | Tokenized documents: `(doc_id, tokens: List[str])` for every page |
| Output | `index: Dict[str, List[Tuple[doc_id, freq]]]` — term → postings list, sorted by `doc_id` |
| Data Structures | Hash map (`dict`) as the outer index; a sorted list of `(doc_id, freq)` per term; a temporary `Counter` per document during the scan |
| Core Algorithm | Single-pass accumulation — count term frequencies per document, then merge each document's counts into the global map |
| Complexity | O(T), T = total tokens in the corpus (each token touched once) |

Keeping each postings list sorted by `doc_id` at build time is what makes Step 5's merge optimization possible later, so it's worth enforcing here rather than sorting on demand.

### Step 2 — Positional Index for Phrase Queries

Extends Step 1 with *where* each term occurs, not just *how often*.

| Aspect | Details |
|---|---|
| Input | Same tokenized documents, scanned left-to-right so each token's position is known |
| Output | `positional_index: Dict[str, Dict[doc_id, List[int]]]` — term → doc_id → sorted list of positions |
| Data Structures | Nested hash maps (`dict` of `dict` of `list`); position lists come out sorted for free, since tokens are scanned in order |
| Core Algorithm | Same scan as Step 1, appending the running position instead of only incrementing a counter. Phrase matching for two adjacent terms is a two-pointer merge over their position lists, testing `pos(B) == pos(A) + 1` |
| Complexity | Build: O(T). Two-term phrase check per candidate doc: O(\|posA\| + \|posB\|); an *n*-word phrase chains *n* − 1 such checks |

Note: `freq` from Step 1 is just `len(positions)` here, so in a production system the two indexes are usually built in one pass. They're kept as separate steps in this worklet to match the spec's incremental structure.

### Step 3 — Boolean Query Processing (AND / OR / NOT)

Answers set-theoretic queries over the vocabulary built in Step 1.

| Aspect | Details |
|---|---|
| Input | A boolean expression, e.g. `crawler AND (index OR trie) NOT java`, plus the doc-id sets underlying each term's postings |
| Output | A single `set[doc_id]` satisfying the expression |
| Data Structures | Python `set` for O(1) membership checks; a small parse tree / postfix (RPN) queue for the expression |
| Core Algorithm | Tokenize the query, apply operator precedence (NOT tightest, then AND, then OR) to build a parse tree, then evaluate bottom-up with `intersection`, `union`, `difference` |
| Complexity | Each set op costs O(min(m,n)) to O(m+n) on postings of size m, n; overall cost scales with the terms involved, not the whole corpus |

This is where the "Discrete" half of the worklet shows up directly: AND/OR/NOT *are* set intersection/union/complement, and De Morgan's laws (`NOT (A AND B) = (NOT A) OR (NOT B)`) are a legitimate way to simplify a query tree before evaluating it, avoiding an expensive "universe minus X" pass where possible.

### Step 4 — Prefix & Wildcard Search via Trie

Resolves patterns like `comp*` against the vocabulary, then reuses Step 1's postings.

| Aspect | Details |
|---|---|
| Input | A prefix (`comp*`) or wildcard pattern, plus the vocabulary — i.e. the key set of the Step 1 index |
| Output | Matching vocabulary terms, then the union of their postings → `set[doc_id]` |
| Data Structures | Trie: each node holds a `char → child` map plus an `is_end` flag; built once over the vocabulary |
| Core Algorithm | Build by inserting every vocabulary term. Prefix query: walk the trie along the prefix, then DFS/BFS the subtree to collect completions. General wildcard: split around the `*`, walk the fixed part in the trie, filter the rest against the remaining pattern |
| Complexity | Build: O(sum of term lengths). Prefix lookup: O(len(prefix) + k), k = number of matches |

### Step 5 — Optimized Postings Merge (Sorted Merge + Skip Pointers)

Speeds up the AND-type merges that Steps 2 and 3 both rely on.

| Aspect | Details |
|---|---|
| Input | Two or more postings lists from Step 1, already sorted by `doc_id` |
| Output | The merged/intersected postings list, plus a benchmark of plain vs. skip-pointer merge |
| Data Structures | Sorted arrays of `doc_id`; skip pointers inserted roughly every √L entries in a list of length L, each jumping ahead to a later entry |
| Core Algorithm | Baseline: two-pointer sorted merge. Optimized: while advancing, jump via a skip pointer whenever its target is still ≤ the other list's current value, skipping a run of comparisons that can't possibly match |
| Complexity | Plain merge: O(m+n) worst case — already well below the naive O(m×n) nested-loop check. Skip-pointer merge keeps the same worst case but does fewer comparisons in practice, closer to O(m/√L + n) when matches are sparse |

To measure the speed-up: run the same set of AND/phrase queries through both merge routines, log either comparison counts or wall-clock time (`time.perf_counter()`), and report the ratio — the gain should be most visible on queries mixing a short postings list with a much longer one.

## 4. Interface B — Output Delivered to Worklet 3

| Artifact | Form | Why Worklet 3 Needs It |
|---|---|---|
| Inverted index | `term → [(doc_id, freq)]` | Term frequency for TF-IDF/BM25; postings-list length doubles as document frequency |
| Positional index | `term → doc_id → [positions]` | Phrase-aware scoring and locating exact match positions for highlighting |
| `boolean_query()`, `phrase_query()`, `prefix_query()`, `wildcard_query()` | Functions returning `set[doc_id]` | The CLI/REPL calls these to get a candidate set, then ranks *only* that set instead of the whole corpus |
| Vocabulary trie | Trie object | Reusable for autosuggest / query correction in the CLI |
| `doc_id` → metadata map | `dict` | Title, URL, and text needed to render and highlight results |
| Document length per `doc_id` | `dict[doc_id, int]` | Cheap to derive in Step 1 (sum of a doc's term frequencies); needed for TF-IDF/BM25 length normalization |

The boundary is deliberate: Worklet 2's functions return **candidate doc-id sets**, not scores or an ordering. Ranking, top-k selection, caching, and CLI formatting are entirely Worklet 3's responsibility — Worklet 2 never sorts by relevance.

## 5. Quick Reference

| Step | Data Structure(s) | Core Algorithm | Complexity |
|---|---|---|---|
| 1. Inverted index | Hash map + sorted postings | Single-pass frequency accumulation | O(T) |
| 2. Positional index | Nested hash maps + position lists | Position-tagged scan; two-pointer phrase match | O(T) build / O(m+n) per phrase |
| 3. Boolean query | Sets + parse tree | Intersection / union / difference | O(m+n) per operation |
| 4. Prefix / wildcard | Trie | Traversal + subtree collection | O(len(pattern) + k) |
| 5. Merge optimization | Sorted arrays + skip pointers | Two-pointer merge with skips | O(m+n) worst case, sub-linear in practice |

*(T = total corpus tokens, m/n = postings-list sizes, k = number of matches, L = postings-list length)*
