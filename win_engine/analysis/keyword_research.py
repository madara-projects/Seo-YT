"""Research-backed, atomic tag selection for generated YouTube packages.

Research queries and YouTube result text are evidence sources. They are never
copied directly into the final tag list.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from win_engine.analysis.generation_quality import (
    has_unsupported_instructional_framing,
    is_short_content,
    is_silent_quote_only_short,
    source_requires_noninstructional_framing,
)
from win_engine.analysis.topic_lock import infer_category, source_casing_map
from win_engine.analysis.transliteration import has_tamil, phonetic_keys, phonetic_match
from win_engine.ingestion.search_suggest import demand_rank, suggestion_index


_FORMAT_GENERIC = {"short", "shorts", "yt", "video", "videos", "youtube", "content", "viral", "trending", "fyp"}
_PREFERRED_SHORT_TAGS = ("yt", "shorts")
_BROAD_EMOTIONAL_TERMS = {
    "emotion", "emotional", "feelings", "healing", "hurt", "loneliness", "lonely",
    "motivation", "pain", "sad", "sadness", "selfcare", "self-care",
}
_TOPIC_GENERIC = {"quote", "quotes", "emotional", "reflection", "reflections", "melancholy", "melancholic", "mood", "moods", "relatable", "deep", "motivation", "sad", "cinematic", "aesthetics", "finding", "watching", "moody", "atmospheric", "personal", "meaningful"}
_STOP = _FORMAT_GENERIC | _TOPIC_GENERIC | {"the", "and", "with", "from", "that", "this", "your", "about", "in", "of", "on", "at", "into", "when", "what", "how", "was", "were", "have", "has", "for", "are", "but", "not", "just"}
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
    search_demand: dict[str, Any] | None = None,
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
    entity_rows = [row for row in entity_signals]
    reflective = bool(quote) or source_requires_noninstructional_framing(script, brief)
    subjects = subject_terms(
        sem, entity_rows, source_terms, themes=quote_themes(quote, script) if reflective else (),
    )
    # The background ("rainy road with vehicles") decorates the video; words
    # only it mentions are not what the video is about.
    visual_only = set(_tokens(brief.get("visual_requirements") or "")) - set(_tokens(script)) - set(_tokens(quote))
    subjects -= visual_only
    visual_terms = set(_tokens(brief.get("visual_requirements") or ""))
    candidates: dict[str, dict[str, Any]] = {}
    opportunities = search_opportunities or {}
    semantic_evidence = _semantic_evidence_map(sem)

    _add(candidates, sem.get("primary_topic"), "semantic", "core_topic", content_terms, visual_terms, semantic_evidence=semantic_evidence)
    for value in sem.get("secondary_topics") or []:
        _add(candidates, value, "semantic", "secondary_topic", content_terms, visual_terms, semantic_evidence=semantic_evidence)
    for value in sem.get("search_intents") or []:
        _add(candidates, value, "semantic", "search_intent", content_terms, visual_terms, semantic_evidence=semantic_evidence)
    for cluster in sem.get("keyword_clusters") or []:
        if isinstance(cluster, dict):
            for value in cluster.get("candidates") or []:
                _add(candidates, value, "semantic_cluster", "long_tail", content_terms, visual_terms, semantic_evidence=semantic_evidence)
    for entity in entity_rows:
        if isinstance(entity, dict):
            _add(candidates, entity.get("entity"), "entity", "entity", content_terms, visual_terms)
    for audience in sem.get("audience") or []:
        _add(candidates, audience, "semantic", "audience", content_terms, visual_terms, semantic_evidence=semantic_evidence)
    # Focused planner queries are deterministic combinations of creator-backed
    # concepts (for example ``silence in grief``).  They are often better
    # search phrases than isolated quote words, so admit them as candidates
    # only when the complete meaningful phrase is strongly source-supported.
    # Raw YouTube result wording is still never promoted into the pool.
    non_instructional = source_requires_noninstructional_framing(script, brief)
    for query in query_rows:
        query_text = _normalize(query.get("query"))
        support_score, _ = _source_support(query_text, source_terms)
        if (
            query_text
            and len(_tokens(query_text)) <= 3
            and support_score >= 70
            and not (non_instructional and has_unsupported_instructional_framing(query_text))
            and _visual_score(query_text, visual_terms) <= _content_score(query_text, content_terms)
        ):
            _add(candidates, query_text, "research_query", "long_tail", content_terms, visual_terms)
    # Creator intent and viewer promise can prove relevance, but they are prose
    # instructions rather than atomic search terms. Semantic candidates may use
    # their concepts; the full sentences must never become tags themselves.
    for value in _creator_visual_concepts(brief.get("visual_requirements") or ""):
        _add(candidates, value, "creator_visual", "contextual", content_terms, visual_terms)
    for opportunity in opportunities.get("opportunities") or []:
        if isinstance(opportunity, dict):
            _add(
                candidates, opportunity.get("concept"), "research_discovery", "opportunity",
                content_terms, visual_terms, opportunity=opportunity,
            )

    # Search suggestions are phrases real viewers type. One becomes a candidate
    # only when every word is grounded in the creator's source or declared
    # language/format — "chettinad chicken biryani in tamil" qualifies,
    # "... in malayalam" and "s25 ultra vs iphone 17" do not.
    demand_index = suggestion_index(search_demand)
    source_letters = _single_letters(script, brief.get("content"), quote)
    grounded_suggestions = [
        phrase for phrase in demand_index
        if _suggestion_is_grounded(phrase, source_terms, content_terms) and _mentions_subject(phrase, subjects)
        and not _foreign_single_letters(phrase, source_letters)
    ]
    for phrase in grounded_suggestions:
        _add(candidates, phrase, "search_demand", "long_tail", content_terms, visual_terms)
    # Scoring treats "real viewers type this" as research evidence, so the
    # rank must be known before a candidate is scored.
    for candidate in candidates.values():
        candidate["demand_rank"] = _validated_demand_rank(str(candidate.get("keyword") or ""), demand_index, subjects)

    scored: list[dict[str, Any]] = []
    rejected_before_selection = 0
    for candidate in candidates.values():
        entry = _score(candidate, result_rows, query_rows, quote, content_terms, source_terms, visual_terms)
        if entry and not (non_instructional and has_unsupported_instructional_framing(entry.get("keyword"))):
            _annotate_demand(entry, demand_index, subjects)
            scored.append(entry)
        else:
            rejected_before_selection += 1
    scored.sort(key=lambda item: (-item["keyword_relevance_score"], item["keyword"]))
    core_targets = [item for item in scored if item.get("classification") != "contextual"]
    visual_targets = [item for item in scored if item.get("classification") == "contextual"]
    research_targets = _diverse(core_targets, limit=7)
    if len(research_targets) < 8 and visual_targets:
        research_targets.extend(_diverse(visual_targets, limit=1))
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
    demand_validated = [item["keyword"] for item in scored if item.get("demand_validated")]
    demand_summary = {
        "status": str((search_demand or {}).get("status") or "not_checked"),
        "scope": "youtube_search_suggestions_not_volume",
        "queries": list((search_demand or {}).get("queries") or []),
        "suggestions": dict((search_demand or {}).get("suggestions") or {}),
        "grounded_suggestions": grounded_suggestions,
        "validated_keywords": demand_validated,
        "explanation": (
            "Phrases marked as validated appear in YouTube's own search suggestions, so real viewers type "
            "them. Suggestion rank reflects relative popularity for that prefix; it is not search volume."
        ),
    }
    return {
        "status": "youtube_evidence" if result_rows else "semantic_only",
        "confidence": "observed_youtube_relevance" if result_rows else "limited_without_youtube_research",
        "evidence_scope": "sampled_youtube_results_not_search_volume" if result_rows else "semantic_source_only",
        "search_volume_available": False,
        "search_demand_available": bool(demand_summary["suggestions"]),
        "search_demand": demand_summary,
        "subject_terms": sorted(subjects),
        "primary_topic": _normalize(sem.get("primary_topic")),
        "limitations": [
            "The YouTube Data API exposes sampled matching results, not keyword search volume.",
            "A returned result supports phrase relevance only when the required meaningful terms appear in its public metadata.",
        ],
        "semantic_source": sem.get("source", "unknown"),
        "candidate_count": len(scored), "candidates": scored[:40], "selected_keywords": [], "selected_tags": [],
        "research_targets": research_targets,
        "search_opportunities": opportunities,
        "diagnostics": diagnostics,
        "research_policy": "Source-grounded focused queries may become tag candidates; YouTube results only validate them and raw result phrases are never copied into tags.",
        "content_terms": sorted(content_terms), "visual_terms": sorted(visual_terms),
    }


def select_final_tags(
    research: dict[str, Any], *, generated_tags: Iterable[str], title: str, script: str,
    creator_brief: dict[str, Any] | None = None, is_short: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Select only strong, diverse, atomic concepts; never pad a tag count."""
    brief = creator_brief or {}
    short_requested = bool(is_short or is_short_content(script, brief))
    quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "")
    source_letters = _single_letters(script, brief.get("content"), quote)
    non_instructional = source_requires_noninstructional_framing(script, brief)
    content_terms = set(research.get("content_terms") or _tokens(script))
    visual_terms = set(research.get("visual_terms") or [])
    indexed = {
        str(item.get("keyword") or ""): dict(item) for item in research.get("candidates") or []
        if isinstance(item, dict) and item.get("keyword")
    }
    demand_index = suggestion_index(research.get("search_demand"))
    subjects = set(research.get("subject_terms") or [])

    # Model tags are suggestions, not authority. They need semantic support and
    # cannot create an unsupported niche or bypass the same validation rules.
    rejected_candidates: list[dict[str, Any]] = []
    for raw in generated_tags:
        for text in _atomic_concepts(raw):
            key = _normalize(text)
            if not key or key in indexed:
                continue
            classification, rejected = _classify(key, "model", content_terms, visual_terms)
            searched = _validated_demand_rank(key, demand_index, subjects) is not None
            if rejected or (_is_broad_emotional(key) and not searched) or not _semantic_support(key, content_terms):
                rejected_candidates.append({
                    "keyword": key or str(text),
                    "reason": rejected or ("broad_term_without_research_evidence" if _is_broad_emotional(key) else "missing_semantic_support"),
                    "source": "model_suggestion",
                })
                continue
            entry = _model_entry(key, classification, content_terms, visual_terms)
            _annotate_demand(entry, demand_index, subjects)
            indexed[key] = entry

    eligible: list[dict[str, Any]] = []
    rejected_count = 0
    for item in indexed.values():
        entry = dict(item)
        if non_instructional and has_unsupported_instructional_framing(entry.get("keyword")):
            rejected_count += 1
            rejected_candidates.append({"keyword": entry.get("keyword"), "reason": "unsupported_instructional_framing", "source": entry.get("source")})
            continue
        reject_reason = _reject_reason(entry, title, quote, content_terms)
        if reject_reason:
            rejected_count += 1
            rejected_candidates.append({"keyword": entry.get("keyword"), "reason": reject_reason, "source": entry.get("source")})
            continue
        if int(entry.get("source_support_score") or 0) < 50:
            rejected_count += 1
            rejected_candidates.append({"keyword": entry.get("keyword"), "reason": "weak_source_support", "source": entry.get("source")})
            continue
        # One-letter model names carry the whole difference: "xbox series s"
        # passed as grounded on a video about the Series X.
        if _foreign_single_letters(entry.get("keyword"), source_letters):
            rejected_count += 1
            rejected_candidates.append({"keyword": entry.get("keyword"), "reason": "model_letter_not_in_source", "source": entry.get("source")})
            continue
        # Entity signals are lifted from competitor titles. A name the creator
        # only partly used ("No Repeat Home" from "No Repeat Home Workout")
        # names a different video, unless viewers demonstrably search it.
        if (
            entry.get("source") == "entity"
            and int(entry.get("source_support_score") or 0) < 100
            and not entry.get("demand_validated")
        ):
            rejected_count += 1
            rejected_candidates.append({"keyword": entry.get("keyword"), "reason": "entity_not_in_source", "source": entry.get("source")})
            continue
        if int(entry.get("keyword_relevance_score") or 0) < 50:
            rejected_count += 1
            rejected_candidates.append({"keyword": entry.get("keyword"), "reason": "below_minimum_tag_quality", "source": entry.get("source")})
            continue
        eligible.append(entry)
    eligible.sort(key=lambda item: (-item["keyword_relevance_score"], item["keyword"]))
    if short_requested:
        # A Short has five tag slots. Phrases viewers really type fill them
        # first; a high-scoring interpretation such as "trust violation" had
        # been taking the slots of "betrayal quotes".
        eligible.sort(key=lambda item: not item.get("demand_validated"))
    primary_codes ={token for token in _tokens(research.get("primary_topic")) if _MODEL_CODE_RE.fullmatch(token)}
    # A phrase YouTube was asked about and has no completions for is one
    # nobody types ("vlookup sumif if formula chatgpt").
    unsearched = {
        _normalize(query) for query, rows in ((research.get("search_demand") or {}).get("suggestions") or {}).items()
        if not rows
    }
    chosen = _diverse_tag_selection(eligible, limit=5 if short_requested else 12, subjects=subjects,
                                    primary_codes=primary_codes, unsearched=unsearched)
    if short_requested:
        chosen_keywords = {item["keyword"] for item in chosen}
        for tag in _PREFERRED_SHORT_TAGS:
            if tag not in chosen_keywords:
                chosen.append(_platform_tag_entry(tag))
    tags = [item["keyword"] for item in chosen]
    chosen_keys = set(tags)
    for item in eligible:
        if item["keyword"] not in chosen_keys:
            rejected_candidates.append({"keyword": item["keyword"], "reason": "duplicate_or_low_diversity", "source": item.get("source")})
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
        "rejected_candidates": rejected_candidates,
        "tag_provenance": [
            {
                "tag": item["keyword"],
                "provenance": item.get("source_classification"),
                "source_support": item.get("source_support"),
                "source_support_score": item.get("source_support_score"),
                "intent": item.get("intent"),
                "topic_cluster": item.get("cluster"),
                "specificity": item.get("specificity_score"),
                "evidence_strength": item.get("research_evidence_score"),
                "matching_result_count": item.get("evidence_count"),
                "query_alignment_score": item.get("query_alignment_score"),
                "score": item.get("keyword_relevance_score"),
            }
            for item in chosen
        ],
        "selected_result_evidence": {
            "tags_with_matching_results": [
                item["keyword"] for item in chosen
                if item.get("classification") != "platform_format" and int(item.get("evidence_count") or 0) > 0
            ],
            "tags_without_matching_results": [
                item["keyword"] for item in chosen
                if item.get("classification") != "platform_format" and int(item.get("evidence_count") or 0) == 0
            ],
            "scope": "sampled_youtube_results_not_search_volume",
            "search_volume_available": False,
        },
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
        "selection_policy": "Tags are atomic source-grounded search concepts. Multi-word result evidence requires strict phrase-term coverage; planned-query alignment is scored separately and is never represented as search volume. A second tag from the same topic family is retained only when it independently clears 72 or has matching-result evidence and keeps the selected subject-tag average at or above 72. Weak generic, visual-only, title-copy, quote-copy, malformed, duplicate, competitor-derived, and unsupported candidates are excluded; visual context is capped at one tag. The creator-preferred yt and shorts platform tags are appended only for Shorts.",
    }
    return tags, evidence


def synchronize_tag_evidence(evidence: dict[str, Any], tags: Iterable[str]) -> dict[str, Any]:
    """Rebuild every selected-tag view from one authoritative final tag list."""

    result = dict(evidence or {})
    final_tags = list(dict.fromkeys(_normalize(tag) for tag in tags if _normalize(tag)))
    indexed = {
        _normalize(item.get("keyword")): dict(item)
        for item in [*(result.get("selected_keywords") or []), *(result.get("candidates") or [])]
        if isinstance(item, dict) and _normalize(item.get("keyword"))
    }
    selected: list[dict[str, Any]] = []
    for tag in final_tags:
        row = indexed.get(tag)
        if row is None and tag in _PREFERRED_SHORT_TAGS:
            row = _platform_tag_entry(tag)
        if row is not None:
            selected.append(row)
    subject = [item for item in selected if item.get("classification") != "platform_format"]
    contribution = [item for item in subject if item.get("source_classification") in {"combined", "research_discovered"}]
    result.update({
        "selected_keywords": selected,
        "selected_tags": [item["keyword"] for item in selected],
        "tag_provenance": [{
            "tag": item["keyword"], "provenance": item.get("source_classification"),
            "source_support": item.get("source_support"),
            "source_support_score": item.get("source_support_score"), "intent": item.get("intent"),
            "topic_cluster": item.get("cluster"), "specificity": item.get("specificity_score"),
            "evidence_strength": item.get("research_evidence_score"),
            "matching_result_count": item.get("evidence_count"),
            "query_alignment_score": item.get("query_alignment_score"),
            "score": item.get("keyword_relevance_score"),
        } for item in selected],
        "selected_result_evidence": {
            "tags_with_matching_results": [item["keyword"] for item in subject if int(item.get("evidence_count") or 0) > 0],
            "tags_without_matching_results": [item["keyword"] for item in subject if int(item.get("evidence_count") or 0) == 0],
            "scope": "sampled_youtube_results_not_search_volume", "search_volume_available": False,
        },
    })
    previous = dict(result.get("research_contribution") or {})
    previous.update({
        "research_selected_count": len(contribution),
        "combined_selected_count": sum(item.get("source_classification") == "combined" for item in contribution),
        "research_discovered_selected_count": sum(item.get("source_classification") == "research_discovered" for item in contribution),
        "selected_concepts": [item["keyword"] for item in contribution],
        "research_enhanced_tags": [item["keyword"] for item in selected],
    })
    result["research_contribution"] = previous
    return result


def _add(
    target: dict[str, dict[str, Any]], value: Any, source: str, hint: str,
    content_terms: set[str], visual_terms: set[str], opportunity: dict[str, Any] | None = None,
    semantic_evidence: dict[str, dict[str, str]] | None = None,
) -> None:
    for raw in _atomic_concepts(value):
        text = _normalize(raw)
        if not text:
            continue
        classification, rejected = _classify(text, hint, content_terms, visual_terms)
        if rejected:
            continue
        proof = (semantic_evidence or {}).get(text)
        actual_source = "semantic_visual" if proof and proof.get("source_scope") == "visual" else source
        if actual_source == "semantic_visual":
            classification = "contextual"
        entry = target.setdefault(text, {"keyword": text, "sources": set(), "classification": classification})
        entry["sources"].add(actual_source)
        if proof:
            entry["semantic_evidence"] = dict(proof)
        if opportunity:
            entry["opportunity"] = dict(opportunity)
        if _class_rank(classification) < _class_rank(str(entry.get("classification") or "generic")):
            entry["classification"] = classification


def _score(candidate: dict[str, Any], results: list[dict[str, Any]], queries: list[dict[str, Any]], quote: str, content_terms: set[str], source_terms: set[str], visual_terms: set[str]) -> dict[str, Any] | None:
    text = str(candidate["keyword"])
    classification = str(candidate.get("classification") or "generic")
    opportunity = candidate.get("opportunity") if isinstance(candidate.get("opportunity"), dict) else {}
    semantic_evidence = candidate.get("semantic_evidence") if isinstance(candidate.get("semantic_evidence"), dict) else {}
    semantic_confirmation = bool(opportunity.get("semantic_confirmed")) and int(opportunity.get("script_relevance_score") or 0) >= 70
    # Gemini confirmation may score and describe an opportunity, but it cannot
    # replace an actual anchor in the creator source/semantic core. This stops
    # a related-result theme from inventing a new situation, diagnosis, or
    # relationship event around the video.
    creator_visual = "creator_visual" in (candidate.get("sources") or [])
    if not _semantic_support(text, content_terms) and not (creator_visual and _visual_score(text, visual_terms)):
        return None
    source_support_score, source_support = _source_support(text, source_terms)
    if semantic_evidence:
        source_support_score = max(source_support_score, 85)
        source_support = (
            f"validated {semantic_evidence.get('relationship', 'semantic')} interpretation of creator phrase: "
            f"{semantic_evidence.get('source_phrase', '')}"
        )[:300]
    if "research_discovery" in (candidate.get("sources") or []) and source_support_score < 70:
        return None
    content_relevance = max(
        _content_score(text, content_terms),
        min(42, int(opportunity.get("script_relevance_score") or 0) // 2) if semantic_confirmation else 0,
    )
    visual_relevance = _visual_score(text, visual_terms)
    evidence_count = _evidence_count(text, results)
    tokens = set(_tokens(text))
    if evidence_count >= 1 and tokens and len(tokens & content_terms) == len(tokens) and len(tokens) >= 2:
        content_relevance = max(content_relevance, 42)
    # A broad emotional phrase needs evidence that people look for it. Two
    # matching results were the only accepted proof; appearing in YouTube's
    # own search suggestions ("betrayal quotes") is stronger proof of exactly that.
    if _is_broad_emotional(text) and evidence_count < 2 and candidate.get("demand_rank") is None:
        return None
    if classification == "entity" and content_relevance < 28:
        return None
    if classification == "audience" and (content_relevance < 42 or _evidence_count(text, results) == 0):
        return None
    if classification == "contextual" and (
        source_support_score < 70 or evidence_count < 1
    ):
        return None
    query_support = _query_support(text, queries)
    opportunity_evidence = int(opportunity.get("research_relevance_score") or 0)
    evidence_score = min(24, evidence_count * 8)
    if semantic_confirmation and evidence_count:
        evidence_score = max(evidence_score, min(24, opportunity_evidence // 4))
    query_alignment_score = min(4, query_support * 2)
    intent_score = _intent_score(classification)
    specificity = _specificity_score(text)
    focused_evidence_phrase = bool(
        "research_query" in (candidate.get("sources") or [])
        and evidence_count >= 1
        and 1 < len(_tokens(text)) <= 4
    )
    grounded_paraphrase = bool(semantic_evidence and semantic_evidence.get("source_scope") != "visual"
        and 1 < len(_tokens(text)) <= 4 and _normalize(text) not in _normalize(quote))
    quote_copy_penalty = 18 if _quote_like(text, quote) and not (focused_evidence_phrase or grounded_paraphrase) else 0
    total = max(0, min(100, content_relevance + evidence_score + query_alignment_score + intent_score + specificity + source_support_score // 7 - quote_copy_penalty))
    if total < 28:
        return None
    sources = sorted(candidate.get("sources") or [])
    source_classification = _source_classification(sources, evidence_count, semantic_confirmation)
    return {
        "keyword": text, "sources": sources, "source": "+".join(sources), "source_classification": source_classification,
        "classification": classification,
        "content_relevance_score": content_relevance, "visual_relevance_score": visual_relevance,
        "source_support_score": source_support_score, "source_support": source_support,
        "research_evidence_score": evidence_score, "query_alignment_score": query_alignment_score,
        "intent_score": intent_score, "specificity_score": specificity,
        "diversity_score": None, "keyword_relevance_score": total, "evidence_count": evidence_count,
        "semantic_confirmed": semantic_confirmation,
        "semantic_evidence": semantic_evidence or None,
        "cluster": str(opportunity.get("cluster") or _family(text)),
        "intent": str(opportunity.get("intent") or _intent_label(classification)),
        "selection_reason": _reason(classification, evidence_count, query_support, source_classification),
        "reason": _reason(classification, evidence_count, query_support, source_classification),
    }


def _semantic_evidence_map(semantic: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Expose only evidence that passed semantic_research's creator-source checks."""

    if semantic.get("concept_evidence_validated") is not True:
        return {}
    result: dict[str, dict[str, str]] = {}
    for item in semantic.get("concept_evidence") or []:
        if not isinstance(item, dict):
            continue
        concept = _normalize(item.get("concept"))
        phrase = str(item.get("source_phrase") or "").strip()
        relationship = str(item.get("relationship") or "").strip().casefold()
        source_scope = str(item.get("source_scope") or "content").strip().casefold()
        if concept and phrase and relationship in {"direct", "paraphrase", "metaphor"}:
            result[concept] = {
                "concept": concept, "source_phrase": phrase, "relationship": relationship,
                "source_scope": "visual" if source_scope == "visual" else "content",
            }
    return result


def _platform_tag_entry(text: str) -> dict[str, Any]:
    return {
        "keyword": text, "sources": ["creator_strategy"], "source": "creator_strategy",
        "source_classification": "creator_strategy", "classification": "platform_format",
        "content_relevance_score": 0, "visual_relevance_score": 0,
        "source_support_score": 100, "source_support": "creator-preferred Shorts discovery tag",
        "research_evidence_score": 0, "intent_score": 0, "specificity_score": 0,
        "diversity_score": 100.0, "keyword_relevance_score": 0, "evidence_count": 0,
        "cluster": "platform", "intent": "format_discovery",
        "selection_reason": "Explicit creator strategy preference for Shorts uploads.",
        "reason": "Explicit creator strategy preference for Shorts uploads.",
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
    words = text.split()
    # A named entity never starts with a bare verb. "make chettinad chicken"
    # is a capitalised run lifted out of a competitor title
    # ("How To Make Chettinad Chicken Biryani"), not an entity.
    if hint == "entity" and words and words[0] in _ENTITY_VERB_STARTS:
        return "malformed", "malformed_entity"
    if _repeats_a_word(text):
        return "malformed", "repeated_word"
    if _noisy(text):
        return "irrelevant", "noisy_competitor_phrase"
    if _ungrounded_number(text, content_terms):
        return "irrelevant", "number_not_in_source"
    if _creator_instruction_leak(text):
        return "irrelevant", "creator_instruction_leakage"
    if _fragmented(text):
        return "malformed", "fragmented_phrase"
    if hint == "search_intent" and _tokens(text) and _tokens(text)[0] in {"discover", "explore", "find", "watch", "lovers"}:
        return "malformed", "non_search_instruction"
    if _visual_score(text, visual_terms) > _content_score(text, content_terms):
        return "contextual", None
    return {"core_topic": "core_topic", "secondary_topic": "secondary_topic", "search_intent": "search_intent", "long_tail": "long_tail", "opportunity": "long_tail", "entity": "entity", "audience": "audience"}.get(hint, "secondary_topic"), None


def _reject_reason(entry: dict[str, Any], title: str, quote: str, content_terms: set[str]) -> str | None:
    text = str(entry.get("keyword") or "")
    classification = str(entry.get("classification") or "generic")
    if classification in {"generic", "malformed", "irrelevant"} or _is_generic(text) or _malformed(text) or _noisy(text):
        return classification
    words = _tokens(text)
    if quote and _normalize(text) in {"heart and soul"}:
        return "ambiguous_quote_fragment"
    if quote and re.match(r"^(?:why|how) am i\b", _normalize(text)) and not re.search(r"\b(?:i|i'm|i am)\b", quote, re.IGNORECASE):
        return "unsupported_perspective_shift"
    if words and words[0] in {"discover", "embracing", "finding", "explore", "watch"} and words[0] not in content_terms:
        return "unsupported_action_framing"
    if classification == "contextual" and (
        int(entry.get("source_support_score") or 0) < 70
        or int(entry.get("research_evidence_score") or 0) < 8
    ):
        return "visual_only"
    if classification != "contextual" and not _semantic_support(text, content_terms):
        return "irrelevant"
    evidence = int(entry.get("research_evidence_score") or 0)
    # Search evidence can validate a source-grounded concept, but it cannot
    # turn a chopped portion of the on-screen quote into a useful tag.  Exact
    # quote fragments are both weak search language and a common source of
    # malformed endings such as "some people only value when".
    focused_query_phrase = bool(
        "research_query" in (entry.get("sources") or [])
        and int(entry.get("evidence_count") or 0) >= 1
        and 1 < len(words) <= 4
    )
    grounded_paraphrase = bool(entry.get("semantic_evidence")
        and 1 < len(words) <= 4 and _normalize(text) not in _normalize(quote))
    # "painful love" reuses two quote words but is not a chopped span of the
    # quote, and viewers really search it; only contiguous fragments are copies.
    # Raw words: "betrayal quotes" is two typed words even though "quotes" is
    # a stopword for relevance scoring.
    searched_recombination = bool(entry.get("demand_validated")
        and 1 < len(_normalize(text).split()) <= 4 and _normalize(text) not in _normalize(quote))
    if _quote_like(text, quote) and not (focused_query_phrase or grounded_paraphrase or searched_recombination):
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


# YouTube caps the tag field at 500 characters (multi-word tags count their
# quotes). Stay safely under it.
_TAG_CHARACTER_BUDGET = 450


def _tag_field_length(tags: Iterable[str]) -> int:
    values = list(tags)
    return sum(len(tag) + (2 if " " in tag else 0) for tag in values) + max(0, len(values) - 1)


def _tag_modifiers(keyword: str, subjects: set[str] | None) -> list[str]:
    """Words that narrow a search without naming the subject ("price", "india").

    Format and intent words ("tutorial", "review", "beginners") are how people
    search a subject at all, so they are not counted.
    """

    if not subjects:
        return []
    return [
        token for token in dict.fromkeys(_tokens(keyword))
        if token not in _GENERIC_SUBJECT_WORDS
        and token not in _FUNCTION_WORDS
        and not _mentions_subject(token, subjects)
    ]


def _diverse_tag_selection(
    items: list[dict[str, Any]], *, limit: int, subjects: set[str] | None = None,
    primary_codes: set[str] | None = None, unsearched: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Select diverse subject tags while allowing at most one visual-context tag.

    Variants of the main keyword that real viewers type ("cold brew coffee",
    "cold brew coffee recipe", "how to make cold brew coffee at home") are
    different searches, not duplicates. Demand-validated variants may share a
    topic family; unvalidated near-duplicates are still pruned.
    """

    selected: list[dict[str, Any]] = []
    family_counts: dict[str, int] = {}
    modifier_counts: dict[str, int] = {}
    other_model_count = 0
    visual_count = 0
    # When real searches are available, they fill the tag field first and
    # unvalidated phrases only top it up. Script wording such as "just
    # starting out" or "keep your knees safe" is grounded, but nobody searches it.
    validated_available = sum(
        1 for item in items if item.get("demand_validated") and item.get("classification") != "contextual"
    )
    demand_rich = validated_available >= 3
    unvalidated_cap = 4 if demand_rich else limit
    unvalidated_count = 0
    for item in items:
        contextual = item.get("classification") == "contextual"
        if contextual and visual_count >= 1:
            continue
        if _tag_field_length([*(chosen["keyword"] for chosen in selected), item["keyword"]]) > _TAG_CHARACTER_BUDGET:
            continue
        # A review that asks "worth upgrading from the S24 Ultra?" once earned
        # four S24 tags; one comparison tag helps, more dilute the S25 targeting.
        keyword_tokens = set(_tokens(item["keyword"]))
        other_model = bool(primary_codes) and not (keyword_tokens & primary_codes) and any(
            _MODEL_CODE_RE.fullmatch(token) for token in keyword_tokens
        )
        if other_model and other_model_count >= 1:
            continue
        # Only prune once enough real searches exist to fill the space, and
        # never prune a semantically validated interpretation ("new
        # beginnings" for "doors closing are protection").
        if demand_rich and not contextual and not item.get("demand_validated"):
            if subjects and not item.get("semantic_evidence") and not _mentions_subject(item["keyword"], subjects):
                continue  # names nothing this video is about
            if unvalidated_count >= unvalidated_cap:
                continue
            if _normalize(item["keyword"]) in (unsearched or set()):
                continue  # YouTube has no searches starting with it
        if item.get("demand_validated") and not contextual:
            # Five "... price in india" variants crowd a review's tag field
            # with one sub-intent; a non-subject modifier may recur only twice.
            modifiers = _tag_modifiers(item["keyword"], subjects)
            if any(modifier_counts.get(modifier, 0) >= 2 for modifier in modifiers):
                continue
            family = _family(item["keyword"])
            # Compare the words viewers type: relevance tokens drop "sad" and
            # "quotes", which made "sad betrayal quotes" a copy of "betrayal quotes".
            exact_overlap = max((_typed_similarity(item["keyword"], chosen["keyword"]) for chosen in selected), default=0.0)
            if family_counts.get(family, 0) < 4 and exact_overlap < 0.9:
                chosen = dict(item)
                chosen["diversity_score"] = round(max(0.0, 100.0 - exact_overlap * 100.0), 1)
                selected.append(chosen)
                family_counts[family] = family_counts.get(family, 0) + 1
                other_model_count += int(other_model)
                for modifier in modifiers:
                    modifier_counts[modifier] = modifier_counts.get(modifier, 0) + 1
                if len(selected) >= limit:
                    break
                continue
        backed_count = sum(
            1 for chosen in selected
            if chosen.get("classification") != "contextual" and int(chosen.get("evidence_count") or 0) > 0
        )
        # Once two subject phrases have genuine matching-result support, do
        # not lower the whole package by padding it with a sub-threshold,
        # source-only phrase. Fewer strong tags are preferable to more weak
        # ones, while source-only fallback remains available when research is
        # sparse for a niche script.
        if (
            not contextual
            and backed_count >= 2
            and int(item.get("evidence_count") or 0) == 0
            and int(item.get("keyword_relevance_score") or 0) < 72
        ):
            continue
        family = _family(item["keyword"])
        overlap = max((_evidence_similarity(item["keyword"], chosen["keyword"]) for chosen in selected), default=0.0)
        family_count = family_counts.get(family, 0)
        subject_scores = [
            int(chosen.get("keyword_relevance_score") or 0) for chosen in selected
            if chosen.get("classification") != "contextual"
        ]
        item_score = int(item.get("keyword_relevance_score") or 0)
        projected_average = (sum(subject_scores) + item_score) / max(len(subject_scores) + 1, 1)
        evidence_backed_extension = bool(
            int(item.get("evidence_count") or 0) > 0 and projected_average >= 72
        )
        if (
            overlap >= 0.67
            or family_count >= 2
            or (family_count == 1 and item_score < 72 and not evidence_backed_extension)
            or (len(subject_scores) >= 3 and (sum(subject_scores) / len(subject_scores)) >= 90.0 and projected_average < 90.0)
        ):
            continue
        chosen = dict(item)
        chosen["diversity_score"] = round(max(0.0, 100.0 - overlap * 100.0), 1)
        selected.append(chosen)
        family_counts[family] = family_counts.get(family, 0) + 1
        other_model_count += int(other_model)
        visual_count += int(contextual)
        unvalidated_count += int(not contextual and not item.get("demand_validated"))
        if len(selected) >= limit:
            break
    return selected


def _is_broad_emotional(text: str) -> bool:
    words = set(_tokens(text))
    return bool(words & _BROAD_EMOTIONAL_TERMS) and len(words) <= 3


def _content_terms(semantic: dict[str, Any], script: str, brief: dict[str, Any]) -> set[str]:
    # Only creator source and the semantic core establish relevance. Search
    # intents and cluster candidates are proposals to validate, never proof of
    # themselves.
    values: list[Any] = [semantic.get("primary_topic"), *(semantic.get("secondary_topics") or [])]
    if _brief_field_is_creator_supplied(brief, "creator_intent"):
        values.append(brief.get("creator_intent"))
    if _brief_field_is_creator_supplied(brief, "viewer_promise"):
        values.append(brief.get("viewer_promise"))
    values.append(script)
    visual_context = set(_tokens(brief.get("visual_requirements") or "")) | _VISUAL_TERMS
    # Declared language/format terms are deliberately NOT content terms: they
    # may complete a phrase ("... in tamil") but must never make a tag relevant
    # on their own ("tamil songs" on a biryani video).
    return {token for value in values for token in _tokens(value) if token not in visual_context}


_LANGUAGE_SEARCH_WORDS = {
    "tamil": {"tamil", "tamizh", "thamizh"},
    "tanglish": {"tamil", "tamizh", "thamizh"},
    "hindi": {"hindi"},
    "hinglish": {"hindi"},
}
_FORMAT_SEARCH_WORDS = {
    "tutorial": {"tutorial"}, "review": {"review"}, "unboxing": {"unboxing"},
    "vlog": {"vlog"}, "comparison": {"comparison", "vs"}, "educational": {"explained"},
}


def _declared_context_terms(script: str, brief: dict[str, Any]) -> set[str]:
    """Facts the creator declared about the video rather than said in it.

    "chicken biryani recipe in tamil" is how Tamil viewers search, and "tamil"
    is true of a video the creator marked as Tamil even though the script
    never says the word. The same holds for the declared format.
    """

    terms: set[str] = set()
    language = str(brief.get("language") or brief.get("video_language") or "").casefold()
    terms |= _LANGUAGE_SEARCH_WORDS.get(language, set())
    if has_tamil(script) or has_tamil(brief.get("content")):
        terms |= _LANGUAGE_SEARCH_WORDS["tamil"]
    video_format = str(brief.get("video_format") or "").casefold().strip()
    terms |= _FORMAT_SEARCH_WORDS.get(video_format, set())
    return terms


def _source_terms(script: str, brief: dict[str, Any]) -> set[str]:
    """Use only creator supplied material to prove a research-derived tag."""
    values = [script]
    values.extend(brief.get(field) for field in (
        "content", "exact_quote", "on_screen_text", "topic", "viewer_promise", "unique_angle",
        "factual_claims", "visual_requirements", "creator_intent", "content_constraints",
    ))
    return {token for value in values for token in _tokens(value)} | _declared_context_terms(script, brief)


def _creator_visual_concepts(value: Any) -> list[str]:
    """Extract only explicit, searchable visual actions/settings from creator notes."""

    text = _normalize(value)
    concepts: list[str] = []
    if re.search(r"\b(?:person|man|woman|boy|girl)\s+(?:is\s+)?walking\s+alone\b", text):
        concepts.append("walking alone")
    if re.search(r"\bquiet\s+streets?\b", text):
        concepts.append("quiet streets")
    if "rain" in _tokens(text) or "rainy" in _tokens(text):
        concepts.append("walking in rain" if "walking" in _tokens(text) else "rainy scene")
    return concepts


def _source_support(text: str, source_terms: set[str]) -> tuple[int, str]:
    words = set(_tokens(text))
    if not words:
        return 0, "no source concept"
    source_roots = {_term_root(word) for word in source_terms}
    cross_script = _cross_script_keys(source_terms)
    matched = {
        word for word in words
        if word in source_terms or _term_root(word) in source_roots or _sounds_grounded(word, cross_script)
    }
    # A related search result cannot add an unrelated domain, use case, or
    # decision frame merely because it is popular in YouTube search.
    unsupported_context = {"gaming", "performance", "region", "choosing", "correct", "best"}
    if any(word in unsupported_context and word not in source_terms for word in words):
        return 0, "unsupported adjacent context"
    ratio = len(matched) / len(words)
    if ratio >= 1.0:
        return 100, "direct creator-source support"
    # A few narrow semantic bridges preserve natural search wording for an
    # explicitly supplied emotional idea. They are source-led, documented,
    # and never introduce a new life context, diagnosis, or relationship fact.
    source_roots = {_term_root(word) for word in source_terms}
    word_roots = {_term_root(word) for word in words}
    if word_roots <= {"feel", "forgotten"} and source_roots & {"erase", "abandon", "forgotten", "unseen"}:
        return 70, "emotional-absence semantic bridge"
    if word_roots <= {"unspoken", "feel"} and source_roots & {"heart", "imagine", "life", "knew"}:
        return 70, "unspoken-feelings semantic bridge"
    if word_roots <= {"being", "need", "but", "not", "chosen"} and source_roots & {"need", "choose", "chos"}:
        return 70, "needed-not-chosen semantic bridge"
    worth_source = bool(source_roots & {"deserve", "worth", "rare", "find"})
    if worth_source and word_roots <= {
        "know", "worth", "being", "value", "hard", "replace", "rare", "person",
        "genuine", "appreciation", "appreciate",
    }:
        return 80, "rarity-and-worth semantic bridge"
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
    tokens = set(_tokens(text))
    matched = tokens & content_terms
    keys = _cross_script_keys(content_terms)
    if keys:
        matched |= {token for token in tokens if _sounds_grounded(token, keys)}
    return min(42, len(matched) * 14)


def _visual_score(text: str, visual_terms: set[str]) -> int:
    return min(24, len(set(_tokens(text)) & (visual_terms | _VISUAL_TERMS)) * 12)


def _evidence_count(text: str, results: list[dict[str, Any]]) -> int:
    """Count strict public-result matches without pretending they are search volume.

    Two-word phrases require both meaningful words. Longer phrases require at
    least 75% of their meaningful words (and never fewer than two). This stops
    a broad anchor such as ``grief`` from validating ``absence in grief`` by
    itself.
    """

    words = set(_evidence_tokens(text))
    if not words:
        return 0
    required = 1 if len(words) == 1 else max(2, (len(words) * 3 + 3) // 4)
    return sum(
        1
        for row in results
        if len(words & set(_evidence_tokens(f"{row.get('title') or ''} {row.get('description') or ''}"))) >= required
    )


def _query_support(text: str, queries: list[dict[str, Any]]) -> int:
    words = set(_evidence_tokens(text))
    if not words:
        return 0
    return sum(
        1 for item in queries
        if words <= set(_evidence_tokens(item.get("query") or ""))
    )


def _intent_score(classification: str) -> int:
    return {"core_topic": 16, "secondary_topic": 15, "search_intent": 20, "long_tail": 18, "entity": 12, "audience": 8, "contextual": 3}.get(classification, 0)


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
    return any(token in _NOISY_TERMS for token in _tokens(text))


def _ungrounded_number(text: str, grounded_terms: set[str]) -> bool:
    """A number the creator never wrote, such as a stale year from a competitor title.

    Any token containing a digit used to be rejected outright, which removed
    the terms tech and gaming viewers actually search: "galaxy s25 ultra",
    "iphone 16", "windows 11", "ps5". Model numbers and figures that appear in
    the creator's own source are grounded and kept.
    """

    return any(
        any(char.isdigit() for char in token) and token not in grounded_terms
        for token in _tokens(text)
    )


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
    roots = {_term_root(term) for term in content_terms}
    tokens = _tokens(text)
    if set(tokens) & content_terms or any(_term_root(term) in roots for term in tokens):
        return True
    keys = _cross_script_keys(content_terms)
    return any(_sounds_grounded(term, keys) for term in tokens)


def _term_root(value: str) -> str:
    """Small deterministic inflection bridge; this is not synonym expansion."""

    word = str(value or "").casefold()
    if word in {"rarity", "rarities"}:
        return "rare"
    if word in {"valued", "values", "valuing"}:
        return "value"
    if word in {"appreciated", "appreciates", "appreciating"}:
        return "appreciate"
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
        if len(word) > 2 and word[-1:] == word[-2:-1]:
            word = word[:-1]
    elif len(word) > 4 and word.endswith("ied"):
        word = word[:-3] + "y"
    elif len(word) > 4 and word.endswith("ed"):
        word = word[:-1] if word[-2:-1] == "e" else word[:-2]
    elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word


def _brief_field_is_creator_supplied(brief: dict[str, Any], field: str) -> bool:
    row = ((brief.get("field_provenance") or {}).get(field) or {})
    return bool(brief.get(field)) and (not row or row.get("source") == "creator_supplied")


def _quote_like(text: str, quote: str) -> bool:
    normalized, normalized_quote = _normalize(text), _normalize(quote)
    # A compact state/concept such as ``being misunderstood`` is a useful
    # search phrase even when those exact two words occur in the quote.  This
    # exception is deliberately narrow; long copied clauses remain blocked.
    words = _tokens(text)
    if len(words) == 2 and words[0] in {"being", "feeling"} and words[1] in {
        "misunderstood", "genuine", "valued", "chosen",
    }:
        return False
    if len(normalized) >= 8 and normalized in normalized_quote:
        return True
    word_set, quote_words = set(words), set(_tokens(quote))
    return len(word_set) >= 2 and bool(word_set) and len(word_set & quote_words) / len(word_set) >= 0.8


def _title_copy(text: str, title: str) -> bool:
    words, title_words = set(_tokens(text)), set(_tokens(title))
    return len(words) >= 2 and bool(words) and len(words & title_words) / len(words) >= 0.8


def _family(text: str) -> str:
    words = set(_tokens(text))
    if words & {"forgotten", "unseen", "erased", "abandoned", "abandonment", "rejection", "absence", "distance", "invisible"}:
        return "emotional_absence"
    if "silence" in words:
        return "silence"
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


_TYPED_FILLER = {"the", "a", "an", "of", "in", "for", "to", "and", "on", "with"}


def _typed_similarity(left: str, right: str) -> float:
    a = set(_normalize(left).split()) - _TYPED_FILLER
    b = set(_normalize(right).split()) - _TYPED_FILLER
    return len(a & b) / max(len(a | b), 1)


def _evidence_similarity(left: str, right: str) -> float:
    """Compare final tags while retaining intent words such as quote/quotes."""

    a, b = set(_evidence_tokens(left)), set(_evidence_tokens(right))
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
        return f"{label} was Gemini-confirmed against the creator source and supported by matching sampled YouTube result metadata; this is not search-volume evidence."
    if evidence_count:
        return f"{label} supported by semantic analysis and matching sampled YouTube result metadata; this is not search-volume evidence."
    if query_support:
        return f"{label} derived from semantic analysis and aligned with a planned query; no matching-result or search-volume claim is made."
    return f"{label} derived from semantic analysis; no search-volume claim is made."


def _normalize(value: Any) -> str:
    # Tamil script is kept. Stripping everything outside [A-Za-z0-9] turned a
    # Tamil script into an empty string, so a Tamil video had no source terms
    # at all and every tag was automatically "unsupported".
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9஀-௿' -]", " ", str(value or "").casefold())).strip(" -")


def _tokens(value: Any) -> list[str]:
    return [
        word for word in re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?|[஀-௿]+", _normalize(value))
        if word not in _STOP and len(word) > 1
    ]


def _cross_script_keys(terms: Iterable[str]) -> set[str]:
    """Phonetic keys of the source, only when it contains Tamil script.

    Sound-alike matching is what lets an English search tag be grounded in a
    Tamil script. It is not applied to Latin-only sources: literal matching
    already works there, and phonetic keys would let unrelated sound-alikes
    ("bitter"/"better") pass as grounded.
    """

    words = list(terms)
    if not any(has_tamil(word) for word in words):
        return set()
    return phonetic_keys(words)


def _sounds_grounded(word: str, keys: set[str]) -> bool:
    return bool(keys) and phonetic_match(word, keys)


# Words that describe *how* a video treats its subject, not the subject itself.
# A phrase made only of these ("hidden details", "trailer breakdown") matches
# searches about every other video, so it proves nothing about this one.
_GENERIC_SUBJECT_WORDS = {
    "video", "videos", "tutorial", "review", "guide", "tips", "tip", "details", "detail",
    "hidden", "breakdown", "analysis", "comparison", "compare", "trailer", "map", "new",
    "best", "easy", "how", "make", "beginners", "beginner", "full", "complete", "part",
    "episode", "things", "thing", "people", "city", "series", "missed", "every", "explained",
    "recipe", "home", "simple", "quick", "top", "ultimate", "honest", "way", "ways",
}


# A product or model code such as "s24", "ps5" or "m3". Spec tokens that start
# with a digit ("200mp", "5g", "4k") are not models.
_MODEL_CODE_RE = re.compile(r"[a-z]+\d+[a-z0-9]*")
# A standalone letter or digit ("Series X", "GTA 5"); the "s" of "game's" is not one.
_SINGLE_CHAR_RE = re.compile(r"(?<![\w'’])[a-z0-9](?![\w'’])")


def _single_letters(*sources: Any) -> set[str]:
    return {char for source in sources for char in _SINGLE_CHAR_RE.findall(str(source or "").casefold())}


def _foreign_single_letters(keyword: Any, source_letters: set[str]) -> set[str]:
    """Standalone letters/digits in a phrase that the creator's source never uses.

    _tokens drops one-character words, so "xbox series s" looked fully
    grounded in a script about the Series X. "a" and "i" are ordinary words.
    """

    return set(_SINGLE_CHAR_RE.findall(str(keyword or "").casefold())) - source_letters - {"a", "i"}
# Pronouns and function words survive _tokens but never name a subject: a
# quote's only extracted "subject" was once "you", which blocked every seed.
_FUNCTION_WORDS = {
    "you", "your", "yours", "they", "them", "their", "we", "our", "us", "he", "him", "his",
    "she", "her", "it", "its", "me", "my", "mine", "is", "be", "been", "being", "am",
    "if", "so", "or", "an", "as", "by", "to", "do", "did", "does", "done", "would", "could",
    "should", "will", "can", "may", "might", "must", "never", "ever", "who", "whom", "which",
    "there", "then", "than", "no", "yes", "all", "any", "some", "one", "out", "up", "down",
    "off", "over", "only", "also", "too", "very", "even", "still", "yet", "didn't", "don't",
    "won't", "can't", "isn't", "wasn't", "that's", "it's", "you're", "they're", "i'm",
}
# Themes people search quote videos by ("betrayal quotes"). Semantic topics
# tend to paraphrase them away ("hidden deceit"), so a quote's own theme word
# is read from the creator's source directly.
# Words that mostly appear in idioms ("it's time to", "by heart") are left out.
_QUOTE_THEMES = {
    "alone", "attitude", "betrayal", "breakup", "cheating", "dreams", "ego", "faith", "fake",
    "family", "father", "friends", "friendship", "happiness", "heartbreak", "hope", "hurt",
    "karma", "kindness", "lies", "life", "loneliness", "love", "loyalty", "memories",
    "mother", "pain", "patience", "peace", "regret", "relationship", "relationships",
    "respect", "sacrifice", "silence", "strength", "success", "trust", "truth",
}


_PAINFUL_QUOTE_RE = re.compile(
    r"\b(?:pain(?:ful)?|hurts?|hurting|cry(?:ing)?|tears?|broken|lonely|alone|miss(?:ing)?|sad(?:ness)?|"
    r"heartbreak|regrets?|lost|never)\b",
    re.IGNORECASE,
)


def quote_themes(*sources: Any) -> list[str]:
    """Searchable theme words the creator's own words use, in source order."""

    found: list[str] = []
    for source in sources:
        for token in _tokens(source):
            if token in _QUOTE_THEMES and token not in found:
                found.append(token)
    return found


def _mentions_subject(text: str, subjects: set[str]) -> bool:
    if not subjects:
        return True  # no subject evidence available: do not filter
    tokens = set(_tokens(text))
    if tokens & subjects or {_term_root(token) for token in tokens} & {_term_root(term) for term in subjects}:
        return True
    keys = _cross_script_keys(subjects)
    return any(_sounds_grounded(token, keys) for token in tokens)


def subject_terms(
    semantic: dict[str, Any] | None, entity_signals: Iterable[Any], source_terms: set[str],
    *, themes: Iterable[str] = (),
) -> set[str]:
    """Words naming what this video is about, each grounded in the creator's source.

    Built from the semantic topic and entities plus extracted entity signals,
    keeping only words the creator actually used. Entity signals alone are
    unreliable — they are lifted from competitor titles and can name other
    videos entirely ("Avengers Doomsday") — so grounding is mandatory.
    ``themes`` are quote themes already read from the creator's own words.
    """

    sem = semantic or {}
    phrases: list[Any] = [sem.get("primary_topic"), *(sem.get("secondary_topics") or [])[:2]]
    for entity in sem.get("entities") or []:
        phrases.append(entity.get("name") or entity.get("entity") if isinstance(entity, dict) else entity)
    for row in entity_signals or []:
        if isinstance(row, dict):
            phrases.append(row.get("entity"))
    roots = {_term_root(term) for term in source_terms}
    keys = _cross_script_keys(source_terms)
    terms: set[str] = set(themes)
    for phrase in phrases:
        for token in _tokens(phrase):
            if token in _GENERIC_SUBJECT_WORDS or token in _FUNCTION_WORDS:
                continue
            if token in source_terms or _term_root(token) in roots or _sounds_grounded(token, keys):
                terms.add(token)
    return terms


def _written_as_name(word: str, source: str) -> bool:
    """True for a model code or a word the creator writes as a name.

    "FastAPI" and "GTA" read as names wherever they stand; "Munnar" counts
    when the source capitalises it mid-sentence, which "cold" never is.
    """

    if any(char.isdigit() for char in word):
        return True
    for match in re.finditer(rf"(?<![\w'’]){re.escape(word)}(?![\w'’])", source, re.IGNORECASE):
        form = match.group(0)
        if form[1:] != form[1:].lower():
            return True
    return source_casing_map(source).get(word.casefold(), "")[:1].isupper()


def demand_seed_phrases(
    research: dict[str, Any], semantic: dict[str, Any] | None, creator_brief: dict[str, Any] | None,
    *, limit: int = 6,
) -> list[str]:
    """Short, subject-anchored phrases to check against YouTube search suggestions.

    Seeds must name the video's subject. Generic seeds ("hidden details",
    "trailer breakdown") return suggestions about other videos entirely.
    Shorter heads return the richest variants: "fastapi tutorial" surfaces
    "fastapi tutorial in tamil", while "fastapi rest api tutorial" returns
    only itself.
    """

    subjects = set(research.get("subject_terms") or [])
    brief = creator_brief or {}
    video_format = str(brief.get("video_format") or "").casefold().strip()
    format_word = next(iter(_FORMAT_SEARCH_WORDS.get(video_format, set()) - {"vs"}), "")
    if format_word == "tutorial" and infer_category(f"{brief.get('content') or ''} {brief.get('topic') or ''}") == "cooking":
        format_word = "recipe"  # cooking viewers search "<dish> recipe", not "<dish> tutorial"
    seeds: list[str] = []

    def add(value: Any) -> None:
        phrase = _normalize(value)
        words = phrase.split()
        if not 1 <= len(words) <= 5 or phrase in seeds:
            return
        if any(phrase in seed for seed in seeds) or not _mentions_subject(phrase, subjects):
            return
        seeds.append(phrase)

    quote = brief.get("exact_quote") or brief.get("on_screen_text")
    if quote:
        # Quote viewers search by theme: "betrayal quotes", "trust quotes".
        themes = quote_themes(quote, brief.get("content"))[:2]
        for theme in themes:
            add(f"{theme} quotes")
        # A painful quote is searched as "sad love quotes"; only a quote that
        # actually voices pain earns the "sad" seed.
        if themes and _PAINFUL_QUOTE_RE.search(str(quote)):
            add(f"sad {themes[0]} quotes")
    primary = _normalize((semantic or {}).get("primary_topic"))
    if primary:
        # The head without trailing format words ("gta 6 trailer 2 breakdown"
        # -> "gta 6 trailer 2"), then the full topic.
        words = primary.split()
        while len(words) > 1 and words[-1] in _GENERIC_SUBJECT_WORDS:
            words = words[:-1]
        head = " ".join(words)
        add(head)
        if format_word:
            # "<subject> <format>" is how most people search tutorials and
            # reviews: "fastapi tutorial", "galaxy s25 ultra review".
            if len(words) <= 3:
                add(f"{head} {format_word}")
            # The first word alone must be a name ("fastapi tutorial"). An
            # adjective head ("cold" from "cold brew coffee") seeded "cold
            # recipe", whose suggestions shipped as the tag "cold recipes".
            first = words[0]
            if first in subjects and len(first) >= 4 and _written_as_name(first, str(brief.get("content") or "")):
                add(f"{first} {format_word}")
        add(primary)
    for candidate in research.get("candidates") or []:
        if len(seeds) >= limit:
            break
        if isinstance(candidate, dict) and candidate.get("classification") != "contextual":
            add(candidate.get("keyword"))
    return seeds[:limit]


_ENTITY_VERB_STARTS = {
    "make", "making", "cook", "cooking", "how", "watch", "try", "learn", "build", "get",
    "see", "check", "do", "use", "buy", "best", "top", "easy", "quick",
}


# Words a searcher adds that describe the *kind* of video rather than claim a
# new fact about it. A suggestion may carry at most one of these beyond the
# words grounded in the creator's source.
_NEUTRAL_SEARCH_MODIFIERS = {
    "recipe", "recipes", "easy", "simple", "homemade", "home", "beginners", "beginner",
    "tutorial", "explained", "review", "quotes", "quote", "make", "making", "step",
    "steps", "method", "full", "complete", "tips", "guide",
}


def _repeats_a_word(text: str) -> bool:
    """A content word used twice, as in the real (but garbled) suggestion
    "chettinad biryani chicken biryani". "step by step" style idioms are fine."""

    words = _normalize(text).split()
    counts: dict[str, int] = {}
    for position, word in enumerate(words):
        if word in _STOP or len(word) <= 2:
            continue
        idiom = 0 < position < len(words) and words[position - 1] == "by"
        if not idiom:
            counts[word] = counts.get(word, 0) + 1
    return any(count > 1 for count in counts.values())


def _suggestion_is_grounded(phrase: str, source_terms: set[str], content_terms: set[str]) -> bool:
    tokens = _tokens(phrase)
    if not tokens or len(tokens) > _MAX_TAG_WORDS or not _semantic_support(phrase, content_terms):
        return False
    if _repeats_a_word(phrase):
        return False
    roots = {_term_root(term) for term in source_terms}
    keys = _cross_script_keys(source_terms)
    ungrounded = [
        token for token in tokens
        if token not in source_terms and _term_root(token) not in roots and not _sounds_grounded(token, keys)
    ]
    return not ungrounded or (len(ungrounded) == 1 and ungrounded[0] in _NEUTRAL_SEARCH_MODIFIERS)


def _validated_demand_rank(
    keyword: str, index: dict[str, dict[str, Any]], subjects: set[str] | None = None,
) -> int | None:
    """Suggestion rank, but only for phrases specific enough for it to mean anything.

    A single generic word ("perspective", "importance") prefixes countless
    suggestions, and a subject-less phrase ("hidden details") is typed by
    people looking for other videos — neither says anything about this one.
    """

    # Count the words actually typed: "betrayal quotes" is two words even
    # though "quotes" is a stopword for relevance scoring.
    if not index or len(_normalize(keyword).split()) < 2 or not _mentions_subject(keyword, subjects or set()):
        return None
    return demand_rank(keyword, index)


def _annotate_demand(
    entry: dict[str, Any], index: dict[str, dict[str, Any]], subjects: set[str] | None = None,
) -> None:
    """Mark a keyword that real viewers type and lift it by its suggestion rank."""

    if not index or entry.get("classification") == "platform_format":
        return
    rank = _validated_demand_rank(str(entry.get("keyword") or ""), index, subjects)
    if rank is None:
        return
    # Weighted like result evidence (which scores up to 24): real viewers
    # typing the phrase is at least as strong a relevance signal as a few
    # sampled results containing it.
    boost = max(10, 22 - 2 * rank)
    entry["demand_validated"] = True
    entry["demand_rank"] = rank
    entry["search_demand"] = "youtube_search_suggestion"
    entry["keyword_relevance_score"] = min(100, int(entry.get("keyword_relevance_score") or 0) + boost)
    note = f"; typed by real viewers (YouTube search suggestion, rank {rank + 1})"
    entry["reason"] = f"{entry.get('reason') or ''}{note}".lstrip("; ")
    entry["selection_reason"] = entry["reason"]


_EVIDENCE_STOP = {
    "a", "an", "and", "as", "at", "by", "for", "from", "how", "in", "into",
    "is", "of", "on", "or", "the", "this", "to", "with", "you", "your",
}


def _evidence_tokens(value: Any) -> list[str]:
    """Keep topic and search-intent words while removing only grammar words."""

    return [
        word for word in re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", _normalize(value))
        if word not in _EVIDENCE_STOP and len(word) > 1
    ]
