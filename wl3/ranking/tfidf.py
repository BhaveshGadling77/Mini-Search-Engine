"""
TF-IDF Relevance Scorer
=======================
Implements the classic Term Frequency–Inverse Document Frequency scoring
algorithm for ranking documents against a query.

Formula:
    Score(q, d) = Σ  tf(t, d) × log₁₀(N / df(t))
                  t ∈ q ∩ d

where:
    tf(t, d)  = raw frequency of term t in document d
    df(t)     = number of documents containing term t
    N         = total number of documents in the corpus
    IDF(t)    = log₁₀(N / df(t))

Data contract with Worklet 2:
    doc_tf   — comes from resolve_query(query)["candidates"][doc_id]
    doc_freq — comes from resolve_query(query)["doc_freq"]
    total_docs — comes from get_corpus_stats()["total_docs"]
"""

import math


class TFIDFScorer:
    """
    Computes TF-IDF relevance score for a single document
    against a set of query terms.

    This scorer is stateless: all data is passed in per call.
    Instantiate once and call score() for every candidate document.

    Example
    -------
    >>> scorer = TFIDFScorer()
    >>> doc_tf = {"machine": 3, "learning": 4}
    >>> doc_freq = {"machine": 3, "learning": 4}
    >>> scorer.score(doc_tf, doc_freq, total_docs=10,
    ...              query_terms=["machine", "learning"])
    3.1603...
    """

    def score(
        self,
        doc_tf: dict[str, int],
        doc_freq: dict[str, int],
        total_docs: int,
        query_terms: list[str],
    ) -> float:
        """
        Compute the TF-IDF score for one document.

        Parameters
        ----------
        doc_tf : dict[str, int]
            Term frequencies for query terms in THIS specific document.
            Keys are query terms; values are raw counts in the document.
            Source: ``resolve_query(query_string)[0][doc_id]``
        doc_freq : dict[str, int]
            Document frequency for each query term across the entire corpus.
            Keys are query terms; values are counts of docs that contain the term.
            Source: ``resolve_query(query_string)[1]``
        total_docs : int
            Total number of documents in the corpus.
            Source: ``get_corpus_stats()["total_docs"]``
        query_terms : list[str]
            The parsed, normalised query terms to score against.

        Returns
        -------
        float
            TF-IDF relevance score.  Higher is more relevant.
            Returns 0.0 if no query term appears in the document.

        Notes
        -----
        - Terms with tf == 0 (not in the document) contribute 0.
        - Terms with df == 0 (not in any document) are skipped to
          avoid division by zero.
        - IDF uses log base 10 as specified in the project requirements.
        """
        if not query_terms or total_docs <= 0:
            return 0.0

        score = 0.0
        for term in query_terms:
            tf = doc_tf.get(term, 0)
            df = doc_freq.get(term, 0)

            # Skip if term is absent from document or corpus
            if tf <= 0 or df <= 0:
                continue

            # Guard against df > total_docs (invalid/stale W2 data).
            # log10(N/df) is negative when df > N; clamp to 0 so that
            # corrupted index data never produces a negative score.
            idf = max(0.0, math.log10(total_docs / df))
            score += tf * idf

        return score
