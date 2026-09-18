# Worklet 2 — Inverted Index & Query Processing
### Final Task Breakdown (4 Members)

Member 1 - Pratham Baisane
Member 2 - Anshul Kalmegh
Member 3 - Bhavesh Gadling
Member 4 - Anurag De

## Input Contract (from Worklet 1)

Worklet 1 gives us a **file path** to a corpus stored as JSONL (one JSON object per line). Each line looks like:

```json
{
  "doc_id": 1,
  "url": "https://example.com/page1",
  "title": "...",
  "tokens": ["the", "quick", "brown", "fox"],
  "metadata": {
    "length": 342,
    "fetched_at": "..."
  }
}
```

Note: there is **no raw text/content field** — only `tokens`. Anything Worklet 2 needs to show as a "snippet" has to be reconstructed from `tokens` (see Open Decisions).

---

## Member 1 — Corpus Loading, Positional Inverted Index & Frequency Tables

**Goal:** Read the corpus Worklet 1 hands us and turn it into every data structure the other three members (and Worklet 3) depend on.

**Tasks**
- `load_corpus(path)`: stream the JSONL file line by line, parse each into an internal doc record `{doc_id, title, url, tokens, length, fetched_at}`.
- Build the **positional inverted index**: `term → { doc_id: [positions] }`
  - Example: `index["ball"] = {0: [1, 4], 2: [9, 18]}`
- Build the **forward index / per-doc term-frequency table**: `doc_id → {term: freq}` — this is just `Counter(tokens)` per doc, and doubles as the source for both `get_term_freq` and `get_doc_terms` (used by Worklet 3, see below). No need to store frequency twice — freq is `len(positions)` if you want to save memory instead.
- Compute **corpus stats** at load time: `total_docs`, `avg_doc_length` (from `metadata.length`, or `len(tokens)` if length isn't reliable).
- Track an **index version** — e.g. a hash of the corpus path + build timestamp — bumped every time `build_index()` runs, so cached results can be invalidated correctly.
- Keep postings lists **sorted by doc_id** — Member 3's merges depend on this.
- Expose the vocabulary — Member 2 needs it to build the trie.

**Interface to expose (internal — consumed by Members 2, 3, 4)**
```
load_corpus(path) -> None
build_index() -> None
get_postings(term) -> dict[doc_id, list[positions]]
get_term_freq(term, doc_id) -> int
get_doc_freq(term) -> int                    # number of docs containing term
get_doc_term_freqs(doc_id) -> dict[term, int]  # forward index for one doc
get_document(doc_id) -> dict                  # {title, url, tokens, length, fetched_at}
get_vocabulary() -> list[str]
get_corpus_stats() -> dict                    # {total_docs, avg_doc_length}
get_index_version() -> str | int
```

**Depends on:** Worklet 1's corpus path.
**Blocks:** Members 2, 3, 4 (everyone reads from this index).

---

## Member 2 — Trie (Prefix & Wildcard)

**Goal:** Fast lookup over the vocabulary for prefix and wildcard queries (single words only, for now).

**Tasks**
- Implement `TrieNode` and `Trie` classes; insert every term from Member 1's `get_vocabulary()`.
- Implement prefix search: given `"ba"`, return all vocabulary terms starting with `"ba"`.
- Implement basic wildcard search (e.g. `"b*l"`, `"ba*"`) — scope to what a plain trie can reasonably do; document in code what patterns are/aren't supported yet.
- Return **terms only**, not doc IDs — resolving terms → doc IDs is Member 4's job.

**Interface to expose**
```
build_trie(vocabulary) -> None
search_prefix(prefix) -> list[str]
search_wildcard(pattern) -> list[str]
```

**Depends on:** Member 1's vocabulary.
**Blocks:** Member 4 (wildcard query resolution).

---

## Member 3 — Boolean Operations (+ Skip Lists if time permits)

**Goal:** Given doc-ID sets for individual terms, combine them per boolean logic.

**Tasks**
- Implement `AND(term1, term2)`, `OR(term1, term2)`, `NOT(term)` — each pulls postings from Member 1's index and returns matching doc IDs.
- Use sorted-list intersection/union (not naive set conversion) since postings are sorted — this is an explicit learning-outcome check.
- **Stretch goal:** add skip pointers to postings lists and use them in `AND` merges; note the measured speed-up.

**Interface to expose**
```
boolean_and(term1, term2) -> list[doc_id]
boolean_or(term1, term2) -> list[doc_id]
boolean_not(term, all_doc_ids) -> list[doc_id]
```

**Depends on:** Member 1's postings lists.
**Blocks:** Member 4 (parser calls these directly).

---

## Member 4 — Query Parser + Worklet 3 Interface (Integration Layer)

**Goal:** Everything that turns a raw query into results, and everything Worklet 3 will actually call. This member owns the boundary between Worklet 2 and Worklet 3 — **W3 never talks to Members 1–3 or to Worklet 1 directly.**

**Tasks**
- Build a query REPL/CLI loop for local testing: read a query string, detect its type, call the right function(s), print results.
- Query-type detection and routing:
  - `a AND b` / `a OR b` / `NOT a` → Member 3's boolean functions.
  - `"a b c"` (quoted) → **phrase query**: pull positions from Member 1's positional index and check the terms occur at consecutive positions in the same doc. *(Write this here — it doesn't exist elsewhere.)*
  - `a*` / `*a` → **wildcard query**: call Member 2's `search_prefix`/`search_wildcard`, then pull and union postings for each returned term from Member 1's index. *(Also written here — bridges Member 2 and Member 1.)*
- Build and expose the **5-function Worklet 3 interface**, each one a thin(ish) layer over Members 1–3:

### The 5 functions Worklet 3 calls

**1. `resolve_query(query_string)`** — called on every user search
- Runs the query through the same routing logic as the REPL above to get the matching doc IDs.
- For each matching doc, look up each query word's frequency via Member 1's `get_term_freq(word, doc_id)`.
- For each query word, look up its doc frequency via Member 1's `get_doc_freq(word)`.
- Returns:
  - `candidates: dict[int, dict[str, int]]` — per matching doc, frequency of each query word
  - `doc_freq: dict[str, int]` — per query word, how many docs contain it

**2. `get_corpus_stats()`** — called once at startup
- Pass-through to Member 1's `get_corpus_stats()`.
- Returns `{total_docs: int, avg_doc_length: float}`.

**3. `get_index_version()`** — called once at startup, before loading any saved cache
- Pass-through to Member 1's `get_index_version()`.
- Lets Worklet 3 detect a stale cache.

**4. `get_doc_snippet_data(doc_ids)`** — called after ranking, only for final top-k results
- For each `doc_id`, call Member 1's `get_document(doc_id)`.
- Returns `dict[int, dict]` → `{"title": str, "url": str, "text": str}`.
- `"text"` has to be **reconstructed by joining `tokens`**, since the corpus has no raw text field (see Open Decisions).
- W2 relays this from W1's stored data — W3 never touches W1.

**5. `get_doc_terms(doc_ids)`** — called for relevance feedback / vector ranking / MMR
- For each `doc_id`, call Member 1's `get_doc_term_freqs(doc_id)`.
- Returns `dict[int, dict[str, int]]` — every word in the doc and its frequency, not just query words.

**Depends on:** Members 1, 2, 3 and 4 (this is the integration layer).
**Blocks:** Worklet 3 (entirely, via these 5 functions).

---

## Open Decisions to Confirm as a Team
- [ ] Corpus has no raw `text`/`content` field — decide whether `get_doc_snippet_data`'s `"text"` is just `" ".join(tokens)`, or whether to ask the Worklet 1 team to add a real text field for better snippets.
- [ ] Exact wildcard pattern support in Member 2's trie (prefix-only vs. mid-word `*`).
- [ ] Whether Member 1 stores per-doc term frequency explicitly or derives it from `len(positions)` each time.
- [ ] What `get_index_version()` actually is — corpus-path hash, file mtime, or a manually bumped build counter. Pick the simplest one that works.
