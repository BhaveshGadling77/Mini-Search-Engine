"""JSONL corpus writer.

Append-only, one document per line. The file is opened once and flushed after
every record for crash safety, so a partial crawl still yields a usable
(if incomplete) corpus.
"""


import json
import os


class JSONLStore:
    """Append-only JSONL persistence for crawled `Document` objects."""

    def __init__(self, path: str) -> None:
        self._path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._file = open(path, "a", encoding="utf-8")

    def append(self, document) -> None:
        """Write a single document record as a JSON line and flush."""
        line = json.dumps(document.to_dict(), ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "JSONLStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()