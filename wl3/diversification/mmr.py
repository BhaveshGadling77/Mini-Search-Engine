"""Maximum Marginal Relevance (MMR) for search result diversification."""

from __future__ import annotations

from ..ranking.vector import VectorScorer
from ..retrieval.top_k import ScoredDocument


class MMR:
    """Greedily balance query relevance with document diversity."""

    def __init__(self, lambda_param: float = 0.7) -> None:
        if not 0.0 <= lambda_param <= 1.0:
            raise ValueError("lambda_param must be between 0 and 1")
        self.lambda_param = lambda_param

    def rerank(
        self,
        pool: list[ScoredDocument],
        query_vec: dict[str, float],
        doc_vectors: dict[int, dict[str, float]],
        k: int,
    ) -> list[ScoredDocument]:
        """Return up to k documents ranked by MMR score.

        query_vec and doc_vectors must use the same vector representation.
        The returned ScoredDocument.score is the computed MMR score.
        """
        if k <= 0 or not pool:
            return []

        # Preserve pool order when scores tie and ignore duplicate IDs.
        candidates = []
        seen_ids = set()
        for doc in pool:
            if doc.doc_id not in seen_ids:
                candidates.append(doc)
                seen_ids.add(doc.doc_id)

        relevance = {
            doc.doc_id: VectorScorer.cosine_similarity(
                query_vec, doc_vectors.get(doc.doc_id, {})
            )
            for doc in candidates
        }

        selected: list[ScoredDocument] = []
        remaining = list(candidates)

        while remaining and len(selected) < k:
            best_doc = None
            best_score = float("-inf")

            for doc in remaining:
                if selected:
                    max_similarity = max(
                        VectorScorer.cosine_similarity(
                            doc_vectors.get(doc.doc_id, {}),
                            doc_vectors.get(chosen.doc_id, {}),
                        )
                        for chosen in selected
                    )
                else:
                    max_similarity = 0.0

                mmr_score = (
                    self.lambda_param * relevance[doc.doc_id]
                    - (1.0 - self.lambda_param) * max_similarity
                )

                # Strict comparison keeps the earlier pool item on ties.
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_doc = doc

            if best_doc is None:
                break

            selected.append(
                ScoredDocument(doc_id=best_doc.doc_id, score=best_score)
            )
            remaining.remove(best_doc)

        return selected
