from __future__ import annotations

import logging
import re
from hashlib import sha256
from typing import Any

from win_engine.analysis.entity_extractor import extract_entity_signals
from win_engine.analysis.keyword_extractor import extract_keyword_signals
from win_engine.analysis.research_insights import build_research_decision
from win_engine.analysis.semantic_research import analyze_script_semantics, refine_research_semantics
from win_engine.analysis.keyword_research import build_keyword_research
from win_engine.analysis.search_opportunities import discover_search_opportunities
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
        semantic_analysis = analyze_script_semantics(script, creator_brief)
        research_queries = plan_research_queries(
            script=script,
            creator_brief=creator_brief,
            semantic_analysis=semantic_analysis,
            region=region,
            primary_language=primary_language,
            max_queries=self._settings.youtube_max_research_queries,
        )
        query = research_queries[0]["query"] if research_queries else script[:120]
        cache_policy, ttl_seconds = self._select_cache_policy(query)

        youtube_results, query_diagnostics = self._search_research_queries(research_queries, cache_policy, ttl_seconds)
        youtube_results = self._filter_relevant_results(youtube_results, creator_brief)
        query_diagnostics["youtube_results_relevant"] = len(youtube_results)

        scored_results = score_outliers(youtube_results, region=region, primary_language=primary_language)
        scored_results = self._attach_velocity_signals(scored_results)
        self._history.record_snapshots(query, scored_results)
        top_opportunities = scored_results[:3]
        research_text = brief_research_text(script, creator_brief)
        keyword_signals = extract_keyword_signals(research_text, scored_results, region, primary_language)
        entity_signals = extract_entity_signals(research_text, scored_results)
        search_opportunities = discover_search_opportunities(
            script=script,
            semantic=semantic_analysis,
            youtube_results=scored_results,
            creator_brief=creator_brief,
        )
        keyword_research = build_keyword_research(
            script=script,
            semantic=semantic_analysis,
            youtube_results=scored_results,
            research_queries=research_queries,
            entity_signals=entity_signals,
            creator_brief=creator_brief,
            search_opportunities=search_opportunities,
            query_diagnostics=query_diagnostics,
        )
        # Research gets one extra bounded pass; writer retries cannot invent
        # stronger evidence for weak tags. Extra queries are explicitly capped.
        strong = [row for row in keyword_research.get("candidates", [])
                  if row.get("keyword_relevance_score", 0) >= 90 and row.get("evidence_count", 0) > 0]
        if len(strong) < 3 and research_queries:
            refinement = refine_research_semantics(script, creator_brief or {}, research_queries)
            proposed = plan_research_queries(script=script, creator_brief=creator_brief,
                semantic_analysis=refinement, region=region, primary_language=primary_language,
                max_queries=5) if refinement else []
            previous = {item["query"].casefold() for item in research_queries}
            def query_terms(value: str) -> set[str]:
                return set(re.findall(r"\w+", value.casefold())) - {
                    "a", "an", "the", "of", "to", "for", "in", "about", "quote", "quotes"}
            previous_terms = [query_terms(item["query"]) for item in research_queries]
            extra_queries = []
            for item in proposed:
                terms = query_terms(item["query"])
                if (item["query"].casefold() not in previous and 0 < len(terms) <= 3
                    and terms not in previous_terms):
                    extra_queries.append(item)
                    previous_terms.append(terms)
                if len(extra_queries) == 2:
                    break
            if extra_queries:
                extra_results, extra_diagnostics = self._search_research_queries(extra_queries, cache_policy, ttl_seconds)
                merged = {}
                for row in [*scored_results, *self._filter_relevant_results(extra_results, creator_brief)]:
                    key = row.get("video_id") or row.get("id") or (row.get("title"), row.get("channel_title"))
                    merged[key] = row
                scored_results = self._attach_velocity_signals(score_outliers(list(merged.values()),
                    region=region, primary_language=primary_language))
                research_queries.extend(extra_queries)
                for field in ("secondary_topics", "search_intents", "concept_evidence", "keyword_clusters"):
                    semantic_analysis[field] = [*(semantic_analysis.get(field) or []), *(refinement.get(field) or [])]
                if refinement.get("primary_topic"):
                    semantic_analysis["secondary_topics"].append(refinement["primary_topic"])
                query_diagnostics["refinement"] = {"queries": extra_queries, "diagnostics": extra_diagnostics,
                    "maximum_extra_queries": 2}
                top_opportunities = scored_results[:3]
                keyword_research = build_keyword_research(script=script, semantic=semantic_analysis,
                    youtube_results=scored_results, research_queries=research_queries, entity_signals=entity_signals,
                    creator_brief=creator_brief, search_opportunities=search_opportunities,
                    query_diagnostics=query_diagnostics)
        owned_performance = self._history.owned_performance_summary()
        upload_timing = build_upload_timing(
            scored_results,
            region=region,
            channel_analytics=owned_performance.get("latest_sync") or {},
            historical_videos=owned_performance.get("videos") or [],
            video_format=str((creator_brief or {}).get("video_format") or ""),
            strategy=str((creator_brief or {}).get("title_style") or "balanced"),
            timezone_name=self._settings.creator_timezone,
        )
        thumbnail_intelligence = analyze_thumbnails(scored_results)
        runtime_state = self._youtube.runtime_state()
        research_warnings = [runtime_state["warning"]] if runtime_state.get("warning") else []
        if not research_queries:
            research_warnings.append("No usable research topic survived semantic validation. Review the supplied topic before relying on this package's SEO research.")

        logger.info(
            "Research gathered: youtube=%s",
            len(youtube_results),
        )

        return {
            "youtube_results": scored_results,
            "top_opportunities": top_opportunities,
            "keyword_signals": keyword_signals,
            "semantic_analysis": semantic_analysis,
            "keyword_research": keyword_research,
            "entity_signals": entity_signals,
            "upload_timing": upload_timing,
            "thumbnail_intelligence": thumbnail_intelligence,
            "research_queries": research_queries,
            "research_diagnostics": query_diagnostics,
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
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        """Search each planned angle and de-duplicate videos across the result set."""

        merged: dict[str, dict[str, object]] = {}
        attempts: list[dict[str, object]] = []
        for item in research_queries:
            query = item["query"]
            query_type = item["type"]
            cache_id = sha256(query.casefold().encode("utf-8")).hexdigest()[:20]
            youtube_key = f"yt:{cache_policy}:{cache_id}"
            results = self._cache.get(youtube_key)
            cached = results is not None
            if results is None:
                results = self._youtube.search_videos(query, self._settings.youtube_max_results)
                self._cache.set(youtube_key, results, ttl_seconds=ttl_seconds)
            runtime = self._youtube.runtime_state()
            warning = runtime.get("warning")
            attempts.append({
                "type": query_type, "query": query, "cache": "hit" if cached else "miss",
                "result_count": len(results or []),
                "status": "failed" if warning and not results else "success",
            })

            for result in results or []:
                video_id = str(result.get("video_id") or "")
                if not video_id:
                    continue
                existing = merged.get(video_id)
                if existing:
                    matched = list(existing.get("matched_queries") or [])
                    if query not in matched:
                        matched.append(query)
                        existing["matched_queries"] = matched
                    matched_types = list(existing.get("matched_query_types") or [])
                    if query_type not in matched_types:
                        matched_types.append(query_type)
                        existing["matched_query_types"] = matched_types
                    details = list(existing.get("matched_query_details") or [])
                    if not any(item.get("query") == query for item in details if isinstance(item, dict)):
                        details.append({"query": query, "type": query_type})
                        existing["matched_query_details"] = details
                    continue
                merged[video_id] = {
                    **result,
                    "research_query": query,
                    "matched_queries": [query],
                    "matched_query_types": [query_type],
                    "matched_query_details": [{"query": query, "type": query_type}],
                }
        return list(merged.values()), {
            "queries_generated": len(research_queries),
            "queries_successful": sum(1 for item in attempts if item["status"] == "success"),
            "queries_failed": sum(1 for item in attempts if item["status"] == "failed"),
            "youtube_results_collected": sum(int(item["result_count"]) for item in attempts),
            "youtube_results_unique": len(merged),
            "query_attempts": attempts,
            "quota_policy": "Queries are de-duplicated, bounded by YOUTUBE_MAX_RESEARCH_QUERIES, cached, and each query is bounded by YOUTUBE_MAX_RESULTS.",
        }

    @staticmethod
    def _filter_relevant_results(
        results: list[dict[str, object]], creator_brief: dict[str, Any] | None = None,
    ) -> list[dict[str, object]]:
        """Keep only results with a meaningful lexical anchor from their query.

        YouTube search can return broadly popular Shorts for sparse queries. Those
        rows must not influence scoring, tags, or generation unless their public
        title/description contains a non-generic query concept.
        """

        generic = {
            "a", "about", "after", "an", "and", "as", "at", "before", "by", "could", "don't", "from", "have", "how", "in", "is", "just", "of", "on", "or", "the", "to",
            "quote", "quotes", "reflective", "short", "shorts", "someone", "their", "there", "these", "this", "video",
            "what", "when", "where", "which", "with", "would", "youtube",
        }
        requested_format = str((creator_brief or {}).get("video_format") or "").casefold()
        short_requested = "short" in requested_format or requested_format in {"reel", "reels", "quote"}
        relevant: list[dict[str, object]] = []
        for result in results:
            duration_seconds = ResearchService._duration_seconds(result.get("duration"))
            if short_requested and duration_seconds is not None and duration_seconds > 180:
                continue
            public_text = " ".join(str(result.get(field) or "") for field in ("title", "description", "channel_title")).casefold()
            public_tokens = set(re.findall(r"[a-z][a-z'-]+", public_text))
            query_values = [
                str(item.get("query") or "")
                for item in (result.get("matched_query_details") or [])
                if isinstance(item, dict) and item.get("query")
            ] or [str(item) for item in (result.get("matched_queries") or []) if str(item).strip()]
            if not query_values:
                query_values = [str(result.get("research_query") or "")]
            matches: list[tuple[float, str, set[str], set[str]]] = []
            for query in query_values:
                query_tokens = {
                    token.casefold()
                    for token in re.findall(r"[A-Za-z][A-Za-z'-]+", query)
                    if len(token) >= 4 and token.casefold() not in generic
                }
                overlap = query_tokens & public_tokens
                required_matches = (
                    1 if len(query_tokens) == 1
                    else len(query_tokens) if len(query_tokens) == 2
                    else max(2, (len(query_tokens) * 2 + 2) // 3)
                )
                if query_tokens and len(overlap) >= required_matches:
                    matches.append((len(overlap) / len(query_tokens), query, query_tokens, overlap))
            if matches:
                _, matched_query, query_tokens, overlap = max(matches, key=lambda item: (item[0], len(item[3])))
                relevance_score = round(100 * len(overlap) / max(1, min(3, len(query_tokens))))
                if len(query_tokens) == 1:
                    # One broad word is useful discovery evidence, but an exact
                    # match is not enough to claim high-confidence relevance.
                    relevance_score = min(relevance_score, 60)
                if relevance_score < 25:
                    continue
                relevant.append({
                    **result,
                    "research_query": matched_query,
                    "research_relevance_score": min(100, relevance_score),
                    "research_relevance_terms": sorted(overlap),
                    "research_query_term_count": len(query_tokens),
                    "research_query_matched_term_count": len(overlap),
                    "research_query_match_ratio": round(len(overlap) / len(query_tokens), 3),
                    "research_evidence_scope": "sampled_results_not_search_volume",
                    "format_match": "short" if short_requested else "unspecified",
                })
        return relevant

    @staticmethod
    def _duration_seconds(value: object) -> int | None:
        """Parse the bounded ISO-8601 durations returned by YouTube."""

        match = re.fullmatch(
            r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
            str(value or ""),
        )
        if not match:
            return None
        parts = {name: int(raw or 0) for name, raw in match.groupdict().items()}
        return parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"]

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
