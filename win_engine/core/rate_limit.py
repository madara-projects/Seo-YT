from __future__ import annotations

import time
from collections import deque
from typing import Deque


class InMemoryRateLimiter:
    """Very small per-key sliding-window rate limiter for local and single-instance use."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._events: dict[str, Deque[float]] = {}

    def check(self, key: str) -> tuple[bool, int]:
        now = time.time()
        bucket = self._events.setdefault(key, deque())
        cutoff = now - self._window_seconds

        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self._max_requests:
            retry_after = max(1, int(self._window_seconds - (now - bucket[0])))
            return False, retry_after

        bucket.append(now)
        return True, 0
