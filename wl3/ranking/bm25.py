"""
BM25 (Okapi BM25) Relevance Scorer
====================================
Implements the Okapi BM25 ranking function, which extends TF-IDF with
two important improvements:

    1. Term-frequency saturation (k1): repeated term occurrences give
       diminishing returns rather than unbounded linear growth.
    2. Document-length normalization (b): long documents are penalised
       relative to the corpus average.

Formula:
    BM25(q, d) = Σ  IDF(t)  ×  [ tf(t,d) × (k1 + 1) ]
                 t     ─────────────────────────────────────────────
                       tf(t,d) + k1 × (1 − b + b × |d| / avgdl)

    IDF(t) = log₁₀( (N − df(t) + 0.5) / (df(t) + 0.5)  +  1 )

    Default hyperparameters (Okapi BM25 standard):
        k1 = 1.5   — term-frequency saturation
        b  = 0.75  — length normalisation weight

Data contract with Worklet 2:
    doc_tf         — resolve_query(query_string)[0][doc_id]
    doc_freq       — resolve_query(query_string)[1]
    total_docs     — get_corpus_stats()["total_docs"]
    avg_doc_length — get_corpus_stats()["avg_doc_length"]
    doc_length     — sum(get_doc_terms([doc_id])[doc_id].values())
                     (FULL term counts, not just query terms)
"""

import math


class BM25Scorer:
    """
    Computes the Okapi BM25 relevance score for a single document
    against a set of query terms.

    Hyperparameters k1 and b are set at construction time and apply
    to every subsequent score() call.

    Example
    -------
    >>> scorer = BM25Scorer(k1=1.5, b=0.75)
    >>> doc_tf = {"machine": 3, "learning": 4}
    >>> doc_freq = {"machine": 3, "learning": 4}
    >>> scorer.score(doc_tf, doc_freq,
    ...              total_docs=10, doc_length=16, avg_doc_length=45.0,
    ...              query_terms=["machine", "learning"])
    1.8013...
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        """
        Parameters
        ----------
        k1 : float
            Term-frequency saturation parameter.
            Typical range: 1.2 – 2.0.  Default: 1.5.
            Higher → more credit for high-frequency terms.
        b : float
            Document-length normalisation weight.
            Range: [0, 1].  Default: 0.75.
            0 = no length normalisation; 1 = full normalisation.
        """
        if k1 < 0:
            raise ValueError(f"k1 must be non-negative, got {k1}")
        if not (0.0 <= b <= 1.0):
            raise ValueError(f"b must be in [0, 1], got {b}")

        self.k1 = k1
        self.b = b

    def score(
        self,
        doc_tf: dict[str, int],
        doc_freq: dict[str, int],
        total_docs: int,
        doc_length: int,
        avg_doc_length: float,
        query_terms: list[str],
    ) -> float:
        """
        Compute the BM25 score for one document.

        Parameters
        ----------
        doc_tf : dict[str, int]
            Term frequencies for query terms in this document.
            Source: ``resolve_query(query_string)[0][doc_id]``
        doc_freq : dict[str, int]
            Per-term document frequencies across the corpus.
            Source: ``resolve_query(query_string)[1]``
        total_docs : int
            Total number of documents in the corpus.
            Source: ``get_corpus_stats()["total_docs"]``
        doc_length : int
            Total number of tokens in this document (ALL terms, not just
            query terms).  Must be computed from the full token list:
            ``sum(get_doc_terms([doc_id])[doc_id].values())``
        avg_doc_length : float
            Mean document length across the corpus.
            Source: ``get_corpus_stats()["avg_doc_length"]``
        query_terms : list[str]
            Normalised query terms.

        Returns
        -------
        float
            BM25 relevance score.  Higher is more relevant.
            Returns 0.0 if no query term appears in the document.

        Notes
        -----
        - The IDF formula used here is the Lucene/Robertson variant with
          a ``+ 1`` offset to ensure IDF is always non-negative, even for
          very common terms where ``df`` approaches ``N``.
        - When ``avg_doc_length == 0`` the length normalisation term
          degenerates to ``1 − b`` so scoring still works on single docs.
        """
        if not query_terms or total_docs <= 0:
            return 0.0

        # Guard against pathological avg_doc_length
        if avg_doc_length <= 0:
            avg_doc_length = max(doc_length, 1)

        score = 0.0
        for term in query_terms:
            tf = doc_tf.get(term, 0)
            df = doc_freq.get(term, 0)

            if tf <= 0 or df <= 0:
                continue

            # BM25 IDF — Robertson-Sparck Jones variant (+1 avoids negatives
            # for moderate df; clamp to 0 as a safety net for df > total_docs).
            idf = max(0.0, math.log10(
                (total_docs - df + 0.5) / (df + 0.5) + 1
            ))

            # Length-normalised TF component
            numerator = tf * (self.k1 + 1)
            length_norm = 1 - self.b + self.b * (doc_length / avg_doc_length)
            denominator = tf + self.k1 * length_norm

            score += idf * (numerator / denominator)

        return score
