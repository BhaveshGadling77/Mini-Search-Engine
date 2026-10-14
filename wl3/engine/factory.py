"""
Shared engine construction for the CLI, Flask app and evaluator, so that
none of them re-implement wiring (they only differ in presentation).
"""

from __future__ import annotations

import os

from wl3.engine.query_engine import QueryEngine
from wl3.integration.worklet2_adapter import create_adapter

DEFAULT_CACHE_DB = os.path.join("data", "wl3_cache.db")


def build_engine(
    backend_spec: str | None = None,
    corpus_path: str | None = None,
    synthetic: bool = False,
    cache_db_path: str | None = DEFAULT_CACHE_DB,
    cache_capacity: int = 100,
) -> QueryEngine:
    """
    Build a ready-to-use QueryEngine.

    Source of Worklet 2 data, in priority order: ``backend_spec`` (real W2
    module), ``corpus_path`` (JSON corpus, in-memory W2), else the synthetic
    demo corpus when ``synthetic`` is true.  Environment variables
    ``WL3_W2_BACKEND`` / ``WL3_CORPUS`` provide the same settings.
    """
    backend_spec = backend_spec or os.environ.get("WL3_W2_BACKEND")
    corpus_path = corpus_path or os.environ.get("WL3_CORPUS")
    if cache_db_path:
        os.makedirs(os.path.dirname(cache_db_path) or ".", exist_ok=True)
    adapter = create_adapter(backend_spec, corpus_path, synthetic=synthetic or not (backend_spec or corpus_path))
    return QueryEngine(adapter, cache_db_path=cache_db_path, cache_capacity=cache_capacity)
