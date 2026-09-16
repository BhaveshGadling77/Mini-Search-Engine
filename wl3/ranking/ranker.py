"""
Unified Ranker — Strategy Pattern Facade
=========================================
Provides a single entry point for all ranking algorithms so that
QueryEngine never needs to know which scorer is being used.

Supported modes (RankingMode enum):
    TFIDF  — TF × IDF scoring (fastest; only needs query-term TFs)
    BM25   — Okapi BM25 (needs full doc lengths + TFs)
    VECTOR — Sparse TF-IDF cosine similarity (needs full doc term vectors)

Calling contract for QueryEngine (Person 4):
    1. Call resolve_query(query)  → candidates, doc_freq
    2. Call get_corpus_stats()    → total_docs, avg_doc_length  (cache at startup)
    3. If mode is BM25 or VECTOR, also call get_doc_terms(doc_ids)
       to obtain full term vectors and compute per-document lengths.
    4. Call ranker.rank(...)      → {doc_id: score}
    5. Pass scores to TopKRetriever.

Integration with Person 3 (MMR / Rocchio):
    - The VECTOR mode exposes VectorScorer.build_tfidf_vector and
      VectorScorer.cosine_similarity as static methods; Person 3 can
      import and use them directly without going through Ranker.
    - When Rocchio generates term_boosts, QueryEngine may call
      rank() with the boosted query_terms list (terms repeated
      proportionally to boost weight) — no Ranker changes needed.
"""

from __future__ import annotations

from enum import Enum

from wl3.ranking.bm25 import BM25Scorer
from wl3.ranking.tfidf import TFIDFScorer
from wl3.ranking.vector import VectorScorer


class RankingMode(Enum):
    """
    Available ranking strategies.

    Attributes
    ----------
    TFIDF : str
        Classic TF-IDF scoring.  Requires only query-term TFs.
    BM25 : str
        Okapi BM25.  Requires full document lengths.
    VECTOR : str
        Sparse TF-IDF cosine similarity.  Requires full doc term vectors.
    """

    TFIDF = "tfidf"
    BM25 = "bm25"
    VECTOR = "vector"


class Ranker:
    """
    Strategy-pattern facade over TFIDFScorer, BM25Scorer, and VectorScorer.

    QueryEngine selects a RankingMode; Ranker delegates to the correct
    scorer and returns a ``{doc_id: score}`` mapping for all candidates.

    Parameters
    ----------
    bm25_k1 : float
        BM25 term-saturation parameter (default 1.5).
    bm25_b : float
        BM25 length-normalisation parameter (default 0.75).

    Example
    -------
    >>> ranker = Ranker()
    >>> scores = ranker.rank(
    ...     ranking_mode=RankingMode.TFIDF,
    ...     candidates={0: {"machine": 3, "learning": 4},
    ...                  7: {"machine": 2, "learning": 3}},
    ...     doc_freq={"machine": 3, "learning": 4},
    ...     total_docs=10,
    ...     query_terms=["machine", "learning"],
    ... )
    >>> scores[0] > scores[7]   # doc 0 should rank higher
    True
    """

    def __init__(self, bm25_k1: float = 1.5, bm25_b: float = 0.75) -> None:
        self._tfidf = TFIDFScorer()
        self._bm25 = BM25Scorer(k1=bm25_k1, b=bm25_b)
        self._vector = VectorScorer()

    def rank(
        self,
        ranking_mode: RankingMode,
        candidates: dict[int, dict[str, int]],
        doc_freq: dict[str, int],
        total_docs: int,
        query_terms: list[str],
        *,
        avg_doc_length: float = 0.0,
        doc_lengths: dict[int, int] | None = None,
        doc_terms_full: dict[int, dict[str, int]] | None = None,
    ) -> dict[int, float]:
        """
        Score every candidate document and return a score mapping.

        Parameters
        ----------
        ranking_mode : RankingMode
            Which algorithm to apply.
        candidates : dict[int, dict[str, int]]
            Maps doc_id → {query_term: tf_in_doc}.
            Source: ``resolve_query(query_string)[0]``
        doc_freq : dict[str, int]
            Maps query_term → document_frequency.
            Source: ``resolve_query(query_string)[1]``
        total_docs : int
            Total documents in the corpus.
            Source: ``get_corpus_stats()["total_docs"]``
        query_terms : list[str]
            Normalised query terms.

        Keyword-only parameters
        -----------------------
        avg_doc_length : float
            Required for BM25.  From ``get_corpus_stats()["avg_doc_length"]``.
        doc_lengths : dict[int, int] | None
            Maps doc_id → total token count (ALL terms, not just query terms).
            Required for BM25.  Compute as:
            ``{did: sum(terms.values())
               for did, terms in get_doc_terms(doc_ids).items()}``
        doc_terms_full : dict[int, dict[str, int]] | None
            Maps doc_id → complete term→frequency dict.
            Required for VECTOR mode.
            Source: ``get_doc_terms(doc_ids)``

        Returns
        -------
        dict[int, float]
            Maps doc_id → relevance score.  Empty dict if no candidates.

        Raises
        ------
        ValueError
            If a required parameter for the selected mode is missing.
        """
        if not candidates:
            return {}

        if ranking_mode == RankingMode.TFIDF:
            return self._rank_tfidf(candidates, doc_freq, total_docs, query_terms)

        elif ranking_mode == RankingMode.BM25:
            return self._rank_bm25(
                candidates, doc_freq, total_docs, query_terms,
                avg_doc_length, doc_lengths,
            )

        elif ranking_mode == RankingMode.VECTOR:
            return self._rank_vector(
                candidates, doc_freq, total_docs, query_terms, doc_terms_full,
            )

        else:
            raise ValueError(
                f"Unknown ranking mode: {ranking_mode!r}.  "
                f"Valid modes: {[m.value for m in RankingMode]}"
            )

    # ------------------------------------------------------------------
    # Private helpers (one per strategy)
    # ------------------------------------------------------------------

    def _rank_tfidf(
        self,
        candidates: dict[int, dict[str, int]],
        doc_freq: dict[str, int],
        total_docs: int,
        query_terms: list[str],
    ) -> dict[int, float]:
        return {
            doc_id: self._tfidf.score(
                doc_tf=doc_tf,
                doc_freq=doc_freq,
                total_docs=total_docs,
                query_terms=query_terms,
            )
            for doc_id, doc_tf in candidates.items()
        }

    def _rank_bm25(
        self,
        candidates: dict[int, dict[str, int]],
        doc_freq: dict[str, int],
        total_docs: int,
        query_terms: list[str],
        avg_doc_length: float,
        doc_lengths: dict[int, int] | None,
    ) -> dict[int, float]:
        if doc_lengths is None:
            raise ValueError(
                "BM25 requires 'doc_lengths'.  "
                "Compute it as: {did: sum(terms.values()) "
                "for did, terms in get_doc_terms(doc_ids).items()}"
            )
        return {
            doc_id: self._bm25.score(
                doc_tf=doc_tf,
                doc_freq=doc_freq,
                total_docs=total_docs,
                doc_length=doc_lengths.get(doc_id, 0),
                avg_doc_length=avg_doc_length,
                query_terms=query_terms,
            )
            for doc_id, doc_tf in candidates.items()
        }

    def _rank_vector(
        self,
        candidates: dict[int, dict[str, int]],
        doc_freq: dict[str, int],
        total_docs: int,
        query_terms: list[str],
        doc_terms_full: dict[int, dict[str, int]] | None,
    ) -> dict[int, float]:
        if doc_terms_full is None:
            raise ValueError(
                "VECTOR mode requires 'doc_terms_full'.  "
                "Source: get_doc_terms(doc_ids)"
            )
        scores: dict[int, float] = {}
        for doc_id in candidates:
            full_terms = doc_terms_full.get(doc_id, {})
            scores[doc_id] = self._vector.score(
                query_terms=query_terms,
                doc_terms_full=full_terms,
                doc_freq=doc_freq,
                total_docs=total_docs,
            )
        return scores
