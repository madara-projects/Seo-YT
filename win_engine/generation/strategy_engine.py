"""SEO package builder.

Ollama-first. Calls win_engine.llm.seo_writer with full context (language,
region, audience, competitor view counts) and falls back to a minimal
deterministic template only when Ollama is unreachable.
"""

from __future__ import annotations

from typing import Any

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.gap_engine import analyze_opportunity_gaps
from win_engine.analysis.language_engine import build_language_strategy
from win_engine.analysis.pacing_engine import analyze_script_pacing
from win_engine.analysis.strategy_layer import (
    build_channel_intelligence,
    build_content_graph_strategy,
)
from win_engine.analysis.thumbnail_classifier import build_thumbnail_strategy
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.learning_engine import build_feedback_package
from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import (
    build_binge_bridge,
    build_chapters,
    build_session_expansion,
)
from win_engine.llm.seo_writer import write_multilang_packages


_TOPIC_STOPWORDS = {"video", "youtube", "will", "what", "days", "today", "going"}


def build_seo_package(
    intent: str,
    script: str,
    research: dict[str, object],
    history_store: HistoryStore,
) -> dict[str, object]:
    """Generate the full SEO package. Ollama is the primary generator."""

    keyword_signals = research.get("keyword_signals", []) or []
    entity_signals = research.get("entity_signals", []) or []
    top_opportunities = research.get("top_opportunities", []) or []
    language_context = research.get("language_context", {})
    if not isinstance(language_context, dict):
        language_context = {}

    primary_topic, secondary_topic = _topic_from_signals(
        keyword_signals,
        fallback=str(research.get("main_topic") or ""),
    )
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

    # Always generate English + Tamil + Tanglish so the creator gets all three
    # from a single request. One reachability check inside the helper.
    _LANGS = ["english", "tamil", "tanglish"]
    multilang_raw = write_multilang_packages(
        script,
        competitors=competitors,
        languages=_LANGS,
        region=region,
        audience_type=audience_type,
        category=category,
    )
    fallback_languages = [lang for lang in _LANGS if not multilang_raw.get(lang)]

    def _resolve(lang: str) -> dict[str, Any]:
        return multilang_raw.get(lang) or _fallback_package(primary_topic, keyword_signals)

    multilang = {lang: _resolve(lang) for lang in _LANGS}

    # The English package backs the top-level fields and all downstream analysis.
    llm_pkg = multilang_raw.get("english")
    pkg = multilang["english"]

    title = pkg["title"]
    description = pkg["description"]
    tags = pkg["tags"]
    hashtags = pkg["hashtags"]
    variant_titles = list(pkg["variants"]) or [title]
    while len(variant_titles) < 5:
        variant_titles.append(variant_titles[-1])

    title_variants_data = [
        {
            "title": v,
            "score": _deterministic_score(v, primary_topic),
            "estimated_ctr": f"{_deterministic_score(v, primary_topic) * 1.1:.1f}%",
            "character_count": len(v),
        }
        for v in variant_titles[:5]
    ]

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

    content_audit = audit_content_package(script, title, primary_topic, secondary_topic, angle)
    opportunity_gap_analysis = analyze_opportunity_gaps(
        keyword_signals=keyword_signals,
        entity_signals=entity_signals,
        youtube_results=research.get("youtube_results", []),
        top_opportunities=top_opportunities,
        language_context=language_context,
        target_title=title,
    )
    pacing_analysis = analyze_script_pacing(script)
    channel_intelligence = build_channel_intelligence(research.get("youtube_results", []))
    content_graph_strategy = build_content_graph_strategy(
        primary_topic=primary_topic,
        secondary_topic=secondary_topic,
        angle=angle,
        keyword_signals=keyword_signals,
    )
    chapters = build_chapters(script, keyword_signals)
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

    history_store.record_analysis_run(
        query=script[:120],
        intent=intent,
        content_angle=angle,
        title=title,
        title_score=float(title_optimization["scored_variants"][0]["score"])
        if title_optimization["scored_variants"]
        else 0.0,
        retention_risk=str(content_audit["retention_risk"]["level"]),
        opportunity_label=str(opportunity_gap_analysis["opportunity_score"]["label"]),
        opportunity_score=float(opportunity_gap_analysis["opportunity_score"]["score"]),
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

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "title_variants": title_variants_data,
        "content_angle": angle,
        "title_optimization": title_optimization,
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
        "generation_source": "ollama" if any(multilang_raw.values()) else "fallback",
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


def _deterministic_score(title: str, topic: str) -> float:
    """Length + topic-presence score. Replaces the prior random.uniform(7.5, 9.8)."""
    score = 6.0
    n = len(title)
    if 45 <= n <= 65:
        score += 1.5
    elif 35 <= n <= 70:
        score += 0.7
    if topic and topic.lower() in title.lower():
        score += 1.0
    lowered = title.lower()
    if any(k in lowered for k in ("how to", "why ", "what ", "?")):
        score += 0.5
    if any(c.isdigit() for c in title):
        score += 0.3
    return round(min(score, 9.5), 1)


def _fallback_package(primary_topic: str, keyword_signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic minimal SEO package used only when Ollama is offline.

    No randomness, no clickbait Mad Libs. Just a topic-locked title set, a
    real description scaffold, and topic + research-derived tags. Downstream
    topic_lock will still validate this.
    """
    pretty = (primary_topic or "your topic").strip().title()
    variants = [
        f"How to {pretty} (Step-by-Step)",
        f"{pretty}: Real Methods That Work",
        f"{pretty} for Beginners — Honest Guide",
        f"What I Learned About {pretty}",
        f"{pretty} Tips That Actually Help",
    ]
    description = (
        f"{pretty} — a practical walkthrough.\n\n"
        f"In this video I cover what {pretty.lower()} actually involves, "
        f"the mistakes most people make when they start, and the steps that "
        f"genuinely move the needle. By the end you will have a clear, "
        f"simple plan you can apply immediately.\n\n"
        f"If this helped, leave a like and tell me in the comments what you "
        f"want covered next."
    )
    tags: list[str] = []
    seen: set[str] = set()
    if primary_topic:
        tags.append(primary_topic.lower())
        seen.add(primary_topic.lower())
    for signal in keyword_signals or []:
        kw = str(signal.get("keyword", "")).strip().lower()
        if not kw or kw in seen:
            continue
        tags.append(kw)
        seen.add(kw)
        if len(tags) >= 10:
            break
    return {
        "title": variants[0],
        "variants": variants,
        "description": description,
        "tags": tags[:10],
        "hashtags": [],
    }
