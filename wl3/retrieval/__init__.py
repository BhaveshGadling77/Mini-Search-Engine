"""
wl3.retrieval — Public API
===========================
Re-exports public classes so callers can do:

    from wl3.retrieval import TopKRetriever, ScoredDocument
"""

from wl3.retrieval.top_k import ScoredDocument, TopKRetriever

__all__ = ["TopKRetriever", "ScoredDocument"]
