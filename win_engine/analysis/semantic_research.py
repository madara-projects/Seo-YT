"""Structured semantic understanding for the SEO research pipeline.

This module deliberately keeps semantic interpretation separate from keyword
selection.  A concept mentioned by a creator is useful context, not automatic
search evidence.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from win_engine.llm import gemini_client


logger = logging.getLogger(__name__)

_FIELDS = ("primary_topic", "secondary_topics", "entities", "audience", "search_intents", "keyword_clusters")
_STOPWORDS = {"video", "short", "shorts", "quote", "screen", "background", "youtube", "content"}
_GROUNDING_STOPWORDS = _STOPWORDS | {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "is", "of", "on", "or", "the", "to", "with",
    "visual", "footage", "rain", "rainy", "road", "night", "city", "setting", "reflection", "personal", "people", "viewers",
}


def analyze_script_semantics(script: str, creator_brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return validated semantic JSON, with a clearly marked local fallback."""

    source = _source_text(script, creator_brief)
    if gemini_client.is_available():
        raw = gemini_client.generate(
            prompt=(
                "Analyze this video source for YouTube research. Return JSON only with "
                "primary_topic (string), secondary_topics (array), entities (array), audience (array), "
                "search_intents (array), viewer_intent (one of informational, emotional_relatable, problem_solving, "
                "how_to, explanation, comparison, curiosity, story_experience, current_event, entertainment), and "
                "keyword_clusters (array of {cluster, candidates}). "
                "Separate content entities from likely viewer search concepts. Do not treat an exact quote, "
                "title wording, or every script word as a keyword. Every field/list item must be one atomic, "
                "natural concept; never concatenate several labels into one phrase. Do not claim search volume or performance.\n\n"
                f"Creator source:\n{source[:8000]}"
            ),
            system="You are a careful semantic research analyst. Return compact valid JSON only.",
            max_tokens=700,
            temperature=0.2,
        )
        parsed = _parse(raw)
        if parsed:
            parsed = _ground_semantics(parsed, source)
            if not parsed.get("primary_topic"):
                return _fallback(source, creator_brief)
            parsed["source"] = "gemini"
            parsed["confidence"] = "semantic_inference"
            return parsed
        logger.warning("Semantic Gemini response was unavailable or invalid; using local semantic fallback.")

    return _fallback(source, creator_brief)


def _parse(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict) or not isinstance(value.get("primary_topic"), str):
        return None
    result: dict[str, Any] = {"primary_topic": _clean(value["primary_topic"])[:180]}
    if not result["primary_topic"]:
        return None
    for field in _FIELDS[1:5]:
        result[field] = _strings(value.get(field), limit=12)
    clusters: list[dict[str, Any]] = []
    for item in value.get("keyword_clusters") or []:
        if not isinstance(item, dict):
            continue
        cluster = _clean(item.get("cluster"))[:100]
        candidates = _strings(item.get("candidates"), limit=10)
        if cluster and candidates:
            clusters.append({"cluster": cluster, "candidates": candidates})
    result["keyword_clusters"] = clusters[:8]
    viewer_intent = _clean(value.get("viewer_intent") or value.get("intent")).casefold().replace(" ", "_").replace("-", "_")
    if viewer_intent:
        result["viewer_intent"] = viewer_intent[:40]
    return result


def _fallback(source: str, brief: dict[str, Any] | None) -> dict[str, Any]:
    words = [word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z'-]*", source) if len(word) > 3]
    meaningful = [word for word in words if word not in _STOPWORDS]
    primary = " ".join(dict.fromkeys(meaningful[:5])) or "video topic"
    audience = _strings([(brief or {}).get("target_audience"), (brief or {}).get("creator_intent")], limit=2)
    return {
        "primary_topic": primary,
        "secondary_topics": _strings((brief or {}).get("viewer_promise"), limit=2),
        "entities": [],
        "audience": audience,
        "search_intents": _strings((brief or {}).get("viewer_promise"), limit=2),
        "keyword_clusters": [],
        "viewer_intent": _fallback_intent(source),
        "source": "local_fallback",
        "confidence": "limited_without_gemini",
    }


def _fallback_intent(source: str) -> str:
    text = source.casefold()
    if re.search(r"\b(?:how to|tutorial|guide|steps?)\b", text):
        return "how_to"
    if re.search(r"\b(?:why|what is|explained)\b", text):
        return "explanation"
    if re.search(r"\b(?:today|latest|breaking|news)\b", text):
        return "current_event"
    if re.search(r"\b(?:feel|heart|miss|lonely|love|quote)\b", text):
        return "emotional_relatable"
    return "informational"


def _ground_semantics(value: dict[str, Any], source: str) -> dict[str, Any]:
    """Keep semantic labels tied to the creator source, not adjacent life stories.

    Semantic interpretation may abstract a phrase, but it may not introduce an
    unsupported diagnosis, history, relationship event, or audience problem.
    """

    anchors = _ground_tokens(source)
    result = dict(value)
    if not _grounded(result.get("primary_topic"), anchors):
        result["primary_topic"] = ""
    for field in ("secondary_topics", "entities", "audience", "search_intents"):
        result[field] = [item for item in result.get(field) or [] if _grounded(item, anchors)]
    clusters: list[dict[str, Any]] = []
    for cluster in result.get("keyword_clusters") or []:
        if not isinstance(cluster, dict):
            continue
        candidates = [item for item in cluster.get("candidates") or [] if _grounded(item, anchors)]
        if candidates:
            clusters.append({"cluster": cluster.get("cluster"), "candidates": candidates})
    result["keyword_clusters"] = clusters
    return result


def _ground_tokens(value: str) -> set[str]:
    return {
        word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z'-]*", value)
        if len(word) > 2 and word.casefold() not in _GROUNDING_STOPWORDS
    }


def _grounded(value: Any, anchors: set[str]) -> bool:
    words = _ground_tokens(_clean(value))
    if not words:
        return False
    return len(words & anchors) / len(words) >= 0.5


def _source_text(script: str, brief: dict[str, Any] | None) -> str:
    data = brief or {}
    parts = [
        script,
        data.get("target_audience"), data.get("viewer_promise"), data.get("unique_angle"),
        data.get("visual_requirements"), data.get("creator_intent"),
    ]
    return "\n".join(_clean(part) for part in parts if _clean(part))


def _strings(value: Any, *, limit: int) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _clean(item)[:160]
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
        if len(result) >= limit:
            break
    return result


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()
