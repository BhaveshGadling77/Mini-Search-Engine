from wl3.cache.cache_manager import CacheManager, build_cache_key


def test_build_cache_key():
    key = build_cache_key(
        "  Machine   Learning ",
        "BM25",
        10,
        False,
        "v17",
    )

    assert key == (
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )


def test_cache_key_distinguishes_ranking_modes():
    bm25_key = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    tfidf_key = build_cache_key(
        "machine learning",
        "tfidf",
        10,
        False,
        "v17",
    )

    assert bm25_key != tfidf_key


def test_cache_key_distinguishes_k():
    key_10 = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    key_20 = build_cache_key(
        "machine learning",
        "bm25",
        20,
        False,
        "v17",
    )

    assert key_10 != key_20


def test_cache_key_distinguishes_mmr():
    without_mmr = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    with_mmr = build_cache_key(
        "machine learning",
        "bm25",
        10,
        True,
        "v17",
    )

    assert without_mmr != with_mmr


def test_cache_key_distinguishes_index_version():
    old_version = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    new_version = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v18",
    )

    assert old_version != new_version


def test_cache_manager_put_and_get():
    cache = CacheManager(capacity=10)

    key = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    value = ["result1", "result2"]

    cache.put(key, value)

    assert cache.get(key) == value


def test_cache_manager_miss():
    cache = CacheManager(capacity=10)

    key = build_cache_key(
        "unknown",
        "bm25",
        10,
        False,
        "v17",
    )

    assert cache.get(key) is None


def test_cache_manager_remove():
    cache = CacheManager(capacity=10)

    key = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    cache.put(key, ["result1"])

    assert cache.remove(key) is True
    assert cache.get(key) is None


def test_cache_manager_clear():
    cache = CacheManager(capacity=10)

    key1 = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    key2 = build_cache_key(
        "deep learning",
        "bm25",
        10,
        False,
        "v17",
    )

    cache.put(key1, ["result1"])
    cache.put(key2, ["result2"])

    cache.clear()

    assert len(cache) == 0
    assert cache.get(key1) is None
    assert cache.get(key2) is None


def test_sqlite_fallback_promotes_to_lru(tmp_path):
    db_path = tmp_path / "cache.db"

    key = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    value = ["result1", "result2"]

    # Manager 1 writes to both LRU and SQLite.
    cache1 = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v17",
    )

    cache1.put(key, value)

    # Manager 2 simulates a fresh application process.
    # Its LRU starts empty, but SQLite contains the result.
    cache2 = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v17",
    )

    assert cache2.get(key) == value

    # The SQLite result should have been promoted into LRU.
    assert len(cache2) == 1


def test_stale_sqlite_entry_is_not_returned(tmp_path):
    db_path = tmp_path / "cache.db"

    key = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    value = ["old result"]

    cache1 = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v17",
    )

    cache1.put(key, value)

    # New index version.
    cache2 = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v18",
    )

    assert cache2.get(key) is None


def test_put_stores_in_both_levels(tmp_path):
    db_path = tmp_path / "cache.db"

    key = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    value = ["result1"]

    cache = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v17",
    )

    cache.put(key, value)

    # L1 hit.
    assert cache.get(key) == value

    # Create a new manager.
    # This forces lookup through SQLite.
    new_cache = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v17",
    )

    assert new_cache.get(key) == value


def test_clear_removes_both_levels(tmp_path):
    db_path = tmp_path / "cache.db"

    key = build_cache_key(
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    value = ["result1"]

    cache = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v17",
    )

    cache.put(key, value)
    cache.clear()

    assert cache.get(key) is None

    # New manager confirms SQLite was also cleared.
    new_cache = CacheManager(
        capacity=10,
        db_path=str(db_path),
        index_version="v17",
    )

    assert new_cache.get(key) is None