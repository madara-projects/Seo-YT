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

    # With no competitor results there is nothing to compare against; the old
    # fallback branch claimed "competitor thumbnails skew low-resolution" from zero.
    if not youtube_results:
        recommendation = (
            "No competitor thumbnails were available for this run, so there is no comparison to report. "
            "Use a sharp, high-contrast image with little or no text."
        )
    elif low_resolution_count * 2 > len(youtube_results):
        recommendation = "Competitor thumbnails skew low-resolution. A sharp, high-contrast thumbnail can stand out quickly."
    else:
        # Search results list the same default, medium and high sizes for
        # every video, so their presence says nothing about how strong the
        # thumbnails are. Missing metadata used to read as "low-resolution".
        recommendation = (
            "Thumbnail metadata only lists the standard sizes YouTube provides, so it cannot show how strong "
            "competing thumbnails are. Focus on contrast, face/emotion, and short text."
        )

    return {
        "quality_counts": quality_counts,
        "low_resolution_count": low_resolution_count,
        "sample_size": len(youtube_results),
        "recommendation": recommendation,
    }
