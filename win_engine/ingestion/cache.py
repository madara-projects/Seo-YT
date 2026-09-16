from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol


logger = logging.getLogger(__name__)


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...


class TTLCache:
    """Simple in-memory TTL cache for API responses."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None

        expires_at, value = entry
        if time.time() >= expires_at:
            self._store.pop(key, None)
            return None

        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = time.time() + (ttl_seconds if ttl_seconds is not None else self._ttl)
        self._store[key] = (expires_at, value)


class RedisTTLCache:
    """Optional Redis-backed TTL cache with JSON serialization."""

    def __init__(self, redis_url: str, ttl_seconds: int, key_prefix: str = "win_engine") -> None:
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - dependency presence differs by env
            raise RuntimeError("Redis support is not installed.") from exc

        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds
        self._key_prefix = key_prefix

    def get(self, key: str) -> Any | None:
        # redis.from_url connects lazily, so an unreachable server does not fail in
        # __init__ where build_cache would catch it -- it fails on the first command.
        # The cache is an optimization, so a backend outage degrades to a miss rather
        # than failing the request that happened to warm it.
        try:
            raw = self._redis.get(self._full_key(key))
        except Exception as exc:
            logger.warning("Redis cache read unavailable (%s); serving as a cache miss.", type(exc).__name__)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        serialized = json.dumps(value)
        try:
            self._redis.setex(self._full_key(key), ttl_seconds if ttl_seconds is not None else self._ttl, serialized)
        except Exception as exc:
            logger.warning("Redis cache write unavailable (%s); result was not cached.", type(exc).__name__)

    def _full_key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"


def probe_cache_backend(redis_url: str | None) -> bool | None:
    """Return Redis reachability, or None when no Redis is configured.

    Commands connect lazily, so an unreachable server is invisible until the first
    read. Health reporting needs an explicit round trip to see it.
    """

    if not redis_url:
        return None
    try:
        import redis

        redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
        return True
    except Exception as exc:
        logger.warning("Redis health probe failed (%s).", type(exc).__name__)
        return False


def build_cache(ttl_seconds: int, redis_url: str | None = None, key_prefix: str = "win_engine") -> CacheBackend:
    """Build a cache backend, preferring Redis when configured and available."""

    if redis_url:
        try:
            return RedisTTLCache(redis_url=redis_url, ttl_seconds=ttl_seconds, key_prefix=key_prefix)
        except Exception:
            pass
    return TTLCache(ttl_seconds)
