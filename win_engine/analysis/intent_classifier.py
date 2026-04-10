from __future__ import annotations

from typing import Literal


IntentLabel = Literal["SEARCH", "BROWSE", "SUGGESTED"]


def classify_intent(script: str) -> IntentLabel:
    """Basic heuristic intent classifier.

    TODO: Replace with robust classifier using real data.
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
    suggested_markers = [
        "nobody talks about",
        "truth nobody",
        "shocking",
        "viral",
        "secret",
        "mistakes",
        "overhyped",
    ]

    if any(token in lower for token in search_markers):
        return "SEARCH"

    if any(token in lower for token in browse_markers):
        return "BROWSE"

    if any(token in lower for token in suggested_markers):
        return "SUGGESTED"

    return "SUGGESTED"
