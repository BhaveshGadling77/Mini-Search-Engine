"""
Worklet 2 adapter — the ONLY layer in Worklet 3 that talks to Worklet 2.

Worklet 2 exposes five Python-facing functions (see the W2 SRS / W3 SRS 3.2):

    resolve_query(query_string)  -> (candidates, doc_freq)
    get_corpus_stats()           -> {"total_docs": int, "avg_doc_length": float}
    get_index_version()          -> str | int
    get_doc_snippet_data(ids)    -> {doc_id: {"title", "url", "text"}}
    get_doc_terms(ids)           -> {doc_id: {term: tf}}

``Worklet2Adapter`` wraps *any* object or module that provides those five
functions (the real C++/pybind11 module, or the bundled ``InMemoryWorklet2``
used for development, tests and evaluation).  It validates and normalises
what comes back so that the rest of Worklet 3 can rely on clean types, and it
converts every backend failure into a single ``Worklet2Error``.
"""

from __future__ import annotations

import importlib
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# Worklet 2 contract: for a query made only of stopwords it returns the first
# 10 documents plus one extra candidate with this doc id.  It is a marker, not a
# real document: WL3 strips it and tells the user (see QueryEngine).
STOPWORD_ONLY_DOC_ID = -1

REQUIRED_FUNCTIONS = (
    "resolve_query",
    "get_corpus_stats",
    "get_index_version",
    "get_doc_snippet_data",
    "get_doc_terms",
)


class Worklet2Error(RuntimeError):
    """Raised when the Worklet 2 backend is missing, incomplete or fails."""


class Worklet2Adapter:
    """Validated, type-normalising wrapper around a Worklet 2 backend."""

    def __init__(self, backend: Any) -> None:
        missing = [
            name for name in REQUIRED_FUNCTIONS
            if not callable(getattr(backend, name, None))
        ]
        if missing:
            raise Worklet2Error(
                f"Worklet 2 backend is missing required function(s): {missing}"
            )
        self._backend = backend
        self._lock = threading.Lock()
        self._stats: dict | None = None

    # ------------------------------------------------------------------
    # The five Worklet 2 functions
    # ------------------------------------------------------------------

    def resolve_query(
        self, query: str
    ) -> tuple[dict[int, dict[str, int]], dict[str, int]]:
        """Return ``(candidates, doc_freq)`` for a raw query string."""
        try:
            candidates, doc_freq = self._backend.resolve_query(query)
        except Exception as exc:  # noqa: BLE001 - backend may raise anything
            raise Worklet2Error(f"resolve_query failed: {exc}") from exc

        clean_candidates = {
            int(doc_id): {str(t): int(tf) for t, tf in (terms or {}).items()}
            for doc_id, terms in (candidates or {}).items()
        }
        clean_df = {str(t): int(df) for t, df in (doc_freq or {}).items()}
        return clean_candidates, clean_df

    def get_corpus_stats(self, refresh: bool = False) -> dict:
        """Return ``{"total_docs": int, "avg_doc_length": float}`` (cached)."""
        with self._lock:
            if self._stats is None or refresh:
                try:
                    raw = self._backend.get_corpus_stats()
                    self._stats = {
                        "total_docs": int(raw["total_docs"]),
                        "avg_doc_length": float(raw["avg_doc_length"]),
                    }
                except Exception as exc:  # noqa: BLE001
                    raise Worklet2Error(f"get_corpus_stats failed: {exc}") from exc
            return dict(self._stats)

    def get_index_version(self) -> str:
        """Return the current index version as a string."""
        try:
            return str(self._backend.get_index_version())
        except Exception as exc:  # noqa: BLE001
            raise Worklet2Error(f"get_index_version failed: {exc}") from exc

    def get_doc_snippet_data(self, doc_ids: list[int]) -> dict[int, dict]:
        """Return ``{doc_id: {"title", "url", "text"}}`` for display."""
        if not doc_ids:
            return {}
        try:
            raw = self._backend.get_doc_snippet_data(list(doc_ids))
        except Exception as exc:  # noqa: BLE001
            raise Worklet2Error(f"get_doc_snippet_data failed: {exc}") from exc
        return {
            int(doc_id): {
                "title": str((data or {}).get("title", "")),
                "url": str((data or {}).get("url", "")),
                "text": str((data or {}).get("text", "")),
            }
            for doc_id, data in (raw or {}).items()
        }

    def get_doc_terms(self, doc_ids: list[int]) -> dict[int, dict[str, int]]:
        """Return the complete ``{term: tf}`` map of each requested document."""
        if not doc_ids:
            return {}
        try:
            raw = self._backend.get_doc_terms(list(doc_ids))
        except Exception as exc:  # noqa: BLE001
            raise Worklet2Error(f"get_doc_terms failed: {exc}") from exc
        return {
            int(doc_id): {str(t): int(tf) for t, tf in (terms or {}).items()}
            for doc_id, terms in (raw or {}).items()
        }


# ----------------------------------------------------------------------
# Backend loading
# ----------------------------------------------------------------------

def load_backend(spec: str) -> Any:
    """
    Import a Worklet 2 backend from ``"package.module"`` or
    ``"package.module:attribute"`` (the attribute may be an object, or a
    zero-argument factory that returns one).
    """
    module_name, _, attr = spec.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise Worklet2Error(f"Cannot import Worklet 2 backend '{module_name}': {exc}") from exc
    target = getattr(module, attr) if attr else module
    if not attr or not all(callable(getattr(target, n, None)) for n in REQUIRED_FUNCTIONS):
        # allow `module:factory` returning the backend
        if callable(target) and attr:
            target = target()
    return target


def create_adapter(
    backend_spec: str | None = None,
    corpus_path: str | None = None,
    synthetic: bool = False,
) -> Worklet2Adapter:
    """
    Build a ``Worklet2Adapter`` from one of three sources:

    * ``backend_spec``  – real Worklet 2 module (``"wl2_bindings"``)
    * ``corpus_path``   – JSON corpus served by the bundled ``InMemoryWorklet2``
    * ``synthetic``     – generated demo corpus (also used for evaluation)
    """
    from wl3.integration.mock_worklet2 import InMemoryWorklet2

    if backend_spec:
        return Worklet2Adapter(load_backend(backend_spec))
    if corpus_path:
        return Worklet2Adapter(InMemoryWorklet2.from_json(corpus_path))
    if synthetic:
        from wl3.evaluation.synthetic_corpus import build_synthetic_corpus

        documents, _ = build_synthetic_corpus()
        return Worklet2Adapter(InMemoryWorklet2(documents))
    raise Worklet2Error(
        "No Worklet 2 source configured: give a backend spec, a corpus JSON "
        "file, or use the synthetic demo corpus."
    )
