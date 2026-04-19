from __future__ import annotations

from typing import Any

# Brain v2.0 Integration
from win_engine.analysis.dynamic_thresholds import get_dynamic_kill_switch


def analyze_opportunity_gaps(
    keyword_signals: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
    top_opportunities: list[dict[str, Any]],
    language_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gap analysis and opportunity heuristics for Phase 4."""

    language_context = language_context or {}
    keyword_gaps = _keyword_gaps(keyword_signals, youtube_results)
    competition = _competition_meter(youtube_results, language_context)
    
    # Brain v2.0: Dynamic, niche-aware kill switch instead of hard-coded thresholds
    # Pass 'niche' if available in language_context, else default to 'general'
    niche = language_context.get('niche', 'general') if isinstance(language_context, dict) else 'general'
    idea_kill_switch = get_dynamic_kill_switch(
        top_opportunities=top_opportunities,
        competition=competition,
        keyword_gaps=keyword_gaps,
        youtube_results=youtube_results,
        niche=niche,
    )
    
    # Apply Local AI Semantic Analysis for Uniqueness
    uniqueness_score = 0.5
    try:
        from win_engine.analysis.ai_enhancement import get_ai_engine
        if youtube_results:
            competitor_titles = [str(item.get("title", "")) for item in youtube_results[:5]]
            target_title = str(top_opportunities[0].get("title", "")) if top_opportunities else ""
            if target_title and competitor_titles:
                uniqueness_score = get_ai_engine().calculate_uniqueness(target_title, competitor_titles)
    except Exception:
        pass

    differentiation = _differentiation_plan(keyword_gaps, competition, youtube_results)
    opportunity_score = _opportunity_score(keyword_gaps, competition, top_opportunities)
    format_lock = _format_lock_in(top_opportunities, youtube_results, competition)
    viability_verdict = _viability_verdict(opportunity_score, competition, idea_kill_switch, keyword_gaps)

    return {
        "keyword_gaps": keyword_gaps,
        "competition": competition,
        "idea_kill_switch": idea_kill_switch,
        "entity_focus": _entity_focus(entity_signals),
        "differentiation": differentiation,
        "opportunity_score": opportunity_score,
        "ai_uniqueness_score": uniqueness_score,
        "competitor_shadow": _competitor_shadow(youtube_results),
        "format_lock": format_lock,
        "viability_verdict": viability_verdict,
    }


def _keyword_gaps(
    keyword_signals: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result_text = " ".join(
        f"{item.get('title', '')} {item.get('description', '')}" for item in youtube_results
    ).lower()

    gaps: list[dict[str, Any]] = []
    for signal in keyword_signals:
        keyword = str(signal.get("keyword", "")).strip()
        mentions = int(signal.get("mentions", 0))
        if not keyword or keyword in {"youtube", "video", "will", "what"}:
            continue

        result_mentions = result_text.count(keyword.lower())
        if mentions >= 2 and result_mentions <= max(1, mentions):
            gaps.append(
                {
                    "keyword": keyword,
                    "gap_strength": "high" if result_mentions == 0 else "medium",
                    "reason": "Present in your concept but underused in competitor metadata.",
                }
            )

    return gaps[:6]


def _competition_meter(youtube_results: list[dict[str, Any]], language_context: dict[str, Any]) -> dict[str, Any]:
    if not youtube_results:
        return {
            "score": 0,
            "label": "UNKNOWN",
            "reason": "No competitor data available.",
        }

    repeated_title_patterns = sum(
        1 for item in youtube_results if "30 days" in str(item.get("title", "")).lower()
    )
    big_channel_count = sum(
        1 for item in youtube_results if int(item.get("subscriber_count") or 0) >= 250000
    )
    average_outlier = sum(float(item.get("outlier_score") or 0) for item in youtube_results[:5]) / max(len(youtube_results[:5]), 1)

    score = (repeated_title_patterns * 20) + (big_channel_count * 15)
    if average_outlier > 100000:
        score += 25
    elif average_outlier > 10000:
        score += 15
    else:
        score += 5

    audience_type = str(language_context.get("audience_type", "")).strip().lower()
    region = str(language_context.get("region", "")).strip().lower()
    if audience_type in {"local", "diaspora"}:
        score -= 10
    if region in {"tamil nadu", "sri lanka", "gulf"}:
        score -= 5
    score = max(score, 0)

    if score >= 70:
        label = "SATURATED"
        reason = "Large channels and repeated title patterns suggest heavy competition."
    elif score >= 40:
        label = "COMPETITIVE"
        reason = "The topic has traction, but several established videos are already fighting for the click."
    else:
        label = "UNDERSERVED"
        reason = "There is still room to differentiate packaging and angle."

    return {
        "score": round(score, 2),
        "label": label,
        "reason": reason,
        "repeated_title_patterns": repeated_title_patterns,
        "big_channel_count": big_channel_count,
    }


def _idea_kill_switch(
    top_opportunities: list[dict[str, Any]],
    competition: dict[str, Any],
    keyword_gaps: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
) -> dict[str, Any]:
    top_score = float(top_opportunities[0].get("outlier_score") or 0) if top_opportunities else 0.0
    competition_label = competition.get("label", "UNKNOWN")
    small_channel_outliers = sum(1 for item in top_opportunities if item.get("small_channel_outlier"))
    high_gap_count = sum(1 for item in keyword_gaps if item.get("gap_strength") == "high")
    similar_count = len(youtube_results)

    proceed = True
    reason = "Opportunity is strong enough to keep pursuing."
    confidence = "medium"
    recommended_action = "Proceed with a differentiated angle."

    if top_score < 500 and competition_label == "SATURATED" and high_gap_count == 0:
        proceed = False
        reason = "Weak outlier signal plus saturated competition makes this a poor bet."
        confidence = "high"
        recommended_action = "Kill this idea or re-scope it into a narrower subtopic."
    elif top_score < 2000 and competition_label == "COMPETITIVE" and small_channel_outliers == 0 and high_gap_count <= 1:
        proceed = False
        reason = "The topic does not show enough breakout evidence for the current competition level."
        confidence = "high"
        recommended_action = "Rework the topic before investing in production."
    elif high_gap_count >= 2 or small_channel_outliers >= 1:
        reason = "The topic still has breakout room if you lean into the uncovered angle."
        recommended_action = "Proceed, but lock into the clearest underused promise."
    elif similar_count <= 3 and top_score >= 1000:
        reason = "Competitor volume is still light enough to justify a test upload."
        recommended_action = "Proceed with a clear proof-driven package."

    return {
        "proceed": proceed,
        "reason": reason,
        "confidence": confidence,
        "recommended_action": recommended_action,
    }


def _entity_focus(entity_signals: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("entity", "")).strip() for item in entity_signals[:4] if item.get("entity")]


def _differentiation_plan(
    keyword_gaps: list[dict[str, Any]],
    competition: dict[str, Any],
    youtube_results: list[dict[str, Any]],
) -> dict[str, Any]:
    repeated_30_days = sum(1 for item in youtube_results if "30 days" in str(item.get("title", "")).lower())
    repeated_shocking = sum(1 for item in youtube_results if "shocking" in str(item.get("title", "")).lower())

    avoid_patterns: list[str] = []
    if repeated_30_days >= 2:
        avoid_patterns.append("Too many competitor titles lean on the same '30 days' structure.")
    if repeated_shocking >= 2:
        avoid_patterns.append("Curiosity words like 'shocking' are already heavily used in this pocket.")

    emphasis = [item["keyword"] for item in keyword_gaps[:3]]
    if not emphasis:
        emphasis = ["clearer outcome framing", "stronger specificity", "better retention promise"]

    recommendation = (
        "Lean into underused subtopics and a clearer promise."
        if competition.get("label") != "SATURATED"
        else "Differentiate by narrowing the angle and removing generic curiosity phrasing."
    )

    return {
        "recommendation": recommendation,
        "emphasize": emphasis,
        "avoid_patterns": avoid_patterns,
    }


def _opportunity_score(
    keyword_gaps: list[dict[str, Any]],
    competition: dict[str, Any],
    top_opportunities: list[dict[str, Any]],
) -> dict[str, Any]:
    top_outlier = float(top_opportunities[0].get("outlier_score") or 0) if top_opportunities else 0.0
    gap_bonus = min(len(keyword_gaps) * 12, 36)
    small_channel_bonus = min(
        sum(8 for item in top_opportunities[:3] if item.get("small_channel_outlier")),
        16,
    )
    competition_penalty = 30 if competition.get("label") == "SATURATED" else 15 if competition.get("label") == "COMPETITIVE" else 0

    score = min(round((top_outlier / 5000) + gap_bonus + small_channel_bonus - competition_penalty, 2), 100.0)
    score = max(score, 0.0)

    if score >= 60:
        label = "STRONG"
    elif score >= 35:
        label = "WORKABLE"
    else:
        label = "WEAK"

    return {
        "score": score,
        "label": label,
        "gap_bonus": gap_bonus,
        "small_channel_bonus": small_channel_bonus,
        "competition_penalty": competition_penalty,
    }


def _competitor_shadow(youtube_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not youtube_results:
        return {
            "similar_video_count": 0,
            "dominant_title_pattern": "unknown",
            "dominant_hook_pattern": "unknown",
            "recommended_differentiation": "Not enough competitor data yet.",
        }

    titles = [str(item.get("title", "")) for item in youtube_results]
    title_pattern_counts = {
        "experiment": sum(1 for title in titles if any(token in title.lower() for token in ["i tried", "i tested", "for 7 days", "for 30 days"])),
        "search": sum(1 for title in titles if any(token in title.lower() for token in ["how to", "guide", "tutorial"])),
        "curiosity": sum(1 for title in titles if any(token in title.lower() for token in ["shocking", "secret", "truth", "mistake"])),
    }
    dominant_title_pattern = max(title_pattern_counts, key=title_pattern_counts.get)

    hook_pattern_counts = {
        "first_person": sum(1 for title in titles if title.lower().startswith("i ")),
        "how_to": sum(1 for title in titles if title.lower().startswith("how to")),
        "question": sum(1 for title in titles if "?" in title),
    }
    dominant_hook_pattern = max(hook_pattern_counts, key=hook_pattern_counts.get)

    if dominant_title_pattern == "experiment":
        differentiation = "Keep the experiment angle, but narrow the promise or conflict so it does not blend into the same repeated challenge pattern."
    elif dominant_title_pattern == "search":
        differentiation = "Avoid generic tutorial phrasing and lead with a more specific or surprising outcome."
    else:
        differentiation = "Reduce generic curiosity phrasing and make the payoff more concrete."

    return {
        "similar_video_count": len(youtube_results),
        "dominant_title_pattern": dominant_title_pattern,
        "dominant_hook_pattern": dominant_hook_pattern,
        "recommended_differentiation": differentiation,
    }


def _format_lock_in(
    top_opportunities: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
    competition: dict[str, Any],
) -> dict[str, Any]:
    candidates = top_opportunities[:3] if top_opportunities else youtube_results[:3]
    if not candidates:
        return {
            "recommended_format": "unknown",
            "recommended_length": "unknown",
            "title_style": "unknown",
            "reason": "Not enough competitor data to lock a format.",
        }

    short_form_count = 0
    long_form_count = 0
    first_person_count = 0
    proof_count = 0

    for item in candidates:
        duration = str(item.get("duration") or "")
        title = str(item.get("title") or "").lower()
        if _is_short_form_duration(duration):
            short_form_count += 1
        else:
            long_form_count += 1
        if title.startswith("i "):
            first_person_count += 1
        if any(token in title for token in ["result", "truth", "worth it", "what happened", "mistake"]):
            proof_count += 1

    recommended_format = "short-form" if short_form_count > long_form_count else "long-form"
    recommended_length = "under 60s" if recommended_format == "short-form" else "6-12 minutes"
    title_style = "first-person proof" if first_person_count >= 2 else "outcome-led"
    if proof_count >= 2:
        title_style = f"{title_style} with clear payoff"

    if str(competition.get("label", "UNKNOWN")).upper() == "SATURATED":
        reason = "Competition is heavy, so the format should match proven behavior while the angle stays narrower."
    else:
        reason = "Competitor patterns are strong enough to guide packaging without forcing a copycat title."

    return {
        "recommended_format": recommended_format,
        "recommended_length": recommended_length,
        "title_style": title_style,
        "reason": reason,
    }


def _viability_verdict(
    opportunity_score: dict[str, Any],
    competition: dict[str, Any],
    idea_kill_switch: dict[str, Any],
    keyword_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    score_label = str(opportunity_score.get("label", "WEAK")).upper()
    competition_label = str(competition.get("label", "UNKNOWN")).upper()
    gap_count = len(keyword_gaps)
    proceed = bool(idea_kill_switch.get("proceed"))

    if proceed and score_label == "STRONG":
        status = "green"
        summary = "The idea is viable now. Focus on packaging and execution."
    elif proceed and (score_label == "WORKABLE" or gap_count >= 2):
        status = "yellow"
        summary = "The idea is workable, but only if you commit to a clearer differentiation angle."
    else:
        status = "red"
        summary = "The idea is not strong enough yet. Reframe it before publishing."

    if competition_label == "SATURATED" and proceed:
        summary = "The idea can still work, but only with a tighter promise and stronger packaging."

    return {
        "status": status,
        "summary": summary,
        "proceed": proceed,
    }


def _is_short_form_duration(duration: str) -> bool:
    if not duration:
        return False
    normalized = duration.strip().upper()
    if not normalized.startswith("PT"):
        return False
    return "M" not in normalized and "H" not in normalized
