from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "we",
    "with",
    "you",
    "your",
}

_NOISE_TOKENS = {
    "another",
    "avoid",
    "benefits",
    "break",
    "change",
    "changes",
    "completely",
    "day",
    "days",
    "downsides",
    "thing",
    "things",
    "video",
    "videos",
    "really",
    "actually",
    "worth",
    "end",
}

_GENERIC_PHRASES = {
    "here what",
    "what happened",
    "what really",
    "successful people",
    "small changes",
    "something strange",
    "day kept",
    "kept hearing",
    "nobody talks",
}

_PHRASE_PATTERNS = [
    r"\b(?:waking|wake|woke)\s+up\s+at\s+\d{1,2}\s*(?:am|pm)\b",
    r"\b\d{1,2}\s*(?:am|pm)\s+routine\b",
    r"\bfor\s+\d+\s+days\b",
    r"\b(?:morning|sleep|productivity)\s+(?:routine|experiment|challenge)\b",
    r"\b(?:waking up early|wake up early)\b",
    r"\boverhyped\s+habit\b",
    r"\bworth\s+it\b",
    r"\bunexpected\s+downsides\b",
    r"\bmorning\s+productivity\b",
    r"\bproductivity\s+and\s+mindset\b",
]

# Regional keyword priority boosters
_REGION_PRIORITY_KEYWORDS = {
    "india": {"growth", "strategy", "tips", "guide", "channel", "views", "audience"},
    "tamil nadu": {"tamil", "local", "culture", "community", "trending", "regional"},
    "sri lanka": {"growth", "diaspora", "cultural", "strategy", "community"},
    "gulf": {"diaspora", "expat", "culture", "community", "entertainment"},
    "global": {"growth", "strategy", "tips", "international", "audience"},
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9]{3,}", text.lower())
    return [token for token in tokens if token not in _STOP_WORDS and token not in _NOISE_TOKENS]


def _extract_phrases(text: str) -> list[str]:
    lowered = text.lower()
    phrases: list[str] = []

    for pattern in _PHRASE_PATTERNS:
        phrases.extend(match.strip() for match in re.findall(pattern, lowered))

    words = _tokenize(text)
    for size in (2, 3, 4):
        for index in range(len(words) - size + 1):
            phrase = " ".join(words[index:index + size])
            parts = phrase.split()
            if parts[0] in _STOP_WORDS or parts[-1] in _STOP_WORDS:
                continue
            if any(token in _NOISE_TOKENS for token in parts):
                continue
            if phrase in _GENERIC_PHRASES:
                continue
            if len(phrase) < 8:
                continue
            phrases.append(phrase)

    return phrases


def extract_keyword_signals(script: str, youtube_results: Iterable[dict[str, object]], region: str = "global", primary_language: str = "english") -> list[dict[str, object]]:
    """Extract recurring phrase-level keyword signals from script and YouTube metadata, with region-aware prioritization."""

    counter: Counter[str] = Counter()
    script_phrases = _extract_phrases(script)
    counter.update(script_phrases)

    for result in youtube_results:
        title = str(result.get("title", ""))
        description = str(result.get("description", ""))
        counter.update(_extract_phrases(title))
        counter.update(_extract_phrases(description))

    signals: list[dict[str, object]] = []
    region_keywords = _REGION_PRIORITY_KEYWORDS.get(region.lower(), _REGION_PRIORITY_KEYWORDS["global"])
    
    for keyword, count in counter.most_common(15):
        if len(keyword.split()) == 1 and keyword in _NOISE_TOKENS:
            continue
        if keyword in _GENERIC_PHRASES:
            continue
        source_strength = "high" if count >= 5 else "medium" if count >= 3 else "low"
        
        # Apply region-aware priority boost
        regional_boost = 0
        keyword_lower = keyword.lower()
        for region_keyword in region_keywords:
            if region_keyword in keyword_lower:
                regional_boost = 1
                source_strength = "high"
                break
        
        signals.append(
            {
                "keyword": keyword,
                "mentions": count,
                "strength": source_strength,
                "region_relevant": regional_boost == 1,
            }
        )

    # Sort by regional relevance first, then by mention count
    signals.sort(key=lambda x: (x["region_relevant"], x["mentions"]), reverse=True)
    
    return signals[:10]  # Return top 10
