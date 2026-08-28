from __future__ import annotations

import json
import re
import time
from collections import Counter
from urllib.parse import parse_qs, urlparse


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


def history_run_detail(*, include_link: bool = False):
    payload = {
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
    if include_link:
        payload["linked_video_report"] = {
            "linked": True,
            "link_id": 9,
            "video_id": "fixture-video-1",
            "video_url": "https://www.youtube.com/watch?v=fixture-video-1",
            "published_at": "2026-08-14T10:00:00+00:00",
            "metadata_synced_at": "2026-08-15T10:00:00+00:00",
            "youtube": {"title": "Rainy Highway Reflection", "description": "Published description #Shorts", "tags": ["rainy road", "shorts"]},
            "package_usage": {"attribution_status": "creator_selected", "title_match": True, "description_match_percent": 88, "uploaded_tags": ["rainy road", "shorts"], "matching_tags": ["rainy road"], "uploaded_hashtags": ["#Shorts"]},
            "performance": {"views": 1152, "likes": 15, "comments": 2, "average_view_percentage": None, "average_view_duration_seconds": None, "subscribers_gained": 0},
            "diagnosis": {"confidence": "LOW", "verdict": "Collecting evidence", "what_worked": [], "needs_improvement": ["24-hour retention is not available yet."], "attribution_note": "YouTube reports video-level performance; it cannot attribute views to individual tags."},
            "baseline": {"sample_size": 0, "window": "no scheduled window"},
            "comparable_metadata": {"language": "english", "format": "short", "duration_bucket": "unknown", "topic_category": "unknown", "sources": {"language": "package", "format": "package", "duration_bucket": "unknown", "topic_category": "unknown"}},
            "retention_learning": {"status": "insufficient_evidence", "message": "Only 0 verified comparable videos have completed 24-hour retention evidence; at least 5 are required before surfacing correlations.", "sample_size": 0, "minimum_samples": 5},
            "snapshots": [
                {"snapshot_window": "24h", "views": None, "likes": None, "avg_view_percentage": None, "captured_at": "2026-08-15T10:00:00+00:00"},
                {"snapshot_window": "current", "views": 1152, "likes": 15, "avg_view_percentage": None, "captured_at": "2026-08-15T10:00:00+00:00"},
            ],
        }
    return payload


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
        "title": f"{title_prefix}The Truth About Letting Go 💔 #shorts",
        "description": "A reflective short about letting go.",
        "tags": ["letting go", "quotes", "shorts"],
        "hashtags": ["#shorts", "#quotes"],
        "variants": [
            f"{title_prefix}The Truth About Letting Go 💔 #shorts",
            "When You Finally Stop Waiting 🌧️ #shorts",
            "Letting Go Without Forgetting Them 🌙 #shorts",
        ],
    }
    title_thumbnail_packages = [
        {
            "package_id": "package-a",
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
            "package_id": "package-b",
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
            "package_id": "package-c",
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
        "history_run_id": 1,
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
            "video_format": "youtube_shorts",
            "title_style": "curiosity",
            "thumbnail_idea": "Rainy road with high-contrast quote text",
        },
        **research,
        "multilang": {"english": package},
        "upload_timing": {
            "recommended_day": "Thursday",
            "recommended_time": "6:00 PM - 8:00 PM",
            "timezone": "Asia/Kolkata",
            "confidence": "LOW",
            "basis": "general_recommendation",
            "today_recommendation": "Today is a weaker-evidence day. If publishing today, use the general starting window.",
            "today_time": "6:00 PM - 8:00 PM",
            "today_timezone": "Asia/Kolkata",
            "explanation": "Personalized upload timing is not yet established. This is a general starting window, not a prediction of reach.",
            "sample_size": 0,
            "personalized": False,
            "target_region": "GLOBAL",
        },
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
        "retention_assistant": {
            "status": "available",
            "rule_version": "phase5-v1",
            "analysis_basis": "deterministic_local_heuristic",
            "disclaimer": "Pre-publish structure guidance only; it does not predict or guarantee retention, views, reach, or growth.",
            "risk_level": "medium",
            "opening": {"status": "available", "score": 68, "clarity": "clear", "specificity": "present", "generic_setup": False},
            "first_frame": {"status": "available", "readability": "review", "text_word_count": 17, "estimated_single_read_seconds": 6.1, "visual_analysis_basis": "creator_description_only"},
            "pacing": {"status": "available", "format_assessment": "short_form", "word_count": 32, "estimated_spoken_seconds": 12.8, "duration_seconds": 18, "timing_confidence": "duration_based_heuristic"},
            "quote_presentation": {"status": "available", "word_count": 17, "estimated_single_read_seconds": 6.1, "exact_text_preserved_on_screen": True, "attribution": "unavailable"},
            "risk_map": [{"stage": "0-3 seconds", "timing_basis": "duration_supplied_timing_bands", "status": "risk_identified", "risks": [{"risk_code": "first_frame_text_dense", "severity": "medium", "stage": "opening", "explanation": "The first-frame text contains 17 words.", "evidence": "Fixture exact quote", "recommendation": "Reveal the exact text in readable steps."}]}],
            "recommendations": [{"priority": "medium", "risk_code": "first_frame_text_dense", "recommendation": "Reveal the exact text in readable steps.", "guarantee": False}],
            "alternatives": [{"alternative_code": "progressive_text_reveal", "structure": "Keep the wording and reveal it in readable phrases.", "preserves_source": "Fixture exact quote", "guarantee": False}],
            "package_alignment": [
                {"package_id": "package-a", "title": package["variants"][0], "opening_similarity": 0.42, "status": "aligned"},
                {"package_id": "package-b", "title": package["variants"][1], "opening_similarity": 0.31, "status": "aligned"},
                {"package_id": "package-c", "title": package["variants"][2], "opening_similarity": 0.16, "status": "review"},
            ],
            "retention_learning": {"status": "insufficient_evidence", "learning_allowed": False, "sample_size": 0, "minimum_samples": 5, "patterns": [], "message": "Insufficient mature comparable retention evidence."},
            "trace": {"timing_basis": "duration_supplied", "finding_count": 1},
        },
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
        self.ideas = {
            1: {
                "id": 1, "topic": "Rainy highway quote idea", "notes": "Original creator note",
                "format": "youtube_shorts", "language": "english", "region": "global",
                "visual_or_background": "Rainy highway", "on_screen_text": "A quiet exact quote",
                "target_duration_seconds": 18, "emotion_or_intent": "reflection",
                "search_angle": "rainy road quote", "browse_angle": "quiet emotional reflection",
                "audience_angle": "returning quote viewers", "status": "idea",
                "analysis_run_id": None, "published_video_link_id": None,
                "created_at": "2026-08-23T00:00:00+00:00", "updated_at": "2026-08-23T00:00:00+00:00",
                "evidence": {}, "research_snapshots": [], "latest_research": None, "demand_research": [], "latest_demand_research": None,
            }
        }
        self.watch_channels = {}
        self.watch_videos = {}
        self.demands = []
        self.audits = {}
        self.structured_experiments = {}
        page.route("**/*", self._handle)

    def _handle(self, route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path
        method = request.method
        key = f"{method} {path}"
        self.requests[key] += 1
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
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
            _json_response(route, history_run_detail(include_link=self.include_link))
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
        if path == "/api/audits" and method == "GET":
            candidates = []
            if self.include_link:
                saved = self.audits.get(9)
                candidates = [{"id": 9, "analysis_run_id": 1, "youtube_video_id": "fixture-video-1", "published_at": "2026-08-14T10:00:00+00:00", "package_topic": "Linked rainy highway upload", "youtube_metadata": {"title": "Published rainy highway title"}, "latest_performance": {"views": 42, "snapshot_window": "24h"}, "ownership_verified": True, "audit_id": saved.get("id") if saved else None, "audit_captured_at": saved.get("captured_at") if saved else None, "audit_state": saved["summary"]["state"] if saved else "not_run", "idea": {"id": 1, "topic": "Rainy highway quote idea"}, "evidence_state": "mature", "selection_state": "selected"}]
            _json_response(route, {"candidates": candidates, "total": len(candidates)})
            return
        audit_match = re.fullmatch(r"/api/audits/(\d+)(?:/(refresh|findings|evidence))?", path)
        if audit_match:
            link_id = int(audit_match.group(1)); action = audit_match.group(2); saved = self.audits.get(link_id)
            if method == "POST" and action == "refresh":
                saved = {"id": len(self.audits) + 1, "captured_at": "2026-08-23T06:00:00+00:00", "rule_version": "phase8-audit-v1", "summary": {"state": "mature_observation", "message": "Historical intent, actual published metadata, and available observations are separated. No finding establishes causality."}, "video": {"link_id": link_id, "analysis_run_id": 1, "youtube_video_id": "fixture-video-1", "published_at": "2026-08-14T10:00:00+00:00", "format": "youtube_shorts", "language": "english"}, "intent": {"generated_package": {"title": "Generated rainy highway title", "description": "Generated description", "tags": ["rain"], "hashtags": ["#Shorts"]}, "selected_package": {"title": "Selected rainy highway title", "description": "Selected description", "tags": ["rain"], "hashtags": ["#Shorts"]}, "selection_attribution": "creator_selected", "selected_package_id": "package-a"}, "published_reality": {"title": "Published rainy highway title", "description": "Published description", "tags": ["rainy road"], "hashtags": ["#Shorts"], "available": True, "captured_at": "2026-08-23T05:00:00+00:00"}, "comparisons": [{"field": "title", "generated": "Generated rainy highway title", "selected": "Selected rainy highway title", "published": "Published rainy highway title", "selected_to_published": "changed"}, {"field": "description", "generated": "Generated description", "selected": "Selected description", "published": "Published description", "selected_to_published": "changed"}], "before_publication": {"generation_quality": {"status": "pass"}, "retention_assistant": {"risk_level": "medium"}, "demand_research": {"classification": "active_topic"}, "watchlist_context": [], "personal_evidence": {"status": "insufficient_evidence"}, "idea": {"topic": "Rainy highway quote idea"}}, "observed_performance": {"latest_observation": {"views": 42, "avg_view_percentage": 61}, "maturity": "mature_observation", "causality": "not_established"}, "findings": [{"code": "published_title_changed", "severity": "review", "explanation": "Published title differed from the explicitly selected title.", "recommended_interpretation": "Treat performance as evidence about the published title, not the selected draft.", "evidence_state": "observed", "evidence": "creator selection + owned YouTube metadata"}], "learning_candidates": [{"variable": "title_mechanism", "value": "specific_curiosity", "evidence_state": "insufficient_evidence", "sample_size": 1, "interpretation": "Observed association candidate; never causal proof."}], "evidence": {"snapshot_count": 2, "mature_window_count": 1}, "limitations": ["A mature observation can support comparison but does not prove causation."]}
                self.audits[link_id] = saved
                _json_response(route, {"status": "audited", "audit": saved, "versions": [{"id": saved["id"], "captured_at": saved["captured_at"], "summary_state": "mature_observation"}]}, 201); return
            if method == "GET" and not action:
                _json_response(route, {"audit": saved, "versions": ([{"id": saved["id"], "captured_at": saved["captured_at"], "summary_state": saved["summary"]["state"]}] if saved else []), "status": "available" if saved else "not_run"}); return
            if method == "GET" and action == "findings" and saved:_json_response(route,{"audit_id":saved["id"],"summary":saved["summary"],"findings":saved["findings"]});return
            if method == "GET" and action == "evidence" and saved:_json_response(route,{"audit_id":saved["id"],"evidence":saved["evidence"],"observed_performance":saved["observed_performance"],"limitations":saved["limitations"]});return
        if path == "/api/experiment-center/experiments" and method == "GET":
            _json_response(route, {"experiments": list(reversed(list(self.structured_experiments.values()))), "total": len(self.structured_experiments)}); return
        if path == "/api/experiment-center/experiments" and method == "POST":
            body = self.request_bodies[key][-1] or {}; experiment_id = len(self.structured_experiments) + 1
            item = {"id": experiment_id, **body, "description": body.get("description", ""), "status": "draft", "secondary_metrics": body.get("secondary_metrics", []), "target_sample_size": body.get("target_sample_size"), "minimum_sample_size": body.get("minimum_sample_size", 5), "notes": body.get("notes", ""), "assignments": [], "assignment_counts": {"control": 0, "variant": 0, "observational_reference": 0}, "latest_result": None, "created_at": "2026-08-23T06:00:00+00:00", "updated_at": "2026-08-23T06:00:00+00:00"}
            self.structured_experiments[experiment_id] = item; _json_response(route, {"status": "created", "experiment": item}, 201); return
        experiment_match = re.fullmatch(r"/api/experiment-center/experiments/(\d+)(?:/(assignments|compare))?(?:/(\d+))?", path)
        if experiment_match:
            experiment_id = int(experiment_match.group(1)); action = experiment_match.group(2); assignment_id = experiment_match.group(3); item = self.structured_experiments.get(experiment_id)
            if method == "GET" and not action:_json_response(route,{"experiment":item,"result_versions":([{"id":1,"result_state":item["latest_result"]["state"]}] if item and item.get("latest_result") else [])});return
            if method == "PATCH" and not action and item:item.update(self.request_bodies[key][-1] or {});_json_response(route,{"status":"updated","experiment":item});return
            if method == "POST" and action == "assignments" and item:
                body=self.request_bodies[key][-1] or {}; link_id=int(body.get("published_video_link_id") or 0)
                if any(a["published_video_link_id"]==link_id for a in item["assignments"]):_json_response(route,{"error":{"message":"This video is already assigned to the experiment.","request_id":"assignment-fixture"}},422);return
                assignment={"id":len(item["assignments"])+1,"published_video_link_id":link_id,"role":body.get("role"),"youtube_video_id":"fixture-video-1","title":"Published rainy highway title","assigned_at":"2026-08-23T06:10:00+00:00","notes":""};item["assignments"].append(assignment);item["assignment_counts"][assignment["role"]]+=1;_json_response(route,{"status":"assigned","experiment":item},201);return
            if method == "DELETE" and action == "assignments" and item:
                item["assignments"]=[a for a in item["assignments"] if a["id"]!=int(assignment_id)];item["assignment_counts"]={role:sum(a["role"]==role for a in item["assignments"]) for role in ("control","variant","observational_reference")};_json_response(route,{"status":"removed","assignment_id":int(assignment_id)});return
            if method == "POST" and action == "compare" and item:
                item["latest_result"]={"id":1,"captured_at":"2026-08-23T06:20:00+00:00","state":"insufficient_evidence","mode":item["mode"],"label":"PLANNED EXPERIMENT — DIRECTIONAL, NOT CAUSAL PROOF" if item["mode"]=="controlled" else "OBSERVATIONAL — NOT A CONTROLLED EXPERIMENT","sample":{"assigned_control":item["assignment_counts"]["control"],"assigned_variant":item["assignment_counts"]["variant"],"eligible_control":item["assignment_counts"]["control"],"eligible_variant":item["assignment_counts"]["variant"],"minimum_per_group":5},"metrics":[{"metric":item["success_metric"],"control":{"sample_size":1,"median":61},"variant":{"sample_size":0,"median":None},"relative_difference_percent":None,"observed_direction":"even"}],"interpretation":"The sample is too small; no direction is claimed.","limitations":["No fake statistical significance or causal claim is calculated."],"next_recommendation":"Collect more eligible control and variant videos.","learning_candidate":None};_json_response(route,{"status":"compared","result":item["latest_result"],"experiment":item},201);return
        if path == "/api/watchlist/channels" and method == "GET":
            state=(parse_qs(parsed.query).get('state') or [''])[0]; values=[x for x in self.watch_channels.values() if not state or x['state']==state];_json_response(route,{"channels":values,"total":len(values)});return
        if path == "/api/watchlist/channels" and method == "POST":
            body=self.request_bodies[key][-1] or {}; item_id=len(self.watch_channels)+1; item={"id":item_id,"channel_id":body.get('channel_id'),"title":"Fixture Public Channel","thumbnail_url":None,"subscriber_count":120,"video_count":8,"notes":body.get('notes',''),"state":"active","source":"public_observation","last_researched_at":None,"snapshots":[]};self.watch_channels[item_id]=item;_json_response(route,{"status":"created","channel":item},201);return
        if path == "/api/watchlist/videos" and method == "GET":
            query=parse_qs(parsed.query);state=(query.get('state')or[''])[0];q=(query.get('q')or[''])[0].lower();values=[x for x in self.watch_videos.values() if (not state or x['state']==state) and (not q or q in x['title'].lower())];_json_response(route,{"videos":values,"total":len(values)});return
        if path == "/api/watchlist/videos" and method == "POST":
            body=self.request_bodies[key][-1] or {};item_id=len(self.watch_videos)+1;item={"id":item_id,"video_id":"AbCdEfGhI12","title":"Fixture camera outlier","channel_id":"UC-fixture","channel_title":"Fixture Public Channel","published_at":"2026-08-20T00:00:00+00:00","duration_seconds":30,"language":"en","format":"youtube_shorts","notes":body.get('notes',''),"state":"active","source":"public_observation","last_researched_at":None,"snapshots":[],"latest_snapshot":None,"outlier":None};self.watch_videos[item_id]=item;_json_response(route,{"status":"created","video":item},201);return
        watch_match=re.fullmatch(r"/api/watchlist/(channels|videos)/(\d+)(?:/(research|analyze-outlier))?",path)
        if watch_match:
            collection=self.watch_channels if watch_match.group(1)=='channels' else self.watch_videos; singular='channel' if watch_match.group(1)=='channels' else 'video';item=collection.get(int(watch_match.group(2)));action=watch_match.group(3)
            if method=='GET' and item:_json_response(route,{singular:item});return
            if method=='PATCH' and item:item.update(self.request_bodies[key][-1] or {});_json_response(route,{"status":"updated",singular:item});return
            if method=='POST' and action=='research' and item:
                snap={"id":1,"captured_at":"2026-08-23T04:00:00+00:00","source":"public_observation"}
                if singular=='video':snap.update({"view_count":9300,"like_count":510,"comment_count":44});item['latest_snapshot']=snap
                else:snap.update({"subscriber_count":125,"video_count":8})
                item['snapshots'].insert(0,snap);item['last_researched_at']=snap['captured_at'];_json_response(route,{"status":"researched",singular:item,"observed_videos":6});return
            if method=='POST' and action=='analyze-outlier' and item:
                out={"status":"possible_outlier","observed_views":9300,"baseline_median_views":3000,"relative_multiplier":3.1,"sample_size":6,"observation_window":"latest public snapshots","explanation":"Observed views are 3.10x the median of 6 comparable recent videos. This is an observational outlier signal, not a viral prediction.","provenance":"heuristic_public_observation"};item['outlier']=out;_json_response(route,{"status":"analyzed","analysis":out,"video":item});return
        if path == "/api/demand/research" and method == "GET":_json_response(route,{"research":list(reversed(self.demands)),"total":len(self.demands),"limit":50,"offset":0});return
        if path == "/api/demand/research" and method == "POST":
            body=self.request_bodies[key][-1] or {};item={"id":len(self.demands)+1,"idea_id":None,"topic":body.get('topic'),"language":body.get('language'),"format":body.get('format'),"region":body.get('region'),"audience_context":body.get('audience_context'),"classification":"active_topic","captured_at":"2026-08-23T05:00:00+00:00","evidence":{"reasons":["5 relevant public results were observed.","Coverage was observed across 3 independent channels."],"signals":[{"name":"sampled_relevant_results","observed":5,"source":"public_observation","limitation":"Sampled API results, not monthly search volume."}],"watchlist_evidence":[{"outlier_status":"possible_outlier"}],"personal_evidence":{"learning_allowed":False,"sample_size":0,"source":"unavailable"},"limitations":["No official monthly search-volume data is available.","Public association does not establish causation."]}};self.demands.append(item);_json_response(route,{"status":"researched","research":item},201);return
        demand_match=re.fullmatch(r"/api/demand/research/(\d+)(?:/(generate))?",path)
        if demand_match:
            item=next((x for x in self.demands if x['id']==int(demand_match.group(1))),None)
            if method=='GET' and item:_json_response(route,{"research":item});return
            if method=='POST' and demand_match.group(2)=='generate':_json_response(route,{"status":"package_generated","analysis":analyze_success(),"demand_research_id":int(demand_match.group(1))});return
        idea_demand=re.fullmatch(r"/api/ideas/(\d+)/demand-research",path)
        if idea_demand and method=='POST':
            idea=self.ideas[int(idea_demand.group(1))];demand={"id":len(self.demands)+1,"idea_id":idea['id'],"topic":idea['topic'],"classification":"emerging_signal","captured_at":"2026-08-23T05:00:00+00:00","evidence":{"reasons":["3 public observations"],"signals":[],"watchlist_evidence":[],"personal_evidence":{"learning_allowed":False},"limitations":["No official monthly search-volume data is available."]}};self.demands.append(demand);idea['demand_research'].insert(0,{**demand,"stale":False});idea['latest_demand_research']=idea['demand_research'][0];_json_response(route,{"status":"researched","research":demand},201);return
        if path == "/api/ideas" and method == "GET":
            query = parse_qs(parsed.query)
            status_filter = (query.get("status") or [""])[0]
            offset = int((query.get("offset") or ["0"])[0])
            limit = int((query.get("limit") or ["20"])[0])
            values = sorted(self.ideas.values(), key=lambda item: item["id"], reverse=True)
            if status_filter:
                values = [item for item in values if item["status"] == status_filter]
            summaries = [{
                "id": item["id"], "topic": item["topic"], "status": item["status"],
                "format": item["format"], "language": item["language"], "region": item["region"],
                "created_at": item["created_at"], "updated_at": item["updated_at"],
                "analysis_run_id": item["analysis_run_id"], "published_video_link_id": item["published_video_link_id"],
                "last_researched_at": item["latest_research"]["captured_at"] if item["latest_research"] else None,
                "research_snapshot_count": len(item["research_snapshots"]),
                "opportunity_explanation": (item["evidence"] or {}).get("opportunity_explanation", "Research has not been run for this idea."),
                "personal_evidence_status": ((item["evidence"] or {}).get("personal_evidence") or {}).get("status", "insufficient_evidence"),
            } for item in values[offset:offset + limit]]
            _json_response(route, {"ideas": summaries, "total": len(values), "limit": limit, "offset": offset, "status": status_filter or None})
            return
        if path == "/api/ideas" and method == "POST":
            body = self.request_bodies[key][-1] or {}
            idea_id = max(self.ideas) + 1 if self.ideas else 1
            now = "2026-08-23T01:00:00+00:00"
            idea = {
                "id": idea_id, "topic": body.get("topic", "Untitled"), "notes": body.get("notes", ""),
                "format": body.get("format", "unknown"), "language": body.get("language", "english"), "region": body.get("region", "global"),
                "visual_or_background": body.get("visual_or_background", ""), "on_screen_text": body.get("on_screen_text", ""),
                "target_duration_seconds": body.get("target_duration_seconds"), "emotion_or_intent": body.get("emotion_or_intent", ""),
                "search_angle": body.get("search_angle", ""), "browse_angle": body.get("browse_angle", ""), "audience_angle": body.get("audience_angle", ""),
                "status": "idea", "analysis_run_id": None, "published_video_link_id": None,
                "created_at": now, "updated_at": now, "evidence": {}, "research_snapshots": [], "latest_research": None, "demand_research": [], "latest_demand_research": None,
            }
            self.ideas[idea_id] = idea
            _json_response(route, {"status": "created", "idea": idea}, status=201)
            return
        idea_match = re.fullmatch(r"/api/ideas/(\d+)(?:/(research|generate))?", path)
        if idea_match:
            idea_id = int(idea_match.group(1))
            action = idea_match.group(2)
            idea = self.ideas.get(idea_id)
            if not idea:
                _json_response(route, {"error": {"message": "Idea not found.", "request_id": "idea-fixture"}}, status=404)
                return
            if method == "GET" and not action:
                _json_response(route, {"idea": idea})
                return
            if method == "PATCH" and not action:
                body = self.request_bodies[key][-1] or {}
                idea.update(body)
                idea["updated_at"] = "2026-08-23T02:00:00+00:00"
                _json_response(route, {"status": "updated", "idea": idea})
                return
            if method == "POST" and action == "research":
                evidence = {
                    "captured_at": "2026-08-23T03:00:00+00:00", "source": "approved_youtube_data_api_research",
                    "opportunity_explanation": "Observed 1 relevant public YouTube API result; this is not monthly search volume or predicted demand.",
                    "personal_evidence": {"status": "insufficient_evidence", "learning_allowed": False, "sample_size": 0, "confidence_label": "Collecting evidence", "snapshot_window": "24h", "message": "Not enough personal evidence."},
                    "youtube_results": [{"title": "Public rainy road observation", "channel_title": "Fixture public channel", "published_at": "2026-08-20T00:00:00+00:00", "view_count": 51}],
                }
                snapshot = {"id": len(idea["research_snapshots"]) + 1, "captured_at": evidence["captured_at"], "evidence": evidence}
                idea["research_snapshots"].insert(0, snapshot)
                idea["latest_research"] = snapshot
                idea["evidence"] = evidence
                _json_response(route, {"status": "researched", "snapshot": snapshot, "idea": idea})
                return
            if method == "POST" and action == "generate":
                idea["status"] = "package_generated"
                idea["analysis_run_id"] = 1
                _json_response(route, {"status": "package_generated", "idea": idea, "analysis": analyze_success()})
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
