from __future__ import annotations

import logging
import re
from hashlib import sha256
from typing import Any

from win_engine.analysis.entity_extractor import extract_entity_signals
from win_engine.analysis.keyword_extractor import extract_keyword_signals
from win_engine.analysis.research_insights import build_research_decision
from win_engine.analysis.research_planner import brief_research_text, plan_research_queries
from win_engine.analysis.strategy_layer import build_upload_timing
from win_engine.analysis.thumbnail_intelligence import analyze_thumbnails
from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.ingestion.cache import build_cache
from win_engine.ingestion.youtube_client import YouTubeClient
from win_engine.scoring.outlier_engine import score_outliers


logger = logging.getLogger(__name__)


class ResearchService:
    """Coordinates external data lookups for SEO research."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache = build_cache(
            ttl_seconds=settings.cache_ttl_evergreen_seconds,
            redis_url=settings.redis_url,
            key_prefix=settings.redis_key_prefix,
        )
        self._youtube = YouTubeClient(settings.youtube_api_key_pool, settings.request_timeout_seconds)
        self._history = HistoryStore(settings.database_path)

    def gather(
        self,
        script: str,
        region: str = "global",
        primary_language: str = "english",
        creator_brief: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        research_queries = plan_research_queries(
            script=script,
            creator_brief=creator_brief,
            region=region,
            primary_language=primary_language,
            max_queries=self._settings.youtube_max_research_queries,
        )
        query = research_queries[0]["query"] if research_queries else script[:120]
        cache_policy, ttl_seconds = self._select_cache_policy(query)

        youtube_results = self._search_research_queries(research_queries, cache_policy, ttl_seconds)

        scored_results = score_outliers(youtube_results, region=region, primary_language=primary_language)
        scored_results = self._attach_velocity_signals(scored_results)
        self._history.record_snapshots(query, scored_results)
        top_opportunities = scored_results[:3]
        research_text = brief_research_text(script, creator_brief)
        keyword_signals = extract_keyword_signals(research_text, scored_results, region, primary_language)
        entity_signals = extract_entity_signals(research_text, scored_results)
        upload_timing = build_upload_timing(scored_results, region=region)
        thumbnail_intelligence = analyze_thumbnails(scored_results)
        runtime_state = self._youtube.runtime_state()
        research_warnings = [runtime_state["warning"]] if runtime_state.get("warning") else []

        logger.info(
            "Research gathered: youtube=%s",
            len(youtube_results),
        )

        return {
            "youtube_results": scored_results,
            "top_opportunities": top_opportunities,
            "keyword_signals": keyword_signals,
            "entity_signals": entity_signals,
            "upload_timing": upload_timing,
            "thumbnail_intelligence": thumbnail_intelligence,
            "research_queries": research_queries,
            "research_decision": build_research_decision(creator_brief, scored_results),
            "research_warnings": research_warnings,
            "cache_policy": cache_policy,
            "youtube_runtime": runtime_state,
            "history_store": self._history,
        }

    def _search_research_queries(
        self,
        research_queries: list[dict[str, str]],
        cache_policy: str,
        ttl_seconds: int,
    ) -> list[dict[str, object]]:
        """Search each planned angle and de-duplicate videos across the result set."""

        merged: dict[str, dict[str, object]] = {}
        for item in research_queries:
            query = item["query"]
            query_type = item["type"]
            cache_id = sha256(query.casefold().encode("utf-8")).hexdigest()[:20]
            youtube_key = f"yt:{cache_policy}:{cache_id}"
            results = self._cache.get(youtube_key)
            if results is None:
                results = self._youtube.search_videos(query, self._settings.youtube_max_results)
                self._cache.set(youtube_key, results, ttl_seconds=ttl_seconds)

            for result in results or []:
                video_id = str(result.get("video_id") or "")
                if not video_id:
                    continue
                existing = merged.get(video_id)
                if existing:
                    matched = list(existing.get("matched_queries") or [])
                    if query_type not in matched:
                        matched.append(query_type)
                        existing["matched_queries"] = matched
                    continue
                merged[video_id] = {
                    **result,
                    "research_query": query,
                    "matched_queries": [query_type],
                }
        return list(merged.values())

    def diagnostics(self) -> dict[str, object]:
        """Return a quick health check for external integrations."""

        youtube_status = "ok" if self._settings.youtube_api_key_pool else "missing_api_key"

        # Use a short, fixed query so users can see errors easily.
        test_query = "youtube growth tips"

        youtube_error = None

        if youtube_status == "ok":
            try:
                self._youtube.search_videos(test_query, max_results=1, raise_on_error=True)
            except Exception as exc:  # noqa: BLE001 - diagnostics must not expose request URLs or keys
                logger.warning("Diagnostics YouTube check failed: %s", type(exc).__name__)
                youtube_error = "YouTube request failed. Check the API key and network connection."
                youtube_status = "error"

        return {
            "youtube": {
                "status": youtube_status,
                "error": youtube_error,
                **self._youtube.runtime_state(),
            },
        }

    def _select_cache_policy(self, query: str) -> tuple[str, int]:
        lowered = query.lower()
        trending_patterns = [
            r"\b202[0-9]\b",
            r"\btoday\b",
            r"\blatest\b",
            r"\bnew\b",
            r"\bviral\b",
            r"\btrending\b",
            r"\bbreaking\b",
            r"\bnow\b",
        ]

        is_trending = any(re.search(pattern, lowered) for pattern in trending_patterns)
        if is_trending:
            return "trending", self._settings.cache_ttl_trending_seconds

        return "evergreen", self._settings.cache_ttl_evergreen_seconds

    def _attach_velocity_signals(self, youtube_results: list[dict[str, object]]) -> list[dict[str, object]]:
        enriched: list[dict[str, object]] = []

        for result in youtube_results:
            video_id = str(result.get("video_id", ""))
            velocity = self._history.velocity_signals(video_id) if video_id else {}
            enriched.append({**result, **velocity})

        return enriched
