"""Rocchio relevance feedback for query refinement."""

from __future__ import annotations

from collections import defaultdict


class Rocchio:
    """Update a query vector using relevant and non-relevant documents."""

    def __init__(
        self,
        alpha: float = 1.0,
        beta: float = 0.75,
        gamma: float = 0.15,
    ) -> None:
        if alpha < 0 or beta < 0 or gamma < 0:
            raise ValueError("Rocchio parameters must be non-negative")

        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma

    def update_query(
        self,
        query_vec: dict[str, float],
        relevant_vectors: list[dict[str, float]],
        non_relevant_vectors: list[dict[str, float]] | None = None,
    ) -> dict[str, float]:
        """Return a refined query vector using the Rocchio formula."""
        non_relevant_vectors = non_relevant_vectors or []
        updated = defaultdict(float)

        for term, weight in query_vec.items():
            updated[term] += self.alpha * weight

        if relevant_vectors:
            for vector in relevant_vectors:
                for term, weight in vector.items():
                    updated[term] += (
                        self.beta * weight / len(relevant_vectors)
                    )

        if non_relevant_vectors:
            for vector in non_relevant_vectors:
                for term, weight in vector.items():
                    updated[term] -= (
                        self.gamma * weight / len(non_relevant_vectors)
                    )

        # Negative term weights are discarded.
        return {
            term: weight
            for term, weight in updated.items()
            if weight > 0
        }
