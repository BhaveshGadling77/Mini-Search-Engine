import threading

from wl3.cache.cache_manager import CacheManager, build_cache_key


def test_concurrent_put_and_get(tmp_path):
    db_path = tmp_path / "concurrency.db"

    cache = CacheManager(
        capacity=100,
        db_path=str(db_path),
        index_version="v17",
    )

    errors = []

    def worker(thread_id):
        try:
            for i in range(50):
                key = build_cache_key(
                    f"query-{thread_id}-{i}",
                    "bm25",
                    10,
                    False,
                    "v17",
                )

                value = [f"result-{thread_id}-{i}"]

                cache.put(key, value)

                result = cache.get(key)

                if result != value:
                    errors.append(
                        f"Incorrect result for {key}"
                    )

        except Exception as exc:
            errors.append(str(exc))

    threads = [
        threading.Thread(
            target=worker,
            args=(thread_id,),
        )
        for thread_id in range(10)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert errors == []