"""Gemini-first SEO package builder with a deterministic local fallback."""

from __future__ import annotations

from typing import Any

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.creator_brief import creator_topic
from win_engine.analysis.package_builder import build_title_thumbnail_packages
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
from win_engine.llm.seo_writer import write_multilang_packages_with_source


_TOPIC_STOPWORDS = {"video", "youtube", "will", "what", "days", "today", "going"}


def build_seo_package(
    intent: str,
    script: str,
    research: dict[str, object],
    history_store: HistoryStore,
) -> dict[str, object]:
    """Generate the full SEO package. Gemini is the primary generator."""

    keyword_signals = research.get("keyword_signals", []) or []
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
    channel_learning = history_store.learning_summary()
    # Always generate English + Tamil + Tanglish so the creator gets all three
    # from a single request. One reachability check inside the helper.
    _LANGS = ["english", "tamil", "tanglish"]
    multilang_raw, generation_source = write_multilang_packages_with_source(
        script,
        competitors=competitors,
        languages=_LANGS,
        region=region,
        audience_type=audience_type,
        category=category,
        creator_brief=creator_brief,
        channel_learning=channel_learning,
    )
    fallback_languages = [lang for lang in _LANGS if not multilang_raw.get(lang)]

    def _resolve(lang: str) -> dict[str, Any]:
        p = multilang_raw.get(lang) or _fallback_package(primary_topic, keyword_signals, creator_brief)
        video_fmt = str((creator_brief or {}).get("video_format") or "").lower()
        script_lower = (script or "").lower()
        if video_fmt in {"youtube_shorts", "shorts", "quote", "reels"} or any(w in script_lower for w in ["short", "shorts", "quote", "reel", "betrayal", "sunset"]):
            existing_tags = [str(t).strip().lower() for t in (p.get("tags") or []) if str(t).strip()]
            for essential in ["shorts", "yt", "youtube shorts", "viral shorts"]:
                if essential not in existing_tags:
                    existing_tags.append(essential)
            p["tags"] = existing_tags[:12]
        return p

    multilang = {lang: _resolve(lang) for lang in _LANGS}

    # The English package backs the top-level fields and all downstream analysis.
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
    title_thumbnail_packages = build_title_thumbnail_packages(
        title_variants_data,
        creator_brief,
        competitor_titles=[str(item.get("title") or "") for item in research.get("youtube_results", []) if isinstance(item, dict)],
    )

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
        payload={
            "title": title, "description": description, "tags": tags, "hashtags": hashtags,
            "title_variants": title_variants_data, "title_thumbnail_packages": title_thumbnail_packages,
            "content_audit": content_audit, "opportunity_gap_analysis": opportunity_gap_analysis,
            "language_strategy": language_strategy, "pacing_analysis": pacing_analysis,
            "channel_intelligence": channel_intelligence, "content_graph_strategy": content_graph_strategy,
            "thumbnail_strategy": thumbnail_strategy, "chapters": chapters,
            "session_expansion": session_expansion, "binge_bridge": binge_bridge,
            "automation_workflow": automation_workflow, "feedback_package": feedback_package,
            "multilang": multilang, "generation_source": generation_source,
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
        "generation_source": generation_source,
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
    return round(min(score, 9.5), 1)


def _fallback_package(
    primary_topic: str,
    keyword_signals: list[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic minimal SEO package used when primary AI is offline."""
    pretty = (primary_topic or "your topic").strip().title()
    brief = creator_brief or {}
    video_fmt = str(brief.get("video_format") or "").lower()
    is_shorts = video_fmt in {"youtube_shorts", "shorts", "quote", "reels"} or any(w in pretty.lower() for w in ["quote", "betrayal", "sunset", "aesthetic", "shorts"])
    is_vlog = video_fmt in {"vlog", "story"}
    promise = str(brief.get("viewer_promise") or "").strip()

    if is_shorts:
        variants = [
            f"The Hardest Truth: {pretty} 💔 #Shorts",
            f"What They Never Told You... #Shorts",
            f"{pretty} | Watch Until The End... #Shorts",
            f"Read This Before You Trust Anyone... #Shorts",
            f"{pretty} #Shorts #Quotes",
        ]
        description = (
            f"✨ \"{pretty}\"\n\n"
            f"A powerful reflection on {pretty.lower()}, human emotions, and personal perspective. "
            f"Sometimes the hardest truths are the ones we learn quietly. Watch until the very end for the full realization.\n\n"
            + (f"💡 Key Takeaway: {promise}\n\n" if promise else "") +
            f"📌 Don't forget to Like, Share & Subscribe for daily life perspective & quote shorts!\n\n"
            f"----------------------------------------\n"
            f"#Shorts #Quotes #LifeLessons #Mindset #Aesthetic #ShortsFeed #ViralQuotes"
        )
    elif is_vlog:
        variants = [
            f"The Real {pretty}",
            f"Inside My {pretty}",
            f"My Honest {pretty}",
            f"What {pretty} Is Really Like",
            f"A Realistic {pretty}",
        ]
        description = (
            f"Welcome back to the channel! In today's video, I'm taking you inside {pretty.lower()}.\n\n"
            f"🎥 What's inside this video:\n"
            f"- Real behind-the-scenes footage and my unfiltered experience\n"
            f"- The key moments and lessons I learned along the way\n"
            f"- Honest thoughts and daily perspective\n\n"
            + (f"💡 Main Promise: {promise}\n\n" if promise else "") +
            f"🔔 Subscribe to follow along for more real vlogs and weekly content!\n"
            f"💬 Let me know your thoughts in the comments below.\n\n"
            f"----------------------------------------\n"
            f"#Vlog #DailyVlog #Storytime #{pretty.replace(' ', '')}"
        )
    else:
        variants = [
            f"{pretty}: Complete Guide & Breakdown",
            f"{pretty}: Real Methods That Work",
            f"{pretty} for Beginners — Honest Guide",
            f"What I Learned About {pretty}",
            f"{pretty} Tips That Actually Help",
        ]
        description = (
            f"In this comprehensive breakdown, we cover everything you need to know about {pretty.lower()}.\n\n"
            f"📌 What You Will Learn:\n"
            f"• Core fundamentals & exact step-by-step framework\n"
            f"• Common mistakes most creators make and how to avoid them\n"
            f"• Practical strategies that deliver real, measurable results\n\n"
            + (f"💡 Key Takeaway: {promise}\n\n" if promise else "") +
            f"⏱️ Timestamps:\n"
            f"00:00 - Introduction\n"
            f"01:15 - Core Concepts & Setup\n"
            f"04:30 - Step-by-Step Breakdown\n"
            f"08:45 - Key Tips & Pitfalls\n"
            f"11:20 - Summary & Next Steps\n\n"
            f"🔔 If you found this helpful, hit the LIKE button and SUBSCRIBE for more in-depth guides!\n"
            f"💬 Leave a comment below with any questions."
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
        "hashtags": ["#Shorts", "#Quotes", "#LifeLessons"] if is_shorts else ["#YouTube", f"#{pretty.replace(' ', '')}"],
    }
