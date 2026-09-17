"""
wl3/engine/models.py
====================
Shared data models used across the entire WL3 pipeline.

RankedResult is the final output object returned by QueryEngine to
the CLI, Flask, and evaluation layers.  All three consume the same
structured object rather than raw tuples or dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RankedResult:
    """
    A single ranked search result returned by QueryEngine.search().

    Attributes
    ----------
    doc_id : int
        Unique document identifier from the corpus (stable per index version).
    score : float
        Relevance score assigned by the configured ranking strategy
        (TF-IDF score, BM25 score, or cosine similarity).
    title : str
        Document title — populated from get_doc_snippet_data().
    url : str
        Source URL of the document — populated from get_doc_snippet_data().
    snippet : str
        Short excerpt of the document text, possibly with query-term
        highlighting — populated from get_doc_snippet_data().
    rank : int
        1-based position in the final ranked list (1 = highest relevance).
        Set by QueryEngine after sorting; defaults to 0 until assigned.

    Usage
    -----
    QueryEngine builds these objects:

        result = RankedResult(
            doc_id  = 42,
            score   = 3.1604,
            title   = "Machine Learning Basics",
            url     = "https://example.com/ml",
            snippet = "Machine learning is a subset of AI...",
            rank    = 1,
        )

    The CLI and Flask layers receive list[RankedResult] and render them
    without performing any ranking or caching logic themselves.
    """

    doc_id: int
    score: float
    title: str = ""
    url: str = ""
    snippet: str = ""
    rank: int = 0

    def __repr__(self) -> str:
        return (
            f"RankedResult(rank={self.rank}, doc_id={self.doc_id}, "
            f"score={self.score:.4f}, title={self.title!r})"
        )

    def to_dict(self) -> dict:
        """
        Serialise to a plain dict for JSON responses (Flask) or
        structured display (CLI).

        Returns
        -------
        dict with keys: rank, doc_id, score, title, url, snippet
        """
        return {
            "rank": self.rank,
            "doc_id": self.doc_id,
            "score": round(self.score, 6),
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
        }
