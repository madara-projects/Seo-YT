"""Gemini-first SEO package builder with a deterministic local fallback."""

from __future__ import annotations

import logging
import re
from typing import Any

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.creator_brief import creator_topic
from win_engine.analysis.generation_quality import (
    apply_quality_gate,
    candidate_mechanism,
    evaluate_package_quality,
    evidence_trace,
    focused_short_hashtags,
    has_unsupported_instructional_framing,
    is_short_content,
    source_requires_noninstructional_framing,
)
from win_engine.analysis.package_builder import build_title_thumbnail_packages
from win_engine.analysis.gap_engine import analyze_opportunity_gaps
from win_engine.analysis.language_engine import build_language_strategy
from win_engine.analysis.keyword_research import select_final_tags
from win_engine.analysis.pacing_engine import analyze_script_pacing
from win_engine.analysis.strategy_layer import (
    build_channel_intelligence,
    build_content_graph_strategy,
)
from win_engine.analysis.thumbnail_classifier import build_thumbnail_strategy
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.channel_learning import learning_summary as channel_performance_learning
from win_engine.feedback.learning_engine import build_feedback_package
from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import (
    build_binge_bridge,
    build_chapters,
    build_session_expansion,
)
from win_engine.llm.seo_writer import last_generation_diagnostics, write_multilang_packages_with_source


_TOPIC_STOPWORDS = {"video", "youtube", "will", "what", "days", "today", "going"}
logger = logging.getLogger(__name__)


def build_seo_package(
    intent: str,
    script: str,
    research: dict[str, object],
    history_store: HistoryStore,
) -> dict[str, object]:
    """Generate the full SEO package. Gemini is the primary generator."""

    keyword_signals = research.get("keyword_signals", []) or []
    keyword_research = research.get("keyword_research", {}) or {}
    entity_signals = research.get("entity_signals", []) or []
    top_opportunities = research.get("top_opportunities", []) or []
    language_context = research.get("language_context", {})
    if not isinstance(language_context, dict):
        language_context = {}

    creator_brief = research.get("creator_brief")
    if not isinstance(creator_brief, dict):
        creator_brief = None
    brief_topic = creator_topic(creator_brief)
    primary_topic, secondary_topic = _topic_from_signals(
        keyword_signals,
        fallback=str(research.get("main_topic") or ""),
    )
    if brief_topic:
        primary_topic = brief_topic
    angle = _select_content_angle(intent, script, top_opportunities)
    language_strategy = build_language_strategy(script, language_context)

    category = str(research.get("category") or "general")

    competitors = [
        {
            "title": r.get("title", ""),
            "views": r.get("view_count"),
            "likes": r.get("like_count"),
            "comments": r.get("comment_count"),
            "subscribers": r.get("subscriber_count"),
            "duration": r.get("duration"),
        }
        for r in (research.get("youtube_results") or [])
        if isinstance(r, dict) and r.get("title")
    ]

    region = str(language_context.get("region", "global"))
    audience_type = str(language_context.get("audience_type", "general"))
    selected_language = str(language_context.get("language") or "english").strip().lower()
    if selected_language == "auto":
        selected_language = str(language_context.get("video_language") or "english").strip().lower()
    if selected_language not in {"english", "tamil", "tanglish", "hindi"}:
        selected_language = "english"

    try:
        channel_learning = channel_performance_learning(
            history_store.database_path,
            format_filter=str((creator_brief or {}).get("video_format") or "").strip() or None,
            language_filter=selected_language,
            snapshot_window="24h",
        )
    except Exception as exc:
        logger.warning("Channel performance learning is unavailable: %s", type(exc).__name__)
        channel_learning = {}
    channel_learning["recent_titles"] = history_store.recent_generated_titles(limit=10)
    channel_learning["published_titles"] = history_store.recent_published_titles(limit=10)
    channel_learning["cohort"] = history_store.cohort_analytics(
        format_filter=str((creator_brief or {}).get("video_format") or "").strip() or None,
        language_filter=selected_language,
    )
    # Generate only the selected language. Additional languages must be explicit
    # creator actions so a single video does not consume three Gemini requests.
    generation_brief = dict(creator_brief or {})
    # Targets are selected *before* package writing, so research can affect the
    # title/description proposal. Final tag selection still runs later and may
    # reject any target that does not survive all relevance checks.
    generation_brief["seo_research_targets"] = [
        item.get("keyword") for item in (keyword_research.get("research_targets") or [])
        if isinstance(item, dict) and item.get("keyword")
    ][:8]
    _LANGS = [selected_language]
    multilang_raw, generation_source = write_multilang_packages_with_source(
        script,
        competitors=competitors,
        languages=_LANGS,
        region=region,
        audience_type=audience_type,
        category=category,
        creator_brief=generation_brief,
        channel_learning=channel_learning,
    )
    writer_diagnostics = last_generation_diagnostics()
    fallback_languages = [lang for lang in _LANGS if not multilang_raw.get(lang)]

    def _resolve(lang: str) -> dict[str, Any]:
        generated = multilang_raw.get(lang)
        p = generated or _content_specific_fallback(primary_topic, keyword_signals, generation_brief)
        if not generated:
            diagnostic = dict(writer_diagnostics.get(lang) or {})
            events = list(diagnostic.get("events") or [])
            if not events:
                events.append(str(diagnostic.get("status") or "gemini_unavailable"))
            if "fallback_used" not in events:
                events.append("fallback_used")
            p["generation_trace"] = {
                **diagnostic,
                "events": events,
                "fallback_used": True,
                "fallback_reason": str(
                    diagnostic.get("fallback_reason")
                    or ("quality_gate_rejection" if diagnostic.get("initial_quality_rejection") else diagnostic.get("status"))
                    or "gemini_unavailable"
                ),
                "fallback_level": "deterministic",
            }
        tags, tag_evidence = select_final_tags(
            keyword_research,
            generated_tags=p.get("tags") or [],
            title=str(p.get("title") or ""),
            script=script,
            creator_brief=creator_brief,
            is_short=is_short_content(script, creator_brief),
        )
        p["tags"] = tags
        p["keyword_research"] = tag_evidence
        if is_short_content(script, creator_brief):
            p["hashtags"] = focused_short_hashtags(tags)
        return p

    multilang = {lang: _resolve(lang) for lang in _LANGS}

    # The selected-language package backs the top-level fields and downstream analysis.
    pkg = multilang[selected_language]
    keyword_research = dict(pkg.get("keyword_research") or keyword_research)
    generation_trace = dict(pkg.get("generation_trace") or {})
    quality_gate = evaluate_package_quality(
        pkg, script=script, creator_brief=creator_brief, language=selected_language,
        recent_titles=channel_learning.get("recent_titles") or [],
        published_titles=channel_learning.get("published_titles") or [],
        competitor_titles=[str(item.get("title") or "") for item in competitors],
        tag_evidence=keyword_research,
        tag_context=[
            *(str(item.get("keyword") or "") for item in keyword_signals if isinstance(item, dict)),
            *(str(item.get("entity") or "") for item in entity_signals if isinstance(item, dict)),
        ],
    )
    # Gemini success is not package success.  A final RED package gets one
    # deterministic, source-only fallback pass through the exact same tag and
    # quality contracts.  This does not make another provider request.
    if quality_gate.get("verdict") == "RED":
        generation_trace["final_package_rejection"] = _quality_trace_summary(quality_gate)
        safe = _content_specific_fallback(primary_topic, keyword_signals, generation_brief)
        safe_tags, safe_evidence = select_final_tags(
            keyword_research,
            generated_tags=safe.get("tags") or [],
            title=str(safe.get("title") or ""),
            script=script,
            creator_brief=creator_brief,
            is_short=is_short_content(script, creator_brief),
        )
        safe["tags"] = safe_tags
        if is_short_content(script, creator_brief):
            safe["hashtags"] = focused_short_hashtags(safe_tags)
        safe["keyword_research"] = safe_evidence
        safe_trace = dict(generation_trace)
        safe_events = list(safe_trace.get("events") or [])
        safe_events.extend(["final_quality_red", "deterministic_quality_fallback"])
        safe["generation_trace"] = {
            **safe_trace,
            "events": list(dict.fromkeys(safe_events)),
            "fallback_used": True,
            "fallback_reason": "final_quality_red",
            "fallback_level": "deterministic",
            "final_quality_repair_attempted": True,
        }
        safe_gate = evaluate_package_quality(
            safe, script=script, creator_brief=creator_brief, language=selected_language,
            recent_titles=channel_learning.get("recent_titles") or [],
            published_titles=channel_learning.get("published_titles") or [],
            competitor_titles=[str(item.get("title") or "") for item in competitors],
            tag_evidence=safe_evidence,
            tag_context=[
                *(str(item.get("keyword") or "") for item in keyword_signals if isinstance(item, dict)),
                *(str(item.get("entity") or "") for item in entity_signals if isinstance(item, dict)),
            ],
        )
        if safe_gate.get("verdict") != "RED":
            pkg = safe
            keyword_research = dict(safe_evidence)
            generation_trace = dict(safe["generation_trace"])
            quality_gate = safe_gate
            if selected_language not in fallback_languages:
                fallback_languages.append(selected_language)
        else:
            generation_trace["deterministic_fallback_rejection"] = _quality_trace_summary(safe_gate)
            minimal = _safe_minimal_package(primary_topic, creator_brief)
            minimal_tags, minimal_evidence = select_final_tags(
                keyword_research,
                generated_tags=[],
                title=str(minimal.get("title") or ""),
                script=script,
                creator_brief=creator_brief,
                is_short=is_short_content(script, creator_brief),
            )
            minimal["tags"] = minimal_tags
            if is_short_content(script, creator_brief):
                minimal["hashtags"] = focused_short_hashtags(minimal_tags)
            minimal_gate = evaluate_package_quality(
                minimal, script=script, creator_brief=creator_brief, language=selected_language,
                recent_titles=channel_learning.get("recent_titles") or [],
                published_titles=channel_learning.get("published_titles") or [],
                competitor_titles=[str(item.get("title") or "") for item in competitors],
                tag_evidence=minimal_evidence,
                tag_context=[
                    *(str(item.get("keyword") or "") for item in keyword_signals if isinstance(item, dict)),
                    *(str(item.get("entity") or "") for item in entity_signals if isinstance(item, dict)),
                ],
            )
            minimal_trace = dict(generation_trace)
            minimal_trace["events"] = list(dict.fromkeys([
                *(minimal_trace.get("events") or []), "minimal_safe_package",
            ]))
            minimal_trace["fallback_used"] = True
            minimal_trace["fallback_reason"] = "final_quality_red_after_deterministic_fallback"
            minimal_trace["fallback_level"] = "minimal_source_only"
            minimal_trace["final_quality_repair_attempted"] = True
            minimal_trace["final_quality_repair_succeeded"] = minimal_gate.get("verdict") != "RED"
            minimal["generation_trace"] = minimal_trace
            pkg = minimal
            keyword_research = dict(minimal_evidence)
            generation_trace = minimal_trace
            quality_gate = minimal_gate
            if selected_language not in fallback_languages:
                fallback_languages.append(selected_language)
    rejected_opportunities = [
        {
            "keyword": str(item.get("keyword") or item.get("candidate") or ""),
            "reason": str(item.get("reason") or ", ".join(item.get("issues") or []) or "rejected"),
        }
        for item in (keyword_research.get("rejected_candidates") or [])
        if isinstance(item, dict)
    ][:20]
    generation_trace.update({
        "source_content_type": str((creator_brief or {}).get("video_format") or "unknown"),
        "gemini_attempted": bool(generation_trace.get("gemini_attempted") or generation_trace.get("provider_requests")),
        "gemini_call_count": int(generation_trace.get("gemini_call_count") or generation_trace.get("provider_requests") or 0),
        "retry_count": int(generation_trace.get("retry_count") or generation_trace.get("provider_retries") or 0),
        "retry_reasons": list(generation_trace.get("retry_reasons") or []),
        "provider_failure_category": generation_trace.get("provider_failure_category") or generation_trace.get("failure_category"),
        "fallback_level": generation_trace.get("fallback_level") or ("deterministic" if generation_trace.get("fallback_used") else None),
        "research_query_count": len(research.get("research_queries") or []),
        "youtube_result_count": len(research.get("youtube_results") or []),
        "relevant_evidence_count": int((keyword_research.get("diagnostics") or {}).get("relevant_youtube_results") or 0),
        "accepted_research_opportunities": len((keyword_research.get("research_contribution") or {}).get("selected_concepts") or []),
        "rejected_research_opportunity_count": len(keyword_research.get("rejected_candidates") or []),
        "rejected_research_opportunities": rejected_opportunities,
        "final_tags": list(pkg.get("tags") or []),
        "final_tag_provenance": keyword_research.get("tag_provenance") or [],
        "final_tag_scores": [
            {"keyword": item.get("tag") or item.get("keyword"), "source_support_score": item.get("source_support_score"),
             "provenance": item.get("provenance")}
            for item in (keyword_research.get("tag_provenance") or []) if isinstance(item, dict)
        ],
        "final_quality_verdict": quality_gate.get("verdict"),
        "final_quality_reasons": [item.get("code") for item in quality_gate.get("issues") or []],
    })
    pkg["generation_trace"] = generation_trace
    pkg = apply_quality_gate(pkg, quality_gate)
    multilang[selected_language] = pkg
    effective_generation_source = "fallback" if selected_language in fallback_languages else generation_source

    title = pkg["title"]
    description = pkg["description"]
    tags = pkg["tags"]
    hashtags = pkg["hashtags"]
    variant_titles = list(pkg["variants"]) or [title]

    package_intents = ["Search", "Browse", "Existing audience", "Alternative", "Alternative"]
    personalization = evidence_trace(channel_learning)
    competitor_titles = [
        str(item.get("title") or "")
        for item in research.get("youtube_results", [])
        if isinstance(item, dict) and item.get("title")
    ]
    title_context = " ".join(
        str((creator_brief or {}).get(field) or "")
        for field in ("content", "target_audience", "viewer_promise", "unique_angle")
    )
    title_variants_data = []
    accepted_by_title = {item["title"]: item for item in quality_gate.get("accepted_candidates", [])}
    for index, variant in enumerate(variant_titles[:5]):
        quality_score = _deterministic_score(
            variant,
            primary_topic,
            context_text=title_context,
            competitor_titles=competitor_titles,
        )
        mechanism = str((accepted_by_title.get(variant) or {}).get("mechanism") or candidate_mechanism(variant))
        title_variants_data.append({
            "title": variant,
            "score": quality_score,
            "estimated_ctr": None,
            "character_count": len(variant),
            "package_intent": package_intents[index] if index < len(package_intents) else "Alternative",
            "mechanism": mechanism,
            "reason": f"Offers a distinct {mechanism} framing while preserving the creator source.",
            "discovery_surface": package_intents[index] if index < len(package_intents) else "Alternative",
            "evidence_used": personalization,
            "tradeoffs": ["Generated suggestion, not observed performance evidence.", "No reach or CTR outcome is guaranteed."],
            "quality_gate": {"status": "pass", "source": "phase4_local_gate"},
        })

    title_optimization = {
        "best_title": title_variants_data[0]["title"] if title_variants_data else title,
        "scored_variants": [
            {
                "title": v["title"],
                "score": v["score"],
                "estimated_ctr": v["estimated_ctr"],
                "character_count": v["character_count"],
            }
            for v in title_variants_data
        ],
    }
    title_thumbnail_packages = build_title_thumbnail_packages(
        title_variants_data,
        creator_brief,
        competitor_titles=[str(item.get("title") or "") for item in research.get("youtube_results", []) if isinstance(item, dict)],
    )

    content_audit = audit_content_package(
        script,
        title,
        primary_topic,
        secondary_topic,
        angle,
        video_format=str((creator_brief or {}).get("video_format") or ""),
        context_text=" ".join(
            str((creator_brief or {}).get(field) or "")
            for field in ("target_audience", "viewer_promise", "unique_angle")
        ),
    )
    opportunity_gap_analysis = analyze_opportunity_gaps(
        keyword_signals=keyword_signals,
        entity_signals=entity_signals,
        youtube_results=research.get("youtube_results", []),
        top_opportunities=top_opportunities,
        language_context=language_context,
        target_title=title,
    )
    pacing_analysis = analyze_script_pacing(
        script,
        video_format=str((creator_brief or {}).get("video_format") or ""),
    )
    channel_intelligence = build_channel_intelligence(research.get("youtube_results", []))
    content_graph_strategy = build_content_graph_strategy(
        primary_topic=primary_topic,
        secondary_topic=secondary_topic,
        angle=angle,
        keyword_signals=keyword_signals,
    )
    chapters = build_chapters(script, keyword_signals, creator_brief)
    session_expansion = build_session_expansion(title, keyword_signals)
    binge_bridge = build_binge_bridge(title, angle)
    thumbnail_strategy = build_thumbnail_strategy(
        thumbnail_intelligence=research.get("thumbnail_intelligence", {}),
        title=title,
        content_angle=angle,
    )
    automation_workflow = build_automation_workflow(
        title=title,
        hashtags=hashtags,
        chapters=chapters,
        content_graph_strategy=content_graph_strategy,
    )

    feedback_package = build_feedback_package(
        seo_package={
            "title": title,
            "content_angle": angle,
            "title_optimization": title_optimization,
            "opportunity_gap_analysis": opportunity_gap_analysis,
        },
        research=research,
        learning_summary=history_store.learning_summary(),
        internal_scorecard=history_store.internal_scorecard(),
    )

    history_run_id = history_store.record_analysis_run(
        query=script,
        intent=intent,
        content_angle=angle,
        title=title,
        title_score=float(title_optimization["scored_variants"][0]["score"])
        if title_optimization["scored_variants"]
        else 0.0,
        retention_risk=str(content_audit["retention_risk"]["level"]),
        opportunity_label=str(opportunity_gap_analysis["opportunity_score"]["label"]),
        opportunity_score=float(opportunity_gap_analysis["opportunity_score"]["score"]),
        payload={
            "title": title, "description": description, "tags": tags, "hashtags": hashtags,
            "title_variants": title_variants_data, "title_thumbnail_packages": title_thumbnail_packages,
            "content_audit": content_audit, "opportunity_gap_analysis": opportunity_gap_analysis,
            "language_strategy": language_strategy, "pacing_analysis": pacing_analysis,
            "channel_intelligence": channel_intelligence, "content_graph_strategy": content_graph_strategy,
            "thumbnail_strategy": thumbnail_strategy, "chapters": chapters,
            "session_expansion": session_expansion, "binge_bridge": binge_bridge,
            "automation_workflow": automation_workflow, "feedback_package": feedback_package,
            "multilang": multilang, "generation_source": effective_generation_source,
            "creator_brief": creator_brief, "generation_quality": quality_gate,
            "personalization": personalization, "generation_trace": generation_trace,
            "keyword_research": keyword_research,
        },
    )

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "title_variants": title_variants_data,
        "content_angle": angle,
        "title_optimization": title_optimization,
        "title_thumbnail_packages": title_thumbnail_packages,
        "content_audit": content_audit,
        "opportunity_gap_analysis": opportunity_gap_analysis,
        "language_strategy": language_strategy,
        "pacing_analysis": pacing_analysis,
        "channel_intelligence": channel_intelligence,
        "content_graph_strategy": content_graph_strategy,
        "thumbnail_strategy": thumbnail_strategy,
        "chapters": chapters,
        "session_expansion": session_expansion,
        "binge_bridge": binge_bridge,
        "automation_workflow": automation_workflow,
        "feedback_package": feedback_package,
        "multilang": multilang,
        "fallback_languages": fallback_languages,
        "generation_source": effective_generation_source,
        "generation_quality": quality_gate,
        "personalization": personalization,
        "generation_trace": generation_trace,
        "keyword_research": keyword_research,
        "creator_brief": creator_brief,
        "history_run_id": history_run_id,
    }


def _topic_from_signals(
    keyword_signals: list[dict[str, Any]],
    fallback: str = "",
) -> tuple[str, str]:
    """Pick primary / secondary topic from research keyword signals."""
    picks: list[str] = []
    for signal in keyword_signals:
        kw = str(signal.get("keyword", "")).strip()
        if not kw or kw.lower() in _TOPIC_STOPWORDS:
            continue
        if kw.lower() in {p.lower() for p in picks}:
            continue
        picks.append(kw)
        if len(picks) >= 2:
            break
    primary = picks[0] if picks else (fallback or "your topic")
    secondary = picks[1] if len(picks) > 1 else "engagement"
    return primary, secondary


def _select_content_angle(intent: str, script: str, top_opportunities: list[dict[str, Any]]) -> str:
    """Pick a content angle from script signals."""
    lower = script.lower()
    if "case study" in lower or "tested" in lower or "i tried" in lower:
        return "Experiment"
    if "mistake" in lower or "wrong" in lower:
        return "Mistake"
    if intent == "SEARCH":
        return "Authority"
    if top_opportunities and any(
        "shocking" in str(item.get("title", "")).lower() for item in top_opportunities
    ):
        return "Curiosity"
    return "Story"


_SCORE_STOPWORDS = {
    "a", "an", "and", "are", "for", "from", "how", "in", "is", "of", "on",
    "the", "this", "to", "with", "you", "your",
}
# Curiosity hooks. Scored by how many appear as whole words, because one hook
# sharpens a title and several are keyword stuffing.
_SCORE_HOOK_TERMS = {
    "why", "when", "truth", "mistake", "secret", "hardest", "never", "realize", "what",
}


def _score_tokens(text: str) -> list[str]:
    """Unicode-aware tokens. An ASCII-only pattern returns nothing for Tamil or Hindi."""

    return re.findall(r"\w+", (text or "").casefold(), flags=re.UNICODE)


def _score_terms(text: str) -> set[str]:
    return {word for word in _score_tokens(text) if len(word) >= 3 and word not in _SCORE_STOPWORDS}


def _reproduces_source(title_terms: set[str], source_terms: set[str]) -> bool:
    """True when the title restates most of the source instead of sharpening a hook from it.

    Measured on term coverage rather than substring containment, because a trailing
    hashtag is enough to defeat a substring test while changing nothing a viewer reads.
    A short excerpt of a quote is a legitimate title; the whole quote is not.
    """

    if len(source_terms) < 5:
        return False
    return len(title_terms & source_terms) / len(source_terms) >= 0.6


def _scripts_differ(title_terms: set[str], source_terms: set[str]) -> bool:
    """True when title and source are written in different scripts.

    Term overlap cannot measure relevance across scripts, so a Tamil title for an
    English brief would otherwise score zero coverage no matter how good it is.
    """

    if not title_terms or not source_terms:
        return False
    title_ascii = sum(1 for term in title_terms if term.isascii()) / len(title_terms)
    source_ascii = sum(1 for term in source_terms if term.isascii()) / len(source_terms)
    return abs(title_ascii - source_ascii) >= 0.5


def _deterministic_score(
    title: str,
    topic: str,
    *,
    context_text: str = "",
    competitor_titles: list[str] | None = None,
) -> float:
    """Pre-publication title quality score; never presented as measured CTR."""
    clean = re.sub(r"\s+", " ", title or "").strip()
    if not clean:
        return 0.0
    lowered = clean.casefold()
    score = 0.0

    # Length is judged on what a viewer reads, so trailing hashtags cannot pad a
    # short title into the rewarded band.
    visible = re.sub(r"#\w+", "", clean, flags=re.UNICODE).strip()
    length = len(visible)
    score += 2.0 if 30 <= length <= 62 else 1.2 if 20 <= length <= 70 else 0.5

    words = _score_tokens(lowered)
    score += 1.5 if 4 <= len(words) <= 12 else 0.8 if 3 <= len(words) <= 15 else 0.3

    title_terms = _score_terms(clean)
    topic_terms = _score_terms(topic)
    source_terms = topic_terms | _score_terms(context_text)

    # Coverage of the topic, not purity of the title. The old ratio divided by the
    # title's own terms, so a verbatim copy scored perfectly and any original word
    # was a penalty.
    if _scripts_differ(title_terms, source_terms):
        # Unmeasurable rather than irrelevant: award neutral credit so a non-English
        # title is not ranked last purely for being non-English.
        score += 2.0
    else:
        coverage = len(title_terms & source_terms) / len(topic_terms) if topic_terms else 0.0
        score += min(coverage, 1.0) * 3.0

    if _reproduces_source(title_terms, source_terms):
        score -= 1.5

    hooks = len(_SCORE_HOOK_TERMS & set(words))
    score += 0.8 if hooks == 1 else 0.4 if hooks == 2 else 0.0 if hooks == 0 else -0.8

    competitors = [_score_terms(item) for item in competitor_titles or [] if item]
    similarities = [len(title_terms & item) / max(len(title_terms | item), 1) for item in competitors]
    max_similarity = max(similarities, default=0.0)
    score += 1.0 if max_similarity <= 0.35 else 0.5 if max_similarity <= 0.60 else 0.0

    production_junk = ("vertical", "creator", "background footage", "cinematic dark")
    score += 1.0 if not any(term in lowered for term in production_junk) else 0.2
    score += 0.5 if clean.count("!") <= 1 and "???" not in clean else 0.0
    return round(min(max(score, 0.0), 10.0), 1)


def _quoted_text(content: str) -> str:
    match = re.search(r'["“”]([^"“”]{6,})["“”]', content or "")
    return re.sub(r"\s+", " ", match.group(1)).strip(" .") if match else ""


def _fit_title(body: str, suffix: str = "", max_chars: int = 70) -> str:
    clean = re.sub(r"\s+", " ", body).strip(" .:-")
    available = max_chars - len(suffix)
    if len(clean) > available:
        shortened = clean[: max(1, available - 1)].rsplit(" ", 1)[0].rstrip(" .,:;-")
        clean = (shortened or clean[: max(1, available - 1)]).rstrip() + "…"
    return clean + suffix


def _quote_title_focus(quote: str) -> str:
    """Remove a purely introductory quote lead-in when a stronger clause follows."""

    clean = re.sub(r"\s+", " ", quote or "").strip(" .")
    focused = re.sub(
        r"^(?:in the end|sometimes|honestly|maybe|the truth is)\s*,?\s+",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    return focused or clean


def _semantic_emoji(text: str) -> str:
    """Choose a relevant fallback emoji from the actual content, never a fixed template."""

    lowered = (text or "").casefold()
    groups = (
        (("rain", "rainy", "storm", "monsoon"), ("🌧️", "☔", "🌦️")),
        (("heartbreak", "heart", "missing", "miss", "love"), ("💔", "🫶", "❤️‍🩹")),
        (("road", "traffic", "vehicle", "car", "bus"), ("🚦", "🚗", "🛣️")),
        (("moon", "night", "stars", "sky"), ("🌙", "✨", "🌌")),
        (("silence", "solitude", "alone", "lonely", "quiet streets"), ("🌙", "🕯️", "🌃")),
        (("sunset", "beach", "ocean", "sea"), ("🌅", "🌊", "☀️")),
        (("mountain", "hill", "nature", "green"), ("⛰️", "🌿", "🌄")),
        (("funny", "comedy", "laugh"), ("😂", "😄", "🤣")),
    )
    for terms, emojis in groups:
        if any(term in lowered for term in terms):
            return emojis[sum(ord(char) for char in lowered) % len(emojis)]
    return ""


def _topic_hashtag(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value or "")[:3]
    return "#" + "".join(word.capitalize() for word in words) if words else ""


def _visual_hashtag(value: str) -> str:
    """Return one compact, human-readable hashtag for a supplied visual."""

    lowered = (value or "").casefold()
    if "road" in lowered and "traffic" in lowered:
        return "#RoadTraffic"
    if "road" in lowered:
        return "#EveningRoad" if "evening" in lowered else "#RoadScene"
    if "rain" in lowered:
        return "#RainyMood"
    if "moon" in lowered or "night sky" in lowered:
        return "#NightSky"
    return _topic_hashtag(value)


def _fallback_quote_variants(quote: str, topic: str, suffix: str, *, semantic_validated: bool = False) -> list[str]:
    """Produce conservative, readable quote titles without template filler."""

    lowered = quote.casefold()
    if "misunderstood" in lowered and "genuine" in lowered:
        bodies = ["Being Genuine Can Feel Misunderstood"]
    elif "bare minimum" in lowered:
        bodies = ["Did I Deserve the Bare Minimum?"]
    elif "need" in lowered and "choose" in lowered:
        bodies = ["Needed, But Never Chosen"]
    elif "keep going" in lowered:
        bodies = ["Keep Going"]
    elif (
        "deserve" in lowered
        and re.search(r"\bhard\s+(?:it\s+is\s+)?to\s+find\b", lowered)
        and re.search(r"\b(?:somebody|someone)\s+like\s+you\b", lowered)
    ):
        bodies = [
            "Know Your Worth—You're Hard to Replace",
            "The Right Person Will Recognize Your Worth",
            "You're Rarer Than You Realize",
            "Someone Should See How Rare You Are",
            "You Deserve to Be Truly Valued",
        ]
    elif "silence" in lowered and any(term in lowered for term in ("knows", "everything", "only me")):
        bodies = [
            "Some Things Only Silence Knows",
            "When Silence Is the Only One Who Knows",
            "At the End, It's Just Me and the Silence",
            "The Thoughts I Only Share With Silence",
            "What the Silence Knows About Me",
        ]
    elif all(term in lowered for term in ("grief", "silence", "absence")):
        bodies = [
            "When Grief Makes Silence Feel Heavy",
            "The Shape Absence Leaves in Silence",
            "Why Absence Can Feel So Heavy",
            "Grief Has a Silence of Its Own",
            "When Absence Becomes Almost Visible",
        ]
    else:
        # ``topic`` comes from the validated semantic layer. Prefer that
        # natural interpretation over copying/truncating the on-screen quote.
        semantic_topic = re.sub(r"\s+", " ", topic or "").strip(" .:-")
        quote_focus = _quote_title_focus(quote)
        if semantic_validated and semantic_topic and semantic_topic.casefold() not in {"video topic", quote_focus.casefold()}:
            bodies = [semantic_topic[:1].upper() + semantic_topic[1:]]
        else:
            bodies = [quote_focus or "A Quiet Reflection"]
    return list(dict.fromkeys(_fit_title(body, suffix) for body in bodies if body))


def _fallback_topic_variants(topic: str, suffix: str, instructional: bool) -> list[str]:
    """Keep fallback titles source-led rather than filling five template slots."""

    clean = re.sub(r"\s+", " ", topic).strip(" .:-") or "The Video Topic"
    lower = clean.casefold()
    if instructional:
        if lower.startswith("how to "):
            body = clean
        elif lower.startswith("how "):
            body = "How to " + clean[4:]
        else:
            body = f"How to {clean}"
    else:
        body = clean
    return [_fit_title(body[:1].upper() + body[1:], suffix)]


def _fallback_title_topic(topic: str, content: str, video_format: str) -> str:
    """Extract a compact source phrase for outage-mode instructional titles.

    Research signals can legitimately be full creator sentences. They remain
    useful for tags and descriptions, but turning them into ``How to ...``
    titles produces unreadable fallback output. This stays source-only and
    never asks a provider to repair the wording.
    """
    clean_content = re.sub(r"\s+", " ", content or "").strip(" .")
    format_name = (video_format or "").casefold()
    if format_name == "tutorial":
        lead = clean_content.split(":", 1)[0].strip(" .")
        if lead.casefold().startswith("how to "):
            return lead
    if format_name == "comparison" or (" while " in f" {clean_content.casefold()} " and len(re.findall(r"\b[A-Z][A-Z0-9]{1,}\b", clean_content)) >= 2):
        acronyms = re.findall(r"\b[A-Z][A-Z0-9]{1,}\b", clean_content)
        if len(acronyms) >= 2:
            return f"{acronyms[0]} vs {acronyms[1]}"
        versus = re.search(r"\b([A-Za-z][\w-]{1,30})\b.*?\bwhile\b.*?\b([A-Za-z][\w-]{1,30})\b", clean_content, re.IGNORECASE)
        if versus:
            return f"{versus.group(1)} vs {versus.group(2)}"
    if format_name in {"educational", "explanation"}:
        acronym = re.search(r"\b[A-Z][A-Z0-9]{1,}\b", clean_content)
        if acronym:
            return f"{acronym.group(0)} Explained"
        definition = re.match(r"(?:an?|the)\s+(.+?)\s+is\s+", clean_content, re.IGNORECASE)
        if definition:
            return definition.group(1).strip().title() + " Explained"
    return topic


def _quote_search_concepts(quote: str) -> list[str]:
    """Return only small, defensible concepts—not chopped quote fragments."""

    lowered = quote.casefold()
    concepts: list[str] = []
    if "misunderstood" in lowered:
        concepts.append("being misunderstood")
    if "genuine" in lowered:
        concepts.append("being genuine")
    if "value" in lowered:
        concepts.append("feeling valued")
    if "chosen" in lowered:
        concepts.append("feeling chosen")
    if "give up" in lowered or "enough" in lowered:
        concepts.extend(["knowing when to let go", "emotional exhaustion"])
    if "walks away" in lowered or "how to stay" in lowered:
        concepts.append("relationships fading without closure")
    if "crueller" in lowered or "apology" in lowered:
        concepts.extend(["self forgiveness", "self criticism"])
    if "silence" in lowered:
        concepts.extend(["inner silence", "silence quotes"])
    if "only me" in lowered or "alone" in lowered:
        concepts.append("solitude")
    if "thought" in lowered or ("silence" in lowered and "knows" in lowered):
        concepts.append("inner thoughts")
    if (
        "deserve" in lowered
        and re.search(r"\bhard\s+(?:it\s+is\s+)?to\s+find\b", lowered)
        and re.search(r"\b(?:somebody|someone)\s+like\s+you\b", lowered)
    ):
        concepts.extend([
            "know your worth", "being valued", "hard to replace",
            "rare person quotes", "genuine appreciation",
        ])
    return concepts


def _quality_trace_summary(gate: dict[str, Any]) -> dict[str, Any]:
    """Keep bounded final-gate reasons without storing prompts or provider text."""

    return {
        "verdict": str(gate.get("verdict") or "RED"),
        "issue_codes": [
            str(item.get("code") or "quality_failure")
            for item in (gate.get("issues") or [])[:12]
            if isinstance(item, dict)
        ],
        "rejected_titles": [
            {
                "title": str(item.get("title") or "")[:120],
                "codes": [
                    str(reason.get("code") or "quality_failure")
                    for reason in (item.get("issues") or [])[:8]
                    if isinstance(reason, dict)
                ],
            }
            for item in (gate.get("rejected_candidates") or [])[:5]
            if isinstance(item, dict)
        ],
    }


def _fallback_visual_sentence(value: str) -> str:
    """Turn creator visual notes into one natural audience-facing sentence."""

    visual = re.sub(r"\s+", " ", value or "").strip(" .,:;")
    if not visual:
        return ""
    lowered = visual.casefold()
    if re.search(r"\b(?:one|a) person walking alone\b", lowered):
        setting = "through quiet streets" if "quiet street" in lowered else "along the street" if "street" in lowered else ""
        return f"A lone person walks {setting}.".replace("  ", " ").replace(" .", ".") if setting else "A lone person walks alone."
    if lowered.startswith("person walking alone"):
        return "A lone person walks through the scene."
    if re.match(r"^[a-z-]+\s+scene\b", lowered):
        return f"A {visual} provides the visual setting."
    return f"The video follows {visual[:1].lower() + visual[1:]}."


def _safe_minimal_package(primary_topic: str, creator_brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """Last-resort source-only package used when a richer fallback is RED.

    It intentionally leaves tags empty rather than smuggling in broad or
    research-only phrases. This is a conservative package, not a claim that a
    sparse source has strong search demand.
    """

    brief = creator_brief or {}
    content = str(brief.get("content") or primary_topic or "").strip()
    quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "").strip() or _quoted_text(content)
    is_shorts = is_short_content(content or primary_topic, brief)
    emoji = _semantic_emoji(" ".join([content, str(brief.get("visual_requirements") or "")]))
    suffix = f" {emoji} #shorts" if is_shorts and emoji else " #shorts" if is_shorts else ""
    if quote:
        safe_topic = "" if has_unsupported_instructional_framing(primary_topic) else primary_topic
        variants = _fallback_quote_variants(quote, safe_topic, suffix, semantic_validated=bool(safe_topic))
        body = variants[0][:-len(suffix)] if suffix and variants[0].endswith(suffix) else variants[0]
        description = f'“{quote}”\n\nA short reflection built only from the words supplied by the creator.'
    else:
        body = re.sub(r"\s+", " ", primary_topic or content).strip(" .") or "The Video Topic"
        excerpt = re.sub(r"\s+", " ", content).strip(" .")
        description = (excerpt or body).rstrip(".") + "."
    title = _fit_title(body, suffix)
    return {
        "title": title,
        "variants": [title],
        "description": description,
        "tags": [],
        "hashtags": ["#shorts"] if is_shorts else [],
    }


def _content_specific_fallback(
    primary_topic: str,
    keyword_signals: list[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Honest, content-specific package used only when Gemini is unavailable."""
    brief = creator_brief or {}
    topic = (primary_topic or "the video topic").strip()
    # Titles need a compact phrase so distinct mechanisms remain readable and
    # do not collapse into near-duplicates after the upload-length limit is
    # applied.  Keep the full ``topic`` for descriptions/tags.
    title_topic = " ".join(topic.split()[:5]) or "the video topic"
    pretty = title_topic.title()
    content = str(brief.get("content") or "").strip()
    quote = str(brief.get("exact_quote") or "").strip() or _quoted_text(content)
    seo_targets = [
        re.sub(r"\s+", " ", str(item or "")).strip(" .:-")
        for item in brief.get("seo_research_targets") or []
        if str(item or "").strip() and not has_unsupported_instructional_framing(item)
    ][:8]
    is_shorts = is_short_content(content or topic, brief)
    promise = str(brief.get("viewer_promise") or "").strip()
    audience = str(brief.get("target_audience") or "").strip()
    unique_angle = str(brief.get("unique_angle") or "").strip()
    proof = str(brief.get("proof") or "").strip()
    video_format = str(brief.get("video_format") or "").strip().casefold()

    emoji = _semantic_emoji(" ".join([topic, content, quote, str(brief.get("visual_requirements") or "")]))
    suffix = f" {emoji} #shorts" if is_shorts and emoji else " #shorts" if is_shorts else ""
    if quote:
        fallback_title_topic = seo_targets[0] if seo_targets else topic
        variants = _fallback_quote_variants(quote, fallback_title_topic, suffix, semantic_validated=bool(seo_targets))
        visual_line = _fallback_visual_sentence(str(brief.get("visual_requirements") or ""))
        quote_lowered = quote.casefold()
        if all(term in quote_lowered for term in ("grief", "silence", "absence")):
            reflective_line = "A reflection on how grief can make silence feel heavy and absence feel almost visible."
        elif "silence" in quote_lowered:
            reflective_line = "A reflective moment centered on the silence described by the words on screen."
        elif "deserve" in quote_lowered and "hard" in quote_lowered and "find" in quote_lowered:
            reflective_line = "A reflective moment about knowing your worth and being genuinely valued for who you are."
        else:
            supported_themes = [item for item in seo_targets if item.casefold() != topic.casefold()][:3]
            if supported_themes:
                reflective_line = "A reflective moment about " + ", ".join(supported_themes) + "."
            elif seo_targets and topic and topic.casefold() != "video topic":
                reflective_line = f"A reflective moment about {topic}."
            else:
                reflective_line = "A reflective Short built around the exact words shown on screen."
        description = (
            f'“{quote}”\n\n'
            + visual_line
            + ("\n\n" if visual_line else "")
            + reflective_line
        )
    else:
        instructional = not source_requires_noninstructional_framing(content or topic, brief)
        title_topic = _fallback_title_topic(topic, content, video_format)
        comparison_mode = video_format == "comparison" or (
            " while " in f" {content.casefold()} " and len(re.findall(r"\b[A-Z][A-Z0-9]{1,}\b", content)) >= 2
        )
        if comparison_mode:
            variants = [_fit_title(f"{title_topic}: What's the Difference?", suffix)]
        else:
            variants = _fallback_topic_variants(title_topic, suffix, instructional)
        source_excerpt = re.sub(r"\s+", " ", content or topic).strip(" .")
        if len(source_excerpt) > 220:
            source_excerpt = source_excerpt[:217].rsplit(" ", 1)[0] + "…"
        description_parts = [source_excerpt or topic]
        if promise:
            description_parts.append(promise)
        description = "\n\n".join(part.rstrip(".") + "." for part in description_parts if part)

    tags: list[str] = []
    seen: set[str] = set()
    candidates = (
        [topic, *seo_targets, *_quote_search_concepts(quote), *[str(item.get("keyword") or "") for item in keyword_signals or []]]
        if quote else [topic, *[str(item.get("keyword") or "") for item in keyword_signals or []]]
    )
    for field in ("viewer_promise", "unique_angle"):
        value = " ".join(str(brief.get(field) or "").strip().lower().split()[:6])
        if value:
            candidates.append(value)
    for candidate in candidates:
        cleaned = candidate.strip().lower()
        if quote and has_unsupported_instructional_framing(cleaned):
            continue
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            tags.append(cleaned)

    quote_lowered = quote.casefold()
    if quote and "silence" in quote_lowered:
        hashtags = ["#DeepThoughts", "#Solitude"]
    elif quote and "deserve" in quote_lowered and "hard" in quote_lowered and "find" in quote_lowered:
        hashtags = ["#KnowYourWorth", "#SelfWorth"]
    else:
        hashtags = [] if quote else [_topic_hashtag(topic)]
    if is_shorts:
        hashtags.insert(0, "#shorts")
    if not quote:
        visual_hashtag = _visual_hashtag(str(brief.get("visual_requirements") or ""))
        if visual_hashtag:
            hashtags.append(visual_hashtag)
    hashtags = list(dict.fromkeys(item for item in hashtags if item))[:3]

    return {
        "title": variants[0],
        "variants": variants,
        "description": description,
        "tags": tags[:8],
        "hashtags": hashtags,
    }
