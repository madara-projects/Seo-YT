"""Build a small, quota-aware set of YouTube research searches."""

from __future__ import annotations

import re
from typing import Any


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
    angle = _short(brief.get("unique_angle"))
    content = _short(brief.get("content") or script)
    topic = angle or content or "YouTube video"
    audience = _short(brief.get("target_audience"), 9)
    promise = _short(brief.get("viewer_promise"), 10)
    video_format = _short(brief.get("video_format"), 3)
    title_style = _short(brief.get("title_style"), 3)

    candidates = [
        ("main topic", topic),
        ("viewer problem", _join(audience, promise)),
        ("desired result", _join(topic, promise)),
        ("local-language", _join(topic, _local_modifier(region, primary_language))),
        ("format and competitor framing", _join(topic, video_format, title_style, "video")),
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
