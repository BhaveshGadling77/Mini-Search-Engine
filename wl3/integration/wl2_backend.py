"""
Real Worklet 2 backend loader (the C++ ``wl2bridge`` pybind11 module).

Build the module first (see docs/wl2/HowToGetPybindInterface.md)::

    python -m pip install pybind11
    make pybind              # creates build/wl2bridge*.so

Then point Worklet 3 at it::

    python -m wl3.cli.main --backend wl3.integration.wl2_backend:create_backend
    # or:  export WL3_W2_BACKEND=wl3.integration.wl2_backend:create_backend

The corpus is taken from ``$WL3_CORPUS`` (default ``data/crawler.json``).
``wl2bridge.initialize(corpus)`` must run once before the five API functions,
so this loader does it and returns the ready module for ``Worklet2Adapter``.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from types import ModuleType

from wl3.integration.worklet2_adapter import Worklet2Error

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = _REPO_ROOT / "data" / "crawler.json"

_lock = threading.Lock()
_initialized_for: str | None = None


def create_backend(corpus_path: str | None = None) -> ModuleType:
    """Import ``wl2bridge`` from ``build/``, initialise it once, return it."""
    global _initialized_for

    build_dir = str(_REPO_ROOT / "build")
    if build_dir not in sys.path:
        sys.path.insert(0, build_dir)
    try:
        import wl2bridge
    except ImportError as exc:
        raise Worklet2Error(
            "Cannot import 'wl2bridge'. Build it first: activate the venv, "
            "'python -m pip install pybind11', then 'make pybind' from the "
            f"repo root (looked in {build_dir}). Original error: {exc}"
        ) from exc

    corpus = str(corpus_path or os.environ.get("WL3_CORPUS") or DEFAULT_CORPUS)
    if not os.path.isfile(corpus):
        raise Worklet2Error(f"Corpus file not found: {corpus}")

    with _lock:
        # initialize() re-reads the whole corpus (~6s for 500 docs): only once.
        if _initialized_for != corpus:
            try:
                wl2bridge.initialize(corpus)
            except Exception as exc:  # noqa: BLE001
                raise Worklet2Error(f"wl2bridge.initialize({corpus}) failed: {exc}") from exc
            _initialized_for = corpus
    return wl2bridge
