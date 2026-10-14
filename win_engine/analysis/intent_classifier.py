from __future__ import annotations

import re
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

    # A marker opens a word ("reviews" counts); "history" is not a story,
    # "preview" not a review and "fingertips" not tips.
    def has(markers: list[str]) -> bool:
        return any(re.search(rf"\b{re.escape(token)}", lower) for token in markers)

    if has(search_markers):
        return "SEARCH"

    if has(browse_markers):
        return "BROWSE"

    return "SUGGESTED"
