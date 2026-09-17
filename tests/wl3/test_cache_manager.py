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