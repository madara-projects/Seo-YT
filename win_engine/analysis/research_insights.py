"""Convert competitor results and a creator brief into a usable packaging decision."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_research_decision(
    creator_brief: dict[str, Any] | None,
    youtube_results: list[dict[str, Any]],
) -> dict[str, Any]:
    brief = creator_brief or {}
    titles = [str(item.get("title") or "") for item in youtube_results]
    pattern_counts = Counter(_title_pattern(title) for title in titles if title)
    repeated_patterns = [
        {"pattern": pattern.replace("_", " "), "count": count}
        for pattern, count in pattern_counts.most_common()
        if count >= 2 and pattern != "other"
    ]
    dominant = pattern_counts.most_common(1)[0][0].replace("_", " ") if pattern_counts else "no clear pattern"
    small_channel_winners = [
        {
            "title": item.get("title", ""),
            "channel": item.get("channel_title", ""),
            "views": item.get("view_count"),
        }
        for item in youtube_results
        if item.get("small_channel_outlier")
    ][:3]

    audience = str(brief.get("target_audience") or "the intended viewer").strip()
    promise = str(brief.get("viewer_promise") or "a specific, honest outcome").strip()
    unique_angle = str(brief.get("unique_angle") or brief.get("content") or "your real experience").strip()
    proof = str(brief.get("proof") or "the real footage or experience in the video").strip()

    recommended_angle = f"Lead with {unique_angle} for {audience}."
    reason = (
        f"Your differentiator is {proof}; make the viewer payoff ({promise}) explicit instead of copying the dominant {dominant} framing."
    )
    avoid = [f"Do not copy the dominant {dominant} title structure."] if titles else ["Research data is unavailable; keep the promise specific and evidence-based."]
    if repeated_patterns:
        avoid.append("Avoid repeated competitor patterns: " + ", ".join(item["pattern"] for item in repeated_patterns) + ".")

    return {
        "recommended_angle": recommended_angle,
        "reason": reason,
        "dominant_competitor_pattern": dominant,
        "repeated_title_patterns": repeated_patterns,
        "small_channel_winners": small_channel_winners,
        "avoid": avoid,
        "confidence": "high" if len(youtube_results) >= 8 else "medium" if youtube_results else "low",
    }


def _title_pattern(title: str) -> str:
    lowered = title.lower().strip()
    if lowered.startswith("how to") or any(token in lowered for token in ("tutorial", "guide", "tips")):
        return "search tutorial"
    if lowered.startswith("i ") or any(token in lowered for token in ("my day", "vlog", "routine")):
        return "first person story"
    if any(token in lowered for token in ("truth", "secret", "mistake", "shocking")):
        return "curiosity"
    if any(token in lowered for token in ("7 days", "30 days", "challenge", "tried")):
        return "experiment"
    return "other"
