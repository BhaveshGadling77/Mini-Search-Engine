"""
Top-K Document Retrieval via Min-Heap
=======================================
Efficiently selects the K highest-scoring documents from the scored
candidates returned by Ranker.rank().

Algorithm:
    Use Python's heapq.nlargest which maintains a min-heap of size K
    internally, yielding O(N log K) time complexity where N is the number
    of candidates.

    This is significantly faster than sorting all N documents (O(N log N))
    when K << N (e.g. top-10 from 100 000 candidates).

Two entry points:
    get_top_k(scored_documents, k)
        → returns exactly k (or fewer) ScoredDocuments sorted descending.
        → Used in the main search path.

    get_top_k_for_mmr(scored_documents, pool_size=20)
        → returns a larger candidate pool for MMR to re-rank.
        → Used when use_mmr=True in QueryEngine.

Integration with Person 3 (MMR):
    QueryEngine calls get_top_k_for_mmr() to get ~20 candidates,
    then passes them to MMR which returns the final k.

Integration with Person 4 (QueryEngine):
    if use_mmr:
        pool = TopKRetriever.get_top_k_for_mmr(scores, pool_size=20)
        results = mmr.rerank(pool, query_terms, k)
    else:
        results = TopKRetriever.get_top_k(scores, k)
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass


@dataclass
class ScoredDocument:
    """
    A document paired with its computed relevance score.

    Attributes
    ----------
    doc_id : int
        Unique document identifier from the corpus.
    score : float
        Relevance score from one of the ranking algorithms
        (TF-IDF, BM25, or cosine similarity).
    """

    doc_id: int
    score: float

    def __repr__(self) -> str:
        return f"ScoredDocument(doc_id={self.doc_id}, score={self.score:.4f})"


class TopKRetriever:
    """
    Stateless utility class for top-K document extraction.

    All methods are static; there is no state to maintain.
    Instantiation is not required — call methods on the class directly.
    """

    @staticmethod
    def get_top_k(
        scored_documents: dict[int, float],
        k: int,
    ) -> list[ScoredDocument]:
        """
        Return the top-k documents by score using a min-heap.

        Parameters
        ----------
        scored_documents : dict[int, float]
            Maps doc_id → relevance score.
            Typically the output of ``Ranker.rank()``.
        k : int
            Maximum number of results to return.
            If k >= len(scored_documents), all documents are returned.
            If k <= 0, an empty list is returned.

        Returns
        -------
        list[ScoredDocument]
            Top-k documents sorted descending by score (highest first).
            Ties are broken by ascending doc_id for determinism.

        Complexity
        ----------
        Time : O(N log K)   where N = len(scored_documents)
        Space: O(K)

        Examples
        --------
        >>> scores = {0: 3.16, 4: 2.81, 7: 2.43, 1: 0.39}
        >>> TopKRetriever.get_top_k(scores, k=2)
        [ScoredDocument(doc_id=0, score=3.1600),
         ScoredDocument(doc_id=4, score=2.8100)]
        """
        if k <= 0 or not scored_documents:
            return []

        # Filter out NaN scores — heapq comparisons with NaN are undefined
        # (NaN comparisons always return False, silently corrupting heap order).
        # A NaN score indicates a scoring error upstream; exclude those docs.
        clean = {
            doc_id: score
            for doc_id, score in scored_documents.items()
            if not (isinstance(score, float) and math.isnan(score))
        }

        if not clean:
            return []

        # heapq.nlargest is O(N log K) via an internal min-heap of size K.
        # Key: primary sort by score (descending), tiebreak by doc_id (ascending).
        # We negate score so nlargest → highest score first;
        # we use -doc_id so that for equal scores, lower doc_id wins.
        top_items = heapq.nlargest(
            k,
            clean.items(),
            key=lambda item: (item[1], -item[0]),
        )

        return [ScoredDocument(doc_id=doc_id, score=score)
                for doc_id, score in top_items]

    @staticmethod
    def get_top_k_for_mmr(
        scored_documents: dict[int, float],
        pool_size: int = 20,
    ) -> list[ScoredDocument]:
        """
        Return an expanded candidate pool for MMR diversification.

        MMR (Maximum Marginal Relevance) re-ranks candidates to balance
        relevance with diversity.  It needs a pool larger than K so it
        has room to pick diverse documents.

        Typical usage by QueryEngine:
            pool  = TopKRetriever.get_top_k_for_mmr(scores, pool_size=20)
            final = mmr.rerank(pool, query_vec, k)

        Parameters
        ----------
        scored_documents : dict[int, float]
            Maps doc_id → relevance score.
        pool_size : int
            Number of candidates to include in the MMR input pool.
            Default: 20.  Should be meaningfully larger than the
            desired final k (e.g. 3–4× k).

        Returns
        -------
        list[ScoredDocument]
            Top pool_size documents sorted descending by score.
        """
        return TopKRetriever.get_top_k(scored_documents, pool_size)
