"""
InMemoryWorklet2 — a pure-Python stand-in for the real (C++) Worklet 2.

It implements the same five Python-facing functions as the real Worklet 2 so
that Worklet 3 can be developed, tested and evaluated without the C++ build.
It is NOT part of the production pipeline; swap it for the real backend with
``create_adapter(backend_spec="...")``.

Query syntax supported (a tiny subset of what Worklet 2 offers):
    ``a b``        implicit OR
    ``a OR b``     union
    ``a AND b``    intersection
    ``a NOT b``    difference
Operators are evaluated left to right.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOP_WORDS = frozenset(
    "a an and are as at be by for from has in is it its of on or that the to was were will with".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS]


class InMemoryWorklet2:
    """documents: iterable of ``{"id", "title", "url", "text"}`` dicts."""

    def __init__(self, documents: list[dict]) -> None:
        self._docs: dict[int, dict] = {}
        self._terms: dict[int, Counter] = {}
        self._postings: dict[str, dict[int, int]] = {}

        for doc in documents:
            doc_id = int(doc["id"])
            self._docs[doc_id] = {
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "text": doc.get("text", ""),
            }
            counts = Counter(_tokens(doc.get("text", "") + " " + doc.get("title", "")))
            self._terms[doc_id] = counts
            for term, tf in counts.items():
                self._postings.setdefault(term, {})[doc_id] = tf

        total_len = sum(sum(c.values()) for c in self._terms.values())
        self._stats = {
            "total_docs": len(self._docs),
            "avg_doc_length": (total_len / len(self._docs)) if self._docs else 0.0,
        }
        digest = hashlib.sha1(
            json.dumps(sorted((i, d["text"]) for i, d in self._docs.items())).encode()
        ).hexdigest()[:12]
        self._version = f"mem-{digest}"

    @classmethod
    def from_json(cls, path: str) -> "InMemoryWorklet2":
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        docs = data["documents"] if isinstance(data, dict) else data
        return cls(docs)

    # ---- the five Worklet 2 functions -------------------------------

    def resolve_query(self, query_string: str):
        match: set[int] = set()
        pending_op = "or"
        terms_seen: list[str] = []
        first = True

        for raw in re.findall(r"[A-Za-z0-9*]+", query_string):
            word = raw.lower()
            if word in ("and", "or", "not"):
                pending_op = word
                continue
            term = word.rstrip("*")
            if not term or term in _STOP_WORDS:
                continue
            terms_seen.append(term)
            if word.endswith("*"):
                docs = set()
                for vocab_term, posting in self._postings.items():
                    if vocab_term.startswith(term):
                        docs |= set(posting)
            else:
                docs = set(self._postings.get(term, {}))
            if first:
                match, first = docs, False
            elif pending_op == "and":
                match &= docs
            elif pending_op == "not":
                match -= docs
            else:
                match |= docs
            pending_op = "or"

        candidates = {}
        for doc_id in match:
            row = {t: self._terms[doc_id][t] for t in terms_seen if self._terms[doc_id].get(t)}
            candidates[doc_id] = row
        doc_freq = {t: len(self._postings.get(t, {})) for t in set(terms_seen)}
        return candidates, doc_freq

    def get_corpus_stats(self):
        return dict(self._stats)

    def get_index_version(self):
        return self._version

    def get_doc_snippet_data(self, doc_ids):
        return {i: dict(self._docs[i]) for i in doc_ids if i in self._docs}

    def get_doc_terms(self, doc_ids):
        return {i: dict(self._terms[i]) for i in doc_ids if i in self._terms}
