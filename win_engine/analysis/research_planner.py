"""Build a small, quota-aware set of YouTube research searches."""

from __future__ import annotations

import re
from typing import Any


_QUERY_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "in", "into", "is", "it", "of", "on", "or", "that", "the",
    "their", "them", "then", "this", "through", "to", "was", "were", "will",
    "with", "who", "your", "video", "viewers", "experiencing", "engage", "gradually",
    "calming", "exact", "shown", "screen", "background", "footage", "animation",
}


def plan_research_queries(
    *,
    script: str,
    creator_brief: dict[str, Any] | None = None,
    semantic_analysis: dict[str, Any] | None = None,
    region: str = "global",
    primary_language: str = "english",
    max_queries: int = 5,
) -> list[dict[str, str]]:
    """Turn a creator brief into distinct searches, keeping API use predictable."""

    brief = creator_brief or {}
    content = _short(brief.get("content") or script)
    semantic = semantic_analysis or {}
    quote_concepts = _quote_concepts(str(brief.get("exact_quote") or brief.get("on_screen_text") or ""))
    topic_source = " ".join(
        str(value or "")
        for value in (semantic.get("primary_topic"), *(semantic.get("secondary_topics") or []))
    )
    structured_topic = _keyword_phrase(str(brief.get("topic") or ""), 8)
    topic = (quote_concepts[0] if quote_concepts else "") or _keyword_phrase(topic_source, 6) or structured_topic or _keyword_phrase(content, 6) or "YouTube video"
    audience_problem = _keyword_phrase(
        " ".join(str(value or "") for value in (brief.get("target_audience"), brief.get("viewer_promise"))),
        6,
    )
    video_format = _format_phrase(str(brief.get("video_format") or ""))
    intent = _keyword_phrase(" ".join(str(value or "") for value in (semantic.get("search_intents") or [])), 7)
    related = _keyword_phrase(" ".join(
        str(item) for cluster in (semantic.get("keyword_clusters") or []) if isinstance(cluster, dict)
        for item in cluster.get("candidates") or []
    ), 7)
    local_modifier = _local_modifier(region, primary_language)

    # The plan is deliberately conditional: a video only spends an API search
    # on an angle that the semantic source/brief actually supplies.
    candidates = [("primary", topic)]
    candidates.extend(("quote_concept", concept) for concept in quote_concepts[1:])
    if intent:
        candidates.append((f"intent:{semantic.get('viewer_intent') or 'viewer'}", intent))
    elif audience_problem:
        candidates.append(("viewer_problem", audience_problem))
    if related:
        candidates.append(("related_concept", related))
    if audience_problem and audience_problem != intent:
        candidates.append(("viewer_problem", _join(audience_problem, topic)))
    entities = _keyword_phrase(" ".join(str(value or "") for value in (semantic.get("entities") or [])), 5)
    if entities:
        candidates.append(("entity", _join(entities, topic)))
    if local_modifier:
        candidates.append(("local_language", _join(topic, local_modifier)))
    if video_format and str(semantic.get("viewer_intent") or "") in {"entertainment", "story_experience"}:
        candidates.append(("format_context", _join(topic, video_format)))

    queries: list[dict[str, str]] = []
    seen: set[str] = set()
    for query_type, query in candidates:
        cleaned = _short(query, 14)
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        queries.append({"type": query_type, "query": cleaned})
        if len(queries) >= max(1, max_queries):
            break
    return queries


def brief_research_text(script: str, creator_brief: dict[str, Any] | None = None) -> str:
    """Provide keyword extraction with the useful brief context, not only a script opening."""

    brief = creator_brief or {}
    values = [
        brief.get("content") or script,
        brief.get("target_audience"),
        brief.get("viewer_promise"),
        brief.get("unique_angle"),
        brief.get("proof"),
        brief.get("video_format"),
    ]
    return " ".join(str(value).strip() for value in values if str(value or "").strip())


def _short(value: object, words: int = 12) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return " ".join(text.split()[:words]).strip(" -,:;")


def _join(*parts: str) -> str:
    return " ".join(part for part in parts if part and part != "unspecified")


def _extract_quote(text: str) -> str:
    matches = re.findall(r'["\u201c\u201d\']([^"\u201c\u201d\']{12,})["\u201c\u201d\']', text)
    if not matches:
        return ""
    return max(matches, key=len).strip()


def _quote_concepts(quote: str) -> list[str]:
    """Return natural search concepts for common quote meanings, never chopped prose."""

    lowered = quote.casefold()
    concepts: list[str] = []
    if "give up" in lowered or "enough" in lowered:
        concepts.extend(["knowing when to let go", "emotional exhaustion"])
    if "walks away" in lowered or "how to stay" in lowered:
        concepts.append("relationships fading without closure")
    if "misunderstood" in lowered or "genuine" in lowered:
        concepts.extend(["being misunderstood", "being genuine"])
    if "apology" in lowered or "crueller" in lowered:
        concepts.extend(["self forgiveness", "self criticism"])
    if "keep going" in lowered:
        concepts.append("keep going motivation")
    if (
        "deserve" in lowered
        and re.search(r"\bhard\s+(?:it\s+is\s+)?to\s+find\b", lowered)
        and re.search(r"\b(?:somebody|someone)\s+like\s+you\b", lowered)
    ):
        concepts.extend([
            "knowing your worth quotes",
            "being valued for who you are",
            "hard to replace quotes",
            "genuine appreciation quotes",
        ])
    return list(dict.fromkeys(concepts))


def _keyword_phrase(text: str, words: int = 6) -> str:
    useful: list[str] = []
    for word in re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower()):
        normalized = word.strip("'-")
        if len(normalized) < 3 or normalized in _QUERY_STOPWORDS or normalized in useful:
            continue
        useful.append(normalized)
        if len(useful) >= words:
            break
    return " ".join(useful)


def _format_phrase(value: str) -> str:
    lowered = value.lower()
    if any(term in lowered for term in ("short", "reel", "quote")):
        return "quote shorts"
    return _keyword_phrase(value, 3)


def _local_modifier(region: str, primary_language: str) -> str:
    language = primary_language.strip().lower()
    normalized_region = region.strip().lower()
    if language in {"tamil", "tanglish"} or normalized_region in {"tamil nadu", "sri lanka"}:
        return "Tamil"
    if normalized_region == "india":
        return "India"
    if normalized_region == "gulf":
        return "Gulf"
    return ""
