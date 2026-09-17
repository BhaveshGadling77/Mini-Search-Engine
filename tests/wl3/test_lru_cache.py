import pytest

from wl3.cache.lru_cache import LRUCache


def test_put_and_get():
    cache = LRUCache[str, int](capacity=2)

    cache.put("a", 100)

    assert cache.get("a") == 100


def test_cache_miss():
    cache = LRUCache[str, int](capacity=2)

    assert cache.get("missing") is None


def test_lru_eviction():
    cache = LRUCache[str, int](capacity=2)

    cache.put("a", 100)
    cache.put("b", 200)

    # "a" is now the least recently used.
    cache.put("c", 300)

    assert cache.get("a") is None
    assert cache.get("b") == 200
    assert cache.get("c") == 300


def test_get_updates_recency():
    cache = LRUCache[str, int](capacity=2)

    cache.put("a", 100)
    cache.put("b", 200)

    # Access "a", making it most recently used.
    assert cache.get("a") == 100

    # "b" should now be evicted.
    cache.put("c", 300)

    assert cache.get("b") is None
    assert cache.get("a") == 100
    assert cache.get("c") == 300


def test_update_existing_key():
    cache = LRUCache[str, int](capacity=2)

    cache.put("a", 100)
    cache.put("b", 200)

    cache.put("a", 999)

    assert cache.get("a") == 999
    assert len(cache) == 2


def test_remove():
    cache = LRUCache[str, int](capacity=2)

    cache.put("a", 100)

    assert cache.remove("a") is True
    assert cache.get("a") is None

    assert cache.remove("a") is False


def test_clear():
    cache = LRUCache[str, int](capacity=3)

    cache.put("a", 100)
    cache.put("b", 200)
    cache.put("c", 300)

    cache.clear()

    assert len(cache) == 0
    assert cache.get("a") is None
    assert cache.get("b") is None
    assert cache.get("c") is None


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        LRUCache[str, int](capacity=0)