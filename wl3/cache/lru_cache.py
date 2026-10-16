from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar


K = TypeVar("K")
V = TypeVar("V")


@dataclass
class _Node(Generic[K, V]):
    key: K
    value: V
    prev: _Node[K, V] | None = None
    next: _Node[K, V] | None = None


class LRUCache(Generic[K, V]):
    """
    Thread-safe Least Recently Used (LRU) cache.

    Uses:
        - HashMap (dict) for O(1) lookup
        - Doubly linked list for O(1) recency updates and eviction
        - Lock for thread safety
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Cache capacity must be greater than 0")

        self.capacity = capacity

        # HashMap: key -> linked-list node
        self._cache: dict[K, _Node[K, V]] = {}

        # Sentinel nodes for the doubly linked list.
        # Head = most recently used side
        # Tail = least recently used side
        self._head: _Node[K, V] = _Node(None, None)  # type: ignore
        self._tail: _Node[K, V] = _Node(None, None)  # type: ignore

        self._head.next = self._tail
        self._tail.prev = self._head

        # Makes the cache thread-safe.
        self._lock = Lock()

    def _remove_node(self, node: _Node[K, V]) -> None:
        """Remove a node from the doubly linked list."""

        prev_node = node.prev
        next_node = node.next

        if prev_node is not None:
            prev_node.next = next_node

        if next_node is not None:
            next_node.prev = prev_node

    def _add_to_front(self, node: _Node[K, V]) -> None:
        """Add a node immediately after the head."""

        first_node = self._head.next

        node.prev = self._head
        node.next = first_node

        self._head.next = node

        if first_node is not None:
            first_node.prev = node

    def _move_to_front(self, node: _Node[K, V]) -> None:
        """Mark a node as the most recently used."""

        self._remove_node(node)
        self._add_to_front(node)

    def _remove_least_recently_used(self) -> None:
        """Remove the least recently used entry."""

        lru_node = self._tail.prev

        if lru_node is None or lru_node is self._head:
            return

        self._remove_node(lru_node)
        del self._cache[lru_node.key]

    def get(self, key: K) -> V | None:
        """
        Get a value from the cache.

        Returns None if the key does not exist.

        A successful get makes the entry most recently used.
        """

        with self._lock:
            node = self._cache.get(key)

            if node is None:
                return None

            self._move_to_front(node)

            return node.value

    def put(self, key: K, value: V) -> None:
        """
        Insert or update a cache entry.

        If the cache exceeds its capacity, the least recently
        used entry is evicted.
        """

        with self._lock:
            existing_node = self._cache.get(key)

            # Updating an existing key.
            if existing_node is not None:
                existing_node.value = value
                self._move_to_front(existing_node)
                return

            # Adding a new key.
            new_node = _Node(key, value)

            self._cache[key] = new_node
            self._add_to_front(new_node)

            # Evict LRU if capacity is exceeded.
            if len(self._cache) > self.capacity:
                self._remove_least_recently_used()

    def remove(self, key: K) -> bool:
        """
        Remove an entry.

        Returns True if the entry existed and was removed.
        Returns False if the key was not present.
        """

        with self._lock:
            node = self._cache.get(key)

            if node is None:
                return False

            self._remove_node(node)
            del self._cache[key]

            return True

    def clear(self) -> None:
        """Remove all entries from the cache."""

        with self._lock:
            self._cache.clear()

            self._head.next = self._tail
            self._tail.prev = self._head

    def __len__(self) -> int:
        """Return the number of entries in the cache."""

        with self._lock:
            return len(self._cache)

    def __contains__(self, key: K) -> bool:
        """Return True if the key exists in the cache."""

        with self._lock:
            return key in self._cache