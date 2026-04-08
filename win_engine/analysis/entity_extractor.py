from __future__ import annotations

import re
from collections import Counter
from typing import Iterable


_ENTITY_STOPWORDS = {
    "At",
    "But",
    "However",
    "I",
    "In",
    "It",
    "My",
    "There",
    "They",
    "We",
    "How",
    "The",
    "This",
    "That",
    "Your",
    "YouTube",
}


def extract_entity_signals(script: str, youtube_results: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Heuristic entity/topic extraction without external NLP dependencies."""

    samples = [script]
    for result in youtube_results:
        samples.append(str(result.get("title", "")))
        samples.append(str(result.get("description", "")))

    counter: Counter[str] = Counter()
    for sample in samples:
        counter.update(_extract_candidates(sample))

    signals: list[dict[str, object]] = []
    seen_normalized: set[str] = set()
    for entity, mentions in counter.most_common(12):
        normalized = entity.lower().replace(" ", "")
        if normalized in {"am", "pm"}:
            continue
        if normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        entity_type = "year" if entity.isdigit() and len(entity) == 4 else "topic"
        signals.append(
            {
                "entity": entity,
                "mentions": mentions,
                "type": entity_type,
            }
        )
        if len(signals) >= 8:
            break

    return signals


def _extract_candidates(text: str) -> list[str]:
    entities: list[str] = []

    entities.extend(re.findall(r"\b20\d{2}\b", text))
    entities.extend(match.strip() for match in re.findall(r"\b\d{1,2}\s*(?:AM|PM)\b", text))
    entities.extend(match.strip() for match in re.findall(r"\b(?:Wake(?:\s+Up)?|Waking Up)\s+at\s+\d{1,2}\s*(?:AM|PM)\b", text))

    title_case_phrases = re.findall(r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){0,2})\b", text)
    for phrase in title_case_phrases:
        normalized = phrase.strip()
        if normalized in _ENTITY_STOPWORDS or len(normalized) <= 2:
            continue
        entities.append(normalized)

    acronym_phrases = re.findall(r"\b[A-Z]{2,}\b", text)
    entities.extend(acronym for acronym in acronym_phrases if acronym not in {"AM", "PM"} or text.count(acronym) <= 2)

    return entities
