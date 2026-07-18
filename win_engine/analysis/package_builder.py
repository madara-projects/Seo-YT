"""Create usable title-and-thumbnail choices from validated title variants."""

from __future__ import annotations

import re
from typing import Any


def build_title_thumbnail_packages(
    title_variants: list[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return only clear, non-duplicated packages a creator can compare."""

    brief = creator_brief or {}
    packages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, variant in enumerate(title_variants, start=1):
        title = str(variant.get("title") or "").strip()
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        issues = _quality_issues(title, brief)
        if issues:
            continue
        style = _title_style(title)
        packages.append(
            {
                "package": chr(64 + index),
                "title": title,
                "thumbnail_text": _thumbnail_text(title, brief),
                "thumbnail_visual": str(brief.get("thumbnail_idea") or _default_visual(brief)).strip(),
                "viewer_promise": str(brief.get("viewer_promise") or "A clear, truthful reason to watch.").strip(),
                "why_click": _why_click(style, brief),
                "approach": style,
                "misleading_risk": "low",
                "quality_status": "approved",
            }
        )
    return packages[:8]


def _quality_issues(title: str, brief: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if len(title) < 28 or len(title) > 78:
        issues.append("title length is outside the useful range")
    lowered = title.lower()
    if any(term in lowered for term in ("guaranteed", "100%", "secret trick", "get rich quick")):
        issues.append("misleading claim")
    if not any(char.isalpha() for char in title):
        issues.append("title has no usable topic")
    return issues


def _thumbnail_text(title: str, brief: dict[str, Any]) -> str:
    direction = str(brief.get("thumbnail_idea") or "").strip()
    if direction:
        words = re.findall(r"[A-Za-z0-9]+", direction.upper())[:4]
        if words:
            return " ".join(words)
    ignored = {"the", "a", "an", "how", "to", "my", "your", "and", "with", "for", "what", "is", "really"}
    words = [word.upper() for word in re.findall(r"[A-Za-z0-9]+", title) if word.lower() not in ignored]
    return " ".join(words[:4]) or "WATCH THIS"


def _default_visual(brief: dict[str, Any]) -> str:
    proof = str(brief.get("proof") or "").strip()
    return proof or "Use one clear real frame from the video with a readable emotional focal point."


def _title_style(title: str) -> str:
    lowered = title.lower()
    if lowered.startswith("how to") or any(word in lowered for word in ("guide", "tips", "step-by-step")):
        return "searchable"
    if "?" in title or any(word in lowered for word in ("real", "truth", "inside", "what nobody")):
        return "curiosity-led"
    return "balanced"


def _why_click(style: str, brief: dict[str, Any]) -> str:
    promise = str(brief.get("viewer_promise") or "the specific viewer payoff").strip()
    proof = str(brief.get("proof") or "real evidence from the video").strip()
    if style == "searchable":
        return f"It makes the outcome searchable while promising: {promise}"
    if style == "curiosity-led":
        return f"It creates curiosity, backed by {proof}."
    return f"It balances a clear topic with the viewer payoff: {promise}"
