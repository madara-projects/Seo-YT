from __future__ import annotations

from typing import Literal


IntentLabel = Literal["SEARCH", "BROWSE", "SUGGESTED"]


def classify_intent(script: str) -> IntentLabel:
    """Basic heuristic intent classifier.

    Uses deterministic keyword signals and a conservative fallback. SUGGESTED
    is the fallback, so curiosity phrasing ("shocking", "secret") needs no
    marker list of its own.
    """

    lower = script.lower()

    search_markers = [
        "how to",
        "tutorial",
        "guide",
        "tips",
        "step by step",
        "best way",
        "explained",
        "checklist",
    ]
    browse_markers = [
        "story",
        "reaction",
        "i tried",
        "experiment",
        "for 7 days",
        "for 30 days",
        "challenge",
        "case study",
        "review",
        "what happened",
    ]

    if any(token in lower for token in search_markers):
        return "SEARCH"

    if any(token in lower for token in browse_markers):
        return "BROWSE"

    return "SUGGESTED"
