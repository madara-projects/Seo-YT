"""Lightweight text-similarity helper used by competitor gap analysis."""

from __future__ import annotations

import re


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z]{3,}", (text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_content_similarity(text1: str, text2: str) -> float:
    """Return Jaccard similarity over content words, from zero to one."""
    return round(_jaccard(_word_set(text1), _word_set(text2)), 3)
