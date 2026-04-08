from __future__ import annotations

from typing import Literal


IntentLabel = Literal["SEARCH", "BROWSE", "SUGGESTED"]


def classify_intent(script: str) -> IntentLabel:
    """Basic heuristic intent classifier.

    TODO: Replace with robust classifier using real data.
    """

    lower = script.lower()

    if any(token in lower for token in ["how to", "tutorial", "guide", "tips"]):
        return "SEARCH"

    if any(token in lower for token in ["story", "reaction", "i tried", "experiment"]):
        return "BROWSE"

    return "SUGGESTED"
