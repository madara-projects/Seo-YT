"""Build a small, quota-aware set of YouTube research searches."""

from __future__ import annotations

import re
from typing import Any
from win_engine.analysis.semantic_research import usable_research_topic
from win_engine.analysis.generation_quality import (
    has_unsupported_instructional_framing,
    is_short_content,
    source_requires_noninstructional_framing,
)


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
    semantic = semantic_analysis or {}
    semantic_primary = str(semantic.get("primary_topic") or "")
    if _is_visual_semantic(semantic_primary, semantic):
        semantic_primary = ""
    structured_topic = _keyword_phrase(str(brief.get("topic") or ""), 8)
    proven_semantic_topic = _search_phrase(semantic_primary, 6) if semantic.get("concept_evidence_validated") is True else ""
    # Without a validated semantic topic the searches use the creator's own
    # words (the brief's topic, taken from the quote or main phrase). A table of
    # stock "quote concepts" searched "knowing when to let go" for "I can't get
    # enough of you": the opposite meaning, at 100 quota units a query.
    topic = next((value for value in [proven_semantic_topic,
        _search_phrase(semantic_primary, 6), structured_topic,
        *(semantic.get("secondary_topics") or [])] if usable_research_topic(value)), "")
    audience_problem = _keyword_phrase(
        " ".join(str(value or "") for value in (brief.get("target_audience"), brief.get("viewer_promise"))),
        6,
    )
    video_format = _format_phrase(script, brief)
    secondary = [
        _search_phrase(value, 6) for value in (semantic.get("secondary_topics") or [])
        if not _is_visual_semantic(str(value), semantic)
    ]
    intents = [
        _search_phrase(value, 7) for value in (semantic.get("search_intents") or [])
        if not _is_visual_semantic(str(value), semantic)
    ]
    related = [
        _search_phrase(item, 7)
        for cluster in (semantic.get("keyword_clusters") or []) if isinstance(cluster, dict)
        for item in cluster.get("candidates") or []
        if not _is_visual_semantic(str(item), semantic)
    ]
    local_modifier = _local_modifier(region, primary_language)

    # The plan is deliberately conditional: a video only spends an API search
    # on an angle that the semantic source/brief actually supplies.
    candidates = [("primary", topic)]
    # Quote videos benefit from a natural discovery-form variant.  A semantic
    # topic such as "grief" is useful for classification, while viewers are
    # more likely to search a phrase such as "quotes about grief".  Keep this
    # deterministic and source-grounded instead of asking the model to invent
    # a broader emotional angle.
    quote_search = _quote_search_variant(topic) if brief.get("exact_quote") or brief.get("on_screen_text") else ""
    if quote_search and quote_search.casefold() != topic.casefold():
        candidates.append(("quote_search", quote_search))
    candidates.extend((f"intent:{semantic.get('viewer_intent') or 'viewer'}", concept) for concept in intents if concept)
    candidates.extend(("related_concept", concept) for concept in related if concept)
    candidates.extend(("secondary_topic", concept) for concept in secondary if concept and concept != topic)
    if not intents and audience_problem:
        candidates.append(("viewer_problem", audience_problem))
    entities = [
        _search_phrase(value, 5) for value in (semantic.get("entities") or [])
        if not _is_visual_semantic(str(value), semantic)
    ]
    candidates.extend(("entity", entity) for entity in entities if entity)
    if local_modifier:
        candidates.append(("local_language", _join(topic, local_modifier)))
    if video_format and str(semantic.get("viewer_intent") or "") in {"entertainment", "story_experience"}:
        candidates.append(("format_context", _join(topic, video_format)))

    queries: list[dict[str, str]] = []
    seen: set[str] = set()
    for query_type, query in candidates:
        cleaned = _short(query, 8)
        if not usable_research_topic(cleaned):
            continue
        if _low_value_query(cleaned):
            continue
        if _visual_only_query(cleaned, script, brief):
            continue
        if source_requires_noninstructional_framing(script, brief) and has_unsupported_instructional_framing(cleaned):
            continue
        if brief.get("exact_quote") and re.match(r"(?i)^(?:coping with|how to|healing from|tips? for)\b", cleaned):
            continue
        meaningful = _keyword_phrase(cleaned, 8).split()
        if len(meaningful) == 1 and brief.get("exact_quote"):
            base_topic = _keyword_phrase(topic, 3)
            cleaned = (
                f"{cleaned} quotes" if query_type == "primary"
                else f"{cleaned} in {base_topic}" if base_topic and len(base_topic.split()) == 1 and base_topic != meaningful[0]
                else f"{cleaned} quotes"
            )
        key = cleaned.casefold()
        words = _keyword_phrase(cleaned, 8).split()
        if (
            not cleaned or key in seen
            or (len(words) == 1 and words[0] in {"emotion", "emotional", "healing", "loneliness", "motivation", "moving", "pain", "sad"})
            or any(_query_similarity(cleaned, existing) >= 0.8 for existing in seen)
        ):
            continue
        seen.add(key)
        queries.append({"type": query_type, "query": cleaned})
        if len(queries) >= max(1, max_queries):
            break
    return queries


def _visual_only_query(value: str, script: str, brief: dict[str, Any]) -> bool:
    """Reject scenery/camera subjects unless the actual content also discusses them."""

    visual_words = set(_keyword_phrase(str(brief.get("visual_requirements") or ""), 20).split())
    query_words = set(_keyword_phrase(value, 20).split())
    if not visual_words or not query_words:
        return False
    content = " ".join(str(brief.get(field) or "") for field in ("exact_quote", "on_screen_text", "content", "topic"))
    content = content or script
    content_words = set(_keyword_phrase(content, 40).split())
    visual_overlap = len(query_words & visual_words) / len(query_words)
    content_overlap = len(query_words & content_words) / len(query_words)
    return visual_overlap >= 0.5 and content_overlap < 0.5


def _low_value_query(value: str) -> bool:
    """Protect limited search quota from analyst labels and vague prompts."""

    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    if re.match(r"^(?:exploring|understanding|discovering|relatable)\b", normalized):
        return True
    words = set(normalized.split())
    return bool(words) and words <= {
        "content", "emotional", "emotion", "feelings", "feeling", "relatable",
        "reflection", "reflective", "validation", "video", "videos",
    }


def _is_visual_semantic(value: str, semantic: dict[str, Any]) -> bool:
    key = re.sub(r"\s+", " ", value).strip().casefold()
    return any(
        isinstance(item, dict)
        and str(item.get("concept") or "").strip().casefold() == key
        and str(item.get("source_scope") or "content").casefold() == "visual"
        for item in semantic.get("concept_evidence") or []
    )


def _query_similarity(left: str, right: str) -> float:
    a = set(_keyword_phrase(left, 10).split())
    b = set(_keyword_phrase(right, 10).split())
    return len(a & b) / max(len(a | b), 1)


def brief_research_text(script: str, creator_brief: dict[str, Any] | None = None) -> str:
    """Provide keyword extraction with the useful brief context, not only a script opening."""

    brief = creator_brief or {}
    values = [
        brief.get("content") or script,
        brief.get("target_audience"),
        brief.get("viewer_promise"),
        brief.get("unique_angle"),
        brief.get("proof"),
    ]
    # A format guessed from the script says nothing new about it, and for a
    # script with no words the guess ("talking_head") became the topic and title.
    format_source = ((brief.get("field_provenance") or {}).get("video_format") or {}).get("source")
    if format_source != "inferred":
        values.append(brief.get("video_format"))
    return " ".join(str(value).strip() for value in values if str(value or "").strip())


def _short(value: object, words: int = 12) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return " ".join(text.split()[:words]).strip(" -,:;")


def _search_phrase(value: object, words: int = 7) -> str:
    """Keep natural grammar in an atomic semantic phrase while removing input labels."""

    text = _short(value, words)
    if re.search(r"(?i)\b(?:background|footage|visual requirements?|creator source|on screen)\b", text):
        return ""
    return text


def _join(*parts: str) -> str:
    return " ".join(part for part in parts if part and part != "unspecified")


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


def _format_phrase(script: str, brief: dict[str, Any]) -> str:
    # A "short ribs" tutorial is not a Short; one resolver decides for every module.
    if is_short_content(script, brief):
        return "quote shorts" if brief.get("exact_quote") or brief.get("on_screen_text") else "shorts"
    return _keyword_phrase(str(brief.get("video_format") or ""), 3)


def _quote_search_variant(topic: str) -> str:
    """Return one natural, atomic search phrase for a quote topic."""

    cleaned = re.sub(r"\s+", " ", str(topic or "").strip())
    if not cleaned:
        return ""
    without_marker = re.sub(r"(?i)\bquotes?\b", " ", cleaned)
    without_marker = re.sub(r"\s+", " ", without_marker).strip(" -,:;")
    if not without_marker:
        return ""
    return _short(f"quotes about {without_marker}", 8)


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
