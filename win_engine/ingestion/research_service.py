from __future__ import annotations

import logging
import re

from win_engine.analysis.entity_extractor import extract_entity_signals
from win_engine.analysis.keyword_extractor import extract_keyword_signals
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

    def gather(self, script: str, region: str = "global", primary_language: str = "english") -> dict[str, object]:
        query = script[:120]
        cache_policy, ttl_seconds = self._select_cache_policy(query)

        youtube_key = f"yt:{cache_policy}:{query}"

        youtube_results = self._cache.get(youtube_key)
        if youtube_results is None:
            youtube_results = self._youtube.search_videos(query, self._settings.youtube_max_results)
            self._cache.set(youtube_key, youtube_results, ttl_seconds=ttl_seconds)

        scored_results = score_outliers(youtube_results, region=region, primary_language=primary_language)
        scored_results = self._attach_velocity_signals(scored_results)
        self._history.record_snapshots(query, scored_results)
        top_opportunities = scored_results[:3]
        keyword_signals = extract_keyword_signals(script, scored_results, region, primary_language)
        entity_signals = extract_entity_signals(script, scored_results)
        upload_timing = self._history.upload_timing_insights(scored_results)
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
            "research_warnings": research_warnings,
            "cache_policy": cache_policy,
            "youtube_runtime": runtime_state,
            "history_store": self._history,
        }

    def diagnostics(self) -> dict[str, object]:
        """Return a quick health check for external integrations."""

        youtube_status = "ok" if self._settings.youtube_api_key else "missing_api_key"

        # Use a short, fixed query so users can see errors easily.
        test_query = "youtube growth tips"

        youtube_error = None

        if youtube_status == "ok":
            try:
                self._youtube.search_videos(test_query, max_results=1, raise_on_error=True)
            except Exception as exc:  # noqa: BLE001 - show error details to user
                youtube_error = str(exc)
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
