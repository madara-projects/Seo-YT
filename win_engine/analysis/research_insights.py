"""Convert competitor results and a creator brief into a usable packaging decision."""

from __future__ import annotations

from collections import Counter
import re
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

    quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "").strip()
    visual = str(brief.get("visual_requirements") or "").strip(" .")
    audience = str(brief.get("target_audience") or "viewers who relate to the emotion").strip()
    promise = str(brief.get("viewer_promise") or "a brief moment of emotional recognition").strip()
    unique_angle = str(brief.get("unique_angle") or "").strip()
    proof = str(brief.get("proof") or visual or "the creator-supplied video").strip()

    if quote:
        core = "silence and private thoughts" if re.search(r"\bsilence\b", quote, re.IGNORECASE) else "the exact emotional idea in the quote"
        recommended_angle = f"Center the package on {core} for {audience}."
    else:
        topic = str(brief.get("topic") or "the supplied topic").strip()
        recommended_angle = f"Lead with {unique_angle or topic} for {audience}."
    reason = f"Use {proof} to deliver {promise}, without copying competitor wording or adding an unsupported story."
    avoid = [f"Do not copy the dominant {dominant} title structure."] if titles else ["Research data is unavailable; keep the promise specific and evidence-based."]
    if repeated_patterns:
        avoid.append("Avoid repeated competitor patterns: " + ", ".join(item["pattern"] for item in repeated_patterns) + ".")

    relevance_scores = [int(item.get("research_relevance_score") or 0) for item in youtube_results]
    average_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
    multi_term_evidence = sum(
        1 for item in youtube_results
        if len(item.get("research_relevance_terms") or []) >= 2
    )
    confidence = (
        "high" if len(youtube_results) >= 8 and average_relevance >= 75 and multi_term_evidence >= 5
        else "medium" if len(youtube_results) >= 5 and average_relevance >= 55 and multi_term_evidence >= 2
        else "low"
    )

    return {
        "recommended_angle": recommended_angle,
        "reason": reason,
        "dominant_competitor_pattern": dominant,
        "repeated_title_patterns": repeated_patterns,
        "small_channel_winners": small_channel_winners,
        "avoid": avoid,
        "confidence": confidence,
        "evidence_count": len(youtube_results),
        "multi_term_evidence_count": multi_term_evidence,
        "average_relevance_score": round(average_relevance, 1),
        "evidence_scope": "sampled_youtube_results_not_search_volume",
        "search_volume_available": False,
        "confidence_note": "Confidence describes relevance within the sampled API results, not keyword demand or guaranteed reach.",
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
