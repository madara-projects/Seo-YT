from __future__ import annotations

import re
from typing import Any

from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.gap_engine import analyze_opportunity_gaps
from win_engine.analysis.language_engine import build_language_strategy
from win_engine.analysis.pacing_engine import analyze_script_pacing
from win_engine.analysis.strategy_layer import build_channel_intelligence, build_content_graph_strategy
from win_engine.analysis.thumbnail_classifier import build_thumbnail_strategy
from win_engine.analysis.title_optimizer import optimize_titles
from win_engine.feedback.learning_engine import build_feedback_package
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.automation_engine import build_automation_workflow
from win_engine.generation.expansion_engine import build_binge_bridge, build_chapters, build_session_expansion
from win_engine.analysis.nlp_titlegen import generate_dynamic_title, generate_dynamic_description


def build_seo_package(
    intent: str,
    script: str,
    research: dict[str, object],
    history_store: HistoryStore,
) -> dict[str, object]:
    """Generate a first-pass SEO package from research signals."""

    keyword_signals = research.get("keyword_signals", [])
    entity_signals = research.get("entity_signals", [])
    top_opportunities = research.get("top_opportunities", [])
    language_context = research.get("language_context", {})
    if not isinstance(language_context, dict):
        language_context = {}

    script_facts = _extract_script_facts(script, keyword_signals, entity_signals)
    primary_topic = script_facts["action"]
    secondary_topic = script_facts["conflict"]
    angle = _select_content_angle(intent, script, top_opportunities)
    competitor_patterns = _extract_competitor_patterns(research.get("youtube_results", []))
    language_strategy = build_language_strategy(script, language_context)
    # Use NLP-powered dynamic title and description generation
    title = generate_dynamic_title(script)
    description = generate_dynamic_description(script)
    # Optionally, still generate variants for UI display
    title_variants = [title]
    title_optimization = {"best_title": title, "scored_variants": [{"title": title, "score": 10.0}]}
    tags = _build_tags(keyword_signals, script_facts, language_strategy)
    hashtags = _build_hashtags(keyword_signals, entity_signals, script_facts, competitor_patterns, language_strategy)
    content_audit = audit_content_package(script, title, primary_topic, secondary_topic, angle)
    opportunity_gap_analysis = analyze_opportunity_gaps(
        keyword_signals=keyword_signals,
        entity_signals=entity_signals,
        youtube_results=research.get("youtube_results", []),
        top_opportunities=top_opportunities,
        language_context=language_context,
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
        title_score=float(title_optimization["scored_variants"][0]["score"]) if title_optimization["scored_variants"] else 0.0,
        retention_risk=str(content_audit["retention_risk"]["level"]),
        opportunity_label=str(opportunity_gap_analysis["opportunity_score"]["label"]),
        opportunity_score=float(opportunity_gap_analysis["opportunity_score"]["score"]),
    )
    seo_package_for_feedback = {
        "title": title,
        "content_angle": angle,
        "title_optimization": title_optimization,
        "opportunity_gap_analysis": opportunity_gap_analysis,
    }
    feedback_package = build_feedback_package(
        seo_package=seo_package_for_feedback,
        research=research,
        learning_summary=history_store.learning_summary(),
        internal_scorecard=history_store.internal_scorecard(),
    )

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "hashtags": hashtags,
        "title_variants": title_variants,
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
    }


def _best_topic(
    keyword_signals: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
    fallback: str,
) -> str:
    for signal in keyword_signals:
        keyword = str(signal.get("keyword", "")).strip()
        if keyword and keyword not in {"youtube", "video", "will", "what", "days"}:
            return _humanize_topic(keyword)

    for signal in entity_signals:
        entity = str(signal.get("entity", "")).strip()
        if entity and entity not in {"In", "If", "Days"}:
            return entity

    return fallback


def _secondary_topic(keyword_signals: list[dict[str, Any]], exclude: str) -> str:
    exclude_lower = exclude.lower()
    for signal in keyword_signals:
        keyword = str(signal.get("keyword", "")).strip()
        if not keyword:
            continue
        if keyword.lower() in {exclude_lower, "youtube", "video", "will", "what"}:
            continue
        return _humanize_topic(keyword)
    return "better retention"


def _humanize_topic(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())


def _extract_script_facts(
    script: str,
    keyword_signals: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
) -> dict[str, str]:
    lowered = script.lower()
    action = ""
    duration = ""
    conflict = ""
    promise = ""

    action_match = re.search(r"\b(?:waking|wake|woke)\s+up\s+at\s+\d{1,2}\s*(?:am|pm)(?:\s+every\s+day)?\b", lowered)
    if action_match:
        action = action_match.group(0).replace(" every day", "")
    elif keyword_signals:
        for signal in keyword_signals:
            keyword = str(signal.get("keyword", "")).strip()
            if any(token in keyword for token in {"waking up", "wake up", "5 am", "routine", "morning productivity"}):
                action = keyword
                break

    duration_match = re.search(r"\bfor\s+\d+\s+days\b", lowered)
    if duration_match:
        duration = duration_match.group(0).replace("for ", "")
    elif re.search(r"\b\d+\s+days\b", lowered):
        duration = re.search(r"\b\d+\s+days\b", lowered).group(0)

    if any(token in lowered for token in {"worth it", "overhyped", "life-changing", "should you"}):
        if "worth it" in lowered and "overhyped" in lowered:
            conflict = "worth it or overhyped"
        elif "worth it" in lowered:
            conflict = "was it worth it"
        elif "overhyped" in lowered:
            conflict = "is it overhyped"
        else:
            conflict = "should you try it"
    elif "unexpected downsides" in lowered or "downsides" in lowered:
        conflict = "benefits vs downsides"

    if any(token in lowered for token in {"views", "retention", "youtube growth", "shorts growth", "go viral"}):
        if "views" in lowered and "retention" in lowered:
            promise = "more views and better retention"
        elif "views" in lowered:
            promise = "more views"
        elif "retention" in lowered:
            promise = "better retention"
        else:
            promise = "faster channel growth"
    elif any(token in lowered for token in {"productivity", "mindset", "life-changing"}):
        if "productivity" in lowered and "mindset" in lowered:
            promise = "productivity and mindset"
        elif "productivity" in lowered:
            promise = "better productivity"
        elif "mindset" in lowered:
            promise = "better mindset"
        else:
            promise = "life-changing results"

    if not action:
        action = _best_topic(keyword_signals, entity_signals, fallback="YouTube growth")
    if not duration:
        duration = "7 days" if "7 days" in lowered else "one week"
    if not conflict:
        conflict = _secondary_topic(keyword_signals, exclude=action)
    if not promise:
        promise = "what changed"

    return {
        "action": _humanize_phrase(action),
        "duration": duration,
        "conflict": _humanize_phrase(conflict),
        "promise": _humanize_phrase(promise),
    }


def _humanize_phrase(value: str) -> str:
    cleaned = value.strip().replace("_", " ")
    if not cleaned:
        return cleaned
    cleaned = re.sub(r"\byoutube\b", "YouTube", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b5 am\b", "5 AM", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b4 am\b", "4 AM", cleaned, flags=re.IGNORECASE)
    if cleaned.lower() in {"5 am", "4 am"}:
        return cleaned.upper()
    return cleaned[0].upper() + cleaned[1:]


def _select_content_angle(intent: str, script: str, top_opportunities: list[dict[str, Any]]) -> str:
    lower = script.lower()

    if "case study" in lower or "tested" in lower or "i tried" in lower:
        return "Experiment"
    if "mistake" in lower or "wrong" in lower:
        return "Mistake"
    if intent == "SEARCH":
        return "Authority"
    if top_opportunities and any("shocking" in str(item.get("title", "")).lower() for item in top_opportunities):
        return "Curiosity"
    return "Story"


def _build_title_variants(
    primary_topic: str,
    secondary_topic: str,
    angle: str,
    intent: str,
    script_facts: dict[str, str],
    competitor_patterns: dict[str, str],
    language_strategy: dict[str, Any],
) -> list[str]:
    action = script_facts["action"]
    duration = script_facts["duration"]
    conflict = script_facts["conflict"]
    promise = script_facts["promise"]
    base_question = conflict.title() if conflict else "Was It Worth It?"

    seo_title = f"{action} for {duration}: {base_question}"
    psychological_title = f"I Tried {action} for {duration}. Here's What Happened"
    hybrid_title = f"{action} for {duration}: The Honest Truth"

    if angle == "Experiment":
        seo_title = f"I Tried {action} for {duration}: Was It Worth It?"
        psychological_title = f"I Tried {action} for {duration}. Here's What Happened"
        hybrid_title = f"{action} for {duration}: The Benefits, Downsides, and Honest Truth"
    elif angle == "Authority":
        seo_title = f"{action}: What Actually Happens After {duration}"
        psychological_title = f"The Truth About {action} for {duration}"
        hybrid_title = f"{action} for {duration}: {promise.title()}"
    elif angle == "Curiosity":
        seo_title = f"{action} for {duration}: The Truth Nobody Talks About"
        psychological_title = f"I Tried {action} for {duration} and Something Changed"
        hybrid_title = f"{action} for {duration}: {base_question}"

    if competitor_patterns.get("uses_how_to") == "yes" and intent == "SEARCH":
        seo_title = f"How to {action[0].lower() + action[1:]} for {duration}: {promise.title()}"
    if competitor_patterns.get("uses_first_person") == "yes" and "I Tried" not in psychological_title:
        psychological_title = f"I Tried {action} for {duration}. Here's What Happened"

    titles = [seo_title, hybrid_title, psychological_title] if intent == "SEARCH" else [psychological_title, hybrid_title, seo_title] if intent == "BROWSE" else [hybrid_title, psychological_title, seo_title]
    return _localize_title_variants(titles, script_facts, language_strategy)


def _choose_primary_title(
    intent: str,
    title_variants: list[str],
    title_optimization: dict[str, Any],
) -> str:
    if not title_variants:
        return "YouTube Strategy Breakdown"
    optimized = str(title_optimization.get("best_title", "")).strip()
    return optimized or title_variants[0]


def _build_description(
    script: str,
    primary_topic: str,
    secondary_topic: str,
    angle: str,
    top_opportunities: list[dict[str, Any]],
    script_facts: dict[str, str],
    language_strategy: dict[str, Any],
) -> str:
    summary = _summarize_script(script)
    opportunity_hook = ""
    if top_opportunities:
        top_title = str(top_opportunities[0].get("title", "")).strip()
        if top_title:
            opportunity_hook = f" Inspired by breakout patterns like \"{top_title}\"."

    description = (
        f"I tried {script_facts['action'].lower()} for {script_facts['duration']} because I wanted to know if it would actually improve {script_facts['promise'].lower()} or if the whole thing was just overhyped.\n\n"
        f"In this video, I break down what changed, what felt harder than expected, and the downside nobody mentions before you start.{opportunity_hook}\n\n"
        f"{summary}\n\n"
        f"If you have been thinking about trying this yourself, watch to the end before you decide."
    )
    audience_type = str(language_strategy.get("audience_type", "")).lower()
    primary_language = str(language_strategy.get("primary_language", "")).lower()
    if primary_language in {"tamil", "tanglish"}:
        description += "\n\nThis package is tuned for a more local, spoken-style audience response rather than a flat generic SEO tone."
    if audience_type == "diaspora":
        description += "\n\nThis version also leans toward a broader audience that still connects with local context."
    return description


def _summarize_script(script: str) -> str:
    cleaned = re.sub(r"\s+", " ", script).strip()
    if len(cleaned) <= 220:
        return cleaned
    return cleaned[:217].rstrip() + "..."


def _build_hashtags(
    keyword_signals: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
    script_facts: dict[str, str],
    competitor_patterns: dict[str, str],
    language_strategy: dict[str, Any],
) -> list[str]:
    tags: list[str] = []

    action_lower = script_facts["action"].lower()
    seed_tags = [script_facts["action"].lower(), script_facts["duration"].lower()]

    if "am" in action_lower:
        seed_tags.extend(["morning routine", "productivity", "self improvement"])
    elif "youtube" in action_lower or "shorts" in action_lower:
        seed_tags.extend(["youtube growth", "shorts strategy", "audience retention"])
    else:
        seed_tags.extend([script_facts["promise"].lower(), "creator tips"])

    for keyword in seed_tags:
        normalized = keyword.strip().replace(" ", "")
        if not normalized:
            continue
        tag = "#" + normalized
        if tag not in tags:
            tags.append(tag)

    for signal in keyword_signals[:6]:
        keyword = str(signal.get("keyword", "")).strip()
        if not keyword or len(keyword.split()) > 4:
            continue
        normalized = keyword.replace(" ", "")
        if normalized.lower() in {"will", "what", "video", "days", "onehabit", "for30days"}:
            continue
        tag = "#" + normalized.lower()
        if tag not in tags:
            tags.append(tag)

    if competitor_patterns.get("topic_shorts") == "yes" and "#shorts" not in tags:
        tags.append("#shorts")

    primary_language = str(language_strategy.get("primary_language", "")).lower()
    region = str(language_strategy.get("selected_region", "")).lower()
    if primary_language in {"tamil", "tanglish"}:
        for extra_tag in ["#tamilyoutube", "#tamilcreator"]:
            if extra_tag not in tags:
                tags.append(extra_tag)
    if region == "india" and "#india" not in tags:
        tags.append("#india")
    if region == "tamil nadu" and "#tamilnadu" not in tags:
        tags.append("#tamilnadu")

    if "#youtube" not in tags:
        tags.insert(0, "#youtube")

    return tags[:6]


def _build_tags(
    keyword_signals: list[dict[str, Any]],
    script_facts: dict[str, str],
    language_strategy: dict[str, Any],
) -> list[str]:
    tags: list[str] = []

    seeds = [
        script_facts["action"],
        script_facts["duration"],
        script_facts["promise"],
        script_facts["conflict"],
    ]

    for seed in seeds:
        cleaned = seed.strip()
        if not cleaned:
            continue
        if cleaned.lower() not in {item.lower() for item in tags}:
            tags.append(cleaned)

    for signal in keyword_signals[:8]:
        keyword = str(signal.get("keyword", "")).strip()
        if not keyword or len(keyword.split()) > 5:
            continue
        if keyword.lower() not in {item.lower() for item in tags}:
            tags.append(keyword)

    primary_language = str(language_strategy.get("primary_language", "")).lower()
    region = str(language_strategy.get("selected_region", "")).lower()
    if primary_language in {"tamil", "tanglish"}:
        for extra in ["Tamil YouTube", "Tamil Creator"]:
            if extra.lower() not in {item.lower() for item in tags}:
                tags.append(extra)
    if region == "india" and "India" not in tags:
        tags.append("India")
    if region == "tamil nadu" and "Tamil Nadu" not in tags:
        tags.append("Tamil Nadu")

    return tags[:10]


def _extract_competitor_patterns(youtube_results: list[dict[str, Any]]) -> dict[str, str]:
    titles = [str(item.get("title", "")) for item in youtube_results[:5]]
    lowered_titles = [title.lower() for title in titles]
    return {
        "uses_how_to": "yes" if any(title.startswith("how to") for title in lowered_titles) else "no",
        "uses_first_person": "yes" if sum(1 for title in lowered_titles if title.startswith("i ")) >= 2 else "no",
        "topic_shorts": "yes" if any("#shorts" in title or "shorts" in title for title in lowered_titles) else "no",
    }


def _localize_title_variants(
    title_variants: list[str],
    script_facts: dict[str, str],
    language_strategy: dict[str, Any],
) -> list[str]:
    primary_language = str(language_strategy.get("primary_language", "")).lower()
    audience_type = str(language_strategy.get("audience_type", "")).lower()
    region = str(language_strategy.get("selected_region", "")).lower()

    if primary_language == "tamil":
        localized = [
            f"{script_facts['action']} for {script_facts['duration']} | Worth It-ah?",
            f"I Tried {script_facts['action']} for {script_facts['duration']} | Real Result",
            f"{script_facts['action']} {script_facts['duration']} Challenge | Honest Review",
        ]
        return localized

    if primary_language == "tanglish":
        localized = [
            f"I Tried {script_facts['action']} for {script_facts['duration']} | Worth It-ah?",
            f"{script_facts['action']} for {script_facts['duration']} | Real Talk",
            f"{script_facts['action']} Challenge | Honest Result",
        ]
        return localized

    if audience_type == "diaspora" and region in {"india", "tamil nadu", "sri lanka", "gulf"}:
        return [
            title_variants[0],
            f"{title_variants[1]} | No Hype",
            title_variants[2],
        ]

    return title_variants
