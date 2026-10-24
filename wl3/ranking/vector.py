"""
Vector Space Model — Sparse TF-IDF Cosine Similarity Scorer
============================================================
Implements cosine similarity between sparse TF-IDF weighted vectors
for the query and a document.

This is NOT a dense embedding / sentence-transformer approach.
It is the classical sparse vector space model where each dimension
corresponds to one vocabulary term and its weight is its TF-IDF score.

Formula:
    w(t, x) = tf(t, x) × log₁₀(N / df(t))

    q_vec[t] = tf(t, query) × IDF(t)
    d_vec[t] = tf(t, doc)   × IDF(t)

    cosine(q, d) = (q_vec · d_vec) / (‖q_vec‖ × ‖d_vec‖)

    Result is in [0, 1]:
        1 → identical direction (most relevant)
        0 → orthogonal (no shared terms)

Data contract with Worklet 2:
    query_terms    — the parsed query terms list
    doc_terms_full — get_doc_terms([doc_id])[doc_id]   (ALL terms, not just query)
    doc_freq       — resolve_query(query_string)[1], augmented with DFs for doc terms
    total_docs     — get_corpus_stats()["total_docs"]

Important
---------
VectorScorer requires the FULL per-document term vector (all terms),
whereas TFIDFScorer and BM25Scorer only need query-term TFs.
QueryEngine must call get_doc_terms() before invoking VECTOR mode.

Public static helpers
---------------------
build_tfidf_vector(terms, doc_freq, total_docs) → dict[str, float]
    Exposed for use by MMR (Person 3) and Rocchio (Person 3).

cosine_similarity(vec_a, vec_b) → float
    Exposed for document-to-document similarity in MMR.
"""

import math


class VectorScorer:
    """
    Sparse TF-IDF cosine-similarity scorer.

    The scorer is stateless: all data is passed in per call.
    The two static helpers (build_tfidf_vector and cosine_similarity)
    are the shared utilities used by MMR and Rocchio.

    Example
    -------
    >>> scorer = VectorScorer()
    >>> query_terms = ["machine", "learning"]
    >>> doc_terms_full = {"machine": 3, "learning": 4, "subset": 1,
    ...                   "artificial": 2, "intelligence": 2,
    ...                   "is": 2, "a": 1, "of": 1}
    >>> doc_freq = {"machine": 3, "learning": 4, "subset": 1,
    ...             "artificial": 2, "intelligence": 2}
    >>> scorer.score(query_terms, doc_terms_full, doc_freq, total_docs=10)
    0.862...
    """

    # ------------------------------------------------------------------
    # Primary scoring interface (used by Ranker)
    # ------------------------------------------------------------------

    def score(
        self,
        query_terms: list[str],
        doc_terms_full: dict[str, int],
        doc_freq: dict[str, int],
        total_docs: int,
    ) -> float:
        """
        Compute cosine similarity between the query vector and the
        document vector in sparse TF-IDF space.

        Parameters
        ----------
        query_terms : list[str]
            The normalised query terms.  Duplicate terms increase their
            TF in the query vector.
        doc_terms_full : dict[str, int]
            Complete term→frequency map for the document.
            Source: ``get_doc_terms([doc_id])[doc_id]``
        doc_freq : dict[str, int]
            Document frequency for terms.  Should cover both query terms
            and document terms for an accurate IDF.
            Source: ``resolve_query()[1]`` (query terms' DFs at minimum)
        total_docs : int
            Total number of documents in the corpus.
            Source: ``get_corpus_stats()["total_docs"]``

        Returns
        -------
        float
            Cosine similarity in [0.0, 1.0].
            Returns 0.0 if either vector has zero magnitude.
        """
        if not query_terms or not doc_terms_full or total_docs <= 0:
            return 0.0

        # Build query TF (count term occurrences in the query list)
        query_tf: dict[str, int] = {}
        for term in query_terms:
            query_tf[term] = query_tf.get(term, 0) + 1

        # Build sparse TF-IDF vectors
        query_vec = self.build_tfidf_vector(query_tf, doc_freq, total_docs)
        doc_vec = self.build_tfidf_vector(doc_terms_full, doc_freq, total_docs)

        if not query_vec or not doc_vec:
            return 0.0

        return self.cosine_similarity(query_vec, doc_vec)

    # ------------------------------------------------------------------
    # Static helper utilities — shared with MMR (Person 3) and Rocchio
    # ------------------------------------------------------------------

    @staticmethod
    def build_tfidf_vector(
        terms: dict[str, int],
        doc_freq: dict[str, int],
        total_docs: int,
    ) -> dict[str, float]:
        """
        Build a sparse TF-IDF weighted vector.

        Used internally by score() and exported for MMR and Rocchio.

        Parameters
        ----------
        terms : dict[str, int]
            Term→frequency map (either the query or a document).
        doc_freq : dict[str, int]
            Corpus-wide document frequencies.
        total_docs : int
            Total number of documents in the corpus.

        Returns
        -------
        dict[str, float]
            Sparse vector mapping term → TF-IDF weight.
            Terms with df == 0 are omitted (unknown terms).
        """
        vec: dict[str, float] = {}
        for term, tf in terms.items():
            df = doc_freq.get(term, 0)
            if tf > 0 and df > 0:
                # Clamp to 0: if df > total_docs (invalid W2 data), IDF would
                # be negative, which would invert the direction of the vector.
                idf = max(0.0, math.log10(total_docs / df))
                weight = tf * idf
                if weight != 0.0:
                    vec[term] = weight
        return vec

    @staticmethod
    def cosine_similarity(
        vec_a: dict[str, float],
        vec_b: dict[str, float],
    ) -> float:
        """
        Cosine similarity between two sparse TF-IDF vectors.

        Used internally by score() and exported for document-to-document
        similarity inside MMR diversification.

        Parameters
        ----------
        vec_a, vec_b : dict[str, float]
            Sparse vectors (term → weight).  Can be query or document
            vectors built by build_tfidf_vector().

        Returns
        -------
        float
            Cosine similarity in [0.0, 1.0].
            Returns 0.0 if either vector is empty or has zero magnitude.
        """
        if not vec_a or not vec_b:
            return 0.0

        # Dot product — iterate over the smaller vector for efficiency
        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a

        dot_product = sum(
            vec_a[term] * vec_b[term]
            for term in vec_a
            if term in vec_b
        )

        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0

        # Clamp to [0, 1] to guard against floating-point drift
        return min(1.0, dot_product / (mag_a * mag_b))
