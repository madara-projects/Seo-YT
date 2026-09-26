from __future__ import annotations

import re
from typing import Any

from win_engine.analysis.source_cues import is_short_video, source_quote


def analyze_script_pacing(script: str, video_format: str = "", exact_quote: str = "") -> dict[str, Any]:
    """Analyze spoken-script pacing or quote-Short readability as appropriate."""

    format_brief = {"video_format": video_format}
    quote = exact_quote.strip() or source_quote(script, format_brief)
    if quote and is_short_video(script, format_brief):
        quote_words = re.findall(r"\b[\w'’]+\b", quote)
        word_count = len(quote_words)
        reading_seconds = max(3, round(word_count / 2.8))
        return {
            "analysis_type": "quote_short",
            "pace_label": "reflective",
            "avg_sentence_length": word_count,
            "hook_density": "single emotional hook",
            "pattern_interrupts": 1,
            "recommended_read_time_seconds": reading_seconds,
            "recommendation": (
                f"Show the quote within the first second, keep it readable for about "
                f"{reading_seconds}-{reading_seconds + 2} seconds, use strong text contrast, "
                "and end on a clean visual or audio loop. Multiple curiosity turns are not needed."
            ),
        }

    cleaned = re.sub(r"\s+", " ", script).strip()
    sentences = [part.strip() for part in re.split(r"[.!?]+", cleaned) if part.strip()]
    words = re.findall(r"\b[\w']+\b", cleaned)

    if not sentences:
        return {
            "analysis_type": "spoken_script",
            "pace_label": "unknown",
            "avg_sentence_length": 0,
            "hook_density": "low",
            "pattern_interrupts": 0,
            "recommendation": "Add clearer sentences and stronger hook transitions.",
        }

    avg_sentence_length = round(len(words) / max(len(sentences), 1), 2)
    hook_terms = [
        "but",
        "however",
        "instead",
        "because",
        "then",
        "now",
        "first",
        "next",
        "finally",
        "surprising",
        "mistake",
        "secret",
    ]
    interrupt_terms = [
        "but",
        "however",
        "instead",
        "suddenly",
        "then",
        "here's",
        "watch",
        "now",
    ]
    hook_count = sum(cleaned.lower().count(term) for term in hook_terms)
    pattern_interrupts = sum(cleaned.lower().count(term) for term in interrupt_terms)

    if avg_sentence_length <= 14:
        pace_label = "fast"
    elif avg_sentence_length <= 22:
        pace_label = "balanced"
    else:
        pace_label = "slow"

    if hook_count >= 8:
        hook_density = "high"
    elif hook_count >= 4:
        hook_density = "medium"
    else:
        hook_density = "low"

    recommendation = _pacing_recommendation(
        pace_label=pace_label,
        hook_density=hook_density,
        pattern_interrupts=pattern_interrupts,
    )

    return {
        "analysis_type": "spoken_script",
        "pace_label": pace_label,
        "avg_sentence_length": avg_sentence_length,
        "hook_density": hook_density,
        "pattern_interrupts": pattern_interrupts,
        "recommendation": recommendation,
    }


def _pacing_recommendation(pace_label: str, hook_density: str, pattern_interrupts: int) -> str:
    if pace_label == "slow":
        return "Shorten sentences and add more transitions so the opening feels easier to follow."
    if hook_density == "low":
        return "Add more curiosity turns, contrast words, and mini-payoffs across the script."
    if pattern_interrupts < 3:
        return "Introduce more section breaks or contrast beats to reset attention."
    return "The script pacing looks healthy for a strategic explainer format."
