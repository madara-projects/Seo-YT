from __future__ import annotations

from typing import Any


def build_thumbnail_strategy(
    thumbnail_intelligence: dict[str, Any],
    title: str,
    content_angle: str,
) -> dict[str, Any]:
    """Classify a likely thumbnail style and suggest a baseline direction."""

    quality_counts = thumbnail_intelligence.get("quality_counts", {})
    high_quality = int(quality_counts.get("high", 0))
    maxres = int(quality_counts.get("maxres", 0))
    lower_title = title.lower()

    if content_angle == "Experiment" or "tested" in lower_title or "tried" in lower_title:
        style = "proof_thumbnail"
    elif any(term in lower_title for term in ["why", "secret", "mistake", "shocking"]):
        style = "curiosity_thumbnail"
    else:
        style = "instructional_thumbnail"

    strength = "strong" if (high_quality + maxres) >= 3 else "average"

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
