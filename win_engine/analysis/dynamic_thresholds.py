"""Go/no-go heuristic for an idea, read from the sampled competitor research.

The thresholds are fixed defaults. Nothing supplies historical results or a
niche, so the per-niche calibration this module once carried never ran; the
defaults below are all it has ever used.
"""

from __future__ import annotations

from typing import Any

from win_engine.analysis.numbers import optional_number


# A top outlier score below this is a weak breakout signal.
_OUTLIER_THRESHOLD = 800
# Underserved pockets are easier to win and saturated ones harder.
_COMPETITION_MULTIPLIER = {"UNDERSERVED": 0.6, "COMPETITIVE": 1.0, "SATURATED": 1.5}
# High-gap keywords needed before the gaps alone justify proceeding.
_MIN_HIGH_GAPS = 2


def get_dynamic_kill_switch(
    top_opportunities: list[dict[str, Any]],
    competition: dict[str, Any],
    keyword_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a publish recommendation from current research signals.

    Every input is a small-sample heuristic (at most a few dozen results,
    simple title and channel-size counts), so confidence is never above low.
    """

    competition_label = competition.get("label", "UNKNOWN")
    outlier_threshold = _OUTLIER_THRESHOLD * _COMPETITION_MULTIPLIER.get(competition_label, 1.0)
    gap_threshold = _MIN_HIGH_GAPS
    # An unmeasured top score is not a weak one; the outlier rules skip it.
    top_score = optional_number(top_opportunities[0].get("outlier_score")) if top_opportunities else None
    small_channel_outliers = sum(1 for item in top_opportunities if item.get("small_channel_outlier"))
    high_gap_count = sum(1 for item in keyword_gaps if item.get("gap_strength") == "high")

    proceed = True
    reason = "Opportunity is strong enough to keep pursuing."
    recommended_action = "Proceed with a differentiated angle."

    if (
        top_score is not None
        and top_score < outlier_threshold
        and competition_label == "SATURATED"
        and high_gap_count == 0
    ):
        proceed = False
        reason = "Weak outlier signal plus saturated competition leaves no room."
        recommended_action = "Kill this idea or re-scope into a narrower subtopic."
    # Fewer gaps than the proceed threshold: at the threshold itself the gaps
    # justify proceeding, which the rule below says.
    elif (
        top_score is not None
        and top_score < (outlier_threshold * 0.8)
        and competition_label == "COMPETITIVE"
        and small_channel_outliers == 0
        and high_gap_count < gap_threshold
    ):
        proceed = False
        reason = "Topic lacks breakout evidence for current competition level."
        recommended_action = "Rework the topic before investing in production."
    elif high_gap_count >= gap_threshold or small_channel_outliers >= 2:
        reason = "Topic has breakout room if you lean into uncovered angles."
        recommended_action = "Proceed, but lock into clearest underused promise."
    elif competition_label == "UNDERSERVED":
        reason = "Few large channels or repeated title patterns appeared in the sampled results."
        recommended_action = "Proceed with a differentiated angle; the competition read comes from a small sample."

    return {
        "proceed": proceed,
        "reason": reason,
        "confidence": "low",
        "evidence_state": "heuristic",
        "recommended_action": recommended_action,
        "thresholds_used": {
            "outlier_threshold": outlier_threshold,
            "gap_threshold": gap_threshold,
        },
    }
