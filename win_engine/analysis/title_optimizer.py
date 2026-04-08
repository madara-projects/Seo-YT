from __future__ import annotations

import re
from typing import Any


_POWER_WORDS = {
    "best",
    "guide",
    "proven",
    "fast",
    "viral",
    "secret",
    "shocking",
    "mistakes",
    "strategy",
    "results",
    "grow",
}

_CURIOSITY_WORDS = {
    "why",
    "how",
    "what",
    "unexpected",
    "surprised",
    "truth",
    "worth it",
    "worked",
    "results",
}

# Tamil/Tanglish validated real-world phrases
_TAMIL_VALIDATED_PHRASES = {
    "da",
    "pa",
    "illa",
    "macha",
    "semma",
    "vera level",
    "podu",
    "ah",
    "ey",
    "dei",
    "machan",
    "pogadhe",
    "sariyanda",
    "sathasai",
    "neeyum",
    "ivlo",
}

_TANGLISH_VALIDATED_PATTERNS = [
    r"\bda\b",
    r"\bpa\b",
    r"\bmacha\b",
    r"\bsemma\b",
    r"\bvera level\b",
    r"\bpodu\b",
    r"\bey\b",
    r"\bdei\b",
    r"\bgood ah\b",
    r"\bvenalum\b",
]


def optimize_titles(title_variants: list[str], primary_topic: str, secondary_topic: str, language_strategy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score title variants and choose the strongest one, with language-aware optimization."""

    language_strategy = language_strategy or {}
    primary_language = language_strategy.get("primary_language", "english")
    
    scored_variants: list[dict[str, Any]] = []
    for title in title_variants:
        length_score = _length_score(title, primary_language)
        power_score = _word_score(title, _POWER_WORDS)
        curiosity_score = _word_score(title, _CURIOSITY_WORDS)
        topic_score = _topic_score(title, primary_topic, secondary_topic)
        structure_score = _structure_score(title)
        realism_penalty = _realism_penalty(title, primary_topic)
        
        # Language-specific bonuses
        language_bonus = 0.0
        if primary_language in {"tamil", "tanglish"}:
            language_bonus = _tamil_tanglish_bonus(title)
        
        mobile_hook_ok = len(title) <= 65
        total = round(length_score + power_score + curiosity_score + topic_score + structure_score - realism_penalty + language_bonus, 2)

        scored_variants.append(
            {
                "title": title,
                "score": total,
                "mobile_hook_ok": mobile_hook_ok,
                "length": len(title),
                "power_score": power_score,
                "curiosity_score": curiosity_score,
                "topic_score": topic_score,
                "structure_score": structure_score,
                "realism_penalty": realism_penalty,
                "language_bonus": language_bonus,
            }
        )

    scored_variants.sort(key=lambda item: item["score"], reverse=True)
    best = scored_variants[0] if scored_variants else {"title": "YouTube Strategy Breakdown", "score": 0}

    return {
        "best_title": best["title"],
        "scored_variants": scored_variants,
    }


def _length_score(title: str, primary_language: str = "english") -> float:
    length = len(title)
    # Tamil/Tanglish titles can be slightly longer due to script characteristics
    if primary_language in {"tamil", "tanglish"}:
        if 48 <= length <= 68:
            return 4.0
        if 38 <= length <= 78:
            return 2.5
    else:
        if 45 <= length <= 62:
            return 4.0
        if 35 <= length <= 70:
            return 2.5
    return 1.0


def _word_score(title: str, vocabulary: set[str]) -> float:
    lowered = title.lower()
    matches = sum(1 for word in vocabulary if word in lowered)
    return min(matches * 1.5, 4.5)


def _topic_score(title: str, primary_topic: str, secondary_topic: str) -> float:
    lowered = title.lower()
    score = 0.0
    if primary_topic.lower() in lowered:
        score += 3.0
    if secondary_topic.lower() in lowered:
        score += 2.0
    return score


def _structure_score(title: str) -> float:
    lowered = title.lower()
    score = 0.0
    if re.search(r"\bfor\s+\d+\s+days\b", lowered):
        score += 1.5
    if "?" in title:
        score += 1.0
    if any(token in lowered for token in {"here's what happened", "honest truth", "worth it"}):
        score += 1.5
    if re.search(r"\b\d{1,2}\s*(am|pm)\b", lowered):
        score += 1.0
    return score


def _realism_penalty(title: str, primary_topic: str) -> float:
    penalty = 0.0
    lowered = title.lower()
    primary_words = {part for part in primary_topic.lower().split() if len(part) > 2}

    if any(token in lowered for token in {"strategy that gets more views", "playbook", "better youtube strategy"}) and "youtube" not in lowered:
        penalty += 2.5
    for duration in re.findall(r"\bfor\s+(\d+\s+days)\b", lowered):
        if duration not in primary_topic.lower():
            penalty += 3.0
    if len(primary_words) <= 1 and "am" not in primary_topic.lower():
        penalty += 2.0
    if any(token in lowered for token in {"wake", "days"}) and "wake up" not in lowered and "5 am" not in lowered:
        penalty += 1.5
    if any(token in lowered for token in {"benefits, downsides, and the truth", "benefits downsides"}):
        penalty += 1.0
    if len(title.split()) <= 5:
        penalty += 1.0
    return penalty


def _tamil_tanglish_bonus(title: str) -> float:
    """Apply bonus scoring for validated Tamil/Tanglish phrasing patterns."""
    bonus = 0.0
    lowered = title.lower()
    
    # Check for validated Tamil/Tanglish particles and expressions
    tanglish_matches = sum(1 for pattern in _TANGLISH_VALIDATED_PATTERNS if re.search(pattern, lowered))
    if tanglish_matches > 0:
        bonus += min(tanglish_matches * 0.8, 2.5)
    
    # Check for validated Tamil phrases in lowercase
    for phrase in _TAMIL_VALIDATED_PHRASES:
        if f" {phrase} " in f" {lowered} " or f" {phrase}," in f" {lowered}," or f" {phrase}?" in f" {lowered}?":
            bonus += 0.6
    
    # Natural spoken rhythm - shorter words mixed with content
    words = title.split()
    if len(words) >= 5:
        avg_word_length = sum(len(w) for w in words) / len(words)
        # Tamil/Tanglish should have variety: mix of short particles and longer words
        if 3 <= avg_word_length <= 7:
            bonus += 1.0
    
    # Avoid overstuffing: penalty reduction if title doesn't look cluttered
    if lowered.count("  ") == 0:
        bonus += 0.3
    
    return bonus

