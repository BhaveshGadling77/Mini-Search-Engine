from __future__ import annotations

from typing import Any

from wl3.cache.lru_cache import LRUCache


def build_cache_key(
    query: str,
    ranking_mode: str,
    k: int,
    use_mmr: bool,
    index_version: str | int,
) -> tuple:
    """
    Build the unique key used by the shared cache.

    The key distinguishes:
        - normalized query
        - ranking mode
        - requested result count
        - MMR usage
        - index version
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
    Coordinates the in-memory LRU cache and, eventually,
    the SQLite persistent cache.

    QueryEngine should interact with CacheManager rather than
    directly accessing LRUCache or SQLiteCache.
    """

    def __init__(self, capacity: int = 100):
        self._lru = LRUCache[Any, Any](capacity)

    def get(self, key: tuple) -> Any | None:
        """
        Retrieve a value from the cache.

        Currently checks the in-memory LRU cache.
        SQLite persistence will be added later.
        """

        return self._lru.get(key)

    def put(self, key: tuple, value: Any) -> None:
        """Store a value in the in-memory cache."""

        self._lru.put(key, value)

    def remove(self, key: tuple) -> bool:
        """Remove a value from the cache."""

        return self._lru.remove(key)

    def clear(self) -> None:
        """Clear the in-memory cache."""

        self._lru.clear()

    def __len__(self) -> int:
        """Return the number of entries in the in-memory cache."""

        return len(self._lru)