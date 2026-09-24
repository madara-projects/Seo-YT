from __future__ import annotations

from typing import Any


def build_thumbnail_strategy(
    thumbnail_intelligence: dict[str, Any],
    title: str,
    content_angle: str,
    *,
    quote_short: bool = False,
    video_format: str = "",
) -> dict[str, Any]:
    """Classify a likely thumbnail style and suggest a baseline direction."""

    quality_counts = thumbnail_intelligence.get("quality_counts", {})
    high_quality = int(quality_counts.get("high", 0))
    maxres = int(quality_counts.get("maxres", 0))
    lower_title = title.lower()
    sample_size = int(thumbnail_intelligence.get("sample_size") or sum(int(v or 0) for v in quality_counts.values()))
    strength = "strong" if (high_quality + maxres) >= 3 else "average" if sample_size else "unknown"

    if quote_short:
        # Every quote Short used to be classed "instructional_thumbnail".
        return {
            "style": "quote_frame",
            "competitive_strength": strength,
            "recommendation": (
                "Use a frame where the full quote is legible over the background, with strong contrast "
                "and no extra text; the line itself is the hook."
            ),
        }

    fmt = video_format.casefold()
    # The format decides first: a phone review, a travel vlog and a comparison
    # were all "instructional_thumbnail" before.
    if "vlog" in fmt or "travel" in fmt:
        return {
            "style": "scene_thumbnail",
            "competitive_strength": strength,
            "recommendation": "Use the most striking real frame (the view or the moment), your face if you are in it, and at most three words.",
        }
    if "comparison" in fmt or " vs " in f" {lower_title} ":
        return {
            "style": "comparison_thumbnail",
            "competitive_strength": strength,
            "recommendation": "Show both options side by side with a one-word label each and a clear visual winner or question.",
        }
    if content_angle == "Experiment" or "review" in fmt or "tested" in lower_title or "tried" in lower_title:
        style = "proof_thumbnail"
    elif any(term in lower_title for term in ["why", "secret", "mistake", "shocking"]):
        style = "curiosity_thumbnail"
    else:
        style = "instructional_thumbnail"

    if style == "proof_thumbnail":
        recommendation = "Use before/after numbers, a reaction face, and one proof element from the experiment."
    elif style == "curiosity_thumbnail":
        recommendation = "Use a high-contrast focal object with minimal text and a clear emotional expression."
    else:
        recommendation = "Use a clean topic label, one visual object, and enough contrast to stay readable on mobile."

    return {
        "style": style,
        "competitive_strength": strength,
        "recommendation": recommendation,
    }
