from __future__ import annotations

from typing import Any, Dict

from win_engine.analysis.intent_classifier import classify_intent
from win_engine.analysis.topic_lock import (
    expand_idea_to_script,
    extract_main_topic,
    fallback_keyword_signals,
    force_topic_in_description,
    force_topic_in_tags,
    force_topic_in_title,
    infer_category,
    is_short_idea,
    normalize_risk_terms,
)
from win_engine.core.schemas import AnalyzeResponse
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.strategy_engine import build_seo_package


def generate_seo_suggestions(
    script: str,
    research: dict[str, object],
    context: dict[str, Any] | None = None,
) -> Dict[str, object]:
    """Generate first-pass SEO suggestions from local research signals."""

    # ---- Topic-lock pre-process ----------------------------------------
    safe_script = normalize_risk_terms(script or "")          # Fix 6
    if is_short_idea(safe_script):                            # Fix 4
        safe_script = expand_idea_to_script(safe_script)

    ctx = context or {}
    category = infer_category(safe_script, hint=ctx.get("category"))   # Fix 2
    main_topic = extract_main_topic(safe_script)                       # Fix 1
    # --------------------------------------------------------------------

    intent = classify_intent(safe_script)
    history_store = research.get("history_store")
    if not isinstance(history_store, HistoryStore):
        raise ValueError("History store missing from research payload.")

    research_payload = dict(research)
    if context:
        research_payload["language_context"] = context
    research_payload["category"] = category
    research_payload["main_topic"] = main_topic

    # Fix 3: API fallback — seed keyword signals from category presets when
    # YouTube returned nothing usable.
    yt_results = research_payload.get("youtube_results") or []
    existing_signals = research_payload.get("keyword_signals") or []
    if not yt_results and not existing_signals:
        research_payload["keyword_signals"] = fallback_keyword_signals(category)

    seo_package = build_seo_package(intent, safe_script, research_payload, history_store)

    # ---- Topic-lock post-process ---------------------------------------
    locked_title = force_topic_in_title(seo_package["title"], main_topic, category)   # Fix 1 + 5
    locked_description = force_topic_in_description(seo_package["description"], main_topic)
    locked_tags = force_topic_in_tags(seo_package["tags"], main_topic, category)
    locked_variants = [
        force_topic_in_title(variant["title"], main_topic, category)
        for variant in seo_package["title_variants"]
    ]
    # --------------------------------------------------------------------

    return AnalyzeResponse(
        title=locked_title,
        description=locked_description,
        tags=locked_tags,
        hashtags=seo_package["hashtags"],
        intent=intent,
        content_angle=seo_package["content_angle"],
        title_variants=locked_variants,
        title_optimization=seo_package["title_optimization"],
        content_audit=seo_package["content_audit"],
        cache_policy=research_payload.get("cache_policy", "evergreen"),
        research_warnings=research_payload.get("research_warnings", []),
        youtube_results=research_payload.get("youtube_results", []),
        top_opportunities=research_payload.get("top_opportunities", []),
        keyword_signals=research_payload.get("keyword_signals", []),
        entity_signals=research_payload.get("entity_signals", []),
        upload_timing=research_payload.get("upload_timing", {}),
        thumbnail_intelligence=research_payload.get("thumbnail_intelligence", {}),
        opportunity_gap_analysis=seo_package["opportunity_gap_analysis"],
        competitor_shadow=seo_package["opportunity_gap_analysis"].get("competitor_shadow", {}),
        language_strategy=seo_package["language_strategy"],
        pacing_analysis=seo_package["pacing_analysis"],
        channel_intelligence=seo_package["channel_intelligence"],
        content_graph_strategy=seo_package["content_graph_strategy"],
        thumbnail_strategy=seo_package["thumbnail_strategy"],
        chapters=seo_package["chapters"],
        session_expansion=seo_package["session_expansion"],
        binge_bridge=seo_package["binge_bridge"],
        automation_workflow=seo_package["automation_workflow"],
        performance_sync=seo_package["feedback_package"]["performance_sync"],
        learning_engine=seo_package["feedback_package"]["learning_engine"],
        winning_patterns=seo_package["feedback_package"]["winning_patterns"],
        ctr_prediction=seo_package["feedback_package"]["ctr_prediction"],
        ab_test_pack=seo_package["feedback_package"]["ab_test_pack"],
        internal_scorecard=seo_package["feedback_package"]["internal_scorecard"],
        historical_comparison=seo_package["feedback_package"]["historical_comparison"],
    ).model_dump()
