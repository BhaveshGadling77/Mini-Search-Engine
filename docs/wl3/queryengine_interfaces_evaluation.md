# QueryEngine, Interfaces & Evaluation (Person 4)

Files: `wl3/integration/`, `wl3/engine/{query_engine,factory,text}.py`, `wl3/cli/main.py`,
`wl3/web/app.py`, `wl3/evaluation/{engine_evaluator,synthetic_corpus}.py`.
Tests: `tests/wl3/test_query_engine.py`, `test_integration.py`, `test_engine_evaluation.py`.

## Data flow

```
CLI (wl3/cli/main.py) ─┐
                       ├─► QueryEngine.search(query, session_id, ranking_mode, k, use_mmr)
Flask (wl3/web/app.py)─┘        │
   1 session has feedback?  ◄── SessionManager (P3)
   2 no  -> CacheManager.get(key)  (LRU -> SQLite, P2)         hit -> return
   3 miss-> Worklet2Adapter.resolve_query / get_doc_terms      (only door to W2)
   4 Ranker.rank (TF-IDF | BM25 | Vector)                      (P1)
   5 TopKRetriever (k, or ~20 when MMR)                        (P1)
   6 MMR.rerank on the pool                                    (P3)
   7 get_doc_snippet_data -> list[RankedResult]
   8 store in cache (only non-personalised)
```

## Worklet 2 adapter

`Worklet2Adapter(backend)` wraps anything with the five W2 functions
(`resolve_query`, `get_corpus_stats`, `get_index_version`, `get_doc_snippet_data`,
`get_doc_terms`), checks they exist, normalises types and converts failures to `Worklet2Error`.

* Real W2: `python3 -m wl3.cli.main --backend my_w2_module[:attr]` (or env `WL3_W2_BACKEND`).
* No W2 yet: `InMemoryWorklet2` (`--corpus your_corpus.json` with `{"documents": [{id,title,url,text}, ...]}`, or the built-in synthetic demo corpus when no source is given).

## Decisions worth knowing for the viva

1. **Cache key** = (normalised query, mode, k, use_mmr, index_version) from P2's `build_cache_key`.
2. **Personalised searches never read or write the shared cache.**
3. **Rocchio** (P3, `update_query`) is called with an empty query and the TF-IDF vectors of every
   document the session marked relevant; the result is stored as the session's term boosts.
   At search time the strongest boosts (max 10) are appended to the scoring terms (repeated up to 2x,
   proportional to boost), so TF-IDF/BM25/Vector all honour them without changing `Ranker`.
4. **MMR** chooses *which* documents are shown; the reported score stays the relevance score and the final
   list is sorted by relevance (SRS 3.5.2).
5. **Document frequency gap:** W2 returns df only for query terms, but Vector ranking and MMR need df for
   every document term. For the other terms the engine uses "number of candidate documents containing the term".
   Ask the W2 team for a `get_doc_freq(terms)` function if exact values are needed.
6. Cold start order: `get_index_version()` is read *before* the cache is opened, so stale entries are never served.

## Evaluation

```bash
python3 -m wl3.evaluation.engine_evaluator                       # demo corpus, prints the report
python3 -m wl3.evaluation.engine_evaluator --out docs/wl3/eval.json   # also saves .json/.txt
python3 -m wl3.evaluation.engine_evaluator --backend W2MODULE --queries my_labels.json
```

`my_labels.json`: `[{"query": "machine learning", "relevant_docs": [12, 25, 41]}, ...]`.
Reports P@5/10, R@5/10, MRR, MAP and mean/median latency for cache miss, cache hit, SQLite cold start and
concurrent access (+ consistency check), and heap-vs-sort Top-K timing.
**The bundled numbers use a synthetic corpus (relevance known by construction) and are only a pipeline check.**
For the final report, label ~30-50 queries on the real W1/W2 corpus. `evaluation/evaluator.py` (P1) is the
quick offline scorer; `engine_evaluator.py` is the full end-to-end one.

## Running

```bash
python3 -m pytest tests/wl3 -q               # 236 tests
python3 run_tests.py && python3 stress_tests.py
python3 -m wl3.cli.main                       # REPL on the demo corpus (:help for commands)
python3 -m wl3.web.app                        # http://127.0.0.1:5000  (needs: pip install flask)
```
