"""Create usable title-and-thumbnail choices from validated title variants."""

from __future__ import annotations

import re
from typing import Any

from win_engine.ai_enhancement import find_content_similarity
from win_engine.analysis.generation_quality import candidate_mechanism, unicode_words


_GENERIC_WORDS = {
    "amazing", "best", "crazy", "epic", "life", "movie", "new", "video", "vlog", "wow",
    "today", "update", "watch", "must", "viral", "everything", "things",
}
_CONTEXT_STOPWORDS = {"about", "after", "and", "are", "for", "from", "have", "into", "my", "of", "our", "the", "this", "to", "with", "your"}


def build_title_thumbnail_packages(
    title_variants: list[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
    competitor_titles: list[str] | None = None,
    validated: bool = False,
) -> list[dict[str, Any]]:
    """Return only clear, non-duplicated packages a creator can compare."""

    brief = creator_brief or {}
    packages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for variant in title_variants:
        title = str(variant.get("title") or "").strip()
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        issues = [] if validated else _quality_issues(title, brief, competitor_titles or [])
        if issues:
            continue
        style = _title_style(title)
        package_intent = str(variant.get("package_intent") or "Alternative")
        packages.append(
            {
                "package_id": f"package-{chr(97 + len(packages))}",
                "package": chr(65 + len(packages)),
                "title": title,
                "thumbnail_text": _thumbnail_text(title, brief),
                "thumbnail_visual": str(brief.get("thumbnail_idea") or _default_visual(brief)).strip(),
                "viewer_promise": str(brief.get("viewer_promise") or "A clear, truthful reason to watch.").strip(),
                "why_click": _why_click(style, brief, package_intent),
                "approach": style,
                "package_intent": package_intent,
                "best_for": _best_for(style, brief, package_intent),
                "misleading_risk": "low",
                "quality_status": "approved",
                "mechanism": str(variant.get("mechanism") or candidate_mechanism(title)),
                "reason": str(variant.get("reason") or "A distinct, source-supported packaging option."),
                "discovery_surface": str(variant.get("discovery_surface") or package_intent),
                "evidence_used": variant.get("evidence_used") or {"status": "insufficient_evidence"},
                "tradeoffs": variant.get("tradeoffs") or ["Generated suggestion; publishing outcome is not guaranteed."],
                "quality_gate": variant.get("quality_gate") or {"status": "pass", "source": "local"},
                "provenance": "generated_suggestion",
            }
        )
    return packages[:8]


def _quality_issues(title: str, brief: dict[str, Any], competitor_titles: list[str]) -> list[str]:
    issues: list[str] = []
    if len(title) < 28 or len(title) > 70:
        issues.append("title length is outside the useful range")
    lowered = title.lower()
    if any(term in lowered for term in ("guaranteed", "100%", "secret trick", "get rich quick", "you won't believe")):
        issues.append("misleading claim")
    title_words = _meaningful_words(title)
    if len(title_words) < 3 or all(word in _GENERIC_WORDS for word in title_words):
        issues.append("title is too vague")
    context_words = _meaningful_words(" ".join(str(brief.get(field) or "") for field in ("content", "unique_angle", "viewer_promise", "proof")))
    if context_words and not set(title_words).intersection(context_words):
        issues.append("title is not connected to the video brief")
    if any(find_content_similarity(title, competitor) >= 0.78 for competitor in competitor_titles if competitor):
        issues.append("title is too similar to a competitor")
    return issues


def _meaningful_words(value: str) -> list[str]:
    return [word for word in unicode_words(value) if len(word) >= 3 and word not in _CONTEXT_STOPWORDS]


def _thumbnail_text(title: str, brief: dict[str, Any]) -> str:
    direction = str(brief.get("thumbnail_idea") or "").strip()
    if direction:
        words = unicode_words(direction.upper())[:4]
        if words:
            return " ".join(words)
    ignored = {"the", "a", "an", "how", "to", "my", "your", "and", "with", "for", "what", "is", "really"}
    words = [word.upper() for word in unicode_words(title) if word.lower() not in ignored]
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


def _why_click(style: str, brief: dict[str, Any], package_intent: str = "") -> str:
    promise = str(brief.get("viewer_promise") or "the specific viewer payoff").strip()
    proof = str(brief.get("proof") or "real evidence from the video").strip()
    if package_intent == "Existing audience":
        return f"It reconnects returning viewers with the subject they already care about: {promise}"
    if package_intent == "Browse":
        return f"It creates a feed-friendly curiosity hook, backed by {proof}."
    if style == "searchable" or package_intent == "Search":
        return f"It makes the outcome searchable while promising: {promise}"
    if style == "curiosity-led":
        return f"It creates curiosity, backed by {proof}."
    return f"It balances a clear topic with the viewer payoff: {promise}"


def _best_for(style: str, brief: dict[str, Any], package_intent: str = "") -> str:
    if package_intent == "Search":
        return "Search / new viewers"
    if package_intent == "Browse":
        return "Browse / home and suggested viewers"
    if package_intent == "Existing audience":
        return "Returning viewers / existing audience"
    if style == "searchable":
        return "Search / new viewers"
    if style == "curiosity-led":
        return "Browse / relatable viewers"
    return "Search and browse"
