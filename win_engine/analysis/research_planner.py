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
    region: str = "global",
    primary_language: str = "english",
    max_queries: int = 5,
) -> list[dict[str, str]]:
    """Turn a creator brief into distinct searches, keeping API use predictable."""

    brief = creator_brief or {}
    content = _short(brief.get("content") or script)
    quote = _extract_quote(str(brief.get("content") or script))
    topic_source = " ".join(
        str(value or "")
        for value in (quote, brief.get("viewer_promise"), brief.get("target_audience"))
    )
    topic = _keyword_phrase(topic_source, 6) or _keyword_phrase(content, 6) or "YouTube video"
    audience_problem = _keyword_phrase(
        " ".join(str(value or "") for value in (brief.get("target_audience"), brief.get("viewer_promise"))),
        6,
    )
    video_format = _format_phrase(str(brief.get("video_format") or ""))
    exact_quote = _short(quote, 12)
    local_modifier = _local_modifier(region, primary_language)

    candidates = [
        ("main topic", exact_quote or topic),
        ("viewer problem", _join(audience_problem, "quotes")),
        ("desired result", _join(topic, "relatable quote")),
        ("local-language", _join(topic, local_modifier) if local_modifier else ""),
        ("format and competitor framing", _join(topic, video_format)),
    ]

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
