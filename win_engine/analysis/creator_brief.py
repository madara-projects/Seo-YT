"""Turn creator-provided context into a concise, generation-ready video brief."""

from __future__ import annotations

import re
from typing import Any


_DISPLAY_NAMES = {
    "target_audience": "who the video is for",
    "viewer_promise": "what the viewer will get",
    "unique_angle": "what makes this video different",
    "proof": "proof, footage, result, or personal experience",
}

_TOPIC_STOPWORDS = {
    "a", "an", "and", "the", "this", "that", "with", "for", "from", "my", "our",
    "video", "footage", "show", "shows", "showing", "real", "realistic", "perfect",
    "what", "will", "see", "feel", "learn", "work", "life", "content",
    "day", "own", "not", "but", "into", "your", "their",
}


def build_creator_brief(
    *,
    script: str,
    target_audience: str = "",
    viewer_promise: str = "",
    unique_angle: str = "",
    proof: str = "",
    video_format: str = "",
    title_style: str = "balanced",
    thumbnail_idea: str = "",
) -> dict[str, Any]:
    """Build a transparent brief and flag the missing context that weakens packaging."""

    brief = {
        "content": script.strip(),
        "target_audience": target_audience.strip(),
        "viewer_promise": viewer_promise.strip(),
        "unique_angle": unique_angle.strip(),
        "proof": proof.strip(),
        "video_format": video_format.strip() or "unspecified",
        "title_style": title_style.strip() or "balanced",
        "thumbnail_idea": thumbnail_idea.strip(),
    }

    missing = [field for field in _DISPLAY_NAMES if not brief[field]]
    warnings: list[str] = []
    if len(brief["content"]) < 40:
        warnings.append("Add a little more about what actually happens in the video.")
    if missing:
        labels = ", ".join(_DISPLAY_NAMES[field] for field in missing)
        warnings.append(f"For stronger packaging, add: {labels}.")

    completed = len(_DISPLAY_NAMES) - len(missing)
    if completed == len(_DISPLAY_NAMES) and len(brief["content"]) >= 40:
        status = "ready"
        recommendation = "Your brief has enough context for audience-aware packaging."
    elif completed >= 2:
        status = "needs_detail"
        recommendation = "The tool can generate ideas, but one or two more details will make them more specific."
    else:
        status = "needs_detail"
        recommendation = "Start with the viewer and the result or feeling they should get from the video."

    return {
        **brief,
        "status": status,
        "completeness": round((completed / len(_DISPLAY_NAMES)) * 100),
        "missing_fields": missing,
        "warnings": warnings,
        "recommendation": recommendation,
    }


def creator_topic(creator_brief: dict[str, Any] | None) -> str:
    """Make a compact topic for fallbacks and topic locking from the creator's own words."""

    brief = creator_brief or {}
    sources = [brief.get("unique_angle"), brief.get("content"), brief.get("viewer_promise")]
    candidates: list[str] = []
    for source in sources:
        for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", str(source or "").lower()):
            if len(word) < 3 or word in _TOPIC_STOPWORDS or word in candidates:
                continue
            candidates.append(word)

    # Preserve the first two concrete words from the unique angle, then make a
    # creator / routine context explicit before less useful words such as "job".
    selected = candidates[:2]
    for word in ("creator", "routine", "vlog", "review", "tutorial"):
        if word in candidates and word not in selected:
            selected.append(word)
    for word in candidates:
        if word not in selected:
            selected.append(word)
        if len(selected) >= 4:
            break
    return " ".join(selected[:4])
