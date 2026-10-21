"""Tokenization & normalization pipeline.

Pipeline (budgeted <= 2 s per page):
1. Split on word boundaries, keeping only alphanumeric tokens
   (stray punctuation is dropped in the same regex pass).
2. Lowercase.
3. Drop stop-words against a frozen `set` in ``crawler.config``.

When the input ``text`` contains ``SECTION_BREAK`` sentinels (see
``crawler.parser``), the tokenizer can split into **segments** — one
list of tokens per contiguous block — so that phrase-query matching
never considers tokens from separate HTML sections as adjacent.
"""

from __future__ import annotations

import re

from crawler import config
from crawler.parser import SECTION_BREAK

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def tokenize_segments(text: str | None) -> list[list[str]]:
    """Split ``text`` into per-section token lists.

    Each inner list corresponds to a contiguous block of text in the
    original HTML (delimited by ``SECTION_BREAK`` sentinels). Tokens
    within a segment were genuinely adjacent on the page; tokens in
    *different* segments were not and must not be treated as a phrase
    match.

    Returns an empty list when *text* is falsy.
    """
    if not text:
        return []

    # Split on the sentinel first, then tokenize each fragment.
    fragments = text.split(SECTION_BREAK)
    segments: list[list[str]] = []
    for fragment in fragments:
        tokens = _TOKEN_RE.findall(fragment)
        tokens = [t.lower() for t in tokens]
        tokens = [t for t in tokens if t not in config.STOPWORDS]
        if tokens:
            segments.append(tokens)
    return segments


def tokenize(text: str | None) -> list[str]:
    """Split ``text`` into normalized (lowercase, stop-word-free) tokens.

    This is the flat (legacy) interface. For phrase-aware processing use
    ``tokenize_segments`` instead.
    """
    segments = tokenize_segments(text)
    flat: list[str] = []
    for seg in segments:
        flat.extend(seg)
    return flat