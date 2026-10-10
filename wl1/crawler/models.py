"""Document model: the immutable unit of persistence for the crawler.

`Document` is the join-key carrier for Worklet 2 (indexing) and
Worklet 3 (ranking). Its JSON serialization (see ``to_dict``) is the
frozen interface contract between worklets.

The ``doc_id`` is a collision-safe truncated UUID rather than a sequential
counter, so parallel runs / restarts never produce duplicate keys.
"""

from __future__ import annotations

import dataclasses
import uuid
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
    def new_doc_id() -> str:
        """Generate a unique document id, e.g. ``d-3f2a1b9c``."""
        return "d-" + uuid.uuid4().hex[:8]

    @staticmethod
    def now_iso() -> str:
        """Return the current UTC timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")