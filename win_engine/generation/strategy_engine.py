"""Gemini-first SEO package builder with a deterministic local fallback."""

from __future__ import annotations

import logging
import re
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
from win_engine.feedback.channel_learning import learning_summary as channel_performance_learning
from win_engine.feedback.learning_engine import build_feedback_package
from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import (
    build_binge_bridge,
    build_chapters,
    build_session_expansion,
)
from win_engine.llm.seo_writer import write_multilang_packages_with_source


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
        channel_learning = channel_performance_learning(history_store.database_path)
    except Exception as exc:
        logger.warning("Channel performance learning is unavailable: %s", type(exc).__name__)
        channel_learning = {}
    channel_learning["recent_titles"] = history_store.recent_generated_titles(limit=10)
    channel_learning["cohort"] = history_store.cohort_analytics(
        format_filter=str((creator_brief or {}).get("video_format") or "").strip() or None,
        language_filter=selected_language,
    )
    # Generate only the selected language. Additional languages must be explicit
    # creator actions so a single video does not consume three Gemini requests.
    _LANGS = [selected_language]
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
        p = multilang_raw.get(lang) or _content_specific_fallback(primary_topic, keyword_signals, creator_brief)
        video_fmt = str((creator_brief or {}).get("video_format") or "").lower()
        script_lower = (script or "").lower()
        is_short_form = video_fmt in {"youtube_shorts", "shorts", "quote", "reels"} or bool(
            re.search(r"\b(?:short|shorts|reel|reels|quote)\b", script_lower)
        )
        if is_short_form:
            existing_tags = [str(t).strip().lower() for t in (p.get("tags") or []) if str(t).strip()]
            required_tags = ["shorts", "youtube shorts"]
            topic_tags = [tag for tag in existing_tags if tag not in required_tags]
            p["tags"] = topic_tags[: 12 - len(required_tags)] + required_tags
        return p

    multilang = {lang: _resolve(lang) for lang in _LANGS}

    # The selected-language package backs the top-level fields and downstream analysis.
    pkg = multilang[selected_language]

    title = pkg["title"]
    description = pkg["description"]
    tags = pkg["tags"]
    hashtags = pkg["hashtags"]
    variant_titles = list(pkg["variants"]) or [title]
    while len(variant_titles) < 5:
        variant_titles.append(variant_titles[-1])

    package_intents = ["Search", "Browse", "Existing audience", "Alternative", "Alternative"]
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
    for index, variant in enumerate(variant_titles[:5]):
        quality_score = _deterministic_score(
            variant,
            primary_topic,
            context_text=title_context,
            competitor_titles=competitor_titles,
        )
        title_variants_data.append({
            "title": variant,
            "score": quality_score,
            "estimated_ctr": None,
            "character_count": len(variant),
            "package_intent": package_intents[index] if index < len(package_intents) else "Alternative",
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


def _deterministic_score(
    title: str,
    topic: str,
    *,
    context_text: str = "",
    competitor_titles: list[str] | None = None,
) -> float:
    """Pre-publication title quality score; never presented as measured CTR."""
    clean = re.sub(r"\s+", " ", title or "").strip()
    lowered = clean.lower()
    score = 0.0
    length = len(clean)
    score += 2.0 if 45 <= length <= 65 else 1.2 if 35 <= length <= 70 else 0.5

    words = re.findall(r"[a-z0-9]+", lowered)
    score += 1.5 if 5 <= len(words) <= 12 else 0.8 if 3 <= len(words) <= 15 else 0.3

    stopwords = {"a", "an", "and", "are", "for", "from", "how", "in", "is", "of", "on", "the", "this", "to", "with", "you", "your"}
    title_terms = {word for word in words if len(word) >= 3 and word not in stopwords}
    source_terms = {
        word for word in re.findall(r"[a-z0-9]+", f"{topic} {context_text}".lower())
        if len(word) >= 3 and word not in stopwords
    }
    relevance = len(title_terms & source_terms) / len(title_terms) if title_terms else 0.0
    score += relevance * 3.0

    if any(term in lowered for term in ("why", "when", "truth", "mistake", "secret", "hardest", "never", "realize", "what")):
        score += 1.0

    competitors = [set(re.findall(r"[a-z0-9]+", item.lower())) for item in competitor_titles or [] if item]
    similarities = [len(title_terms & item) / max(len(title_terms | item), 1) for item in competitors]
    max_similarity = max(similarities, default=0.0)
    score += 1.0 if max_similarity <= 0.35 else 0.5 if max_similarity <= 0.60 else 0.0

    production_junk = ("vertical", "creator", "background footage", "cinematic dark")
    score += 1.0 if not any(term in lowered for term in production_junk) else 0.2
    score += 0.5 if clean and clean.count("!") <= 1 and "???" not in clean else 0.0
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


def _content_specific_fallback(
    primary_topic: str,
    keyword_signals: list[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Honest, content-specific package used only when Gemini is unavailable."""
    brief = creator_brief or {}
    topic = (primary_topic or "the video topic").strip()
    pretty = topic.title()
    content = str(brief.get("content") or "").strip()
    quote = _quoted_text(content)
    video_format = str(brief.get("video_format") or "").lower()
    is_shorts = video_format in {"youtube_shorts", "shorts", "quote", "reels"}
    promise = str(brief.get("viewer_promise") or "").strip()
    audience = str(brief.get("target_audience") or "").strip()
    unique_angle = str(brief.get("unique_angle") or "").strip()
    proof = str(brief.get("proof") or "").strip()

    suffix = " #Shorts" if is_shorts else ""
    if quote:
        variants = [
            _fit_title(quote, suffix),
            _fit_title(f"The Meaning Behind: {quote}", suffix),
            _fit_title(f"Read This Twice: {quote}", suffix),
            _fit_title(f"{pretty}: A Quiet Reminder", suffix),
            _fit_title(f"A Quote About {pretty}", suffix),
        ]
        visual_match = re.search(
            r"(?i)\bbackground\s*visuals?\s*(?:is|:)?\s*(.*?)(?=\s+and\s+.*(?:screen|quote)|[.;]|$)",
            content,
        )
        visual = re.sub(r"\s+", " ", visual_match.group(1)).strip(" .") if visual_match else "the accompanying visual"
        if visual and not re.match(r"(?i)^(?:a|an|the)\s", visual):
            visual = "a " + visual
        description = (
            f'“{quote}”\n\n'
            f"This Short pairs the on-screen quote with {visual}, creating a quiet moment to reflect on {topic}. "
            f"The words are the focus, while the visual supports their mood without changing their meaning."
        )
    else:
        variants = [
            _fit_title(f"{pretty}: What You Need to Know", suffix),
            _fit_title(f"The Honest Truth About {pretty}", suffix),
            _fit_title(f"What {pretty} Really Means", suffix),
            _fit_title(f"A Different Way to See {pretty}", suffix),
            _fit_title(f"The Most Useful Lesson From {pretty}", suffix),
        ]
        rotation = sum(ord(char) for char in topic.casefold()) % len(variants)
        variants = variants[rotation:] + variants[:rotation]
        description_parts = [
            f"This video focuses on {topic}.",
            promise or "It explains the idea using the actual details shown in the video.",
        ]
        if unique_angle:
            description_parts.append(f"Its distinct angle is {unique_angle}.")
        if proof:
            description_parts.append(f"The video supports this with {proof}.")
        if audience:
            description_parts.append(f"It is intended for {audience}.")
        description = "\n\n".join(description_parts)

    tags: list[str] = []
    seen: set[str] = set()
    quote_words = [word.lower() for word in re.findall(r"[A-Za-z]{4,}", quote)]
    quote_tags = []
    if quote_words:
        meaningful = [word for word in quote_words if word not in {"some", "look", "looks", "because", "they", "theyre"}]
        quote_tags = [
            f"{meaningful[0]} quote" if meaningful else "",
            " ".join(meaningful[-2:]) if len(meaningful) >= 2 else "",
            f"{meaningful[-1]} quote" if meaningful else "",
            "emotional quotes",
            "life reflections",
            "aesthetic quote shorts",
        ]
    candidates = [topic, *quote_tags] if quote else [topic, *[str(item.get("keyword") or "") for item in keyword_signals or []]]
    for candidate in candidates:
        cleaned = candidate.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            tags.append(cleaned)

    return {
        "title": variants[0],
        "variants": variants,
        "description": description,
        "tags": tags[:8],
        "hashtags": ["#Shorts", "#Quotes", "#LifeLessons"] if is_shorts else [f"#{re.sub(r'[^A-Za-z0-9]', '', pretty)}"],
    }
