# Using the `wl2/lib` text processing library

`wl2/lib` provides shared English text processing for Worklet 2. The public API is
`lib/src/include/text_processing.h`; its implementation is
`lib/src/libfreeling/text_processing.cc`.

## Processing behavior

The library lowercases tokens, splits text on non-alphanumeric characters
(preserving `_` and `*`), removes the built-in English stopword list, and
lemmatizes remaining words. Index construction and query parsing must use these
same functions so that both sides produce identical terms. The lemmatizer uses
a small irregular-word map and common English suffix rules. It is suitable for
this educational search engine, not a full linguistic analyzer.

## API

```cpp
#include "text_processing.h"

auto raw_words = wl2::tokenize("The cats were running");
auto index_terms = wl2::process_text("The cats were running");
// index_terms: {"cat", "run"}
std::string lemma = wl2::lemmatize("running"); // "run"
bool ignored = wl2::is_stopword("the");         // true
```

Use `process_text` when converting document text or a query/phrase into index
terms. Use `lemmatize` for a single non-stopword lookup. Wildcard patterns are
kept intact by `process_text`; do not lemmatize their prefix or suffix
independently.

## Worklet 2 integration

The current index builder and query parser include the library using a path
relative to their source files. When compiling either component, also compile
`lib/src/libfreeling/text_processing.cc`. The `wl2/Makefile` already adds this
source to the CLI, bridge test, and Python binding builds.

For a new index path, process the document text once, then index each returned
term. For query handling, process ordinary terms before lookup; retain Boolean
operators and wildcard syntax in the parser. Phrase text should also go through
`process_text`, and document phrase text should use the same transformation.
This means stopwords do not occupy positions in phrase matching, consistent
with their omission from the index.
Boolean operators are reserved in uppercase (`AND`, `OR`, `NOT`); lowercase
forms are treated as stopwords. A single `*` can match an infix wildcard term,
such as `f*x`.

When changing the stopword list or lemmatizer, rebuild the index and keep query
processing on the same library version. Existing serialized indexes contain
their old vocabulary and are not compatible with changed preprocessing rules.

## Build example

```sh
g++ -std=c++17 -Iwl2/lib/src/include \
  wl2/Pos_Inverted_Index/query_parser.cpp \
  wl2/Inverted_Index/CorpusReader.cpp \
  wl2/lib/src/libfreeling/text_processing.cc \
  -c
```

The project build can be run from `wl2/` with `make cli` or `make test-wl2`.
