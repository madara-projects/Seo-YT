from __future__ import annotations

import re
from typing import Any, Dict

from win_engine.analysis.intent_classifier import classify_intent
from win_engine.analysis.creator_brief import creator_topic
from win_engine.analysis.research_planner import brief_research_text
from win_engine.analysis.topic_lock import (
    _is_junk_tag,
    expand_idea_to_script,
    extract_main_topic,
    fallback_keyword_signals,
    force_hashtags,
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
    creator_brief = ctx.get("creator_brief")
    topic_source = brief_research_text(
        safe_script,
        creator_brief if isinstance(creator_brief, dict) else None,
    )
    category = infer_category(topic_source, hint=ctx.get("category"))   # Fix 2
    main_topic = creator_topic(creator_brief if isinstance(creator_brief, dict) else None) or extract_main_topic(topic_source)  # Fix 1
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
    if isinstance(creator_brief, dict):
        research_payload["creator_brief"] = creator_brief

    # Fix 3: API fallback — seed keyword signals from category presets when
    # YouTube returned nothing usable.
    yt_results = research_payload.get("youtube_results") or []
    existing_signals = research_payload.get("keyword_signals") or []
    if not yt_results and not existing_signals:
        research_payload["keyword_signals"] = fallback_keyword_signals(category)

    seo_package = build_seo_package(intent, safe_script, research_payload, history_store)

    # ---- Topic-lock post-process ---------------------------------------
    # force_topic_in_title now only regenerates if the LLM title is broken
    # (empty, < 10 chars, or all-junk). LLM output is preserved otherwise.
    # force_hashtags accepts the LLM's hashtags and only tops up if missing.
    locked_title = force_topic_in_title(seo_package["title"], main_topic, category)
    locked_description = force_topic_in_description(seo_package["description"], main_topic)
    locked_tags = force_topic_in_tags(seo_package["tags"], main_topic, category)
    locked_hashtags = force_hashtags(seo_package.get("hashtags") or [], main_topic, category)
    locked_description = format_upload_ready_description(
        locked_description,
        locked_hashtags,
        category=category,
        topic=main_topic,
    )
    locked_variants = [
        force_topic_in_title(v["title"], main_topic, category, variant_index=i)
        for i, v in enumerate(seo_package["title_variants"])
    ]

    # Patch title_optimization so best_title + scored_variants are also topic-locked.
    title_opt = dict(seo_package.get("title_optimization") or {})
    if title_opt.get("best_title"):
        title_opt["best_title"] = force_topic_in_title(
            title_opt["best_title"], main_topic, category)
    sv = list(title_opt.get("scored_variants") or [])
    for i, item in enumerate(sv):
        if isinstance(item, dict) and item.get("title"):
            item["title"] = force_topic_in_title(
                item["title"], main_topic, category, variant_index=i)
    title_opt["scored_variants"] = sv

    # Strip junk from any keyword_signals that came back from research.
    locked_signals = [
        s for s in (research_payload.get("keyword_signals") or [])
        if not _is_junk_tag(str(s.get("keyword", "")))
    ]

    # ---- Selected-language package -------------------------------------
    def _lock_pkg(p: dict[str, Any], lang: str) -> dict[str, Any]:
        if not isinstance(p, dict):
            return {}
        title = force_topic_in_title(p.get("title", ""), main_topic, category)
        variants = [
            force_topic_in_title(v, main_topic, category, variant_index=i)
            for i, v in enumerate(p.get("variants", []) or [])
        ]
        tags = force_topic_in_tags(p.get("tags", []) or [], main_topic, category)
        hashtags = force_hashtags(p.get("hashtags", []) or [], main_topic, category)
        description = p.get("description", "") or ""
        # Only English gets the topic-presence fallback; Tamil / Tanglish
        # descriptions stay in their own language, untouched.
        if lang == "english":
            description = force_topic_in_description(description, main_topic)
        return {
            "title": title,
            "variants": variants,
            "description": description,
            "tags": tags,
            "hashtags": hashtags,
        }

    multilang_packages = {
        lang: _lock_pkg(p, lang)
        for lang, p in (seo_package.get("multilang") or {}).items()
    }

    # Honest warning when a non-English language falls back to the English template.
    research_warnings = list(research_payload.get("research_warnings", []) or [])
    if isinstance(creator_brief, dict):
        research_warnings.extend(creator_brief.get("warnings", []))
    non_english_fallback = [
        lang for lang in (seo_package.get("fallback_languages") or []) if lang != "english"
    ]
    generation_source = str(seo_package.get("generation_source") or "fallback")
    if generation_source == "fallback":
        research_warnings.append(
            "Gemini was unavailable, so this run used the content-specific local fallback."
        )
    if non_english_fallback:
        provider_hint = "Gemini" if generation_source == "fallback" else "the configured AI provider"
        research_warnings.append(
            ", ".join(sorted(non_english_fallback)).title()
            + " fell back to an English template because " + provider_hint
            + " returned no native output."
        )
    # --------------------------------------------------------------------

    response = AnalyzeResponse(
        title=locked_title,
        description=locked_description,
        tags=locked_tags,
        hashtags=locked_hashtags,
        intent=intent,
        content_angle=seo_package["content_angle"],
        title_variants=locked_variants,
        title_optimization=title_opt,
        title_thumbnail_packages=seo_package.get("title_thumbnail_packages", []),
        content_audit=seo_package["content_audit"],
        cache_policy=research_payload.get("cache_policy", "evergreen"),
        research_warnings=research_warnings,
        generation_source=generation_source,
        creator_brief=creator_brief if isinstance(creator_brief, dict) else {},
        research_queries=research_payload.get("research_queries", []),
        research_decision=research_payload.get("research_decision", {}),
        multilang=multilang_packages,
        youtube_results=research_payload.get("youtube_results", []),
        top_opportunities=research_payload.get("top_opportunities", []),
        keyword_signals=locked_signals,
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
    history_store = research_payload.get("history_store")
    history_run_id = seo_package.get("history_run_id")
    if isinstance(history_store, HistoryStore) and isinstance(history_run_id, int):
        history_store.update_analysis_payload(history_run_id, response["title"], response)
    return response


def format_upload_ready_description(
    description: str,
    hashtags: list[str],
    *,
    category: str = "general",
    topic: str = "",
) -> str:
    """Add restrained visual structure and the selected hashtags to a description."""

    text = (description or "").strip()
    if not text:
        return text

    # Gemini may put hashtags in its prose even though hashtags are returned
    # separately. Remove hashtag-only lines so we can render one clean final line.
    prose_lines = [
        line for line in text.splitlines()
        if not re.fullmatch(r"\s*(?:#[A-Za-z0-9_]+\s*)+", line)
    ]
    text = "\n".join(prose_lines).strip()

    if not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text):
        lowered = f"{topic} {category}".lower()
        if any(term in lowered for term in ("heartbreak", "unrequited", "sad", "betrayal")):
            emoji = "💔"
        else:
            emoji = {
                "gaming": "🎮", "cooking": "🍽️", "tech": "💻", "finance": "📈",
                "fitness": "💪", "quotes": "💭", "shorts": "🎬", "youtube_shorts": "🎬",
            }.get(category.lower(), "🎥")
        text = f"{emoji} {text}"

    selected: list[str] = []
    existing = {match.casefold() for match in re.findall(r"#[A-Za-z0-9_]+", text)}
    for raw in hashtags or []:
        hashtag = str(raw or "").strip()
        if not hashtag:
            continue
        if not hashtag.startswith("#"):
            hashtag = f"#{hashtag.lstrip('#')}"
        if hashtag.casefold() not in existing:
            selected.append(hashtag)
            existing.add(hashtag.casefold())
    if selected:
        text = f"{text}\n\n{' '.join(selected)}"
    return text
