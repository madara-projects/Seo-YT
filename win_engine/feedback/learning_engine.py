from __future__ import annotations

from typing import Any


def build_feedback_package(
    seo_package: dict[str, Any],
    research: dict[str, Any],
    learning_summary: dict[str, Any],
    internal_scorecard: dict[str, Any],
) -> dict[str, Any]:
    """Build Phase 5 feedback signals from generated package and stored history."""

    scored_variants = seo_package.get("title_optimization", {}).get("scored_variants", [])
    best_variant = scored_variants[0] if scored_variants else {"title": seo_package["title"], "score": 0}
    winning_titles = learning_summary.get("winning_titles", [])
    angle_effectiveness = learning_summary.get("angle_effectiveness", [])

    ctr_prediction = _ctr_prediction(best_variant)
    winning_patterns = _winning_patterns(angle_effectiveness, winning_titles)
    ab_test_pack = _ab_test_pack(scored_variants, seo_package["title"])
    performance_sync = _performance_sync(research, seo_package, internal_scorecard)
    historical_comparison = _historical_comparison(best_variant, seo_package, internal_scorecard)

    return {
        "performance_sync": performance_sync,
        "learning_engine": {
            "current_angle": seo_package["content_angle"],
            "angle_effectiveness": angle_effectiveness,
            "retention_pattern": learning_summary.get("retention_pattern", []),
            "recent_runs": learning_summary.get("recent_runs", []),
        },
        "winning_patterns": winning_patterns,
        "ctr_prediction": ctr_prediction,
        "ab_test_pack": ab_test_pack,
        "internal_scorecard": internal_scorecard,
        "historical_comparison": historical_comparison,
    }


def _ctr_prediction(best_variant: dict[str, Any]) -> dict[str, Any]:
    score = float(best_variant.get("score") or 0)
    if score >= 10:
        label = "HIGH"
        confidence = "strong"
    elif score >= 7:
        label = "MEDIUM"
        confidence = "moderate"
    else:
        label = "LOW"
        confidence = "early"

    return {
        "label": label,
        "score": round(score, 2),
        "confidence": confidence,
        "expected_band": _expected_ctr_band(label),
        "reason": "Derived from title length, power words, curiosity markers, and topic coverage.",
    }


def _expected_ctr_band(label: str) -> str:
    if label == "HIGH":
        return "above recent baseline"
    if label == "MEDIUM":
        return "around recent baseline"
    return "below recent baseline"


def _winning_patterns(
    angle_effectiveness: list[dict[str, Any]],
    winning_titles: list[dict[str, Any]],
) -> dict[str, Any]:
    best_angle = angle_effectiveness[0]["content_angle"] if angle_effectiveness else "UNKNOWN"
    best_title = winning_titles[0]["title"] if winning_titles else ""
    return {
        "best_angle_so_far": best_angle,
        "best_title_so_far": best_title,
        "observation": (
            f"The strongest recurring angle so far is {best_angle}."
            if best_angle != "UNKNOWN"
            else "Not enough history yet to identify a dominant winning angle."
        ),
    }


def _ab_test_pack(scored_variants: list[dict[str, Any]], fallback_title: str) -> dict[str, str]:
    if len(scored_variants) >= 2:
        return {
            "variation_a": scored_variants[0]["title"],
            "variation_b": scored_variants[1]["title"],
        }
    return {
        "variation_a": fallback_title,
        "variation_b": fallback_title,
    }


def _performance_sync(
    research: dict[str, Any],
    seo_package: dict[str, Any],
    internal_scorecard: dict[str, Any],
) -> dict[str, Any]:
    youtube_results = research.get("youtube_results", [])
    top_views = max((int(item.get("view_count") or 0) for item in youtube_results), default=0)
    avg_outlier = (
        sum(float(item.get("outlier_score") or 0) for item in youtube_results[:5]) / max(len(youtube_results[:5]), 1)
        if youtube_results
        else 0.0
    )
    current_score = 0.0
    scored_variants = seo_package.get("title_optimization", {}).get("scored_variants", [])
    if scored_variants:
        current_score = float(scored_variants[0].get("score") or 0)
    baseline = float(internal_scorecard.get("avg_title_score") or 0)
    return {
        "top_competitor_views": top_views,
        "average_outlier_score": round(avg_outlier, 2),
        "snapshot_count": len(youtube_results),
        "current_title_score": round(current_score, 2),
        "historical_title_score_avg": round(baseline, 2),
        "title_score_vs_history": round(current_score - baseline, 2),
    }


def _historical_comparison(
    best_variant: dict[str, Any],
    seo_package: dict[str, Any],
    internal_scorecard: dict[str, Any],
) -> dict[str, Any]:
    current_title_score = round(float(best_variant.get("score") or 0), 2)
    current_opportunity_score = round(
        float(seo_package.get("opportunity_gap_analysis", {}).get("opportunity_score", {}).get("score") or 0),
        2,
    )
    avg_title_score = round(float(internal_scorecard.get("avg_title_score") or 0), 2)
    avg_opportunity_score = round(float(internal_scorecard.get("avg_opportunity_score") or 0), 2)

    return {
        "title_score_vs_average": round(current_title_score - avg_title_score, 2),
        "opportunity_score_vs_average": round(current_opportunity_score - avg_opportunity_score, 2),
        "summary": _comparison_summary(
            current_title_score=current_title_score,
            avg_title_score=avg_title_score,
            current_opportunity_score=current_opportunity_score,
            avg_opportunity_score=avg_opportunity_score,
            total_runs=int(internal_scorecard.get("total_runs") or 0),
        ),
    }


def _comparison_summary(
    current_title_score: float,
    avg_title_score: float,
    current_opportunity_score: float,
    avg_opportunity_score: float,
    total_runs: int,
) -> str:
    if total_runs < 3:
        return "The engine is still collecting history, so comparisons are directional rather than stable."
    if current_title_score >= avg_title_score and current_opportunity_score >= avg_opportunity_score:
        return "This analysis is scoring above your recent average on both packaging and opportunity."
    if current_title_score < avg_title_score and current_opportunity_score < avg_opportunity_score:
        return "This analysis is weaker than your recent average and may need a stronger angle or title."
    return "This analysis is mixed versus your recent average: one side is stronger, the other needs work."
