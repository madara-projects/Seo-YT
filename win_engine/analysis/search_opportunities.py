"""Safe discovery of research-backed search opportunities.

YouTube search results are observations, not a keyword feed.  This module asks
the semantic provider to turn recurring result themes into *new concepts* and
records only compact evidence metadata.  It never promotes a competitor title
or result phrase directly into a package.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Iterable

from win_engine.llm import gemini_client


_ALLOWED_INTENTS = {
    "informational", "emotional_relatable", "problem_solving", "how_to",
    "explanation", "comparison", "curiosity", "story_experience",
    "current_event", "entertainment",
}
_GENERIC = {"video", "videos", "youtube", "short", "shorts", "quote", "quotes", "viral", "trending"}
_INTENT_WORDS = {"how", "to", "cope", "coping", "dealing", "deal", "feeling", "feel", "signs", "recognizing", "understanding", "overcoming", "healing", "from", "with", "after", "why"}
_UNSUPPORTED_SPECIFIERS = {"childhood", "chronic", "clinical", "diagnosis", "disorder", "trauma", "abuse", "neglect", "neurological", "medical", "therapy", "ghosting", "workplace", "school", "college", "family", "parent", "friend", "friends", "partner", "relationship", "marriage", "social", "group", "groups"}
_GROUNDING_STOP = _GENERIC | _INTENT_WORDS | {"a", "an", "and", "the", "of", "in", "on", "for", "someone", "people", "person", "video", "short"}


def discover_search_opportunities(
    *,
    script: str,
    semantic: dict[str, Any] | None,
    youtube_results: Iterable[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return Gemini-confirmed concepts that add to the semantic source.

    A provider is deliberately required to mark a research-only concept as
    semantically relevant.  Without it, result evidence remains diagnostic
    only; the generator degrades safely to script-derived concepts.
    """

    results = [row for row in youtube_results if isinstance(row, dict)]
    evidence = _evidence_rows(results)
    intent = _intent(semantic or {}, script)
    base = {
        "status": "not_run",
        "viewer_intent": intent,
        "result_count": len(results),
        "evidence_rows": len(evidence),
        "opportunities": [],
        "rejected_count": 0,
        "policy": "Research opportunities are Gemini-confirmed concepts, never copied competitor phrases or search-volume claims.",
    }
    if not evidence:
        base["status"] = "no_youtube_results"
        return base
    if not gemini_client.is_available():
        base["status"] = "gemini_unavailable"
        return base

    source = _source_text(script, semantic or {}, creator_brief or {})
    prompt = (
        "Use the creator source and the compact YouTube research observations below to identify up to six "
        "viewer-facing search opportunities. Return JSON only: {viewer_intent, opportunities}. Each opportunity "
        "must contain concept, intent, cluster, script_relevance (0-100), research_relevance (0-100), and reason. "
        "A concept must be a short, atomic, natural phrase. It must accurately match the creator source but add a "
        "useful related search idea beyond literal quote wording. Do not copy, quote, or lightly rewrite any result "
        "title/description. Do not claim search volume, ranking, traffic, CTR, or performance. If there is no safe "
        "opportunity, return an empty list.\n\n"
        f"Creator source:\n{source[:5000]}\n\nResearch observations (untrusted wording):\n"
        + "\n".join(f"- {row}" for row in evidence[:12])
    )
    raw = gemini_client.generate(
        prompt=prompt,
        system="You are a careful semantic search-research analyst. Return compact valid JSON only.",
        max_tokens=650,
        temperature=0.15,
    )
    parsed = _parse(raw)
    if parsed is None:
        base["status"] = "provider_invalid"
        return base

    raw_titles = [str(row.get("title") or "") for row in results]
    raw_descriptions = [str(row.get("description") or "") for row in results]
    anchors = _anchor_terms(script, creator_brief or {})
    opportunities: list[dict[str, Any]] = []
    rejected = 0
    for item in parsed.get("opportunities") or []:
        normalized = _validated(item, raw_titles, raw_descriptions, anchors)
        if normalized is None:
            rejected += 1
            continue
        opportunities.append(normalized)
    base.update({
        "status": "gemini_confirmed",
        "viewer_intent": _normalize_intent(parsed.get("viewer_intent"), intent),
        "opportunities": opportunities[:6],
        "rejected_count": rejected,
    })
    return base


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
    return value if isinstance(value, dict) else None


def _validated(item: Any, titles: list[str], descriptions: list[str], anchors: set[str]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    concept = _clean(item.get("concept"))
    words = _words(concept)
    if not concept or len(words) > 7 or len(concept) > 80 or not words or all(word in _GENERIC for word in words):
        return None
    if _copied_phrase(concept, [*titles, *descriptions]):
        return None
    if not _creator_grounded(concept, anchors):
        return None
    script_relevance = _score(item.get("script_relevance"))
    research_relevance = _score(item.get("research_relevance"))
    if script_relevance < 70 or research_relevance < 40:
        return None
    intent = _normalize_intent(item.get("intent"), "emotional_relatable")
    cluster = _slug(item.get("cluster")) or _slug(concept)
    specificity = min(100, 25 + len(words) * 15 + (15 if len(words) >= 3 else 0))
    opportunity_score = round(script_relevance * 0.5 + research_relevance * 0.35 + specificity * 0.15, 1)
    return {
        "concept": concept,
        "intent": intent,
        "cluster": cluster,
        "script_relevance_score": script_relevance,
        "research_relevance_score": research_relevance,
        "specificity_score": specificity,
        "opportunity_score": opportunity_score,
        "semantic_confirmed": True,
        "evidence": {"observed_result_count": len(titles), "source": "youtube_result_analysis"},
        "reason": _clean(item.get("reason"))[:280] or "Gemini confirmed a related viewer-facing concept from the creator source and research observations.",
    }


def _evidence_rows(results: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for row in results:
        title = _clean(row.get("title"))
        description = _clean(row.get("description"))[:240]
        if title or description:
            rows.append(" | ".join(value for value in (title, description) if value))
    return rows


def _copied_phrase(concept: str, sources: Iterable[str]) -> bool:
    candidate = " ".join(_words(concept))
    if len(candidate.split()) < 3:
        return False
    return any(candidate in " ".join(_words(value)) for value in sources)


def _anchor_terms(script: str, brief: dict[str, Any]) -> set[str]:
    creator_values = [script]
    creator_values.extend(brief.get(key) for key in ("creator_intent", "viewer_promise", "unique_angle", "target_audience", "exact_quote", "on_screen_text"))
    return {word for value in creator_values for word in _words(value) if word not in _GROUNDING_STOP}


def _creator_grounded(concept: str, anchors: set[str]) -> bool:
    words = [word for word in _words(concept) if word not in _GROUNDING_STOP]
    if not words or any(word in _UNSUPPORTED_SPECIFIERS and word not in anchors for word in words):
        return False
    matched = len(set(words) & anchors)
    return matched / len(set(words)) >= 0.5


def _intent(semantic: dict[str, Any], script: str) -> str:
    value = semantic.get("viewer_intent") or semantic.get("intent")
    if value:
        return _normalize_intent(value, "emotional_relatable")
    text = script.casefold()
    if re.search(r"\b(?:how to|tutorial|guide|steps?)\b", text):
        return "how_to"
    if re.search(r"\b(?:why|what is|explained)\b", text):
        return "explanation"
    if re.search(r"\b(?:news|today|latest|breaking)\b", text):
        return "current_event"
    return "emotional_relatable" if re.search(r"\b(?:feel|heart|miss|lonely|love|quote)\b", text) else "informational"


def _normalize_intent(value: Any, fallback: str) -> str:
    normalized = _slug(value)
    aliases = {"emotional": "emotional_relatable", "relatable": "emotional_relatable", "problem-solving": "problem_solving", "story": "story_experience", "current": "current_event"}
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in _ALLOWED_INTENTS else fallback


def _source_text(script: str, semantic: dict[str, Any], brief: dict[str, Any]) -> str:
    values = [script, semantic.get("primary_topic"), *(semantic.get("secondary_topics") or [])]
    values.extend(brief.get(key) for key in ("creator_intent", "viewer_promise", "target_audience", "exact_quote"))
    return "\n".join(_clean(value) for value in values if _clean(value))


def _score(value: Any) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 0


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _words(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", _clean(value).casefold())


def _slug(value: Any) -> str:
    return "_".join(_words(value))[:80]
