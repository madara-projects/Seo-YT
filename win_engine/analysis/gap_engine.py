from __future__ import annotations

import math
from typing import Any

from win_engine.ai_enhancement import find_content_similarity
from win_engine.analysis.dynamic_thresholds import get_dynamic_kill_switch
from win_engine.analysis.numbers import optional_number
from win_engine.analysis.source_cues import is_short_duration
from win_engine.core.iso_duration import duration_seconds


def analyze_opportunity_gaps(
    keyword_signals: list[dict[str, Any]],
    entity_signals: list[dict[str, Any]],
    youtube_results: list[dict[str, Any]],
    top_opportunities: list[dict[str, Any]],
    language_context: dict[str, Any] | None = None,
    target_title: str = "",
) -> dict[str, Any]:
    """Build gap analysis and opportunity heuristics."""

    language_context = language_context or {}
    keyword_gaps = _keyword_gaps(keyword_signals, youtube_results)
    competition = _competition_meter(youtube_results, language_context)
    idea_kill_switch = get_dynamic_kill_switch(
        top_opportunities=top_opportunities,
        competition=competition,
        keyword_gaps=keyword_gaps,
    )

    # Uniqueness = how different the chosen title is from the top competitor
    # titles (1.0 = fully distinct, 0.0 = near-duplicate), by word overlap
    # (Jaccard), not a model. With nothing to compare it is unknown; a fixed
    # 0.5 used to stand in for it.
    uniqueness_score = None
    competitor_titles = [
        str(item.get("title", "")).strip()
        for item in (youtube_results or [])[:5]
        if isinstance(item, dict) and item.get("title")
    ]
    if target_title and competitor_titles:
        uniqueness_score = round(1.0 - max(find_content_similarity(target_title, c) for c in competitor_titles), 3)

    differentiation = _differentiation_plan(keyword_gaps, competition, youtube_results)
    opportunity_score = _opportunity_score(keyword_gaps, competition, top_opportunities)
    format_lock = _format_lock_in(top_opportunities, youtube_results, competition)
    viability_verdict = _viability_verdict(opportunity_score, competition, idea_kill_switch, keyword_gaps)
    if not youtube_results:
        # Without competitor results the score was 25 from "empty competition"
        # alone, labelled WEAK, beside a kill switch saying "strong enough to
        # keep pursuing". Neither was measured; say so instead.
        unmeasured = "No competitor results were available, so demand and competition could not be measured."
        opportunity_score = {**opportunity_score, "score": None, "label": "UNMEASURED", "confidence": "NONE",
                             "measured": False, "reason": unmeasured}
        idea_kill_switch = {**idea_kill_switch, "proceed": True, "status": "insufficient_evidence",
                            "reason": unmeasured + " This is not a verdict on the idea.", "confidence": "none",
                            "recommended_action": "Re-run research when YouTube results are available before making a go/no-go call."}
        viability_verdict = {"status": "unknown", "proceed": True,
                             "summary": "Viability could not be judged without public YouTube results."}

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
    # A hidden or unfetched subscriber count is unknown, not a small channel.
    subscriber_counts = [optional_number(item.get("subscriber_count")) for item in youtube_results]
    big_channel_count = sum(1 for count in subscriber_counts if count is not None and count >= 250000)
    unknown_channel_sizes = sum(1 for count in subscriber_counts if count is None)
    outlier_scores = [
        score for item in youtube_results[:5] if (score := optional_number(item.get("outlier_score"))) is not None
    ]

    score = (repeated_title_patterns * 20) + (big_channel_count * 15)
    if outlier_scores:
        average_outlier = sum(outlier_scores) / len(outlier_scores)
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
    if unknown_channel_sizes:
        reason += f" Channel size was unavailable for {unknown_channel_sizes} result(s), so large channels may be undercounted."

    return {
        "score": round(score, 2),
        "label": label,
        "reason": reason,
        "confidence": "low",
        "evidence_state": "heuristic",
        "basis": (
            f"Counts of '30 days' titles and 250K+ subscriber channels in {len(youtube_results)} sampled "
            "results, plus the average outlier score of the first five; not a measurement of market size or demand."
        ),
        "repeated_title_patterns": repeated_title_patterns,
        "big_channel_count": big_channel_count,
        "unknown_channel_size_count": unknown_channel_sizes,
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
    opportunities = [item for item in top_opportunities[:3] if isinstance(item, dict)]
    # An unmeasured velocity is left out rather than averaged in as zero.
    velocity_scores = [
        min(100.0, 25.0 * math.log10(1.0 + max(views_per_day, 0.0)))
        for item in opportunities
        if (views_per_day := optional_number(item.get("views_per_day"))) is not None
    ]
    demand_score = sum(velocity_scores) / len(velocity_scores) if velocity_scores else 0.0
    gap_score = min((len(keyword_gaps) / 6.0) * 100.0, 100.0)
    competition_score = min(max(float(competition.get("score") or 0), 0.0), 100.0)
    competition_room = 100.0 - competition_score
    breakout_score = (
        sum(1 for item in opportunities if item.get("small_channel_outlier")) / len(opportunities) * 100.0
        if opportunities else 0.0
    )
    relevance_score = (
        sum(min(len(item.get("matched_queries") or []) / 3.0, 1.0) for item in opportunities)
        / len(opportunities) * 100.0
        if opportunities else 0.0
    )

    score = round(
        (demand_score * 0.35)
        + (competition_room * 0.25)
        + (gap_score * 0.20)
        + (breakout_score * 0.10)
        + (relevance_score * 0.10),
        2,
    )
    score = min(max(score, 0.0), 100.0)

    if score >= 70:
        label = "STRONG"
    elif score >= 45:
        label = "WORKABLE"
    else:
        label = "WEAK"

    confidence = "HIGH" if len(opportunities) >= 3 and relevance_score >= 50 else "MEDIUM" if len(opportunities) >= 2 else "LOW"

    return {
        "score": score,
        "label": label,
        "confidence": confidence,
        "reason": "Weighted from current view velocity, competition room, keyword gaps, small-channel breakouts, and research relevance.",
        "components": {
            "demand_velocity": round(demand_score, 2),
            "competition_room": round(competition_room, 2),
            "keyword_gap": round(gap_score, 2),
            "small_channel_breakout": round(breakout_score, 2),
            "research_relevance": round(relevance_score, 2),
        },
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
    unknown_duration_count = 0
    first_person_count = 0
    proof_count = 0

    for item in candidates:
        is_short = is_short_duration(duration_seconds(item.get("duration")))
        title = str(item.get("title") or "").lower()
        # Live, upcoming and unfetched videos have no length to vote with;
        # they used to count as long-form and lock "6-12 minutes". A Short is
        # up to three minutes, as everywhere else; a 60-second cut called a
        # 90-second Short long-form.
        if is_short is None:
            unknown_duration_count += 1
        elif is_short:
            short_form_count += 1
        else:
            long_form_count += 1
        if title.startswith("i "):
            first_person_count += 1
        if any(token in title for token in ["result", "truth", "worth it", "what happened", "mistake"]):
            proof_count += 1

    if short_form_count or long_form_count:
        recommended_format = "short-form" if short_form_count > long_form_count else "long-form"
        recommended_length = "3 minutes or less" if recommended_format == "short-form" else "6-12 minutes"
    else:
        recommended_format = recommended_length = "unknown"
    title_style = "first-person proof" if first_person_count >= 2 else "outcome-led"
    if proof_count >= 2:
        title_style = f"{title_style} with clear payoff"

    if recommended_format == "unknown":
        reason = "None of the compared videos had a known duration, so no format or length is locked."
    elif str(competition.get("label", "UNKNOWN")).upper() == "SATURATED":
        reason = "Competition is heavy, so the format should match proven behavior while the angle stays narrower."
    else:
        reason = "Competitor patterns are strong enough to guide packaging without forcing a copycat title."
    if unknown_duration_count and recommended_format != "unknown":
        reason += f" {unknown_duration_count} compared video(s) had no known duration and were left out of the format vote."

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
