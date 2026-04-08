from __future__ import annotations

from typing import Any


def analyze_thumbnails(youtube_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Basic thumbnail intelligence from available metadata."""

    quality_counts = {"maxres": 0, "high": 0, "medium": 0, "default": 0}
    low_resolution_count = 0

    for result in youtube_results:
        thumbnails = result.get("thumbnails", {}) or {}
        for quality in quality_counts:
            if quality in thumbnails:
                quality_counts[quality] += 1

        best_thumb = thumbnails.get("maxres") or thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default")
        width = int((best_thumb or {}).get("width") or 0)
        if width and width < 480:
            low_resolution_count += 1

    recommendation = (
        "Most competing videos have usable thumbnail resolution. Focus on contrast, face/emotion, and short text."
        if quality_counts["high"] or quality_counts["maxres"]
        else "Competitor thumbnails skew low-resolution. A sharp, high-contrast thumbnail can stand out quickly."
    )

    return {
        "quality_counts": quality_counts,
        "low_resolution_count": low_resolution_count,
        "recommendation": recommendation,
    }
