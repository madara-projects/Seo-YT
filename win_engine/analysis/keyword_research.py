"""Research-backed, atomic tag selection for generated YouTube packages.

Research queries and YouTube result text are evidence sources. They are never
copied directly into the final tag list.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from win_engine.analysis.generation_quality import (
    has_unsupported_instructional_framing,
    is_silent_quote_only_short,
    source_requires_noninstructional_framing,
)


_FORMAT_GENERIC = {"short", "shorts", "video", "videos", "youtube", "content", "viral", "trending", "fyp"}
_TOPIC_GENERIC = {"quote", "quotes", "emotional", "reflection", "reflections", "melancholy", "melancholic", "mood", "moods", "relatable", "deep", "motivation", "sad", "cinematic", "aesthetics", "finding", "watching", "moody", "atmospheric", "personal", "meaningful"}
_STOP = _FORMAT_GENERIC | _TOPIC_GENERIC | {"the", "and", "with", "from", "that", "this", "your", "about", "into", "when", "what", "how", "was", "were", "have", "has", "for", "are", "but", "not", "just"}
_VISUAL_TERMS = {"road", "traffic", "sunset", "sunrise", "sky", "rain", "rainy", "night", "moon", "beach", "mountain", "footage", "visual", "scene", "cloud", "clouds", "tree", "trees", "background", "backgrounds", "moving", "dark", "evening"}
_NOISY_TERMS = {"instagram", "whatsapp", "status", "sadstatus", "aesthetic", "aha9a"}
_CREATOR_META_TERMS = {
    "creator", "content", "video", "concept", "script", "source", "internal", "instruction",
    "guideline", "prompt", "context", "inventing", "invent", "making", "specific", "problem",
}
_CREATOR_META_PHRASES = (
    "without inventing", "without making up", "do not invent", "video concept", "creator content",
    "according to the prompt", "without context", "no specific life problem", "silent reflective quote",
    "minimal reflection",
)
_FRAGMENT_EXAMPLES = {"fast near", "one room", "slow one", "then one", "used talk", "checking same", "evening even", "same empty", "between tcp", "udp user"}
_FRAGMENT_ENDINGS = {"near", "one", "then", "every", "same", "even", "empty", "while", "neither", "after", "before", "with", "without", "of", "for", "to"}
_ABSTRACT_CONCEPTS = {"heartbreak", "loneliness", "rejection", "healing", "loss", "abandonment", "forgotten", "unseen", "erased", "distance", "absence", "grief", "betrayal"}
_PHRASE_CONCEPTS = (
    "coping with feeling forgotten", "being forgotten by someone", "feeling forgotten",
    "emotional distance", "emotional absence", "emotional loss", "emotional healing",
    "emotional reflection", "personal rejection", "deep emotional quotes", "heartbreak sayings",
)
_MAX_TAG_WORDS = 7
_MAX_TAG_CHARS = 80
_MAX_TOKEN_CHARS = 32


def build_keyword_research(
    *, script: str, semantic: dict[str, Any] | None, youtube_results: Iterable[dict[str, Any]],
    research_queries: Iterable[dict[str, Any]], entity_signals: Iterable[dict[str, Any]],
    creator_brief: dict[str, Any] | None = None,
    search_opportunities: dict[str, Any] | None = None,
    query_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create classified candidate concepts and attach research evidence.

    Semantic/creator concepts make the pool. YouTube queries/results validate
    those concepts; raw competitor language cannot become a tag candidate.
    """
    sem = semantic or {}
    brief = creator_brief or {}
    quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "")
    result_rows = [item for item in youtube_results if isinstance(item, dict)]
    query_rows = [item for item in research_queries if isinstance(item, dict)]
    content_terms = _content_terms(sem, script, brief)
    source_terms = _source_terms(script, brief)
    visual_terms = set(_tokens(brief.get("visual_requirements") or ""))
    candidates: dict[str, dict[str, Any]] = {}
    opportunities = search_opportunities or {}

    _add(candidates, sem.get("primary_topic"), "semantic", "core_topic", content_terms, visual_terms)
    for value in sem.get("secondary_topics") or []:
        _add(candidates, value, "semantic", "secondary_topic", content_terms, visual_terms)
    for value in sem.get("search_intents") or []:
        _add(candidates, value, "semantic", "search_intent", content_terms, visual_terms)
    for cluster in sem.get("keyword_clusters") or []:
        if isinstance(cluster, dict):
            for value in cluster.get("candidates") or []:
                _add(candidates, value, "semantic_cluster", "long_tail", content_terms, visual_terms)
    for entity in entity_signals:
        if isinstance(entity, dict):
            _add(candidates, entity.get("entity"), "entity", "entity", content_terms, visual_terms)
    for audience in sem.get("audience") or []:
        _add(candidates, audience, "semantic", "audience", content_terms, visual_terms)
    _add(candidates, brief.get("creator_intent"), "creator_brief", "secondary_topic", content_terms, visual_terms)
    _add(candidates, brief.get("viewer_promise"), "creator_brief", "search_intent", content_terms, visual_terms)
    for opportunity in opportunities.get("opportunities") or []:
        if isinstance(opportunity, dict):
            _add(
                candidates, opportunity.get("concept"), "research_discovery", "opportunity",
                content_terms, visual_terms, opportunity=opportunity,
            )

    scored: list[dict[str, Any]] = []
    rejected_before_selection = 0
    for candidate in candidates.values():
        entry = _score(candidate, result_rows, query_rows, quote, content_terms, source_terms, visual_terms)
        if entry:
            scored.append(entry)
        else:
            rejected_before_selection += 1
    scored.sort(key=lambda item: (-item["keyword_relevance_score"], item["keyword"]))
    research_targets = _diverse(scored, limit=8)
    relevant_results = sum(1 for row in result_rows if _result_relevant(row, content_terms))
    diagnostics = {
        **(query_diagnostics or {}),
        "relevant_youtube_results": relevant_results,
        "concepts_discovered": len(opportunities.get("opportunities") or []),
        "research_discovery_rejected": int(opportunities.get("rejected_count") or 0),
        "candidates_generated": len(candidates),
        "candidates_rejected_before_selection": rejected_before_selection,
        "candidates_survived_filtering": len(scored),
        "research_target_count": len(research_targets),
    }
    return {
        "status": "youtube_evidence" if result_rows else "semantic_only",
        "confidence": "observed_youtube_relevance" if result_rows else "limited_without_youtube_research",
        "semantic_source": sem.get("source", "unknown"),
        "candidate_count": len(scored), "candidates": scored[:40], "selected_keywords": [], "selected_tags": [],
        "research_targets": research_targets,
        "search_opportunities": opportunities,
        "diagnostics": diagnostics,
        "research_policy": "YouTube queries and result text validate candidate concepts; raw result phrases are never copied into tags.",
        "content_terms": sorted(content_terms), "visual_terms": sorted(visual_terms),
    }


def select_final_tags(
    research: dict[str, Any], *, generated_tags: Iterable[str], title: str, script: str,
    creator_brief: dict[str, Any] | None = None, is_short: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Select only strong, diverse, atomic concepts; never pad a tag count."""
    del is_short  # Format belongs in hashtags/metadata, never consumes a tag slot.
    brief = creator_brief or {}
    quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "")
    non_instructional = source_requires_noninstructional_framing(script, brief)
    content_terms = set(research.get("content_terms") or _tokens(script))
    visual_terms = set(research.get("visual_terms") or [])
    indexed = {
        str(item.get("keyword") or ""): dict(item) for item in research.get("candidates") or []
        if isinstance(item, dict) and item.get("keyword")
    }

    # Model tags are suggestions, not authority. They need semantic support and
    # cannot create an unsupported niche or bypass the same validation rules.
    for raw in generated_tags:
        for text in _atomic_concepts(raw):
            key = _normalize(text)
            if not key or key in indexed:
                continue
            classification, rejected = _classify(key, "model", content_terms, visual_terms)
            if rejected or not _semantic_support(key, content_terms):
                continue
            indexed[key] = _model_entry(key, classification, content_terms, visual_terms)

    eligible: list[dict[str, Any]] = []
    rejected_count = 0
    for item in indexed.values():
        entry = dict(item)
        if non_instructional and has_unsupported_instructional_framing(entry.get("keyword")):
            rejected_count += 1
            continue
        if _reject_reason(entry, title, quote, content_terms):
            rejected_count += 1
            continue
        eligible.append(entry)
    eligible.sort(key=lambda item: (-item["keyword_relevance_score"], item["keyword"]))
    chosen = _diverse(eligible, limit=10)
    tags = [item["keyword"] for item in chosen]
    baseline = _diverse(
        [item for item in eligible if item.get("source_classification") == "script_derived"],
        limit=10,
    )
    contribution = [
        item for item in chosen
        if item.get("source_classification") in {"combined", "research_discovered"}
    ]
    evidence = {
        **research, "selected_keywords": chosen, "selected_tags": tags,
        "rejected_candidate_count": rejected_count,
        "research_contribution": {
            "research_selected_count": len(contribution),
            "combined_selected_count": sum(1 for item in contribution if item.get("source_classification") == "combined"),
            "research_discovered_selected_count": sum(1 for item in contribution if item.get("source_classification") == "research_discovered"),
            "selected_concepts": [item["keyword"] for item in contribution],
            "script_only_tags": [item["keyword"] for item in baseline],
            "research_enhanced_tags": tags,
            "material_change": bool(set(tags) - {item["keyword"] for item in baseline}),
            "summary": (
                "Research contributed validated concepts to the final tag set."
                if contribution else "No research-backed concept cleared the final relevance and diversity checks."
            ),
        },
        "diagnostics": {
            **(research.get("diagnostics") or {}),
            "candidates_rejected_at_selection": rejected_count,
            "candidates_selected": len(chosen),
        },
        "selection_policy": "Tags are atomic topic concepts. Weak generic, visual-only, title-copy, quote-copy, malformed, duplicate, and unsupported candidates are excluded; no slots are padded.",
    }
    return tags, evidence


def _add(
    target: dict[str, dict[str, Any]], value: Any, source: str, hint: str,
    content_terms: set[str], visual_terms: set[str], opportunity: dict[str, Any] | None = None,
) -> None:
    for raw in _atomic_concepts(value):
        text = _normalize(raw)
        if not text:
            continue
        classification, rejected = _classify(text, hint, content_terms, visual_terms)
        if rejected:
            continue
        entry = target.setdefault(text, {"keyword": text, "sources": set(), "classification": classification})
        entry["sources"].add(source)
        if opportunity:
            entry["opportunity"] = dict(opportunity)
        if _class_rank(classification) < _class_rank(str(entry.get("classification") or "generic")):
            entry["classification"] = classification


def _score(candidate: dict[str, Any], results: list[dict[str, Any]], queries: list[dict[str, Any]], quote: str, content_terms: set[str], source_terms: set[str], visual_terms: set[str]) -> dict[str, Any] | None:
    text = str(candidate["keyword"])
    classification = str(candidate.get("classification") or "generic")
    opportunity = candidate.get("opportunity") if isinstance(candidate.get("opportunity"), dict) else {}
    semantic_confirmation = bool(opportunity.get("semantic_confirmed")) and int(opportunity.get("script_relevance_score") or 0) >= 70
    # Gemini confirmation may score and describe an opportunity, but it cannot
    # replace an actual anchor in the creator source/semantic core. This stops
    # a related-result theme from inventing a new situation, diagnosis, or
    # relationship event around the video.
    if not _semantic_support(text, content_terms):
        return None
    source_support_score, source_support = _source_support(text, source_terms)
    if "research_discovery" in (candidate.get("sources") or []) and source_support_score < 70:
        return None
    content_relevance = max(
        _content_score(text, content_terms),
        min(42, int(opportunity.get("script_relevance_score") or 0) // 2) if semantic_confirmation else 0,
    )
    visual_relevance = _visual_score(text, visual_terms)
    if classification == "entity" and content_relevance < 28:
        return None
    if classification == "audience" and (content_relevance < 42 or _evidence_count(text, results) == 0):
        return None
    if classification == "contextual" and content_relevance <= visual_relevance:
        return None
    evidence_count = _evidence_count(text, results)
    query_support = _query_support(text, queries)
    opportunity_evidence = int(opportunity.get("research_relevance_score") or 0)
    evidence_score = max(min(24, evidence_count * 8 + query_support * 4), min(24, opportunity_evidence // 4))
    intent_score = _intent_score(classification)
    specificity = _specificity_score(text)
    total = max(0, min(100, content_relevance + evidence_score + intent_score + specificity + source_support_score // 8 - (18 if _quote_like(text, quote) else 0)))
    if total < 28:
        return None
    sources = sorted(candidate.get("sources") or [])
    source_classification = _source_classification(sources, evidence_count, semantic_confirmation)
    return {
        "keyword": text, "sources": sources, "source": "+".join(sources), "source_classification": source_classification,
        "classification": classification,
        "content_relevance_score": content_relevance, "visual_relevance_score": visual_relevance,
        "source_support_score": source_support_score, "source_support": source_support,
        "research_evidence_score": evidence_score, "intent_score": intent_score, "specificity_score": specificity,
        "diversity_score": None, "keyword_relevance_score": total, "evidence_count": evidence_count,
        "semantic_confirmed": semantic_confirmation,
        "cluster": str(opportunity.get("cluster") or _family(text)),
        "intent": str(opportunity.get("intent") or _intent_label(classification)),
        "selection_reason": _reason(classification, evidence_count, query_support, source_classification),
        "reason": _reason(classification, evidence_count, query_support, source_classification),
    }


def _model_entry(text: str, classification: str, content_terms: set[str], visual_terms: set[str]) -> dict[str, Any]:
    content = _content_score(text, content_terms)
    visual = _visual_score(text, visual_terms)
    intent = _intent_score(classification)
    specificity = _specificity_score(text)
    return {
        "keyword": text, "sources": ["model"], "source": "model", "source_classification": "script_derived", "classification": classification,
        "content_relevance_score": content, "visual_relevance_score": visual, "research_evidence_score": 0,
        "source_support_score": 100, "source_support": "generated suggestion has direct semantic support",
        "intent_score": intent, "specificity_score": specificity, "diversity_score": None,
        "keyword_relevance_score": content + intent + specificity, "evidence_count": 0,
        "cluster": _family(text), "intent": _intent_label(classification),
        "selection_reason": "Model suggestion retained only because it matches the semantic topic; it has no independent YouTube evidence.",
        "reason": "Model suggestion retained only because it matches the semantic topic; it has no independent YouTube evidence.",
    }


def _atomic_concepts(value: Any) -> list[str]:
    """Split only clear multi-concept lists; preserve legitimate long-tail phrases."""
    text = _normalize(value)
    if not text:
        return []
    # Commas and separators commonly mean a generated list.  Plain ``and``
    # does not: it can be essential grammar in a comparison such as "manual
    # and burr coffee grinders".
    pieces = [piece.strip() for piece in re.split(r"\s*(?:[,;|/])\s*", text) if piece.strip()]
    if len(pieces) > 1 and all(_tokens(piece) for piece in pieces):
        return pieces
    words = _tokens(text)
    raw_word_count = len(re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text))
    hits = sum(1 for token in words if token in _ABSTRACT_CONCEPTS)
    if " and " in text and hits >= 2:
        abstract_pieces = [piece.strip() for piece in re.split(r"\s+and\s+", text) if piece.strip()]
        if len(abstract_pieces) > 1 and all(any(token in _ABSTRACT_CONCEPTS for token in _tokens(piece)) for piece in abstract_pieces):
            return abstract_pieces
    phrases = [phrase for phrase in _PHRASE_CONCEPTS if phrase in text]
    if raw_word_count >= 4 and hits + len(phrases) >= 3 and not text.startswith(("how to", "ways to", "signs of", "coping with", "why ")):
        found: list[str] = []
        remaining = text
        for phrase in _PHRASE_CONCEPTS:
            if phrase in remaining:
                found.append(phrase)
                remaining = remaining.replace(phrase, " ")
        found.extend(token for token in _tokens(remaining) if token in _ABSTRACT_CONCEPTS)
        return list(dict.fromkeys(found)) or [text]
    return [text]


def _classify(text: str, hint: str, content_terms: set[str], visual_terms: set[str]) -> tuple[str, str | None]:
    if not _tokens(text) or _is_generic(text):
        return "generic", "generic"
    if _malformed(text):
        return "malformed", "malformed"
    if _noisy(text):
        return "irrelevant", "noisy_competitor_phrase"
    if _creator_instruction_leak(text):
        return "irrelevant", "creator_instruction_leakage"
    if _fragmented(text):
        return "malformed", "fragmented_phrase"
    if hint == "search_intent" and _tokens(text) and _tokens(text)[0] in {"explore", "find", "watch", "lovers"}:
        return "malformed", "non_search_instruction"
    if _visual_score(text, visual_terms) > _content_score(text, content_terms):
        return "contextual", None
    return {"core_topic": "core_topic", "secondary_topic": "secondary_topic", "search_intent": "search_intent", "long_tail": "long_tail", "opportunity": "long_tail", "entity": "entity", "audience": "audience"}.get(hint, "secondary_topic"), None


def _reject_reason(entry: dict[str, Any], title: str, quote: str, content_terms: set[str]) -> str | None:
    text = str(entry.get("keyword") or "")
    classification = str(entry.get("classification") or "generic")
    if classification in {"generic", "malformed", "irrelevant"} or _is_generic(text) or _malformed(text) or _noisy(text):
        return classification
    if classification == "contextual" and int(entry.get("content_relevance_score") or 0) <= int(entry.get("visual_relevance_score") or 0):
        return "visual_only"
    if not _semantic_support(text, content_terms):
        return "irrelevant"
    evidence = int(entry.get("research_evidence_score") or 0)
    # Search evidence can validate a source-grounded concept, but it cannot
    # turn a chopped portion of the on-screen quote into a useful tag.  Exact
    # quote fragments are both weak search language and a common source of
    # malformed endings such as "some people only value when".
    if _quote_like(text, quote):
        return "quote_copy"
    independently_supported = classification in {"core_topic", "secondary_topic", "search_intent", "long_tail"} and int(entry.get("content_relevance_score") or 0) >= 28
    if _title_copy(text, title) and evidence < 12 and not independently_supported:
        return "title_copy"
    return None


def _diverse(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    families: set[str] = set()
    for item in items:
        family = _family(item["keyword"])
        overlap = max((_similar(item["keyword"], chosen["keyword"]) for chosen in selected), default=0.0)
        if overlap >= 0.45 or family in families:
            continue
        chosen = dict(item)
        chosen["diversity_score"] = round(max(0.0, 100.0 - overlap * 100.0), 1)
        selected.append(chosen)
        families.add(family)
        if len(selected) >= limit:
            break
    return selected


def _content_terms(semantic: dict[str, Any], script: str, brief: dict[str, Any]) -> set[str]:
    # Only creator source and the semantic core establish relevance. Search
    # intents and cluster candidates are proposals to validate, never proof of
    # themselves.
    values: list[Any] = [semantic.get("primary_topic"), *(semantic.get("secondary_topics") or [])]
    values.extend([brief.get("creator_intent"), brief.get("viewer_promise"), script])
    visual_context = set(_tokens(brief.get("visual_requirements") or "")) | _VISUAL_TERMS
    return {token for value in values for token in _tokens(value) if token not in visual_context}


def _source_terms(script: str, brief: dict[str, Any]) -> set[str]:
    """Use only creator supplied material to prove a research-derived tag."""
    values = [script]
    values.extend(brief.get(field) for field in (
        "content", "exact_quote", "on_screen_text", "topic", "viewer_promise", "unique_angle",
        "factual_claims", "visual_requirements",
    ))
    return {token for value in values for token in _tokens(value)}


def _source_support(text: str, source_terms: set[str]) -> tuple[int, str]:
    words = set(_tokens(text))
    if not words:
        return 0, "no source concept"
    matched = words & source_terms
    # A related search result cannot add an unrelated domain, use case, or
    # decision frame merely because it is popular in YouTube search.
    unsupported_context = {"gaming", "performance", "region", "choosing", "correct", "best"}
    if any(word in unsupported_context and word not in source_terms for word in words):
        return 0, "unsupported adjacent context"
    ratio = len(matched) / len(words)
    if ratio >= 1.0:
        return 100, "direct creator-source support"
    # Narrow, documented semantic bridges preserve useful search language
    # without converting an adjacent use case into the video's subject.
    if {"tcp", "udp", "connection"} & source_terms and words <= {"tcp", "udp", "connection", "oriented", "connectionless"}:
        return 80, "network connection semantic bridge"
    if {"mechanical", "membrane", "keyboard"} & source_terms and words <= {"mechanical", "membrane", "keyboard", "tactile", "typing", "quiet", "quieter"}:
        return 80, "keyboard comparison semantic bridge"
    return int(round(ratio * 100)), "partial creator-source overlap"


def _result_relevant(row: dict[str, Any], content_terms: set[str]) -> bool:
    terms = set(_tokens(f"{row.get('title') or ''} {row.get('description') or ''}"))
    return len(terms & content_terms) >= 2


def _content_score(text: str, content_terms: set[str]) -> int:
    return min(42, len(set(_tokens(text)) & content_terms) * 14)


def _visual_score(text: str, visual_terms: set[str]) -> int:
    return min(24, len(set(_tokens(text)) & (visual_terms | _VISUAL_TERMS)) * 12)


def _evidence_count(text: str, results: list[dict[str, Any]]) -> int:
    words = set(_tokens(text))
    required = max(1, (len(words) + 1) // 2)
    return sum(1 for row in results if len(words & set(_tokens(f"{row.get('title') or ''} {row.get('description') or ''}"))) >= required)


def _query_support(text: str, queries: list[dict[str, Any]]) -> int:
    words = set(_tokens(text))
    return sum(1 for item in queries if words & set(_tokens(item.get("query") or "")))


def _intent_score(classification: str) -> int:
    return {"core_topic": 16, "secondary_topic": 15, "search_intent": 20, "long_tail": 18, "entity": 10, "audience": 8, "contextual": 3}.get(classification, 0)


def _specificity_score(text: str) -> int:
    count = len(_tokens(text))
    return 12 if 2 <= count <= 5 else (7 if count == 1 else 0)


def _is_generic(text: str) -> bool:
    words = _tokens(text)
    return not words or all(word in _TOPIC_GENERIC | _FORMAT_GENERIC for word in words)


def _malformed(text: str) -> bool:
    words = _tokens(text)
    return len(text) > _MAX_TAG_CHARS or len(words) > _MAX_TAG_WORDS or any(len(word) > _MAX_TOKEN_CHARS for word in words)


def _noisy(text: str) -> bool:
    return any(token in _NOISY_TERMS or any(char.isdigit() for char in token) for token in _tokens(text))


def _creator_instruction_leak(text: str) -> bool:
    folded = _normalize(text)
    if any(phrase in folded for phrase in _CREATOR_META_PHRASES):
        return True
    words = set(_tokens(folded))
    return bool(words & _CREATOR_META_TERMS) and bool(words & {"without", "no", "not", "must", "should"})


def _fragmented(text: str) -> bool:
    folded = _normalize(text)
    if folded in _FRAGMENT_EXAMPLES:
        return True
    words = _tokens(folded)
    if not words:
        return False
    if words[-1] in _FRAGMENT_ENDINGS and len(words) <= 6:
        return True
    temporal_word_soup = {"used", "talk", "every", "then", "neither", "same", "kept", "checking"}
    return len(words) <= 7 and len(set(words) & temporal_word_soup) >= 4


def _semantic_support(text: str, content_terms: set[str]) -> bool:
    return bool(set(_tokens(text)) & content_terms)


def _quote_like(text: str, quote: str) -> bool:
    normalized, normalized_quote = _normalize(text), _normalize(quote)
    if len(normalized) >= 8 and normalized in normalized_quote:
        return True
    words, quote_words = set(_tokens(text)), set(_tokens(quote))
    return len(words) >= 2 and bool(words) and len(words & quote_words) / len(words) >= 0.8


def _title_copy(text: str, title: str) -> bool:
    words, title_words = set(_tokens(text)), set(_tokens(title))
    return len(words) >= 2 and bool(words) and len(words & title_words) / len(words) >= 0.8


def _family(text: str) -> str:
    words = set(_tokens(text))
    if words & {"forgotten", "unseen", "erased", "abandoned", "abandonment", "rejection", "absence", "distance", "invisible"}:
        return "emotional_absence"
    if words & {"heartbreak", "betrayal", "grief", "loss"}:
        return "emotional_loss"
    if words & {"loneliness", "alone", "isolated"}:
        return "loneliness"
    if words & _VISUAL_TERMS:
        return "visual"
    return " ".join(sorted(words)[:2]) or "generic"


def _similar(left: str, right: str) -> float:
    a, b = set(_tokens(left)), set(_tokens(right))
    return len(a & b) / max(len(a | b), 1)


def _class_rank(value: str) -> int:
    return {"core_topic": 0, "search_intent": 1, "long_tail": 2, "secondary_topic": 3, "entity": 4, "audience": 5, "contextual": 6, "generic": 7}.get(value, 7)


def _source_classification(sources: list[str], evidence_count: int, semantic_confirmed: bool) -> str:
    if "research_discovery" in sources and not any(source in {"semantic", "semantic_cluster", "creator_brief", "entity"} for source in sources):
        return "research_discovered" if semantic_confirmed else "script_derived"
    if evidence_count or "research_discovery" in sources:
        return "combined"
    return "script_derived"


def _intent_label(classification: str) -> str:
    return {
        "search_intent": "problem_solving", "long_tail": "search_intent",
        "core_topic": "topic", "secondary_topic": "emotional_relatable",
        "entity": "entity", "audience": "audience",
    }.get(classification, "topic")


def _reason(classification: str, evidence_count: int, query_support: int, source_classification: str) -> str:
    label = classification.replace("_", " ").title()
    if source_classification == "research_discovered":
        return f"{label} was Gemini-confirmed against the creator source and supported by aggregate YouTube research observations."
    if evidence_count:
        return f"{label} supported by semantic analysis and matching YouTube research observations."
    if query_support:
        return f"{label} derived from semantic analysis and aligned with the planned research intent."
    return f"{label} derived from semantic analysis; no search-volume claim is made."


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9' -]", " ", str(value or "").casefold())).strip(" -")


def _tokens(value: Any) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", _normalize(value)) if word not in _STOP and len(word) > 1]
