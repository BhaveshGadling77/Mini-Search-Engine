# Worklet 2 Pybind11 Interface

## Build

From the repository root:

```bash
cd wl2
make pybind
```

This builds the `wl2bridge` Python extension in `wl2/build/`.

## Import from Worklet 3

In your Python file inside `wl3/`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT  / "build"))

import wl2bridge
```

## Initialize

```python
corpus_path = ROOT / "data" / "crawler.json"
wl2bridge.initialize(str(corpus_path))
```

Call `initialize()` before using the other functions.

## Call the API

```python
# Query results
candidates, doc_freq = wl2bridge.resolve_query("startup")

# Corpus statistics
stats = wl2bridge.get_corpus_stats()
total_docs = stats["total_docs"]
avg_doc_length = stats["avg_doc_length"]

# Index version
version = wl2bridge.get_index_version()

# Document title, URL, and text
doc_ids = list(candidates.keys())
snippets = wl2bridge.get_doc_snippet_data(doc_ids)

# Full term-frequency maps for documents
terms = wl2bridge.get_doc_terms(doc_ids)
```

## Minimal test script

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wl2" / "build"))

import wl2bridge

wl2bridge.initialize(str(ROOT / "data" / "crawler.json"))

candidates, doc_freq = wl2bridge.resolve_query("startup")
doc_ids = list(candidates.keys())

print("Matches:", len(doc_ids))
print("Corpus stats:", wl2bridge.get_corpus_stats())
print("Index version:", wl2bridge.get_index_version())

if doc_ids:
    print("Snippets:", len(wl2bridge.get_doc_snippet_data(doc_ids)))
    print("Documents with terms:", len(wl2bridge.get_doc_terms(doc_ids)))
```

Run from the repository root:

```bash
python3 wl3/test_wl2bridge.py
```

u can also refer to the code at ![reference codes](../../wl2/pybind_interface_testing/)