import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
print(ROOT)
sys.path.insert(0, str(ROOT / "build"))

import wl2bridge

# Initialize
count = wl2bridge.initialize(str(ROOT / "data" / "crawler.json"))
print("Documents:", count)

# Sample query
candidates, doc_freq = wl2bridge.resolve_query("startup")
doc_ids = list(candidates.keys())

print("\nQuery results")
print("Matching documents:", len(doc_ids))
print("Document frequencies:", doc_freq)

# Corpus statistics
print("\nCorpus stats:", wl2bridge.get_corpus_stats())

# Index version
print("Index version:", wl2bridge.get_index_version())

# Snippets and terms
if doc_ids:
    snippets = wl2bridge.get_doc_snippet_data(doc_ids)
    terms = wl2bridge.get_doc_terms(doc_ids)

    print("\nSnippets retrieved:", len(snippets))
    print("Documents with terms:", len(terms))
else:
    print("\nNo matching documents.")