"""
QueryEngine — the heart of Worklet 3.

Both the CLI/REPL and the Flask app call ``QueryEngine.search(...)``; neither
contains ranking, caching, feedback or diversification logic.  The engine does
no terminal I/O and produces no HTML: it returns ``list[RankedResult]``.

Locked processing sequence (W3 SRS 4.3)::

    search(query, session_id, ranking_mode, k, use_mmr)
      1. does the session have active relevance feedback?
      2. if not -> look in the shared cache (CacheManager: LRU -> SQLite)
      3. hit  -> return cached RankedResults
      4. miss -> W2.resolve_query(query)  (candidates, doc_freq)
      5. Ranker scores every candidate (TF-IDF | BM25 | Vector)
      6. TopKRetriever keeps the best K (or ~20 when MMR is on)
      7. MMR picks the diversified final K (optional)
      8. W2.get_doc_snippet_data(final ids) -> RankedResult objects
      9. non-personalised results are stored in the cache
"""

from __future__ import annotations

import logging
import threading
from collections import Counter

from wl3.cache.cache_manager import CacheManager, build_cache_key
from wl3.diversification.mmr import MMR
from wl3.feedback.rocchio import Rocchio
from wl3.feedback.session_manager import SessionManager
from wl3.engine.models import RankedResult
from wl3.engine.text import make_snippet, tokenize_query
from wl3.integration.worklet2_adapter import Worklet2Adapter
from wl3.ranking.ranker import Ranker, RankingMode
from wl3.ranking.vector import VectorScorer
from wl3.retrieval.top_k import TopKRetriever

logger = logging.getLogger(__name__)

# Accepted spellings for each ranking strategy.
_MODE_ALIASES = {
    "tfidf": RankingMode.TFIDF,
    "tf-idf": RankingMode.TFIDF,
    "tf_idf": RankingMode.TFIDF,
    "bm25": RankingMode.BM25,
    "vector": RankingMode.VECTOR,
    "cosine": RankingMode.VECTOR,
    "vector/cosine": RankingMode.VECTOR,
}


def parse_ranking_mode(mode: str | RankingMode) -> RankingMode:
    """Normalise a user-supplied ranking mode; raises ``ValueError`` if unknown."""
    if isinstance(mode, RankingMode):
        return mode
    key = str(mode).strip().lower()
    if key not in _MODE_ALIASES:
        raise ValueError(
            f"Unknown ranking mode {mode!r}. Valid: tfidf, bm25, vector"
        )
    return _MODE_ALIASES[key]


class QueryEngine:
    """
    Parameters
    ----------
    adapter : Worklet2Adapter
        The only gateway to Worklet 2.
    cache_capacity : int
        Entries in the in-memory LRU.
    cache_db_path : str | None
        SQLite file for persistence.  ``None`` disables caching entirely.
    ranker, session_manager, rocchio, mmr
        Injectable collaborators.  Defaults are Person 1's ``Ranker`` and
        Person 3's ``SessionManager``, ``Rocchio`` and ``MMR``.
    mmr_pool_size : int
        Candidate pool handed to MMR (SRS: ~20).
    mmr_lambda : float
        MMR relevance/diversity trade-off (1.0 = pure relevance); used when
        the engine builds its default ``MMR``.
    """

    FEEDBACK_MAX_TERMS = 10          # boosted terms used per personalised query
    FEEDBACK_MAX_REPEAT = 2          # strongest boost term counts this many times
    FEEDBACK_DOC_TERMS = 25          # most frequent doc terms considered by Rocchio

    def __init__(
        self,
        adapter: Worklet2Adapter,
        *,
        cache_capacity: int = 100,
        cache_db_path: str | None = "cache.db",
        ranker: Ranker | None = None,
        session_manager=None,
        rocchio=None,
        mmr=None,
        mmr_pool_size: int = 20,
        mmr_lambda: float = 0.7,
    ) -> None:
        self.adapter = adapter
        self.ranker = ranker or Ranker()
        self.sessions = session_manager or SessionManager()
        self.rocchio = rocchio or Rocchio()
        self.mmr = mmr or MMR(lambda_param=mmr_lambda)
        self.mmr_pool_size = mmr_pool_size
        self.mmr_lambda = mmr_lambda
        self.cache_capacity = cache_capacity
        self.cache_db_path = cache_db_path

        self._counter_lock = threading.Lock()
        self._df_lock = threading.Lock()
        self._df_cache: dict[str, int] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache: CacheManager | None = None

        self._startup()

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def _startup(self) -> None:
        """Read corpus stats + index version once, then open the cache."""
        stats = self.adapter.get_corpus_stats(refresh=True)
        self.total_docs: int = stats["total_docs"]
        self.avg_doc_length: float = stats["avg_doc_length"]
        self.index_version: str = self.adapter.get_index_version()
        self._df_cache.clear()

        if self.cache_db_path is None:
            self.cache = None
            return
        # Version is fetched BEFORE the cache is opened so stale entries
        # from an older index are never served (SRS FR-5).
        self.cache = CacheManager(
            capacity=self.cache_capacity,
            db_path=self.cache_db_path,
            index_version=self.index_version,
            result_factory=RankedResult,
        )

    def reload(self) -> None:
        """Re-read stats/index version (call after W2 rebuilds its index)."""
        self._startup()

    def clear_cache(self) -> None:
        if self.cache is not None:
            self.cache.clear()

    def reset_counters(self) -> None:
        with self._counter_lock:
            self.cache_hits = 0
            self.cache_misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        session_id: str | None = None,
        ranking_mode: str | RankingMode = "bm25",
        k: int = 10,
        use_mmr: bool = False,
    ) -> list[RankedResult]:
        """Run the full search pipeline; see module docstring."""
        mode = parse_ranking_mode(ranking_mode)
        if not isinstance(k, int) or k <= 0:
            return []
        query_terms = tokenize_query(query)
        if not query_terms:
            return []

        personalized = bool(session_id) and self.sessions.has_feedback(session_id)

        key = None
        if self.cache is not None and not personalized:
            key = build_cache_key(query, mode.value, k, use_mmr, self.index_version)
            cached = self.cache.get(key)
            if cached is not None:
                with self._counter_lock:
                    self.cache_hits += 1
                return list(cached)
        with self._counter_lock:
            self.cache_misses += 1

        results = self._run_pipeline(
            query, query_terms, mode, k, use_mmr,
            boosts=self.sessions.get_term_boosts(session_id) if personalized else None,
        )

        if key is not None:
            self.cache.put(key, results)
        return results

    def mark_relevant(self, session_id: str, doc_id: int) -> bool:
        """
        Record that the user marked ``doc_id`` relevant in this session.

        The document's complete term frequencies come from Worklet 2
        (``get_doc_terms``).  Rocchio turns the TF-IDF vectors of *all*
        documents this session has marked relevant into term boosts, which
        are stored in the session (memory only, never cached or persisted).
        Returns False if Worklet 2 does not know the document.
        """
        if not session_id or not session_id.strip():
            raise ValueError("session_id is required for relevance feedback")
        if not self.adapter.get_doc_terms([doc_id]).get(doc_id):
            return False

        self.sessions.add_relevant_document(session_id, doc_id)
        relevant_ids = sorted(self.sessions.get_or_create(session_id).relevant_doc_ids)
        doc_terms = self.adapter.get_doc_terms(relevant_ids)

        vectors = []
        for terms in doc_terms.values():
            top_terms = dict(
                sorted(terms.items(), key=lambda kv: (-kv[1], kv[0]))[: self.FEEDBACK_DOC_TERMS]
            )
            df = self._document_frequencies(list(top_terms))
            vector = VectorScorer.build_tfidf_vector(top_terms, df, self.total_docs)
            if vector:
                vectors.append(vector)

        boosts = self.rocchio.update_query({}, vectors)
        if not boosts:
            return False
        self.sessions.set_term_boosts(session_id, boosts)
        return True

    def reset_feedback(self, session_id: str) -> None:
        self.sessions.clear_feedback(session_id)

    def stats(self) -> dict:
        with self._counter_lock:
            return {
                "index_version": self.index_version,
                "total_docs": self.total_docs,
                "cache_entries": len(self.cache) if self.cache is not None else 0,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
            }

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        query: str,
        query_terms: list[str],
        mode: RankingMode,
        k: int,
        use_mmr: bool,
        boosts: dict[str, float] | None,
    ) -> list[RankedResult]:
        candidates, doc_freq = self.adapter.resolve_query(query)
        if not candidates:
            return []

        doc_ids = list(candidates)
        needs_full = mode in (RankingMode.BM25, RankingMode.VECTOR) or use_mmr or bool(boosts)
        full_terms = self.adapter.get_doc_terms(doc_ids) if needs_full else {}

        scoring_terms = list(query_terms)
        scoring_candidates = candidates
        scoring_df = dict(doc_freq)

        if boosts:
            scoring_terms, scoring_candidates, scoring_df = self._personalise(
                query_terms, candidates, doc_freq, full_terms, boosts
            )

        # Vector ranking and MMR need a df for EVERY document term, but W2
        # only supplies df for the query terms.  For the remaining terms we
        # use the number of candidate documents containing them.
        full_df = (
            self._estimate_df(scoring_df, full_terms)
            if (mode == RankingMode.VECTOR or use_mmr)
            else scoring_df
        )

        scores = self.ranker.rank(
            ranking_mode=mode,
            candidates=scoring_candidates,
            doc_freq=full_df if mode == RankingMode.VECTOR else scoring_df,
            total_docs=self.total_docs,
            query_terms=scoring_terms,
            avg_doc_length=self.avg_doc_length,
            doc_lengths=(
                {d: sum(t.values()) for d, t in full_terms.items()} if full_terms else None
            ),
            doc_terms_full=full_terms if full_terms else None,
        )

        if use_mmr:
            pool = TopKRetriever.get_top_k_for_mmr(scores, max(self.mmr_pool_size, k))
            vectors = {
                sd.doc_id: VectorScorer.build_tfidf_vector(
                    full_terms.get(sd.doc_id, {}), full_df, self.total_docs
                )
                for sd in pool
            }
            query_vec = VectorScorer.build_tfidf_vector(
                dict(Counter(scoring_terms)), full_df, self.total_docs
            )
            chosen = self.mmr.rerank(pool, query_vec, vectors, k)
            # MMR chooses WHICH documents; the reported score stays the
            # relevance score, and (SRS 3.5.2) output is in descending
            # relevance order.
            final = sorted(
                ((sd.doc_id, scores[sd.doc_id]) for sd in chosen),
                key=lambda item: (-item[1], item[0]),
            )
        else:
            final = [(sd.doc_id, sd.score) for sd in TopKRetriever.get_top_k(scores, k)]

        return self._build_results(final, query_terms)

    def _build_results(
        self, final: list[tuple[int, float]], query_terms: list[str]
    ) -> list[RankedResult]:
        if not final:
            return []
        snippets = self.adapter.get_doc_snippet_data([doc_id for doc_id, _ in final])
        results = []
        for rank, (doc_id, score) in enumerate(final, start=1):
            data = snippets.get(doc_id, {})
            results.append(
                RankedResult(
                    rank=rank,
                    doc_id=doc_id,
                    score=float(score),
                    title=data.get("title", ""),
                    url=data.get("url", ""),
                    snippet=make_snippet(data.get("text", ""), query_terms),
                )
            )
        return results

    # ------------------------------------------------------------------
    # Personalisation helpers
    # ------------------------------------------------------------------

    def _personalise(
        self,
        query_terms: list[str],
        candidates: dict[int, dict[str, int]],
        doc_freq: dict[str, int],
        full_terms: dict[int, dict[str, int]],
        boosts: dict[str, float],
    ):
        """
        Expand the query with the session's Rocchio terms.

        The strongest boost terms are appended to the scoring terms (repeated
        up to FEEDBACK_MAX_REPEAT times, proportional to boost), their
        per-document TFs are read from the full term maps and their DFs are
        looked up once and memoised.  The shared candidate set is unchanged.
        """
        original = set(query_terms)
        ranked = sorted(
            ((t, b) for t, b in boosts.items() if t not in original and b > 0),
            key=lambda tb: (-tb[1], tb[0]),
        )[: self.FEEDBACK_MAX_TERMS]
        if not ranked:
            return list(query_terms), candidates, dict(doc_freq)

        top_boost = ranked[0][1]
        extra_df = self._document_frequencies([t for t, _ in ranked])
        scoring_terms = list(query_terms)
        scoring_df = dict(doc_freq)
        used = []
        for term, boost in ranked:
            if extra_df.get(term, 0) <= 0:
                continue
            reps = max(1, round(self.FEEDBACK_MAX_REPEAT * boost / top_boost))
            scoring_terms.extend([term] * reps)
            scoring_df[term] = extra_df[term]
            used.append(term)

        expanded = {}
        for doc_id, tf in candidates.items():
            row = dict(tf)
            doc_full = full_terms.get(doc_id, {})
            for term in used:
                row[term] = doc_full.get(term, 0)
            expanded[doc_id] = row
        return scoring_terms, expanded, scoring_df

    def _document_frequencies(self, terms: list[str]) -> dict[str, int]:
        """DF for arbitrary terms (single-term W2 lookups, memoised)."""
        with self._df_lock:
            missing = [t for t in terms if t not in self._df_cache]
        for term in missing:
            _, df = self.adapter.resolve_query(term)
            with self._df_lock:
                self._df_cache[term] = df.get(term, 0)
        with self._df_lock:
            return {t: self._df_cache.get(t, 0) for t in terms}

    @staticmethod
    def _estimate_df(
        known_df: dict[str, int], full_terms: dict[int, dict[str, int]]
    ) -> dict[str, int]:
        """W2 df where known, otherwise #candidate docs containing the term."""
        counts: Counter = Counter()
        for terms in full_terms.values():
            counts.update(terms.keys())
        merged = dict(counts)
        merged.update({t: d for t, d in known_df.items() if d > 0})
        return merged
