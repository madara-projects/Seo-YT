"""The in-memory cache is bounded, isolated, shared per process, and honest about Redis."""

import unittest
from unittest.mock import patch

from win_engine.ingestion import cache as cache_module
from win_engine.ingestion.cache import TTLCache, build_cache, shared_cache


class TTLCacheTests(unittest.TestCase):
    def test_least_recently_used_entry_is_evicted_at_the_cap(self):
        cache = TTLCache(ttl_seconds=60, max_entries=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # "b" is now the least recently used
        cache.set("c", 3)

        self.assertEqual((cache.get("a"), cache.get("b"), cache.get("c")), (1, None, 3))

    def test_callers_get_copies(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("rows", [{"title": "Tom &amp; Jerry"}])
        cache.get("rows")[0]["title"] = "changed by a caller"

        self.assertEqual(cache.get("rows"), [{"title": "Tom &amp; Jerry"}])

    def test_expired_entries_are_misses(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("gone", 1, ttl_seconds=0)

        self.assertIsNone(cache.get("gone"))


class SharedCacheTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(cache_module._SHARED_CACHES, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_cache_per_configuration(self):
        first = shared_cache(ttl_seconds=60, key_prefix="win_engine")

        self.assertIs(shared_cache(ttl_seconds=60, key_prefix="win_engine"), first)
        self.assertIsNot(shared_cache(ttl_seconds=60, key_prefix="other"), first)

    def test_redis_fallback_is_logged_once_without_the_url(self):
        url = "redis://:hunter2@cache.internal:6379/0"
        with patch.object(cache_module, "RedisTTLCache", side_effect=ValueError(f"bad url {url}")), \
                self.assertLogs("win_engine.ingestion.cache", level="WARNING") as logs:
            first = shared_cache(ttl_seconds=60, redis_url=url)
            second = shared_cache(ttl_seconds=60, redis_url=url)

        self.assertIsInstance(first, TTLCache)
        self.assertIs(second, first)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("ValueError", logs.output[0])
        self.assertNotIn("hunter2", logs.output[0])

    def test_build_cache_without_redis_is_in_memory(self):
        self.assertIsInstance(build_cache(ttl_seconds=60), TTLCache)


if __name__ == "__main__":
    unittest.main()
