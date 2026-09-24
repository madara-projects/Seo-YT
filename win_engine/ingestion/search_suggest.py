"""YouTube search-suggestion demand signal.

The YouTube Data API returns sampled search *results*; it says nothing about
what viewers actually type. YouTube's search suggestions — the list under the
search box — are the closest freely available demand signal: a phrase that
appears there is something real viewers type, and its position reflects its
relative popularity for that prefix. vidIQ and TubeBuddy build on the same
signal.

It is not search volume and must never be presented as volume.

The endpoint is unofficial (it is what the YouTube search box itself calls), so
every use is bounded, concurrent, cached, and fails soft: when suggestions are
unavailable, the package is generated exactly as it was before, and the
research record says demand could not be checked. Disable it entirely with
``WIN_ENGINE_SEARCH_SUGGEST_ENABLED=false``.
"""

from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from typing import Any, Iterable

import httpx

from win_engine.ingestion.cache import CacheBackend

logger = logging.getLogger(__name__)

ENDPOINT = "https://suggestqueries.google.com/complete/search"
SCOPE = "youtube_search_suggestions_not_volume"

_LANGUAGE_CODES = {"english": "en", "tamil": "en", "tanglish": "en", "hindi": "en"}
_REGION_CODES = {"india": "IN", "in": "IN", "us": "US", "usa": "US", "uk": "GB", "gb": "GB"}


def normalize_phrase(value: Any) -> str:
    """Lower-case, single-spaced phrase for matching suggestions to tags."""

    text = re.sub(r"[^\w஀-௿' ]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


class SearchSuggestClient:
    """Bounded, cached, concurrent access to YouTube search suggestions."""

    def __init__(
        self,
        *,
        enabled: bool,
        timeout_seconds: float,
        max_queries: int,
        cache: CacheBackend | None = None,
        ttl_seconds: int = 3 * 24 * 3600,
    ) -> None:
        self._enabled = enabled
        self._timeout = max(0.5, float(timeout_seconds))
        self._max_queries = max(0, int(max_queries))
        self._cache = cache
        self._ttl = ttl_seconds

    @property
    def enabled(self) -> bool:
        return self._enabled and self._max_queries > 0

    def fetch(self, queries: Iterable[str], *, language: str = "english", region: str = "global") -> dict[str, Any]:
        """Suggestions for each query, plus honest diagnostics about the lookup."""

        wanted: list[str] = []
        for query in queries:
            clean = normalize_phrase(query)
            if clean and clean not in wanted:
                wanted.append(clean)
        wanted = wanted[: self._max_queries]
        result: dict[str, Any] = {
            "status": "disabled" if not self.enabled else "ok",
            "scope": SCOPE,
            "queries": wanted if self.enabled else [],
            "suggestions": {},
            "cache_hits": 0,
            "failed_queries": [],
        }
        if not self.enabled or not wanted:
            if self.enabled:
                result["status"] = "no_seed_queries"
            return result

        hl = _LANGUAGE_CODES.get(str(language or "").casefold(), "en")
        gl = _REGION_CODES.get(str(region or "").casefold(), "")
        pending: list[str] = []
        for query in wanted:
            cached = self._cache.get(self._cache_key(query, hl, gl)) if self._cache else None
            if isinstance(cached, list):
                result["suggestions"][query] = cached
                result["cache_hits"] += 1
            else:
                pending.append(query)

        if pending:
            with ThreadPoolExecutor(max_workers=min(6, len(pending))) as pool:
                fetched = list(pool.map(lambda q: (q, self._request(q, hl, gl)), pending))
            for query, suggestions in fetched:
                if suggestions is None:
                    result["failed_queries"].append(query)
                    continue
                result["suggestions"][query] = suggestions
                if self._cache:
                    try:
                        self._cache.set(self._cache_key(query, hl, gl), suggestions, ttl_seconds=self._ttl)
                    except Exception:  # a cache outage must not cost the result
                        logger.warning("Search suggestion cache write failed.")
        if not result["suggestions"]:
            result["status"] = "unavailable"
        elif result["failed_queries"]:
            result["status"] = "partial"
        return result

    def _request(self, query: str, hl: str, gl: str) -> list[str] | None:
        params = {"client": "firefox", "ds": "yt", "q": query, "hl": hl, "ie": "utf-8", "oe": "utf-8"}
        if gl:
            params["gl"] = gl
        try:
            response = httpx.get(ENDPOINT, params=params, timeout=self._timeout)
            if response.status_code != 200:
                logger.warning("Search suggestions returned HTTP %s.", response.status_code)
                return None
            payload = json.loads(response.content.decode("utf-8", errors="replace"))
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Search suggestions unavailable: %s", type(exc).__name__)
            return None
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            return None
        return [normalize_phrase(item) for item in payload[1] if normalize_phrase(item)][:10]

    @staticmethod
    def _cache_key(query: str, hl: str, gl: str) -> str:
        digest = sha256(f"{hl}|{gl}|{query}".encode("utf-8")).hexdigest()[:24]
        return f"suggest:{digest}"


def suggestion_index(demand: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Every suggested phrase with its best (lowest) rank and the seed it came from."""

    index: dict[str, dict[str, Any]] = {}
    for seed, suggestions in ((demand or {}).get("suggestions") or {}).items():
        for rank, phrase in enumerate(suggestions or []):
            existing = index.get(phrase)
            if existing is None or rank < existing["rank"]:
                index[phrase] = {"rank": rank, "seed": seed}
    return index


def demand_rank(keyword: str, index: dict[str, dict[str, Any]]) -> int | None:
    """Rank of a keyword people type, or None when no suggestion supports it.

    A keyword counts as typed when it is itself a suggestion, or when a
    suggestion extends it word-for-word ("cold brew coffee" is the head of
    "cold brew coffee recipe").
    """

    phrase = normalize_phrase(keyword)
    if not phrase:
        return None
    if phrase in index:
        return int(index[phrase]["rank"])
    extending = [row["rank"] for suggestion, row in index.items() if suggestion.startswith(phrase + " ")]
    return int(min(extending)) + 1 if extending else None
