from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Callable


class SQLiteCache:
    """
    Persistent cache backed by SQLite.

    Each cache key corresponds to one SQLite row.
    The cached result list is stored as JSON.

    The cache validates the stored index version before
    returning a result.
    """

    def __init__(
        self,
        db_path: str,
        index_version: str | int,
        result_factory: Callable[..., Any] | None = None,
    ):
        self.db_path = db_path
        self.index_version = str(index_version)

        # Used later with Samruddhi's RankedResult class.
        # For now, tests can use dictionaries or another dataclass.
        self.result_factory = result_factory

        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        """Create a SQLite connection."""

        return sqlite3.connect(self.db_path)

    def _initialize_database(self) -> None:
        """
        Create the cache table if it does not exist.

        If the database is corrupt or unreadable, continue with
        an empty persistent cache rather than crashing the application.
        """

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        cache_key TEXT PRIMARY KEY,
                        index_version TEXT NOT NULL,
                        results_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )

                connection.commit()

        except sqlite3.Error:
            # A corrupt/unreadable cache should not stop the search engine.
            return

    @staticmethod
    def _serialize_key(key: tuple) -> str:
        """Convert a cache key tuple into deterministic JSON."""

        return json.dumps(
            list(key),
            separators=(",", ":"),
        )

    def _serialize_results(self, results: list[Any]) -> str:
        """
        Convert result objects into JSON.

        Supports:
        - dataclasses such as RankedResult
        - dictionaries
        - simple JSON-serializable values
        - objects with doc_id, score, title, url, snippet attributes
        """

        serialized_results = []

        for result in results:
            if is_dataclass(result):
                serialized_results.append(asdict(result))

            elif isinstance(result, dict):
                serialized_results.append(result)

            elif all(
                hasattr(result, attr)
                for attr in (
                    "doc_id",
                    "score",
                    "title",
                    "url",
                    "snippet",
                )
            ):
                serialized_results.append(
                    {
                        "doc_id": result.doc_id,
                        "score": result.score,
                        "title": result.title,
                        "url": result.url,
                        "snippet": result.snippet,
                    }
                )

            else:
                # Supports simple JSON-serializable values.
                # This is useful for generic CacheManager tests.
                serialized_results.append(result)

        return json.dumps(
            serialized_results,
            separators=(",", ":"),
        )

    def _deserialize_results(self, results_json: str) -> list[Any]:
        """Convert JSON back into result objects."""

        data = json.loads(results_json)

        if self.result_factory is None:
            return data

        return [
            self.result_factory(**result)
            for result in data
        ]

    def put(self, key: tuple, results: list[Any]) -> None:
        """
        Persist a cache entry.

        Uses INSERT OR REPLACE inside a transaction so that the
        entire cache entry is written atomically.
        """

        try:
            cache_key = self._serialize_key(key)
            results_json = self._serialize_results(results)

            created_at = datetime.now(timezone.utc).isoformat()

            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (
                        cache_key,
                        index_version,
                        results_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        self.index_version,
                        results_json,
                        created_at,
                    ),
                )

                connection.commit()

        except (
            sqlite3.Error,
            TypeError,
            ValueError,
            AttributeError,
        ):
            # Persistent caching must never break the search engine.
            return

    def get(self, key: tuple) -> list[Any] | None:
        """
        Retrieve a cached entry.

        Returns None when:
            - the key does not exist
            - the stored index version is stale
            - the database is unreadable
            - the stored JSON is corrupt
        """

        try:
            cache_key = self._serialize_key(key)

            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT index_version, results_json
                    FROM cache_entries
                    WHERE cache_key = ?
                    """,
                    (cache_key,),
                ).fetchone()

            if row is None:
                return None

            stored_index_version, results_json = row

            # Do not restore results generated from an older index.
            if str(stored_index_version) != self.index_version:
                return None

            return self._deserialize_results(results_json)

        except (
            sqlite3.Error,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            # Corrupt/unreadable cache should behave like a cache miss.
            return None

    def remove(self, key: tuple) -> bool:
        """Remove a persistent cache entry."""

        try:
            cache_key = self._serialize_key(key)

            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM cache_entries
                    WHERE cache_key = ?
                    """,
                    (cache_key,),
                )

                connection.commit()

                return cursor.rowcount > 0

        except sqlite3.Error:
            return False

    def clear(self) -> None:
        """Remove all persistent cache entries."""

        try:
            with self._connect() as connection:
                connection.execute(
                    "DELETE FROM cache_entries"
                )

                connection.commit()

        except sqlite3.Error:
            return