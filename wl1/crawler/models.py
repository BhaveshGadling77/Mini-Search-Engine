"""Document model: the immutable unit of persistence for the crawler.

`Document` is the join-key carrier for Worklet 2 (indexing) and
Worklet 3 (ranking). Its JSON serialization (see ``to_dict``) is the
frozen interface contract between worklets.

The ``doc_id`` is a sequential identifier formatted like ``"000XXX"``
(e.g. ``"000001"``) where XXX is the running sequence.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any


@dataclasses.dataclass(frozen=True)
class Document:
    """A single crawled, parsed and tokenized web page.

    All fields are truly immutable: ``tokens`` is a tuple (not list) and
    ``meta`` is copied on construction to prevent external mutation.
    """

    doc_id: str
    url: str
    text: str
    tokens: tuple[str, ...]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable record form (schema frozen for W2/W3)."""
        return {
            "doc_id": self.doc_id,
            "url": self.url,
            "text": self.text,
            "tokens": list(self.tokens),
            "meta": self.meta,
        }

    @staticmethod
    def new_doc_id(seq: int = 1) -> str:
        """Generate a sequential document id formatted like ``000XXX``, e.g. ``000001``."""
        return f"{int(seq):06d}"

    @staticmethod
    def now_iso() -> str:
        """Return the current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")