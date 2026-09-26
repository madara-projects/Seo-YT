from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from win_engine.analysis.entity_extractor import extract_entity_signals
from win_engine.analysis.generation_quality import is_short_content
from win_engine.analysis.keyword_extractor import extract_keyword_signals
from win_engine.analysis.research_insights import build_research_decision
from win_engine.analysis.semantic_research import analyze_script_semantics, refine_research_semantics
from win_engine.analysis.keyword_research import build_keyword_research, demand_seed_phrases
from win_engine.analysis.search_opportunities import discover_search_opportunities
from win_engine.analysis.source_cues import is_short_duration
from win_engine.analysis.research_planner import brief_research_text, plan_research_queries
from win_engine.analysis.strategy_layer import build_upload_timing
from win_engine.analysis.text_tokens import unicode_words
from win_engine.analysis.thumbnail_intelligence import analyze_thumbnails
from win_engine.analysis.transliteration import has_tamil, phonetic_keys, phonetic_match
from win_engine.core.config import Settings
from win_engine.core.iso_duration import duration_seconds
from win_engine.feedback.history_store import HistoryStore
from win_engine.ingestion.cache import shared_cache
from win_engine.ingestion.search_suggest import SearchSuggestClient
from win_engine.ingestion.youtube_client import YouTubeClient, youtube_language_code, youtube_region_code
from win_engine.scoring.outlier_engine import score_outliers


logger = logging.getLogger(__name__)

# Words that say nothing about a result's topic. Three-letter words are query
# terms, so the common function words among them are listed too.
_GENERIC_QUERY_TERMS = frozenset({
    "about", "after", "all", "and", "any", "are", "before", "but", "can", "could", "did", "don't", "for",
    "from", "had", "has", "have", "her", "him", "his", "how", "its", "just", "not", "our", "she", "the",
    "too", "was", "who", "why", "yet", "you",
    "quote", "quotes", "reflective", "short", "shorts", "someone", "their", "there", "these", "this", "video",
    "what", "when", "where", "which", "with", "would", "youtube",
})
_MAX_REFINEMENT_QUERIES = 2
_UNKNOWN_TIME = datetime.min.replace(tzinfo=timezone.utc)
_NO_TOPIC_WARNING = (
    "No usable research topic survived semantic validation. Review the supplied topic before relying on "
    "this package's SEO research."
)


def _words(value: object) -> list[str]:
    # One apostrophe, so "don’t" is the generic "don't" and titles match either spelling.
    return unicode_words(str(value or "").replace("’", "'"))


def _captured_at(row: dict[str, object]) -> datetime:
    """When YouTube reported the row's statistics, or the earliest time when unknown."""

    try:
        value = datetime.fromisoformat(str(row.get("captured_at") or ""))
    except ValueError:
        return _UNKNOWN_TIME
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _ranked(results: list[dict[str, object]]) -> list[dict[str, object]]:
    """Rows with an outlier score; a row without the statistics for one is not ranked."""

    return [row for row in results if row.get("outlier_score") is not None]


def _research_warnings(attempts: list[dict[str, object]], research_queries: list[dict[str, str]]) -> list[str]:
    # The client keeps only its latest call's warning, so a failed first query
    # followed by a good one used to leave the run looking clean.
    warnings = list(dict.fromkeys(str(item["warning"]) for item in attempts if item.get("warning")))
    if not research_queries:
        warnings.append(_NO_TOPIC_WARNING)
    return warnings


class ResearchService:
    """Coordinates external data lookups for SEO research."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache = shared_cache(
            ttl_seconds=settings.cache_ttl_evergreen_seconds,
            redis_url=settings.redis_url,
            key_prefix=settings.redis_key_prefix,
        )
        self._youtube = YouTubeClient(settings.youtube_api_key_pool, settings.request_timeout_seconds)
        self._history = HistoryStore(settings.database_path)
        self._suggest = SearchSuggestClient(
            enabled=settings.search_suggest_enabled,
            timeout_seconds=settings.search_suggest_timeout_seconds,
            max_queries=settings.search_suggest_max_queries,
            cache=self._cache,
        )

    def gather(
        self,
        script: str,
        region: str = "global",
        primary_language: str = "english",
        creator_brief: dict[str, Any] | None = None,
        *,
        results_only: bool = False,
    ) -> dict[str, object]:
        """Research the public YouTube landscape for a script.

        ``results_only`` returns the scored public results and their query record
        and nothing else: no Gemini call, suggestion lookup or keyword research.
        Demand research reads only the results, yet paid for the rest every run.
        """

        run_started = datetime.now(timezone.utc)
        # Without a semantic analysis the planner works from the creator brief,
        # as it does whenever Gemini is unavailable.
        semantic_analysis = {} if results_only else analyze_script_semantics(script, creator_brief)
        research_queries = plan_research_queries(
            script=script,
            creator_brief=creator_brief,
            semantic_analysis=semantic_analysis,
            region=region,
            primary_language=primary_language,
            max_queries=self._settings.youtube_max_research_queries,
        )
        query = research_queries[0]["query"] if research_queries else script[:120]
        # Reported only: each query is cached for its own policy.
        cache_policy, _ = self._select_cache_policy(query)
        locale = {"region": region, "primary_language": primary_language}

        youtube_results, query_diagnostics = self._search_research_queries(research_queries, **locale)
        attempts = list(query_diagnostics["query_attempts"])
        youtube_results = self._filter_relevant_results(youtube_results, creator_brief)
        query_diagnostics["youtube_results_relevant"] = len(youtube_results)

        scored_results = score_outliers(youtube_results)
        if results_only:
            self._record_fresh_snapshots(scored_results, run_started)
            return {
                "youtube_results": scored_results,
                "top_opportunities": _ranked(scored_results)[:3],
                "research_queries": research_queries,
                "research_diagnostics": query_diagnostics,
                "research_warnings": _research_warnings(attempts, research_queries),
                "cache_policy": cache_policy,
                "youtube_runtime": self._youtube.runtime_state(),
            }
        top_opportunities = _ranked(scored_results)[:3]
        research_text = brief_research_text(script, creator_brief)
        keyword_signals = extract_keyword_signals(research_text, scored_results)
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
            # The relevance filter's own terms: "grief quotes for her" is the
            # search "grief quotes" again and is not paid for twice.
            previous_terms = [self._query_terms(item["query"]) for item in research_queries]
            extra_queries = []
            for item in proposed:
                terms = self._query_terms(item["query"])
                if (item["query"].casefold() not in previous and 0 < len(terms) <= 3
                    and terms not in previous_terms):
                    extra_queries.append(item)
                    previous_terms.append(terms)
                if len(extra_queries) == _MAX_REFINEMENT_QUERIES:
                    break
            if extra_queries:
                extra_results, extra_diagnostics = self._search_research_queries(extra_queries, **locale)
                attempts.extend(extra_diagnostics["query_attempts"])
                # A video found again keeps the queries of both passes; the
                # refinement row used to replace the first-pass row outright.
                merged = {str(row.get("video_id")): row for row in scored_results}
                for row in extra_results:
                    key = str(row.get("video_id"))
                    merged[key] = self._merge_rows(merged[key], row) if key in merged else row
                scored_results = score_outliers(self._filter_relevant_results(list(merged.values()), creator_brief))
                research_queries.extend(extra_queries)
                for field in ("secondary_topics", "search_intents", "concept_evidence", "keyword_clusters"):
                    semantic_analysis[field] = [*(semantic_analysis.get(field) or []), *(refinement.get(field) or [])]
                if refinement.get("primary_topic"):
                    semantic_analysis["secondary_topics"].append(refinement["primary_topic"])
                query_diagnostics["refinement"] = {"queries": extra_queries, "diagnostics": extra_diagnostics,
                    "maximum_extra_queries": _MAX_REFINEMENT_QUERIES}
                top_opportunities = _ranked(scored_results)[:3]
                keyword_research = build_keyword_research(script=script, semantic=semantic_analysis,
                    youtube_results=scored_results, research_queries=research_queries, entity_signals=entity_signals,
                    creator_brief=creator_brief, search_opportunities=search_opportunities,
                    query_diagnostics=query_diagnostics)
        self._record_fresh_snapshots(scored_results, run_started)
        # Demand pass: check the strongest source-grounded concepts against
        # what viewers actually type, then rebuild the research with that
        # evidence. Fails soft — without suggestions the research is unchanged.
        seeds = demand_seed_phrases(keyword_research, semantic_analysis, creator_brief)
        search_demand = self._suggest.fetch(seeds, language=primary_language, region=region)
        if search_demand.get("suggestions"):
            keyword_research = build_keyword_research(
                script=script, semantic=semantic_analysis, youtube_results=scored_results,
                research_queries=research_queries, entity_signals=entity_signals,
                creator_brief=creator_brief, search_opportunities=search_opportunities,
                query_diagnostics=query_diagnostics, search_demand=search_demand,
            )
        else:
            keyword_research["search_demand"] = {
                **(keyword_research.get("search_demand") or {}),
                "status": search_demand.get("status"),
                "queries": search_demand.get("queries") or [],
            }
        owned_performance = self._history.owned_performance_summary()
        upload_timing = build_upload_timing(
            scored_results,
            region=region,
            channel_analytics=owned_performance.get("latest_sync") or {},
            historical_videos=owned_performance.get("videos") or [],
            video_format=str((creator_brief or {}).get("video_format") or ""),
            short_form=is_short_content(script, creator_brief),
            strategy=str((creator_brief or {}).get("title_style") or "balanced"),
            timezone_name=self._settings.creator_timezone,
        )
        thumbnail_intelligence = analyze_thumbnails(scored_results)
        runtime_state = self._youtube.runtime_state()
        research_warnings = _research_warnings(attempts, research_queries)

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
        *,
        region: str = "global",
        primary_language: str = "english",
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        """Search each planned angle and de-duplicate videos across the result set."""

        max_results = self._settings.youtube_max_results
        locale = {
            "region_code": youtube_region_code(region),
            "relevance_language": youtube_language_code(primary_language),
        }
        merged: dict[str, dict[str, object]] = {}
        attempts: list[dict[str, object]] = []
        for item in research_queries:
            query = item["query"]
            query_type = item["type"]
            attempt: dict[str, object] = {"type": query_type, "query": query, "warning": None}
            attempts.append(attempt)
            if not self._query_terms(query):
                # No word of this query can anchor a result, so the relevance
                # filter would drop everything a 100-unit search returned.
                attempt.update({"cache": "skipped", "result_count": 0, "status": "skipped"})
                continue
            cache_input = "|".join([query.casefold(), str(max_results), *(value or "" for value in locale.values())])
            digest = sha256(cache_input.encode("utf-8")).hexdigest()[:20]
            # The key is the search alone, so every later run finds it, and the
            # query's own policy sets how long it is kept.
            answer_key, page_key = f"yt:{digest}", f"yt:page:{digest}"
            ttl_seconds = self._select_cache_policy(query)[1]
            entry = self._cache.get(answer_key)  # {"rows": [...]}, an empty answer included
            page = None if entry else self._cache.get(page_key)
            if entry:
                results, status = entry["rows"], "success"
            else:
                # A page kept after a failed statistics lookup costs only the
                # two 1-unit lookups again, not another 100-unit search.
                results = (
                    self._youtube.attach_statistics(page["rows"]) if page
                    else self._youtube.search_videos(query, max_results, **locale) or []
                )
                attempt["warning"] = self._youtube.runtime_state().get("warning")
                complete = [row for row in results if row.get("captured_at")]
                status = (
                    "failed" if attempt["warning"] and not results
                    else "partial" if len(complete) < len(results)
                    else "success"
                )
                # Rows whose statistics lookup failed stay out of the answer, where
                # their gaps would pass for real numbers for days; their search
                # page is kept on its own. An empty answer is cached so the query
                # is not paid for again.
                if status != "failed" and (complete or not results):
                    self._cache.set(answer_key, {"rows": complete}, ttl_seconds=ttl_seconds)
                elif results and not page:
                    self._cache.set(page_key, {"rows": results}, ttl_seconds=ttl_seconds)
            attempt.update({
                "cache": "hit" if entry else "search_page" if page else "miss",
                "result_count": len(results),
                "status": status,
            })

            for result in results:
                video_id = str(result.get("video_id") or "")
                if not video_id:
                    continue
                row = {
                    **result,
                    "research_query": query,
                    "matched_queries": [query],
                    "matched_query_types": [query_type],
                    "matched_query_details": [{"query": query, "type": query_type}],
                }
                merged[video_id] = self._merge_rows(merged[video_id], row) if video_id in merged else row
        return list(merged.values()), {
            "queries_generated": len(research_queries),
            "queries_successful": sum(1 for item in attempts if item["status"] == "success"),
            "queries_partial": sum(1 for item in attempts if item["status"] == "partial"),
            "queries_failed": sum(1 for item in attempts if item["status"] == "failed"),
            "queries_skipped": sum(1 for item in attempts if item["status"] == "skipped"),
            "youtube_results_collected": sum(int(item["result_count"]) for item in attempts),
            "youtube_results_unique": len(merged),
            "query_attempts": attempts,
            "quota_policy": (
                "Queries are de-duplicated and bounded by YOUTUBE_MAX_RESEARCH_QUERIES, plus at most "
                f"{_MAX_REFINEMENT_QUERIES} refinement queries; each returns at most YOUTUBE_MAX_RESULTS results. "
                "Queries without a searchable word are skipped. Results with complete statistics are cached "
                "in Redis when configured, otherwise in this process's memory. A search whose statistics lookup "
                "failed is kept, so a later run repeats only the 1-unit statistics lookups."
            ),
        }

    @staticmethod
    def _merge_rows(existing: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
        """One row per video: the fresher statistics, and every query that found it."""

        fresher = _captured_at(incoming) > _captured_at(existing)
        row = {**existing, **incoming} if fresher else {**incoming, **existing}
        for field in ("matched_queries", "matched_query_types"):
            row[field] = list(dict.fromkeys([*(existing.get(field) or []), *(incoming.get(field) or [])]))
        details = [item for item in existing.get("matched_query_details") or [] if isinstance(item, dict)]
        known = {item.get("query") for item in details}
        row["matched_query_details"] = details + [
            item for item in incoming.get("matched_query_details") or []
            if isinstance(item, dict) and item.get("query") not in known
        ]
        return row

    @staticmethod
    def _query_terms(query: str) -> set[str]:
        """Words of a query that a relevant result has to echo.

        Words of any script count; an ASCII-only pattern dropped every result of
        a Tamil query. Three characters are enough for "god", "war" or "ps5". A
        word needs a letter: titles rarely repeat a year or a count ("2024"),
        and requiring one dropped relevant results.
        """

        return {
            word for word in _words(query)
            if len(word) >= 3 and word not in _GENERIC_QUERY_TERMS and any(char.isalpha() for char in word)
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

        short_requested = bool(creator_brief) and is_short_content("", creator_brief)
        relevant: list[dict[str, object]] = []
        for result in results:
            if short_requested and is_short_duration(duration_seconds(result.get("duration"))) is False:
                continue
            public_words = set(_words(
                " ".join(str(result.get(field) or "") for field in ("title", "description", "channel_title"))
            ))
            # A Tamil word and its Latin spelling meet only through their sound.
            # The bridge stays between scripts: inside one script it would pair
            # unrelated words that share consonants, such as "chicken" and "skin".
            latin_keys = phonetic_keys([word for word in public_words if not has_tamil(word)])
            tamil_keys = phonetic_keys([word for word in public_words if has_tamil(word)])
            query_values = [
                str(item.get("query") or "")
                for item in (result.get("matched_query_details") or [])
                if isinstance(item, dict) and item.get("query")
            ] or [str(item) for item in (result.get("matched_queries") or []) if str(item).strip()]
            if not query_values:
                query_values = [str(result.get("research_query") or "")]
            matches: list[tuple[float, str, set[str], set[str]]] = []
            for query in query_values:
                query_tokens = ResearchService._query_terms(query)
                overlap = {
                    token for token in query_tokens
                    if token in public_words
                    or phonetic_match(token, latin_keys if has_tamil(token) else tamil_keys)
                }
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

    def diagnostics(self) -> dict[str, object]:
        """Return a quick health check for external integrations."""

        youtube_status = "ok" if self._settings.youtube_api_key_pool else "missing_api_key"
        youtube_error = None

        if youtube_status == "ok":
            try:
                self._youtube.ping()
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

    def _record_fresh_snapshots(self, results: list[dict[str, object]], since: datetime) -> None:
        """Store this run's new YouTube observations, each under its own query.

        A cached row was stored when it was fetched; storing it again dated old
        statistics as a new observation. A row without ``captured_at`` has gaps
        from a failed lookup and is no observation at all.
        """

        by_query: dict[str, list[dict[str, object]]] = {}
        for row in results:
            if _captured_at(row) >= since:
                by_query.setdefault(str(row.get("research_query") or ""), []).append(row)
        for query, rows in by_query.items():
            self._history.record_snapshots(query, rows)
