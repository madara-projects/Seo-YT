from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Protocol


logger = logging.getLogger(__name__)
# Health-probe clients, one per Redis URL (see probe_cache_backend).
_PROBE_CLIENTS: dict[str, Any] = {}


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...


class TTLCache:
    """In-memory TTL cache for API responses, bounded to ``max_entries``.

    Values are stored as JSON, the way Redis stores them. Handing out the stored
    object let one caller's edit change the cached copy for every later request,
    and a value Redis cannot hold would have worked only without Redis.
    """

    def __init__(self, ttl_seconds: int, max_entries: int = 512) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max(1, max_entries)
        self._store: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.pop(key, None)
            if entry is None or time.time() >= entry[0]:
                return None
            self._store[key] = entry  # re-inserted last: the most recently used entry
        return json.loads(entry[1])

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        serialized = json.dumps(value)
        expires_at = time.time() + (ttl_seconds if ttl_seconds is not None else self._ttl)
        with self._lock:
            self._store.pop(key, None)
            self._store[key] = (expires_at, serialized)
            if len(self._store) > self._max_entries:
                now = time.time()
                for expired in [name for name, (expiry, _) in self._store.items() if expiry <= now]:
                    del self._store[expired]
            while len(self._store) > self._max_entries:
                del self._store[next(iter(self._store))]  # least recently used


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

        # One pooled client per URL: the health check runs every few seconds.
        client = _PROBE_CLIENTS.get(redis_url)
        if client is None:
            client = _PROBE_CLIENTS.setdefault(
                redis_url, redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
            )
        client.ping()
        return True
    except Exception as exc:
        logger.warning("Redis health probe failed (%s).", type(exc).__name__)
        return False


def build_cache(ttl_seconds: int, redis_url: str | None = None, key_prefix: str = "win_engine") -> CacheBackend:
    """Build a cache backend, preferring Redis when configured and available."""

    if redis_url:
        try:
            return RedisTTLCache(redis_url=redis_url, ttl_seconds=ttl_seconds, key_prefix=key_prefix)
        except Exception as exc:
            # Type only: the URL can carry the Redis password.
            logger.warning("Redis cache unavailable (%s); using the in-memory cache.", type(exc).__name__)
    return TTLCache(ttl_seconds)


_SHARED_CACHES: dict[tuple[str, str, int], CacheBackend] = {}
_SHARED_CACHES_LOCK = threading.Lock()


def shared_cache(ttl_seconds: int, redis_url: str | None = None, key_prefix: str = "win_engine") -> CacheBackend:
    """The process-wide cache for one configuration, built on first use.

    Routes build a new ResearchService per request. Each one used to build its own
    cache, so without Redis no YouTube result or search suggestion was ever reused.
    """

    config = (redis_url or "", key_prefix, ttl_seconds)
    with _SHARED_CACHES_LOCK:
        cache = _SHARED_CACHES.get(config)
        if cache is None:
            cache = _SHARED_CACHES[config] = build_cache(ttl_seconds, redis_url=redis_url, key_prefix=key_prefix)
        return cache
