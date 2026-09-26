from __future__ import annotations

import logging
import re
from typing import Any, Dict

from win_engine.analysis.intent_classifier import classify_intent
from win_engine.analysis.creator_brief import creator_topic
from win_engine.analysis.generation_quality import (
    apply_quality_gate,
    evaluate_package_quality,
    filter_source_hashtags,
    focused_short_hashtags,
    is_short_content,
)
from win_engine.analysis.package_builder import build_title_thumbnail_packages, title_gate_status
from win_engine.analysis.strategy_layer import build_content_graph_strategy
from win_engine.analysis.retention_assistant import analyze_retention_assistant
from win_engine.analysis.keyword_research import select_final_tags, synchronize_tag_evidence
from win_engine.analysis.research_planner import brief_research_text
from win_engine.analysis.topic_lock import (
    is_junk_tag,
    extract_main_topic,
    force_hashtags,
    force_topic_in_description,
    force_topic_in_title,
    infer_category,
    normalize_hashtag,
    normalize_risk_terms,
    source_casing_map,
    unsupported_risk_terms,
)
from win_engine.core.schemas import AnalyzeResponse
from win_engine.feedback.evidence_policy import EARLY_SIGNAL_MIN_SAMPLES
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.learning_engine import build_feedback_package
from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import build_binge_bridge, build_session_expansion
from win_engine.generation.strategy_engine import build_seo_package, resolve_output_language, title_quality_score
from win_engine.generation.quality_refinement import refine_package, enforce_quality_target
from win_engine.llm.seo_writer import with_extra_call


logger = logging.getLogger(__name__)

# Why the writer used its local package, keyed by the provider status or the
# strategy stage's fallback reason. A quality rejection is the only case where
# Gemini actually produced a package.
_QUALITY_FALLBACK_REASONS = {
    "quality_gate_rejection", "gemini_invalid_repair_response",
    "final_quality_red", "final_quality_red_after_deterministic_fallback",
}
_PROVIDER_FALLBACK_CAUSES = {
    "gemini_unavailable": "Gemini is not configured",
    "gemini_cooldown": "Gemini is paused after repeated failures",
    "gemini_rate_limited": "Gemini rate-limited the request",
    "gemini_timeout": "Gemini timed out",
    "gemini_transport_error": "Gemini could not be reached",
    "gemini_permanent_error": "Gemini rejected the request (check the API key and model)",
    "gemini_invalid_response": "Gemini returned an unusable response",
    "gemini_truncated": "Gemini's response was cut off",
    "gemini_application_error": "The Gemini request failed",
}


def _without_risk_terms(titles: list[str], source: str) -> list[str]:
    """Titles that add no risk phrase; reworded only when none is clean.

    Rewording mid-title reads badly ("Get earn diamonds safely?"), so a clean
    alternative is preferred whenever one exists.
    """

    clean = [title for title in titles if not unsupported_risk_terms(title, source)]
    return clean or [normalize_risk_terms(title, source=source) for title in titles]


def _fallback_warning(trace: dict[str, Any]) -> str:
    """Why this run shipped the local package, as the writer's diagnostics recorded it."""

    status = str(trace.get("status") or "")
    reason = str(trace.get("fallback_reason") or "")
    # A rejected local package rewrites the fallback reason to
    # "final_quality_red", but the provider status still says why Gemini
    # produced nothing in the first place.
    if trace.get("initial_quality_rejection") or (
        reason in _QUALITY_FALLBACK_REASONS and status not in _PROVIDER_FALLBACK_CAUSES
    ):
        cause = "No Gemini package passed the local validation checks"
    else:
        cause = (_PROVIDER_FALLBACK_CAUSES.get(status) or _PROVIDER_FALLBACK_CAUSES.get(reason)
                 or "Gemini did not return a usable package")
    return f"{cause}, so this run used the content-specific local fallback."


def generate_seo_suggestions(
    script: str,
    research: dict[str, object],
    context: dict[str, Any] | None = None,
) -> Dict[str, object]:
    """Generate first-pass SEO suggestions from local research signals."""

    # The creator's words reach analysis, the prompts and History as written.
    # Rewriting risky phrases here turned "never install a mod apk" into
    # "never install a official method"; the generated copy is constrained
    # after refinement instead.
    script_text = (script or "").strip()

    ctx = context or {}
    # "auto" is resolved to the video's language exactly as the writer stage
    # resolves it: the literal "auto" matched no package, so the one the UI
    # shows kept the writer's copy, unrefined and never risk-filtered or gated.
    selected_language = resolve_output_language(ctx)
    creator_brief = ctx.get("creator_brief")
    topic_source = brief_research_text(
        script_text,
        creator_brief if isinstance(creator_brief, dict) else None,
    )
    category = infer_category(topic_source, hint=ctx.get("category"))
    main_topic = creator_topic(creator_brief if isinstance(creator_brief, dict) else None) or extract_main_topic(topic_source)
    # The brief's format (or a stated length) decides, never the topic category:
    # "lessons" or "thoughts" made a startup talk "quotes", and then a Short
    # with #shorts and yt/shorts tags.
    short_form = is_short_content(script_text, creator_brief if isinstance(creator_brief, dict) else None)

    intent = classify_intent(script_text)
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

    # With no YouTube results and no script phrases there are no keyword
    # signals, and none are made up: category presets ("tech review", "study
    # tips") were shown as research and then grounded tags, named chapters and
    # fed the gap analysis.
    yt_results = research_payload.get("youtube_results") or []
    keyword_signals_unavailable = not yt_results and not research_payload.get("keyword_signals")
    competitor_titles = [str(item.get("title") or "") for item in yt_results if isinstance(item, dict)]

    seo_package = build_seo_package(intent, script_text, research_payload, history_store)
    # Recent and published titles as they stood before this run was recorded,
    # so the final title is not compared with this run's own writer title.
    channel_learning = seo_package.get("channel_learning") or {}

    # ---- Topic-lock post-process ---------------------------------------
    # force_topic_in_title only regenerates a title that is missing or shorter
    # than six characters; any other generated title is kept as written.
    # force_hashtags accepts the LLM's hashtags and only tops up if missing.
    locked_title = force_topic_in_title(seo_package["title"], main_topic, category, short_form=short_form)
    locked_description = force_topic_in_description(seo_package["description"], main_topic)
    creator_content = str(creator_brief.get("content") or "") if isinstance(creator_brief, dict) else ""
    # Hashtags are built from lowercase tags; names keep the creator's casing.
    casing = source_casing_map(script_text, creator_content)
    # A risky phrase the creator wrote is their subject; one the copy adds is not.
    risk_source = f"{script_text}\n{creator_content}"
    tag_context = [script_text]
    if isinstance(creator_brief, dict):
        tag_context.extend(str(creator_brief.get(field) or "") for field in (
            "content", "target_audience", "viewer_promise", "unique_angle", "proof",
            "visual_requirements", "creator_intent", "content_constraints",
        ))
    tag_context.extend(
        str(item.get(key) or "")
        for item in (research_payload.get("keyword_signals") or [])
        if isinstance(item, dict)
        for key in ("keyword", "entity")
    )
    locked_tags, keyword_research = select_final_tags(
        seo_package.get("keyword_research") or research_payload.get("keyword_research") or {},
        generated_tags=seo_package.get("tags") or [],
        title=locked_title,
        script=script_text,
        creator_brief=creator_brief if isinstance(creator_brief, dict) else None,
        is_short=short_form,
    )
    locked_hashtags = filter_source_hashtags(
        force_hashtags(seo_package.get("hashtags") or [], main_topic, category, tags=locked_tags, casing=casing),
        script_text,
        creator_brief if isinstance(creator_brief, dict) else None,
    )
    if short_form:
        locked_hashtags = focused_short_hashtags(locked_tags, casing)
    locked_description = format_upload_ready_description(
        locked_description,
        locked_hashtags,
        category=category,
        topic=main_topic,
    )
    # Unusable variants all fall back to the same topic title; keep it once.
    locked_variants = list(dict.fromkeys(
        force_topic_in_title(v["title"], main_topic, category, variant_index=i, short_form=short_form)
        for i, v in enumerate(seo_package["title_variants"])
    ))
    generation_source = str(seo_package.get("generation_source") or "fallback")
    refined, refinement_trace = refine_package(
        {"title": locked_title, "variants": locked_variants, "description": locked_description,
         "tags": locked_tags, "hashtags": locked_hashtags},
        script=script_text, brief=creator_brief if isinstance(creator_brief, dict) else {},
        language=selected_language, region=str(ctx.get("region") or "global"),
        evidence=keyword_research, competitors=yt_results,
        channel_learning=channel_learning, local_fallback=generation_source == "fallback",
    )
    # Generated copy may not add an exploit promise ("unlimited diamonds") the
    # creator never made. Tags keep their research provenance, so an offending
    # tag is dropped rather than reworded.
    locked_title = _without_risk_terms([refined["title"], *refined["variants"]], risk_source)[0]
    locked_variants = _without_risk_terms(refined["variants"], risk_source)
    locked_tags = [
        tag for tag in (refined.get("tags") or locked_tags) if not unsupported_risk_terms(tag, risk_source)
    ]
    keyword_research = synchronize_tag_evidence(keyword_research, locked_tags)
    locked_hashtags = (focused_short_hashtags(locked_tags, casing)
        if short_form
        else (refined.get("hashtags") or locked_hashtags))
    locked_hashtags = [tag for tag in locked_hashtags if not unsupported_risk_terms(tag, risk_source)]
    locked_description = format_upload_ready_description(
        normalize_risk_terms(refined["description"], source=risk_source), locked_hashtags,
        category=category, topic=main_topic)
    trace = seo_package["generation_trace"] = {**(seo_package.get("generation_trace") or {}),
                                               "quality_refinement": refinement_trace}
    if refinement_trace.get("attempted"):
        # The repair request is a Gemini call like the writer's own, with its
        # own attempts and retries.
        trace.update(with_extra_call(trace, refinement_trace.get("provider_call") or {}))
        trace["gemini_attempted"] = True
    final_gate = evaluate_package_quality(
        {
            "title": locked_title, "variants": locked_variants,
            "description": locked_description, "tags": locked_tags, "hashtags": locked_hashtags,
        },
        script=script_text,
        creator_brief=creator_brief if isinstance(creator_brief, dict) else None,
        language=selected_language,
        recent_titles=channel_learning.get("recent_titles") or [],
        published_titles=channel_learning.get("published_titles") or [],
        tag_context=tag_context,
        tag_evidence=keyword_research,
        competitor_titles=competitor_titles,
    )
    gated = apply_quality_gate(
        {"title": locked_title, "variants": locked_variants, "description": locked_description,
         "tags": locked_tags, "hashtags": locked_hashtags},
        final_gate,
    )
    locked_title = gated["title"]
    locked_variants = gated["variants"]
    final_gate = enforce_quality_target(final_gate)
    # The writer stage records its own verdict under this key; the package the
    # creator receives is the one judged here, after tag selection and refinement.
    trace["writer_quality_verdict"] = trace.get("final_quality_verdict")
    trace["final_quality_verdict"] = final_gate.get("verdict")
    trace["final_quality_reasons"] = [
        item.get("code") for item in final_gate.get("issues") or [] if isinstance(item, dict)
    ]

    # One package per final title. Filtering the writer-stage variants by the
    # final list left a single package whenever refinement produced new titles
    # (1 of 4 for a quote Short), and packages are what the creator picks from.
    # Each final title is scored and judged here: writer-stage scores belonged
    # to titles refinement may have replaced (a new title showed 0), and every
    # package was labelled approved even when the final gate rejected it.
    writer_variants = {
        str(item.get("title") or "").casefold(): item
        for item in (seo_package.get("title_variants") or []) if isinstance(item, dict)
    }
    final_variants_data = []
    for title in dict.fromkeys([locked_title, *locked_variants]):
        if not title:
            continue
        row = dict(writer_variants.get(title.casefold()) or {"estimated_ctr": None, "package_intent": "Alternative"})
        row.update(
            title=title, character_count=len(title),
            score=title_quality_score(title, seo_package.get("title_scoring")),
            quality_gate=title_gate_status(title, final_gate, source="final_quality_gate"),
        )
        final_variants_data.append(row)
    title_opt = {
        "best_title": locked_title,
        "scored_variants": [
            {field: row.get(field) for field in ("title", "score", "estimated_ctr", "character_count")}
            for row in final_variants_data
        ],
    }
    # Rebuilt from the final titles with the history the writer stage read, so
    # the CTR guidance and A/B pair describe what the creator receives.
    feedback_package = build_feedback_package(
        seo_package={
            "title": locked_title,
            "content_angle": seo_package["content_angle"],
            "title_optimization": title_opt,
            "opportunity_gap_analysis": seo_package["opportunity_gap_analysis"],
        },
        research=research_payload,
        learning_summary=seo_package.get("learning_summary") or {},
        internal_scorecard=seo_package.get("internal_scorecard") or {},
    )

    # Strip junk from any keyword_signals that came back from research.
    locked_signals = [
        s for s in (research_payload.get("keyword_signals") or [])
        if not is_junk_tag(str(s.get("keyword", "")))
    ]

    # ---- Selected-language package -------------------------------------
    def _lock_pkg(p: dict[str, Any], lang: str) -> dict[str, Any]:
        if not isinstance(p, dict):
            return {}
        title = force_topic_in_title(p.get("title", ""), main_topic, category, short_form=short_form)
        variants = list(dict.fromkeys(
            force_topic_in_title(v, main_topic, category, variant_index=i, short_form=short_form)
            for i, v in enumerate(p.get("variants", []) or [])
        ))
        # Every language package gets the risk filter the selected one gets.
        title = _without_risk_terms([title, *variants], risk_source)[0]
        variants = _without_risk_terms(variants, risk_source)
        tags = locked_tags if lang == selected_language else [
            tag for tag in p.get("tags", []) or [] if not unsupported_risk_terms(tag, risk_source)
        ]
        hashtags = filter_source_hashtags(
            force_hashtags(p.get("hashtags", []) or [], main_topic, category, tags=tags, casing=casing),
            script_text,
            creator_brief if isinstance(creator_brief, dict) else None,
        )
        if short_form:
            hashtags = focused_short_hashtags(tags, casing)
        hashtags = [tag for tag in hashtags if not unsupported_risk_terms(tag, risk_source)]
        description = normalize_risk_terms(p.get("description", "") or "", source=risk_source)
        # Only English gets the topic-presence fallback; Tamil / Tanglish
        # descriptions stay in their own language, untouched.
        if lang == "english":
            description = force_topic_in_description(description, main_topic)
        description = format_upload_ready_description(
            description,
            hashtags,
            category=category,
            topic=main_topic,
        )
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

    if selected_language in multilang_packages:
        multilang_packages[selected_language].update(title=locked_title, variants=locked_variants,
            description=locked_description, tags=locked_tags, hashtags=locked_hashtags)

    # Honest warning when a non-English language falls back to the English template.
    research_warnings = list(research_payload.get("research_warnings", []) or [])
    if isinstance(creator_brief, dict):
        research_warnings.extend(creator_brief.get("warnings", []))
    if keyword_signals_unavailable:
        research_warnings.append(
            "Keyword signals are unavailable: YouTube returned no results and no phrases could be "
            "extracted from the script."
        )
    non_english_fallback = [
        lang for lang in (seo_package.get("fallback_languages") or []) if lang != "english"
    ]
    if generation_source == "fallback":
        # The reason matters: "no package passed validation" was reported when
        # Gemini was not configured, cooling down, rate-limited or timed out.
        research_warnings.append(_fallback_warning(trace))
    if non_english_fallback:
        provider_hint = "Gemini" if generation_source == "fallback" else "the configured AI provider"
        research_warnings.append(
            ", ".join(sorted(non_english_fallback)).title()
            + " fell back to an English template because " + provider_hint
            + " returned no native output."
        )
    # --------------------------------------------------------------------

    # The final gate has already judged every title, so the package builder's
    # own checks are skipped and each package carries that gate's verdict.
    final_packages = build_title_thumbnail_packages(
        final_variants_data,
        creator_brief if isinstance(creator_brief, dict) else None,
        competitor_titles=competitor_titles,
        validated=True,
        focus_phrases=[tag for tag in locked_tags if tag not in {"yt", "shorts"}],
    )
    try:
        retention_learning = history_store.retention_learning_summary(
            format_filter=str((creator_brief or {}).get("video_format") or "").strip() or None,
            language_filter=selected_language,
            snapshot_window="24h",
        )
    except Exception as exc:
        logger.warning("Retention learning is unavailable: %s", type(exc).__name__)
        retention_learning = {
            "status": "insufficient_evidence", "learning_allowed": False,
            "sample_size": 0, "minimum_samples": EARLY_SIGNAL_MIN_SAMPLES,
            "message": "Retention evidence could not be evaluated for this run; no historical pattern was applied.",
        }
    retention_assistant = analyze_retention_assistant(
        script_text,
        creator_brief=creator_brief if isinstance(creator_brief, dict) else None,
        content_angle=str(seo_package.get("content_angle") or ""),
        packages=final_packages,
        retention_learning=retention_learning,
    )

    # Follow-up suggestions are rebuilt from what the creator will actually
    # publish: the locked title, the validated final tags and hashtags.
    related_phrases = [tag for tag in locked_tags if tag not in {"yt", "shorts"}]
    content_graph_strategy = build_content_graph_strategy(
        main_topic, related_phrases=related_phrases, short_form=short_form,
    )
    session_expansion = build_session_expansion(related_phrases=related_phrases, short_form=short_form)
    binge_bridge = build_binge_bridge(related_phrases=related_phrases, short_form=short_form)
    automation_workflow = build_automation_workflow(
        title=locked_title, hashtags=locked_hashtags, chapters=seo_package["chapters"],
        content_graph_strategy=content_graph_strategy, short_form=short_form,
    )

    response = AnalyzeResponse(
        title=locked_title,
        description=locked_description,
        tags=locked_tags,
        hashtags=locked_hashtags,
        intent=intent,
        content_angle=seo_package["content_angle"],
        title_variants=locked_variants,
        title_optimization=title_opt,
        title_thumbnail_packages=final_packages,
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
        keyword_research=keyword_research,
        entity_signals=research_payload.get("entity_signals", []),
        upload_timing=research_payload.get("upload_timing", {}),
        thumbnail_intelligence=research_payload.get("thumbnail_intelligence", {}),
        opportunity_gap_analysis=seo_package["opportunity_gap_analysis"],
        competitor_shadow=seo_package["opportunity_gap_analysis"].get("competitor_shadow", {}),
        language_strategy=seo_package["language_strategy"],
        pacing_analysis=seo_package["pacing_analysis"],
        channel_intelligence=seo_package["channel_intelligence"],
        content_graph_strategy=content_graph_strategy,
        thumbnail_strategy=seo_package["thumbnail_strategy"],
        chapters=seo_package["chapters"],
        session_expansion=session_expansion,
        binge_bridge=binge_bridge,
        automation_workflow=automation_workflow,
        performance_sync=feedback_package["performance_sync"],
        learning_engine=feedback_package["learning_engine"],
        winning_patterns=feedback_package["winning_patterns"],
        ctr_prediction=feedback_package["ctr_prediction"],
        ab_test_pack=feedback_package["ab_test_pack"],
        internal_scorecard=feedback_package["internal_scorecard"],
        historical_comparison=feedback_package["historical_comparison"],
        history_run_id=seo_package.get("history_run_id"),
        generation_quality=final_gate,
        personalization=seo_package.get("personalization") or {},
        generation_trace=seo_package.get("generation_trace") or {},
        retention_assistant=retention_assistant,
    ).model_dump()
    history_store = research_payload.get("history_store")
    history_run_id = seo_package.get("history_run_id")
    if isinstance(history_store, HistoryStore) and isinstance(history_run_id, int):
        # The run was recorded with the writer-stage score; refinement may have
        # replaced that title, so the score of the one delivered goes with it.
        history_store.update_analysis_payload(
            history_run_id, response["title"], response,
            title_score=(response.get("ctr_prediction") or {}).get("title_quality_score"),
        )
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
    # Hashtags are matched as "#" followed by any non-space run, not
    # [A-Za-z0-9_]: an ASCII-only pattern missed Tamil hashtags, so a
    # Tamil hashtag line survived here and was appended a second time below.
    prose_lines = [
        line for line in text.splitlines()
        if not re.fullmatch(r"\s*(?:#[^\s#]+\s*)+", line)
        and not re.fullmatch(r"\s*(?:yt|shorts?|youtube(?:\s+shorts?)?)\s*", line, re.IGNORECASE)
    ]
    text = "\n".join(prose_lines).strip()

    emoji_by_category = {
        "gaming": "🎮",
        "cooking": "🍽️",
        "tech": "💻",
        "finance": "📈",
        "fitness": "💪",
        "quotes": "💭",
        "shorts": "🎬",
        "youtube_shorts": "🎬",
    }
    category_key = category.lower()
    if (
        category_key in emoji_by_category
        and not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", text)
    ):
        lowered = f"{topic} {category}".lower()
        if any(term in lowered for term in ("heartbreak", "unrequited", "sad", "betrayal")):
            emoji = "💔"
        else:
            emoji = emoji_by_category[category_key]
        text = f"{emoji} {text}"

    selected: list[str] = []
    existing = {match.casefold().rstrip(".,!?;:") for match in re.findall(r"#[^\s#]+", text)}
    for raw in hashtags or []:
        hashtag = normalize_hashtag(raw)
        if not hashtag:
            continue
        if hashtag.casefold() not in existing:
            selected.append(hashtag)
            existing.add(hashtag.casefold())
    if selected:
        text = f"{text}\n\n{' '.join(selected)}"
    return text
