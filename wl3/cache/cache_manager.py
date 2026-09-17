from __future__ import annotations

from typing import Any

from wl3.cache.lru_cache import LRUCache
from wl3.cache.sqlite_cache import SQLiteCache


def build_cache_key(
    query: str,
    ranking_mode: str,
    k: int,
    use_mmr: bool,
    index_version: str | int,
) -> tuple:
    """
    Build a unique cache key for a search request.
    """

    normalized_query = " ".join(query.lower().split())
    normalized_ranking_mode = ranking_mode.lower()

    return (
        normalized_query,
        normalized_ranking_mode,
        k,
        use_mmr,
        str(index_version),
    )


class CacheManager:
    """
    Two-level cache manager.

    L1: In-memory thread-safe LRU cache
    L2: Persistent SQLite cache

    QueryEngine interacts only with CacheManager.
    """

    def __init__(
        self,
        capacity: int = 100,
        db_path: str = "cache.db",
        index_version: str | int = "unknown",
        result_factory: Any | None = None,
    ):
        self._lru = LRUCache[Any, Any](capacity)

        self._sqlite = SQLiteCache(
            db_path=db_path,
            index_version=index_version,
            result_factory=result_factory,
        )

    def get(self, key: tuple) -> Any | None:
        """
        Get a value from the cache.

        Lookup order:
        1. LRU
        2. SQLite

        If SQLite contains the value, promote it into the LRU.
        """

        # L1: Check in-memory cache first.
        value = self._lru.get(key)

        if value is not None:
            return value

        # L2: Check persistent SQLite cache.
        value = self._sqlite.get(key)

        if value is not None:
            # Promote SQLite hit into LRU.
            self._lru.put(key, value)

        return value

    def put(self, key: tuple, value: Any) -> None:
        """
        Store a value in both LRU and SQLite.
        """

        # L1
        self._lru.put(key, value)

        # L2
        self._sqlite.put(key, value)

    def remove(self, key: tuple) -> bool:
        """
        Remove a key from both cache levels.

        Returns True if the key existed in either cache.
        """

        removed_from_lru = self._lru.remove(key)
        removed_from_sqlite = self._sqlite.remove(key)

        return removed_from_lru or removed_from_sqlite

    def clear(self) -> None:
        """
        Clear both LRU and SQLite caches.
        """

        self._lru.clear()
        self._sqlite.clear()

    def __len__(self) -> int:
        """
        Return the number of entries currently in the LRU cache.
        """

        return len(self._lru)