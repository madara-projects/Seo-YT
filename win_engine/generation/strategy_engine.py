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
        p = generated or _content_specific_fallback(primary_topic, keyword_signals, creator_brief)
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
                "fallback_reason": str(diagnostic.get("status") or "gemini_unavailable"),
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
        tag_context=[
            *(str(item.get("keyword") or "") for item in keyword_signals if isinstance(item, dict)),
            *(str(item.get("entity") or "") for item in entity_signals if isinstance(item, dict)),
        ],
    )
    pkg = apply_quality_gate(pkg, quality_gate)
    multilang[selected_language] = pkg

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
            "multilang": multilang, "generation_source": generation_source,
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
        "generation_source": generation_source,
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
    is_shorts = is_short_content(content or topic, brief)
    promise = str(brief.get("viewer_promise") or "").strip()
    audience = str(brief.get("target_audience") or "").strip()
    unique_angle = str(brief.get("unique_angle") or "").strip()
    proof = str(brief.get("proof") or "").strip()

    emoji = _semantic_emoji(" ".join([topic, content, quote, str(brief.get("visual_requirements") or "")]))
    suffix = f" {emoji} #shorts" if is_shorts and emoji else " #shorts" if is_shorts else ""
    if quote:
        title_quote = _quote_title_focus(quote)
        variants = [
            _fit_title(title_quote, suffix),
            _fit_title(f"The Meaning Behind: {title_quote}", suffix),
            _fit_title(f"Read This Twice: {title_quote}", suffix),
            _fit_title(f"{pretty}: A Quiet Reminder", suffix),
            _fit_title(f"A Quote About {pretty}", suffix),
        ]
        visual_match = re.search(
            r"(?i)\bbackground(?:\s+visuals?)?\s*(?:is|:)?\s*(.*?)(?=\s+and\s+.*(?:screen|quote)|[.;]|$)",
            content,
        )
        visual = re.sub(r"\s+", " ", visual_match.group(1)).strip(" .,:;") if visual_match else "the accompanying visual"
        if visual and not re.match(r"(?i)^(?:a|an|the)\s", visual):
            visual = "a " + visual
        visual_sentence = visual.split(",", 1)[0].rstrip(" .")
        description = (
            f'“{quote}”\n\n'
            f"{visual_sentence[:1].upper() + visual_sentence[1:]} sets a reflective backdrop for these words. "
            "A quiet Short for anyone who connects with the idea expressed in these words."
        )
    else:
        # Keep the fallback useful when Gemini is unavailable: each option is
        # a different discovery mechanism, but all are derived from the same
        # creator-supplied subject rather than a niche-specific template.
        instructional = not source_requires_noninstructional_framing(content or topic, brief)
        variants = (
            [
                _fit_title(f"How {pretty} Works in Practice", suffix),
                _fit_title(f"The Practical Side of {pretty}", suffix),
                _fit_title(f"A Closer Look at {pretty}", suffix),
                _fit_title(f"{pretty}: A Clear Step-by-Step Look", suffix),
                _fit_title(f"What to Know About {pretty}", suffix),
            ] if instructional else [
                _fit_title(f"A Quiet Look at {pretty}", suffix),
                _fit_title(f"The Story Behind {pretty}", suffix),
                _fit_title(f"A Moment About {pretty}", suffix),
                _fit_title(f"What {pretty} Leaves Unsaid", suffix),
                _fit_title(f"Reflecting on {pretty}", suffix),
            ]
        )
        if unique_angle:
            variants[1] = _fit_title(f"{pretty} Through {unique_angle}", suffix)
        if proof:
            variants[2] = _fit_title(f"See {pretty} With {proof}", suffix)
        if promise:
            variants[3] = _fit_title(f"{pretty}: {promise}", suffix)
        rotation = sum(ord(char) for char in topic.casefold()) % len(variants)
        variants = variants[rotation:] + variants[:rotation]
        source_excerpt = re.sub(r"\s+", " ", content or topic).strip(" .")
        if len(source_excerpt) > 220:
            source_excerpt = source_excerpt[:217].rsplit(" ", 1)[0] + "…"
        description_parts = [
            f"A focused look at {topic}, grounded in the creator's supplied material.",
            promise or (
                f"The video walks through the specific details of {topic} shown in the source."
                if instructional else
                f"The video stays with the specific moment about {topic} shown in the source."
            ),
        ]
        if source_excerpt and source_excerpt.casefold() != topic.casefold():
            description_parts.append(f"Source context: {source_excerpt}.")
        if unique_angle:
            description_parts.append(f"Its distinct angle is {unique_angle}.")
        if proof:
            description_parts.append(f"The video supports this with {proof}.")
        if audience:
            description_parts.append(f"It is intended for {audience}.")
        description = "\n\n".join(description_parts)

    tags: list[str] = []
    seen: set[str] = set()
    quote_words = [word.lower() for word in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", quote)]
    quote_tags: list[str] = []
    if quote_words:
        # Keep complete, meaningful clauses from a quote.  Splitting the
        # quote into arbitrary first/last word bags made tags look broken and
        # unhelpful even when the package otherwise passed validation.
        quote_tags = [
            " ".join(re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", sentence.lower())[:8])
            for sentence in re.split(r"[.!?]+", quote)
            if sentence.strip()
        ]
        quote_tags = [tag for tag in quote_tags if tag]
    candidates = [topic, *quote_tags] if quote else [topic, *[str(item.get("keyword") or "") for item in keyword_signals or []]]
    for field in ("viewer_promise", "unique_angle", "visual_requirements"):
        value = " ".join(str(brief.get(field) or "").strip().lower().split()[:6])
        if value:
            candidates.append(value)
    if "emotional" in content.casefold():
        candidates.append("emotional quote")
    for candidate in candidates:
        cleaned = candidate.strip().lower()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            tags.append(cleaned)

    if is_shorts and "shorts" not in seen:
        tags.append("shorts")

    hashtags = [_topic_hashtag(topic)]
    if is_shorts:
        hashtags.append("#shorts")
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
