"""Tokenization & normalization pipeline.

Pipeline (budgeted <= 2 s per page):
1. Split on word boundaries, keeping only alphanumeric tokens
   (stray punctuation is dropped in the same regex pass).
2. Lowercase.
3. Drop stop-words against a frozen `set` in ``crawler.config``.
"""

from __future__ import annotations

import re

from crawler import config

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def tokenize(text: str | None) -> list[str]:
    """Split ``text`` into normalized (lowercase, stop-word-free) tokens."""
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text)
    tokens = [t.lower() for t in tokens]
    return [t for t in tokens if t not in config.STOPWORDS]