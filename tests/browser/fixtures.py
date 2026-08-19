from __future__ import annotations

import json
import time
from collections import Counter
from urllib.parse import urlparse


def _json_response(route, payload, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(payload))


def history_summary(*, include_link: bool = False):
    payload = {
        "learning": {"recent_runs": []},
        "scorecard": {"total_runs": 0, "avg_title_score": None, "avg_opportunity_score": None},
        "owned_performance": {
            "channel": {}, "latest_sync": {}, "videos": [], "total_views": 0,
            "estimated_watch_minutes": 0, "subscribers": None, "lifetime_views": None,
            "views_28_days": None, "linked_videos_count": 0,
        },
    }
    if include_link:
        payload["owned_performance"]["videos"] = [{
            "video_id": "fixture-video-1",
            "title": "Linked rainy highway upload",
            "published_at": "2026-08-14T10:00:00+00:00",
            "views": 42,
            "likes": 3,
            "comments": 1,
            "average_view_percentage": None,
        }]
        payload["owned_performance"]["linked_videos_count"] = 1
    return payload


def history_runs():
    return {
        "runs": [{
            "id": 1,
            "created_at": "2026-08-15T10:00:00+00:00",
            "title": "Rainy Highway Reflection",
            "query": "Rainy highway quote",
            "opportunity_score": 64.2,
            "title_score": 8.5,
            "content_angle": "quiet reflection",
            "linked": False,
        }],
        "limit": 50,
        "offset": 0,
    }


def history_run_detail():
    return {
        "id": 1,
        "created_at": "2026-08-15T10:00:00+00:00",
        "title": "Rainy Highway Reflection",
        "query": "Rainy highway quote",
        "opportunity_score": 64.2,
        "title_score": 8.5,
        "content_angle": "quiet reflection",
        "package": {
            "title": "Didn't I Deserve the Bare Minimum? #Shorts",
            "description": "A quiet reflection on emotional neglect.",
            "tags": ["emotional neglect", "sad quotes", "shorts"],
            "hashtags": ["#shorts", "#quotes"],
            "title_variants": ["When effort is never returned"],
            "chapters": [],
            "creator_brief": {"content": "A rainy highway with an emotional quote."},
        },
        "linked_video_report": {"linked": False},
    }


def _research_fixture(mode: str = "full"):
    if mode == "empty":
        return {
            "research_queries": [],
            "research_decision": {},
            "youtube_results": [],
            "top_opportunities": [],
            "keyword_signals": [],
            "entity_signals": [],
            "thumbnail_intelligence": {},
        }
    if mode == "insufficient":
        return {
            "research_queries": [{"type": "main topic", "query": "rainy highway quote"}],
            "research_decision": {
                "confidence": "low",
                "avoid": ["Research data is unavailable; keep the promise specific and evidence-based."],
            },
            "youtube_results": [],
            "top_opportunities": [],
            "keyword_signals": [],
            "entity_signals": [],
            "thumbnail_intelligence": {},
        }
    result_a = {
        "video_id": "fixture-public-1",
        "title": "When Letting Go Finally Feels Quiet",
        "description": "A public reflection about letting go and healing.",
        "channel_title": "Public Quote Channel",
        "published_at": "2026-08-14T10:00:00+00:00",
        "view_count": 12500,
        "like_count": 420,
        "comment_count": 18,
        "subscriber_count": 8000,
        "outlier_score": 4.2,
        "small_channel_outlier": False,
        "opportunity_reasons": ["Recent public result"],
        "thumbnails": {"high": {"width": 1280, "height": 720}},
    }
    result_b = {
        "video_id": "fixture-public-2",
        "title": "The Truth About Moving On #Shorts",
        "description": "A short public observation about emotional recovery.",
        "channel_title": "Small Public Channel",
        "published_at": "2026-08-12T12:00:00+00:00",
        "view_count": 8300,
        "like_count": 210,
        "comment_count": 9,
        "subscriber_count": 5000,
        "outlier_score": 3.1,
        "small_channel_outlier": False,
        "opportunity_reasons": ["Topic overlap"],
        "thumbnails": {"maxres": {"width": 1920, "height": 1080}},
    }
    return {
        "research_queries": [
            {"type": "main topic", "query": "rainy highway quote"},
            {"type": "viewer problem", "query": "letting go quotes"},
        ],
        "research_decision": {
            "recommended_angle": "Lead with a quiet first-person reflection for viewers healing from loss.",
            "reason": "Use the creator's real quote without copying the dominant public framing.",
            "dominant_competitor_pattern": "curiosity",
            "repeated_title_patterns": [{"pattern": "curiosity", "count": 2}],
            "small_channel_winners": [],
            "avoid": ["Do not copy the dominant curiosity title structure."],
            "confidence": "medium",
        },
        "youtube_results": [result_a, result_b],
        "top_opportunities": [result_a],
        "keyword_signals": [
            {"keyword": "letting go", "mentions": 3, "strength": "medium", "region_relevant": False},
            {"keyword": "healing quote", "mentions": 2, "strength": "low", "region_relevant": False},
        ],
        "entity_signals": [{"entity": "Shorts", "mentions": 2, "type": "topic"}],
        "thumbnail_intelligence": {
            "quality_counts": {"maxres": 1, "high": 1, "medium": 0, "default": 0},
            "low_resolution_count": 0,
            "recommendation": "Use clear contrast and short text as a local setup suggestion.",
        },
    }


def analyze_success(*, creator_research: str = "full", generation_source: str = "gemini", title_prefix: str = ""):
    research = _research_fixture(creator_research)
    package = {
        "title": f"{title_prefix}The Truth About Letting Go #Shorts",
        "description": "A reflective short about letting go.",
        "tags": ["letting go", "quotes", "shorts"],
        "hashtags": ["#shorts", "#quotes"],
        "variants": [
            f"{title_prefix}The Truth About Letting Go #Shorts",
            "When You Finally Stop Waiting #Shorts",
            "A Quiet Reminder About Letting Go #Shorts",
        ],
    }
    title_thumbnail_packages = [
        {
            "package": "A",
            "title": package["variants"][0],
            "thumbnail_text": "LET IT GO",
            "thumbnail_visual": "Rainy road with high-contrast quote text",
            "viewer_promise": "Feel understood in under a minute",
            "why_click": "It connects a clear emotional topic to the viewer promise.",
            "approach": "balanced",
            "package_intent": "Browse",
            "best_for": "Browse / relatable viewers",
            "misleading_risk": "low",
            "quality_status": "approved",
        },
        {
            "package": "B",
            "title": package["variants"][1],
            "thumbnail_text": "STOP WAITING",
            "thumbnail_visual": "Rainy highway with a single focal point",
            "viewer_promise": "Feel understood in under a minute",
            "why_click": "It uses a direct emotional turning point without claiming a result.",
            "approach": "curiosity-led",
            "package_intent": "Existing audience",
            "best_for": "Returning viewers / existing audience",
            "misleading_risk": "low",
            "quality_status": "approved",
        },
        {
            "package": "C",
            "title": package["variants"][2],
            "thumbnail_text": "QUIET REMINDER",
            "thumbnail_visual": "Minimal road frame with readable text",
            "viewer_promise": "Feel understood in under a minute",
            "why_click": "It presents a calm, descriptive alternative.",
            "approach": "searchable",
            "package_intent": "Search",
            "best_for": "Search / new viewers",
            "misleading_risk": "low",
            "quality_status": "approved",
        },
    ]
    return {
        "title": package["title"],
        "description": package["description"],
        "tags": package["tags"],
        "hashtags": package["hashtags"],
        "intent": "reflection",
        "content_angle": "quiet emotional reflection",
        "title_variants": package["variants"],
        "title_optimization": {
            "best_title": package["variants"][0],
            "scored_variants": [
                {"title": package["variants"][0], "score": 8.5, "estimated_ctr": None, "character_count": len(package["variants"][0])},
                {"title": package["variants"][1], "score": 8.1, "estimated_ctr": None, "character_count": len(package["variants"][1])},
                {"title": package["variants"][2], "score": 7.8, "estimated_ctr": None, "character_count": len(package["variants"][2])},
            ],
        },
        "title_thumbnail_packages": title_thumbnail_packages,
        "content_audit": {},
        "cache_policy": "test-fixture",
        "research_warnings": [],
        "generation_source": generation_source,
        "creator_brief": {
            "content": "A reflective quote over a rainy highway.",
            "target_audience": "Viewers processing a difficult relationship",
            "viewer_promise": "Feel understood in under a minute",
            "unique_angle": "A quiet first-person reflection over moving traffic",
            "proof": "Original on-screen quote",
            "video_format": "story",
            "title_style": "curiosity",
            "thumbnail_idea": "Rainy road with high-contrast quote text",
        },
        **research,
        "multilang": {"english": package},
        "upload_timing": {"recommended_day": "Not enough evidence", "sample_size": 0, "confidence": "LOW", "target_region": "GLOBAL"},
        "opportunity_gap_analysis": {"opportunity_score": {"score": 64.2, "label": "WORKABLE", "reason": "Fixture score"}, "competition_score": {}},
        "competitor_shadow": {},
        "language_strategy": {},
        "pacing_analysis": {"pace_label": "reflective", "avg_sentence_length": 8, "hook_density": "medium"},
        "channel_intelligence": {},
        "content_graph_strategy": {},
        "thumbnail_strategy": {},
        "chapters": [],
        "session_expansion": {},
        "binge_bridge": "",
        "automation_workflow": {},
        "performance_sync": {},
        "learning_engine": {},
        "winning_patterns": {},
        "ctr_prediction": {"label": "STRONG", "title_quality_score": 8.5, "reason": "Heuristic fixture"},
        "ab_test_pack": {},
        "internal_scorecard": {},
        "historical_comparison": {},
    }


class FixtureRouter:
    """Intercept every app/API/external request used by browser smoke tests."""

    def __init__(self, page, *, analyze_error: bool = False, include_link: bool = False,
                 collector_state: str = "disabled", collector_error: bool = False,
                 creator_research: str = "full", generation_source: str = "gemini",
                 analyze_delay_ms: int = 0, oauth_state: str = "disconnected"):
        self.page = page
        self.analyze_error = analyze_error
        self.include_link = include_link
        self.collector_state = collector_state
        self.collector_error = collector_error
        self.creator_research = creator_research
        self.generation_source = generation_source
        self.analyze_delay_ms = analyze_delay_ms
        self.oauth_state = oauth_state
        self.requests = Counter()
        self.request_bodies: dict[str, list[object]] = {}
        self.external_requests: list[str] = []
        page.route("**/*", self._handle)

    def _handle(self, route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path
        method = request.method
        key = f"{method} {path}"
        self.requests[key] += 1
        if method in {"POST", "PATCH", "DELETE"}:
            raw_body = request.post_data
            parsed_body = None
            if raw_body:
                try:
                    parsed_body = json.loads(raw_body)
                except (TypeError, json.JSONDecodeError):
                    parsed_body = raw_body
            self.request_bodies.setdefault(key, []).append(parsed_body)

        # Never let browser tests contact a non-local host. Fulfill rather than
        # continue so fonts, OAuth, YouTube, Gemini, and research cannot escape.
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            self.external_requests.append(request.url)
            route.fulfill(status=204, body="")
            return

        if path in {"/", "/app", "/dashboard_view", "/dashboard_legacy"} or path.startswith("/static/"):
            route.continue_()
            return
        if path == "/youtube/channel/status":
            if self.oauth_state == "connected":
                _json_response(route, {
                    "configured": True,
                    "connected": True,
                    "channel": {"id": "fixture-channel", "title": "Fixture Creator Channel"},
                    "latest_sync": {
                        "synced_at": "2099-08-16T10:00:00+00:00",
                        "data": {
                            "current_28_days": {"views": 120, "estimatedMinutesWatched": 45},
                            "channel": {"subscribers": 12, "real_total_views": 340},
                            "video_learning": {"recommendation": "Collecting fixture evidence."},
                        },
                    },
                })
            else:
                _json_response(route, {"configured": False, "connected": False, "channel": None, "latest_sync": None, "setup_message": "Fixture OAuth is disconnected."})
            return
        if path == "/api/snapshot-collector/status":
            if self.collector_error:
                _json_response(route, {"error": {"code": "collector_unavailable", "message": "Collector status unavailable in fixture.", "request_id": "collector-fixture-1"}}, status=503)
            else:
                _json_response(route, {"state": self.collector_state, "enabled": self.collector_state not in {"disabled", "unconfigured"}, "dry_run": self.collector_state == "dry-run", "running": self.collector_state == "running", "last_error": "Fixture collector failure." if self.collector_state == "error" else None, "last_counts": {"links": 0, "windows": 0, "captured": 0, "failed": 0}})
            return
        if path == "/api/history":
            _json_response(route, history_summary(include_link=self.include_link))
            return
        if path == "/api/history/runs" and method == "GET":
            _json_response(route, history_runs())
            return
        if path == "/api/history/runs/1" and method == "GET":
            _json_response(route, history_run_detail())
            return
        if path == "/api/published-videos":
            links = []
            if self.include_link:
                links = [{
                    "id": 9,
                    "youtube_video_id": "fixture-video-1",
                    "history_run_id": 1,
                    "selected_title": "Linked rainy highway upload",
                    "published_at": "2026-08-14T10:00:00+00:00",
                    "latest_performance": {"views": 42, "avg_view_percentage": None, "snapshot_window": "current"},
                }]
            _json_response(route, {"links": links, "total": len(links)})
            return
        if path == "/api/learning/cohorts":
            _json_response(route, {"sample_size": 0, "confidence_label": "Collecting evidence", "learning_allowed": False, "snapshot_window": "24h", "recommendation": "No mature evidence yet.", "metadata_sources": {}})
            return
        if path == "/analyze" and method == "POST":
            if self.analyze_error:
                _json_response(route, {"error": {"code": "test_error", "message": "Fixture analysis failed.", "request_id": "browser-fixture-1"}}, status=503)
            else:
                body = request.post_data or ""
                if self.analyze_delay_ms and "first" in body.lower():
                    time.sleep(self.analyze_delay_ms / 1000)
                title_prefix = "Second: " if "second" in body.lower() else "First: " if "first" in body.lower() else ""
                _json_response(route, analyze_success(creator_research=self.creator_research, generation_source=self.generation_source, title_prefix=title_prefix))
            return
        if path == "/diagnostics":
            _json_response(route, {"youtube": {"status": "fixture"}, "gemini": {"configured": False}})
            return
        if path == "/youtube/channel/refresh" and method == "POST":
            _json_response(route, {"status": "fixture", "channel": {}, "current_28_days": {}, "previous_28_days": {}, "recent_videos": {"rows": []}})
            return
        if path == "/youtube/channel/connect":
            route.fulfill(status=302, headers={"Location": "/#settings"}, body="")
            return
        if path == "/youtube/channel/disconnect" and method == "POST":
            _json_response(route, {"status": "disconnected"})
            return
        if path.startswith("/api/history/runs/") or path.startswith("/api/published-videos/") or path.startswith("/api/experiments"):
            _json_response(route, {"status": "fixture", "link_id": 1, "comparable_metadata": {"language": "unknown", "format": "unknown", "duration_bucket": "unknown", "topic_category": "unknown", "sources": {}}})
            return
        route.fulfill(status=204, body="")

    def count(self, method: str, path: str) -> int:
        return self.requests[f"{method.upper()} {path}"]

    def bodies(self, method: str, path: str) -> list[object]:
        return self.request_bodies.get(f"{method.upper()} {path}", [])
