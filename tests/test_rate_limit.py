"""The in-memory rate limiter enforces its window and forgets idle clients."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from win_engine.core.rate_limit import InMemoryRateLimiter

CLOCK = "win_engine.core.rate_limit.time.monotonic"


class RateLimiterTests(unittest.TestCase):
    def test_limits_within_the_window_and_recovers_after_it(self):
        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
        with patch(CLOCK, return_value=1000.0):
            self.assertEqual(limiter.check("a")[0], True)
            self.assertEqual(limiter.check("a")[0], True)
            allowed, retry_after = limiter.check("a")
        self.assertFalse(allowed)
        self.assertEqual(retry_after, 60)
        with patch(CLOCK, return_value=1061.0):
            self.assertTrue(limiter.check("a")[0])

    def test_idle_keys_are_swept_after_a_window(self):
        limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
        with patch(CLOCK, return_value=1000.0):
            for index in range(50):
                limiter.check(f"127.0.0.1:/api/history/runs/{index}")
        self.assertEqual(len(limiter), 50)

        with patch(CLOCK, return_value=1100.0):
            limiter.check("127.0.0.1:/health")

        self.assertEqual(len(limiter), 1)

    def test_the_key_table_is_capped(self):
        limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60, max_keys=10)
        for index in range(25):
            with patch(CLOCK, return_value=1000.0 + index):
                limiter.check(f"key-{index}")

        self.assertLessEqual(len(limiter), 10)
        # The most recent clients survive; the oldest were dropped first.
        with patch(CLOCK, return_value=1030.0):
            for _ in range(4):
                self.assertTrue(limiter.check("key-24")[0])
            self.assertFalse(limiter.check("key-24")[0])

    def test_flooding_new_keys_cannot_reset_a_throttled_key(self):
        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60, max_keys=5)
        with patch(CLOCK, return_value=1000.0):
            limiter.check("costly")
            limiter.check("costly")
            self.assertFalse(limiter.check("costly")[0])
            for index in range(50):
                limiter.check(f"junk-{index}")
            # Still throttled: its bucket was never the one evicted.
            self.assertFalse(limiter.check("costly")[0])

    def test_a_zero_limit_is_raised_to_one_rather_than_crashing(self):
        limiter = InMemoryRateLimiter(max_requests=0, window_seconds=60)
        with patch(CLOCK, return_value=1000.0):
            self.assertTrue(limiter.check("a")[0])
            self.assertFalse(limiter.check("a")[0])


if __name__ == "__main__":
    unittest.main()
