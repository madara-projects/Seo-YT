from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from win_engine.analysis.text_tokens import unicode_words


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
    # Tamil scripts are tokenized too; without these the top signal of a
    # Tamil script was "இந்த வீடியோவில்" ("in this video").
    "இந்த",
    "அந்த",
    "ஒரு",
    "என்று",
    "மற்றும்",
    "பற்றி",
    "எப்படி",
    "வீடியோ",
    "வீடியோவில்",
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


def _tokenize(text: str) -> list[str]:
    # Every script: an ASCII-only pattern found no words at all in a Tamil
    # script, and an empty script then let every competitor phrase through.
    return [
        token for token in unicode_words(text)
        if len(token) >= 3 and token not in _STOP_WORDS and token not in _NOISE_TOKENS
    ]


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


def extract_keyword_signals(script: str, youtube_results: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Extract recurring phrase-level keyword signals from script and YouTube metadata."""

    counter: Counter[str] = Counter()
    script_phrases = _extract_phrases(script)
    counter.update(script_phrases)

    script_tokens = set(_tokenize(script))
    for result in youtube_results:
        title = str(result.get("title", ""))
        description = str(result.get("description", ""))
        title_phrases = _extract_phrases(title)
        desc_phrases = _extract_phrases(description)
        for phrase in title_phrases + desc_phrases:
            phrase_tokens = set(_tokenize(phrase))
            # A result phrase counts only when it shares a word with the script.
            # A script with no words to share gives nothing to be relevant to,
            # so competitor wording never stands in for the creator's topic.
            if not (phrase_tokens & script_tokens):
                continue
            counter[phrase] += 1

    signals: list[dict[str, object]] = []
    for keyword, count in counter.most_common(15):
        if len(keyword.split()) == 1 and keyword in _NOISE_TOKENS:
            continue
        if keyword in _GENERIC_PHRASES:
            continue
        signals.append(
            {
                "keyword": keyword,
                "mentions": count,
                "strength": "high" if count >= 5 else "medium" if count >= 3 else "low",
            }
        )
    return signals[:10]
