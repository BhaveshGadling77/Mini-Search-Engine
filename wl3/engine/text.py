"""
Small text helpers shared by QueryEngine and the presentation layers.

These are deliberately tiny and dependency free.  They contain *no ranking
logic*; they only prepare query terms and build display snippets.
"""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Boolean operators understood by Worklet 2.  They are part of the query
# *syntax*, not search terms, so they must not be scored.
_OPERATORS = {"and", "or", "not"}


def tokenize_query(query: str) -> list[str]:
    """
    Turn a raw query string into normalised scoring terms.

    Lower-cases, strips punctuation / quotes / wildcards and removes the
    boolean operators AND / OR / NOT.  Order and duplicates are preserved
    (a repeated term means a heavier query weight in the scorers).
    """
    if not query:
        return []
    return [t for t in _TOKEN_RE.findall(query.lower()) if t not in _OPERATORS]


def make_snippet(text: str, terms: list[str], width: int = 200) -> str:
    """
    Build a short plain-text snippet centred on the first query-term hit.

    Falls back to the start of the document when no term is found.
    """
    if not text:
        return ""
    flat = " ".join(text.split())
    if len(flat) <= width:
        return flat

    lowered = flat.lower()
    hit = -1
    for term in terms:
        pos = lowered.find(term)
        if pos != -1 and (hit == -1 or pos < hit):
            hit = pos

    if hit == -1:
        return flat[:width].rstrip() + "..."

    start = max(0, hit - width // 4)
    end = min(len(flat), start + width)
    start = max(0, end - width)
    snippet = flat[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(flat):
        snippet += "..."
    return snippet


def highlight(text: str, terms: list[str], start: str = "\033[1;33m", end: str = "\033[0m") -> str:
    """
    Wrap every whole-word occurrence of a query term in ``start``/``end``.

    Used by the CLI (ANSI colours) and the web layer (``<mark>`` tags).
    """
    unique = sorted({t for t in terms if t}, key=len, reverse=True)
    if not unique or not text:
        return text
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in unique) + r")\b", re.IGNORECASE
    )
    return pattern.sub(lambda m: f"{start}{m.group(0)}{end}", text)
