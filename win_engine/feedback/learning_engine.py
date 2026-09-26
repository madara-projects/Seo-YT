from __future__ import annotations

from typing import Any

def build_feedback_package(
    seo_package: dict[str, Any],
    research: dict[str, Any],
    learning_summary: dict[str, Any],
    internal_scorecard: dict[str, Any],
) -> dict[str, Any]:
    """Build feedback signals from the generated package and stored history."""

    scored_variants = seo_package.get("title_optimization", {}).get("scored_variants", [])
    best_variant = scored_variants[0] if scored_variants else {"title": seo_package["title"], "score": 0}
    winning_titles = learning_summary.get("winning_titles", [])
    angle_effectiveness = learning_summary.get("angle_effectiveness", [])

    ctr_prediction = _ctr_prediction(best_variant, seo_package)
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


def _ctr_prediction(
    best_variant: dict[str, Any],
    seo_package: dict[str, Any],
) -> dict[str, Any]:
    """Return honest pre-publication guidance without claiming measured CTR."""
    quality_score = round(float(best_variant.get("score") or 0), 1)
    return {
        "label": "STRONG" if quality_score >= 8 else "WORKABLE" if quality_score >= 6 else "WEAK",
        "title_quality_score": quality_score,
        "actual_ctr_percent": None,
        "confidence": "PRE-PUBLICATION",
        "expected_band": "Actual CTR requires linked YouTube Analytics impressions.",
        "reason": "Title quality heuristic only; this is not a CTR prediction.",
    }


# A "recurring" pattern needs recurrence: one earlier run is not a pattern.
_MIN_RUNS_FOR_PATTERN = 5
_MIN_RUNS_PER_ANGLE = 3


def _winning_patterns(
    angle_effectiveness: list[dict[str, Any]],
    winning_titles: list[dict[str, Any]],
) -> dict[str, Any]:
    total_runs = sum(int(row.get("run_count") or 0) for row in angle_effectiveness)
    # The list is ordered by average score, so a one-run angle can top it; it
    # is skipped rather than allowed to hide the best angle that has recurred.
    leader = next(
        (row for row in angle_effectiveness if int(row.get("run_count") or 0) >= _MIN_RUNS_PER_ANGLE), None
    )
    if total_runs < _MIN_RUNS_FOR_PATTERN or leader is None:
        return {
            "best_angle_so_far": "UNKNOWN",
            "best_title_so_far": "",
            "sample_size": total_runs,
            "observation": (
                f"Not enough history yet to identify a winning angle ({total_runs} analysed run(s); "
                f"at least {_MIN_RUNS_FOR_PATTERN} are needed, with {_MIN_RUNS_PER_ANGLE} for the leading angle)."
            ),
        }
    best_angle = leader["content_angle"]
    return {
        "best_angle_so_far": best_angle,
        "best_title_so_far": winning_titles[0]["title"] if winning_titles else "",
        "sample_size": total_runs,
        "observation": (
            f"Across {total_runs} analysed runs, {best_angle} has the highest average local title score "
            f"among angles used at least {_MIN_RUNS_PER_ANGLE} times. "
            "This compares packaging scores, not published performance."
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
    # A result without an outlier score is unmeasured; counting it as 0 would drag the average down.
    outlier_scores = [
        float(item["outlier_score"]) for item in youtube_results[:5] if item.get("outlier_score") is not None
    ]
    current_score = 0.0
    scored_variants = seo_package.get("title_optimization", {}).get("scored_variants", [])
    if scored_variants:
        current_score = float(scored_variants[0].get("score") or 0)
    baseline = _history_average(internal_scorecard, "avg_title_score")
    return {
        "top_competitor_views": top_views,
        "average_outlier_score": round(sum(outlier_scores) / len(outlier_scores), 2) if outlier_scores else None,
        "snapshot_count": len(youtube_results),
        "current_title_score": round(current_score, 2),
        "historical_title_score_avg": baseline,
        "title_score_vs_history": round(current_score - baseline, 2) if baseline is not None else None,
    }


def _historical_comparison(
    best_variant: dict[str, Any],
    seo_package: dict[str, Any],
    internal_scorecard: dict[str, Any],
) -> dict[str, Any]:
    current_title_score = round(float(best_variant.get("score") or 0), 2)
    raw_opportunity = seo_package.get("opportunity_gap_analysis", {}).get("opportunity_score", {}).get("score")
    # An unmeasured opportunity (no competitor data) is not a score of 0.
    current_opportunity_score = round(float(raw_opportunity), 2) if raw_opportunity is not None else None
    avg_title_score = _history_average(internal_scorecard, "avg_title_score")
    avg_opportunity_score = _history_average(internal_scorecard, "avg_opportunity_score")

    return {
        "title_score_vs_average": (
            round(current_title_score - avg_title_score, 2) if avg_title_score is not None else None
        ),
        "opportunity_score_vs_average": (
            round(current_opportunity_score - avg_opportunity_score, 2)
            if current_opportunity_score is not None and avg_opportunity_score is not None
            else None
        ),
        "summary": _comparison_summary(
            current_title_score=current_title_score,
            avg_title_score=avg_title_score,
            current_opportunity_score=current_opportunity_score,
            avg_opportunity_score=avg_opportunity_score,
            total_runs=int(internal_scorecard.get("total_runs") or 0),
        ),
    }


def _history_average(internal_scorecard: dict[str, Any], key: str) -> float | None:
    """An average over earlier runs, or None when there are none: no history is not a score of 0."""
    value = internal_scorecard.get(key)
    if value is None or not int(internal_scorecard.get("total_runs") or 0):
        return None
    return round(float(value), 2)


def _comparison_summary(
    current_title_score: float,
    avg_title_score: float | None,
    current_opportunity_score: float | None,
    avg_opportunity_score: float | None,
    total_runs: int,
) -> str:
    if total_runs < 3 or avg_title_score is None:
        return "The engine is still collecting history, so comparisons are directional rather than stable."
    if current_opportunity_score is None or avg_opportunity_score is None:
        side = "above" if current_title_score >= avg_title_score else "below"
        missing = "was not measured for this run" if current_opportunity_score is None else "has no earlier measurements"
        return f"Packaging is scoring {side} your recent average; opportunity {missing}."
    if current_title_score >= avg_title_score and current_opportunity_score >= avg_opportunity_score:
        return "This analysis is scoring above your recent average on both packaging and opportunity."
    if current_title_score < avg_title_score and current_opportunity_score < avg_opportunity_score:
        return "This analysis is weaker than your recent average and may need a stronger angle or title."
    return "This analysis is mixed versus your recent average: one side is stronger, the other needs work."
