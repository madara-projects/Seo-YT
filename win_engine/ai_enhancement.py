"""Lightweight text-similarity helper used by competitor gap analysis and package checks.

Despite the module name, nothing here calls a model: it is word overlap.
"""

from __future__ import annotations

from win_engine.analysis.text_tokens import unicode_words


def _word_set(text: str) -> set[str]:
    # Words of three or more characters in any script. An ASCII-only pattern
    # gave Tamil titles no words at all, so a copied title scored as unique.
    return {word for word in unicode_words(text) if len(word) >= 3 and not word.isdigit()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_content_similarity(text1: str, text2: str) -> float:
    """Return Jaccard similarity over content words, from zero to one."""
    return round(_jaccard(_word_set(text1), _word_set(text2)), 3)
