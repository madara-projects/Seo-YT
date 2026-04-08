from __future__ import annotations

from typing import Any


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
    idea_kill_switch = _idea_kill_switch(top_opportunities, competition)
    differentiation = _differentiation_plan(keyword_gaps, competition, youtube_results)
    opportunity_score = _opportunity_score(keyword_gaps, competition, top_opportunities)

    return {
        "keyword_gaps": keyword_gaps,
        "competition": competition,
        "idea_kill_switch": idea_kill_switch,
        "entity_focus": _entity_focus(entity_signals),
        "differentiation": differentiation,
        "opportunity_score": opportunity_score,
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


def _idea_kill_switch(top_opportunities: list[dict[str, Any]], competition: dict[str, Any]) -> dict[str, Any]:
    top_score = float(top_opportunities[0].get("outlier_score") or 0) if top_opportunities else 0.0
    competition_label = competition.get("label", "UNKNOWN")

    proceed = True
    reason = "Opportunity is strong enough to keep pursuing."

    if top_score < 500 and competition_label == "SATURATED":
        proceed = False
        reason = "Weak outlier signal plus saturated competition makes this a poor bet."
    elif top_score < 2000 and competition_label == "COMPETITIVE":
        proceed = False
        reason = "The topic does not show enough breakout evidence for the current competition level."

    return {
        "proceed": proceed,
        "reason": reason,
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
    competition_penalty = 30 if competition.get("label") == "SATURATED" else 15 if competition.get("label") == "COMPETITIVE" else 0

    score = min(round((top_outlier / 5000) + gap_bonus - competition_penalty, 2), 100.0)
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
    }
