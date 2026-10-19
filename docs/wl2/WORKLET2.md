# Worklet 2: Implementation and Testing Guide

## Purpose and scope

Worklet 2 is the C++ indexing and candidate-retrieval stage between Worklet 1's processed corpus and Worklet 3's ranking layer. It reads document records, builds term/document data, and provides code for positional lookup, Boolean composition, prefix/wildcard vocabulary lookup, and a query bridge. Its intended output is a set/map of matching document IDs with term frequencies; ranking and ordering belong to Worklet 3.

The repository currently contains several related components at different levels of integration. In particular, the standalone positional-index executable, the standalone trie, the reusable postings operations, and the query processor/bridge are separate pieces. The query processor does not currently call the trie or the `PostingsOperations` class. This guide describes the implemented behavior rather than treating the planned architecture as fully connected.

## Technology and source layout

The implementation uses standard C++17 and the C++ standard library. It does not use an external search/index library. The Makefile uses `g++` by default and builds the index demo and postings-operation test/benchmark targets. The Python bridge uses pybind11, but a bridge build target is not currently declared in `wl2/Makefile`.

| Path | Role |
|---|---|
| `wl2/Inverted_Index/CorpusReader.h/.cpp` | `Document` record and JSON Lines corpus reader |
| `wl2/Inverted_Index/Posting.h/.cpp` | Per-term postings: doc ID, token positions, and frequency |
| `wl2/Inverted_Index/HashMap.h/.cpp` | Hash table from terms to posting lists |
| `wl2/Inverted_Index/main.cpp` | Standalone index-building and interactive single-term lookup demo |
| `wl2/trie/trie.h/.cpp` | Compressed trie, reversed trie, and 3-gram-assisted infix lookup |
| `wl2/Pos_Inverted_Index/query_parser.h/.cpp` | Query parsing, matching, corpus stats, and W3-facing API |
| `wl2/Pos_Inverted_Index/python_bindings.cpp` | Optional pybind11 module exposing the query API to Python |
| `wl2/boolean_operations/PostingsOperations.h/.cpp` | Sorted posting-list intersection, union, difference, and skip-style intersection |
| `tests/wl2/` | C++ tests for the query bridge and posting operations, plus benchmark |

## Input contract and corpus loading

`readDocuments(path)` reads a JSONL file: each nonempty physical line is expected to contain one JSON object. It extracts `doc_id`, `title`, `url`, `text`, and `tokens`; IDs may be numeric or quoted numeric strings. If `tokens` is absent/empty and `text` is nonempty, it falls back to whitespace-splitting `text`.

The reader is a small purpose-built parser, not a general JSON library. It handles common JSON string escapes, scans top-level fields, skips nested values, and ignores records whose ID cannot be read. It does not report malformed-line diagnostics or expose Worklet 1 metadata such as `fetched_at`. Prefer supplying token arrays: the text fallback splits on whitespace and does not reproduce Worklet 1 normalization.

`Document` stores integer `docId`, `title`, `url`, `text`, and an ordered `vector<string>` of tokens. Token order matters for positions and phrase matching. IDs need to be unique for the index/query semantics to behave as intended.

## Positional inverted index

`HashMap` maps each term to a heap-allocated `PostingList`. It uses a 211-bucket hash table with separate chaining and grows the bucket array when the entry load factor exceeds 0.75. The hash function is a djb2-style rolling hash. A posting records:

* `docId`: document identifier;
* `positions`: zero-based offsets in that document's token vector;
* `frequency`: number of occurrences, incremented with each position.

`HashMap::update(term, docId, position)` creates/looks up the term list and adds the occurrence. `PostingList::addOccurrence` finds an existing document posting and appends the position, or inserts a new posting into ascending document-ID order. Since documents are read and tokens scanned in order, positions are ascending. A posting's frequency is the size of its positions vector.

`wl2/Inverted_Index/main.cpp` demonstrates this by indexing each token at its vector offset, printing all terms and postings, and offering an interactive exact-term lookup. It reads the hard-coded relative path `sample_input.json` from the current directory; `make -C wl2 run` changes to `wl2/Inverted_Index` before launching, so this resolves to the included sample file.

## Query processing and matching behavior

The separate query processor is initialized with a pointer to a `vector<Document>` using `initialize_query_processor`. It builds:

* `terms`: document ID to normalized term-frequency map;
* `df`: normalized term to number of documents containing it;
* `version`: a string derived from a 64-bit FNV-style hash over document IDs and token content, prefixed by document count.

Normalization here lowercases bytes with the C locale; query tokenization recognizes alphanumeric characters, underscore, and `*`. Worklet 1 is expected to have already normalized corpus tokens. `get_corpus_stats()` returns document count and average **token-vector length**.

`resolve_query(query)` lexes terms, quoted phrases, parentheses, and `AND` / `OR` / `NOT`, then parses with precedence `NOT` > `AND` > `OR`. Adjacent terms are treated as implicit AND. Parenthesized expressions are supported. Boolean evaluation uses ordered `std::set<int>` collections and performs set union/intersection; `NOT` subtracts the operand from the set of all loaded document IDs.

An unquoted word matches documents whose token frequency table contains the word. A word pattern may contain one `*`; the implementation expands it by scanning the vocabulary/DF map and keeping terms matching the literal prefix and suffix around the star. This supports prefix (`comp*`), suffix (`*ing`), and infix (`c*ing`) patterns but not multiple stars. Expansion is a vocabulary scan, not a trie lookup.

Quoted phrases are matched against tokenized `Document::text` when present, otherwise against the joined token vector. Phrase terms must occur consecutively in that source. This deliberately avoids relying on Worklet 1's stop-word-filtered tokens when raw text is available. A wildcard inside a phrase is expanded to matching vocabulary alternatives for that phrase position. The standalone positional index is not currently used by this query processor.

The query result has `candidates` (document ID to frequencies for query/expanded terms present in that candidate) and `doc_freq` (term to corpus document frequency). These are ranking inputs, not ranked results. For an unmatched nonempty query term, the term can still appear in `doc_freq` with value zero.

## Vocabulary trie

`Trie` is separate from the query processor. It uses path-compressed edge labels, a 26-child array indexed by lowercase English letters, and end-of-word markers. `insert` builds the forward trie and records each word under its 3-character grams. `insertReversed` builds a reversed trie to support suffix lookup. Prefix/suffix lookup walks to a matching trie node then collects words below it. `searchForWildCard(prefix, suffix)` intersects prefix and suffix results; `searchForInfixWildCard(pattern)` uses intersected 3-gram candidate sets followed by a substring check (short patterns scan all words).

The trie assumes lowercase `a`–`z` input; punctuation, digits, and other characters are outside its safe supported alphabet. It has a small demonstration program in `trietests.cpp`. It is not currently constructed from the query processor vocabulary or called by `resolve_query`.

## Sorted postings operations

`PostingsOperations` accepts two already-built `PostingList` values and returns a new list:

* `intersect(a,b)`: documents present in both;
* `union_(a,b)`: documents in either, deduplicated by doc ID;
* `difference(a,b)`: documents in `a` but not `b` (not a corpus-wide complement);
* `intersect_with_skips(a,b)`: intersection using square-root-sized index jumps;
* `extract_doc_ids(list)`: return the document IDs only.

The first three use sorted two-pointer merge scans. Results preserve the posting payload from the left input when an ID occurs in both inputs; they do not combine frequencies or positions. The skip variant calculates jump distances from list lengths and checks the target ID before jumping, so it cannot skip over a possible match. These operations are independently tested and are not yet used by the query parser's set evaluator.

## Worklet 3 interface

`query_parser.h` exposes the C++ equivalents of the planned bridge calls:

| Function | Behavior |
|---|---|
| `initialize_query_processor(documents)` | Build term counts, DF, and version state from a caller-owned document vector |
| `resolve_query(query)` | Return candidate term frequencies and document frequencies |
| `get_corpus_stats()` | Return document count and average token-vector length |
| `get_index_version()` | Return the current content-derived version string |
| `get_doc_snippet_data(ids)` | Return title, URL, and original text, falling back to joined tokens |
| `get_doc_terms(ids)` | Return all normalized token frequencies for each requested document |

The input vector must outlive query API calls because the processor holds a pointer to it. The optional pybind11 module exposes `initialize(corpus_path)` and these functions as Python calls; its initializer owns a static document vector so the pointer remains valid. `resolve_query` returns a tuple `(candidates, doc_freq)` in Python. The bridge is an interface implementation, while the repo's current Makefile does not compile or test the Python extension.

## Build, run, and test

From the repository root:

```bash
make -C wl2 index       # build the standalone positional-index executable
make -C wl2 run         # build if needed and run it against the sample corpus
make -C wl2 test        # compile and run postings-operation tests
make -C wl2 benchmark   # compile and run intersection timing scenarios
```

`make -C wl2 test` builds `tests/wl2/QueryPostingsOperationsTest.cpp` with `PostingsOperations.cpp` and `Posting.cpp`. Despite its filename, this target tests posting-list set operations, not the query parser. `tests/wl2/Worklet3BridgeTest.cpp` contains query bridge tests, but it is not wired into the Makefile. The trie demo is also not wired into the Makefile. No test target currently compiles the corpus reader/query parser or pybind module.

### Existing automated coverage

`QueryPostingsOperationsTest.cpp` checks expected AND/OR/difference results, empty lists, identical lists, preservation of matching left-side positions, and 250 deterministic generated sorted-list pairs. For each generated pair it compares all four operations with the C++ standard-library set algorithms.

`Worklet3BridgeTest.cpp` creates a temporary JSONL corpus and asserts reader output, URL extraction, corpus stats, term lookup, phrase matching including rejection of a non-consecutive phrase, Boolean combinations, implicit AND, wildcard matching, NOT behavior, snippet retrieval, document term counts, and nonempty version output. It prints a success line when assertions pass. Because it is not in the Makefile, these checks require a separate compile command and are not included in `make test`.

`trietests.cpp` is an output-oriented manual demo for prefix and suffix searches over six words. It prints results but does not use assertions and is not part of the Makefile targets.

`PostingsOperationsBenchmark.cpp` validates that ordinary and skip-style intersections return the same IDs, warms both paths, then averages 20 operations for dense overlap, disjoint interleaved IDs, and a sparse right list of 1,000 versus 10 entries. It reports microseconds per operation and a timing ratio. This is a workload-specific timing experiment, not a correctness test or a guaranteed speedup; results include the cost of constructing returned posting lists.

## Current boundaries and implementation notes

* The main demo builds a true positional inverted index, but the query API currently builds frequency/DF maps independently from `Document` records.
* Phrase matching uses source text or joined tokens, not the positional postings structure.
* Wildcard query expansion scans the query processor vocabulary; the trie and query engine are not integrated.
* Boolean query evaluation uses `std::set<int>`; `PostingsOperations` is a separate sorted-list implementation and is not called by it.
* The corpus reader recognizes a `text` field if present and has a token-join fallback for snippets. Worklet 1's JSONL shape should be checked when integrating the actual corpus.
* There is no end-to-end target that builds the trie, parser, bridge, and Worklet 3 together. The implemented bridge API is a useful boundary, but the Makefile currently validates only the postings operations by default.

For the design intent and original component plan, see [Overview.md](Overview.md), [FolderStructure.md](FolderStructure.md), and [TaskDivision.md](TaskDivision.md).
