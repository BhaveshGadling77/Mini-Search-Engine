from dataclasses import dataclass

from wl3.cache.sqlite_cache import SQLiteCache


@dataclass
class DummyResult:
    doc_id: int
    score: float
    title: str
    url: str
    snippet: str


def make_key():
    return (
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )


def make_results():
    return [
        DummyResult(
            doc_id=1,
            score=0.95,
            title="Machine Learning",
            url="https://example.com/ml",
            snippet="Introduction to machine learning.",
        ),
        DummyResult(
            doc_id=2,
            score=0.82,
            title="Deep Learning",
            url="https://example.com/dl",
            snippet="Introduction to deep learning.",
        ),
    ]


def test_put_and_get(tmp_path):
    db_path = tmp_path / "cache.db"

    cache = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    key = make_key()
    results = make_results()

    cache.put(key, results)

    retrieved = cache.get(key)

    assert retrieved == results


def test_cache_miss(tmp_path):
    db_path = tmp_path / "cache.db"

    cache = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    assert cache.get(make_key()) is None


def test_persistence_across_instances(tmp_path):
    db_path = tmp_path / "cache.db"

    key = make_key()
    results = make_results()

    cache1 = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    cache1.put(key, results)

    # Simulate restarting the application.
    cache2 = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    assert cache2.get(key) == results


def test_old_index_version_is_stale(tmp_path):
    db_path = tmp_path / "cache.db"

    key = make_key()
    results = make_results()

    old_cache = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    old_cache.put(key, results)

    new_cache = SQLiteCache(
        str(db_path),
        index_version="v18",
        result_factory=DummyResult,
    )

    assert new_cache.get(key) is None


def test_remove(tmp_path):
    db_path = tmp_path / "cache.db"

    cache = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    key = make_key()

    cache.put(key, make_results())

    assert cache.remove(key) is True
    assert cache.get(key) is None

    assert cache.remove(key) is False


def test_clear(tmp_path):
    db_path = tmp_path / "cache.db"

    cache = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    cache.put(make_key(), make_results())

    cache.clear()

    assert cache.get(make_key()) is None


def test_multiple_cache_entries(tmp_path):
    db_path = tmp_path / "cache.db"

    cache = SQLiteCache(
        str(db_path),
        index_version="v17",
        result_factory=DummyResult,
    )

    key1 = (
        "machine learning",
        "bm25",
        10,
        False,
        "v17",
    )

    key2 = (
        "deep learning",
        "tfidf",
        5,
        True,
        "v17",
    )

    results1 = make_results()

    results2 = [
        DummyResult(
            doc_id=3,
            score=0.77,
            title="Neural Networks",
            url="https://example.com/nn",
            snippet="Neural network fundamentals.",
        )
    ]

    cache.put(key1, results1)
    cache.put(key2, results2)

    assert cache.get(key1) == results1
    assert cache.get(key2) == results2
