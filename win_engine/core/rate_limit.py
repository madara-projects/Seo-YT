from __future__ import annotations

import time
from collections import deque
from typing import Deque


class InMemoryRateLimiter:
    """Very small per-key sliding-window rate limiter for local and single-instance use.

    Idle keys are swept once per window, and the table is capped, so it cannot
    grow without bound. A key that is currently throttled is never evicted to
    make room: otherwise touching enough new keys would reset its limit.
    """

    def __init__(self, max_requests: int, window_seconds: int, max_keys: int = 10_000) -> None:
        self._max_requests = max(1, max_requests)
        self._window_seconds = window_seconds
        self._max_keys = max(1, max_keys)
        self._events: dict[str, Deque[float]] = {}
        self._next_sweep = 0.0

    def check(self, key: str) -> tuple[bool, int]:
        # Monotonic, so a system clock change cannot reset or stretch a window.
        now = time.monotonic()
        cutoff = now - self._window_seconds

        if now >= self._next_sweep or (key not in self._events and len(self._events) >= self._max_keys):
            self._sweep(cutoff)
            self._next_sweep = now + self._window_seconds

        bucket = self._events.setdefault(key, deque())

        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self._max_requests:
            retry_after = max(1, int(self._window_seconds - (now - bucket[0])))
            return False, retry_after

        bucket.append(now)
        return True, 0

    def _sweep(self, cutoff: float) -> None:
        # A key with no request inside the window carries no state worth keeping.
        for key in [key for key, bucket in self._events.items() if not bucket or bucket[-1] < cutoff]:
            del self._events[key]
        # Still full: drop the least recently used keys that are not throttled.
        overflow = len(self._events) - self._max_keys + 1
        if overflow > 0:
            evictable = [
                key
                for key, bucket in self._events.items()
                if sum(1 for stamp in bucket if stamp >= cutoff) < self._max_requests
            ]
            for key in sorted(evictable, key=lambda item: self._events[item][-1])[:overflow]:
                del self._events[key]

    def __len__(self) -> int:
        return len(self._events)
