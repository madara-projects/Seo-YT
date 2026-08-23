"""Deterministic hook, pacing, and retention assistance for Phase 5.

The analyzer uses only creator-supplied/inferred brief data, generated package
metadata, and policy-approved historical evidence. Its scores are local
heuristics, never retention predictions.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from win_engine.analysis.generation_quality import normalize_unicode, title_similarity, unicode_words


RULE_VERSION = "phase5-v1"
_GENERIC_OPENINGS = (
    "hey guys", "hello guys", "welcome back", "welcome to my channel",
    "in this video", "today we are going to", "today we're going to",
    "before we begin", "make sure to like", "don't forget to subscribe",
)
_UNSUPPORTED_PROMISES = re.compile(
    r"\b(?:guaranteed|100%|go viral|will make you|will get you|instant(?:ly)?|proven to)\b",
    re.IGNORECASE,
)
_TRANSITIONS = re.compile(
    r"\b(?:but|however|because|instead|then|next|first|finally|meanwhile|so|therefore)\b",
    re.IGNORECASE,
)
_PAYOFF_MARKERS = re.compile(
    r"\b(?:result|reveal|answer|worked|failed|learned|found|finally|payoff|because|here is why)\b",
    re.IGNORECASE,
)
_VOICE_MARKERS = re.compile(r"\b(?:voice[- ]?over|narrat(?:e|ed|ion)|listen|I say|spoken)\b", re.IGNORECASE)
_SHORT_FORMATS = {"short", "shorts", "youtube_shorts", "quote", "reel", "reels"}


def analyze_retention_assistant(
    script: str,
    *,
    creator_brief: dict[str, Any] | None = None,
    content_angle: str = "",
    packages: Iterable[dict[str, Any]] | None = None,
    retention_learning: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return traceable pre-publish assistance plus eligible historical context."""

    brief = creator_brief or {}
    source = normalize_unicode(script or brief.get("content"))
    provenance = brief.get("field_provenance") if isinstance(brief.get("field_provenance"), dict) else {}
    exact_quote = normalize_unicode(brief.get("exact_quote") or _extract_quote(source))
    on_screen_text = normalize_unicode(brief.get("on_screen_text") or exact_quote)
    visual = normalize_unicode(brief.get("visual_requirements"))
    voice_over = normalize_unicode(brief.get("voice_over")).casefold() or "unknown"
    topic = normalize_unicode(brief.get("topic"))
    promise = normalize_unicode(brief.get("viewer_promise"))
    claims = normalize_unicode(brief.get("factual_claims"))
    duration = _number(brief.get("duration_seconds"))
    video_format = normalize_unicode(brief.get("video_format")).casefold()
    is_short = video_format in _SHORT_FORMATS or bool(re.search(r"\b(?:shorts?|reels?)\b", source, re.IGNORECASE))

    if not source:
        return _unavailable_result(retention_learning)

    words = unicode_words(source)
    opening = _opening_text(source)
    opening_words = unicode_words(opening)
    package_list = [item for item in (packages or []) if isinstance(item, dict)]

    hook = _analyze_hook(
        source=source,
        opening=opening,
        topic=topic,
        promise=promise,
        claims=claims,
        exact_quote=exact_quote,
        packages=package_list,
        provenance=provenance,
    )
    first_frame = _analyze_first_frame(
        on_screen_text=on_screen_text,
        exact_quote=exact_quote,
        visual=visual,
        topic=topic,
        packages=package_list,
        provenance=provenance,
    )
    pacing = _analyze_pacing(
        source=source,
        words=words,
        duration=duration,
        is_short=is_short,
        exact_quote=exact_quote,
        voice_over=voice_over,
        provenance=provenance,
    )
    quote = _analyze_quote(
        source=source,
        exact_quote=exact_quote,
        on_screen_text=on_screen_text,
        voice_over=voice_over,
        provenance=provenance,
    )

    risks = [*hook["risks"], *first_frame["risks"], *pacing["risks"], *quote["risks"]]
    risks = _deduplicate_risks(risks)
    risk_map = _risk_map(risks, duration=duration, is_short=is_short)
    recommendations = _recommendations(risks)
    alternatives = _alternatives(
        risks=risks,
        exact_quote=exact_quote,
        opening=opening,
        on_screen_text=on_screen_text,
        visual=visual,
    )
    learning = _normalize_learning(retention_learning)
    severity_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
    overall = max((severity_rank.get(str(item.get("severity")), 0) for item in risks), default=0)
    overall_label = {3: "high", 2: "medium", 1: "low", 0: "none"}[overall]

    return {
        "status": "available",
        "rule_version": RULE_VERSION,
        "analysis_basis": "deterministic_local_heuristic",
        "disclaimer": "Pre-publish structure guidance only; it does not predict or guarantee retention, views, reach, or growth.",
        "input_availability": {
            "script": _availability(True, "creator_supplied"),
            "duration": _availability(duration is not None, _source(provenance, "duration_seconds")),
            "exact_quote": _availability(bool(exact_quote), _source(provenance, "exact_quote")),
            "on_screen_text": _availability(bool(on_screen_text), _source(provenance, "on_screen_text")),
            "voice_over": _availability(voice_over != "unknown", _source(provenance, "voice_over")),
            "visual_requirements": _availability(bool(visual), _source(provenance, "visual_requirements")),
            "selected_package": _availability(bool(package_list), "generated_suggestion"),
        },
        "opening": hook["summary"],
        "first_frame": first_frame["summary"],
        "pacing": pacing["summary"],
        "quote_presentation": quote["summary"],
        "risk_level": overall_label,
        "risk_map": risk_map,
        "recommendations": recommendations,
        "alternatives": alternatives,
        "package_alignment": _package_alignment(package_list, opening, topic, promise),
        "retention_learning": learning,
        "trace": {
            "content_angle": normalize_unicode(content_angle) or "unavailable",
            "inputs_used": [
                name for name, item in {
                    "script": source, "topic": topic, "viewer_promise": promise,
                    "exact_quote": exact_quote, "on_screen_text": on_screen_text,
                    "visual_requirements": visual, "voice_over": voice_over if voice_over != "unknown" else "",
                    "duration_seconds": duration,
                }.items() if item not in (None, "")
            ],
            "timing_basis": "duration_supplied" if duration is not None else "relative_stage_only",
            "finding_count": len(risks),
        },
    }


def _analyze_hook(
    *, source: str, opening: str, topic: str, promise: str, claims: str,
    exact_quote: str, packages: list[dict[str, Any]], provenance: dict[str, Any],
) -> dict[str, Any]:
    lowered = opening.casefold()
    opening_terms = set(unicode_words(opening))
    topic_terms = set(unicode_words(topic))
    promise_terms = set(unicode_words(promise))
    subject_clear = bool(topic_terms & opening_terms) if topic_terms else len(opening_terms) >= 3
    specificity = bool(re.search(r"\b\d+(?:\.\d+)?\b", opening)) or len(opening_terms) >= 6
    curiosity = "?" in opening or bool(re.search(r"\b(?:why|how|but|until|what|never|instead)\b", lowered))
    generic = next((phrase for phrase in _GENERIC_OPENINGS if phrase in lowered), "")
    quote_position = source.find(exact_quote) if exact_quote else -1
    quote_prefix_words = len(unicode_words(source[:quote_position])) if quote_position > 0 else 0
    delayed_quote = bool(exact_quote and quote_position > 0 and quote_prefix_words > 12)
    promise_supported = not _UNSUPPORTED_PROMISES.search(" ".join(
        [promise, *[str(item.get("title") or "") for item in packages]]
    )) or bool(_UNSUPPORTED_PROMISES.search(f"{source} {claims}"))

    score = 45
    score += 20 if subject_clear else -15
    score += 10 if specificity else -5
    score += 10 if curiosity else 0
    score -= 20 if generic else 0
    score -= 15 if delayed_quote else 0
    score -= 25 if not promise_supported else 0
    score = max(0, min(100, score))
    risks: list[dict[str, Any]] = []
    if generic:
        risks.append(_risk("generic_opening", "high", "opening", f"The opening begins with generic setup: '{generic}'.", opening, "Start with the specific subject, conflict, result, or exact quote before channel-style greetings."))
    if not subject_clear:
        risks.append(_risk("subject_not_immediate", "medium", "opening", "The main subject is not identifiable in the opening text.", opening, "Name or show the core subject in the first meaningful beat."))
    if delayed_quote:
        risks.append(_risk("quote_context_delay", "high", "opening", f"Approximately {quote_prefix_words} words appear before the exact quote.", source[:quote_position], "Reveal the exact quote earlier and move optional context after it."))
    if not promise_supported:
        risks.append(_risk("unsupported_opening_promise", "high", "opening", "The package or promise uses guaranteed-performance language that the supplied source does not support.", promise or packages[0].get("title", ""), "Remove the guarantee and describe only what the finished video actually contains."))
    if len(unicode_words(opening)) > 45:
        risks.append(_risk("excessive_opening_exposition", "medium", "opening", "The first meaningful block contains more than 45 words before a clear break.", opening, "Split the opening and move background explanation after the first payoff."))

    return {"summary": {
        "status": "available", "score": score, "score_basis": "local_heuristic_not_measured_retention",
        "clarity": "clear" if subject_clear else "review", "specificity": "present" if specificity else "limited",
        "curiosity": "present" if curiosity else "not_required_or_unavailable",
        "generic_setup": bool(generic), "opening_excerpt": opening,
        "confidence": "heuristic", "provenance": "creator_supplied_and_inferred_brief",
    }, "risks": risks}


def _analyze_first_frame(
    *, on_screen_text: str, exact_quote: str, visual: str, topic: str,
    packages: list[dict[str, Any]], provenance: dict[str, Any],
) -> dict[str, Any]:
    if not on_screen_text and not visual:
        return {"summary": {
            "status": "unavailable", "reason": "No on-screen text or first-visual description was supplied.",
            "score": None, "provenance": "unavailable",
        }, "risks": []}
    text_words = len(unicode_words(on_screen_text))
    reading_seconds = _reading_seconds(text_words) if text_words else None
    risks: list[dict[str, Any]] = []
    if text_words > 25:
        risks.append(_risk("first_frame_text_overload", "high", "opening", f"The supplied on-screen text contains {text_words} words and needs about {reading_seconds:.1f} seconds to read once.", on_screen_text, "Reduce surrounding text, split the reveal across frames, or pair the exact quote with voice-over without changing its wording."))
    elif text_words > 12:
        risks.append(_risk("first_frame_text_dense", "medium", "opening", f"The first-frame text contains {text_words} words.", on_screen_text, "Keep the first frame visually simple and reveal the remaining exact text in readable steps."))
    title = str(packages[0].get("title") or "") if packages else ""
    visual_alignment = None
    if visual and (topic or title):
        visual_alignment = max(title_similarity(visual, topic), title_similarity(visual, title))
        if visual_alignment < 0.08 and len(unicode_words(visual)) >= 3:
            risks.append(_risk("visual_promise_needs_review", "low", "opening", "The supplied visual description does not explicitly identify the package subject.", visual, "Use composition or readable text to make the title-to-visual connection clear immediately."))
    subject_identifiable = bool(set(unicode_words(visual)) & set(unicode_words(topic))) if visual and topic else None
    return {"summary": {
        "status": "available", "text_word_count": text_words, "estimated_single_read_seconds": reading_seconds,
        "readability": "high_burden" if text_words > 25 else "review" if text_words > 12 else "readable",
        "main_subject_identifiable": subject_identifiable if visual else "unavailable",
        "visual_description": visual or "unavailable", "visual_analysis_basis": "creator_description_only" if visual else "unavailable",
        "score": max(0, 100 - max(0, text_words - 10) * 3) if text_words else None,
        "score_basis": "local_text_burden_heuristic" if text_words else "unavailable",
        "provenance": _source(provenance, "on_screen_text") if on_screen_text else _source(provenance, "visual_requirements"),
    }, "risks": risks}


def _analyze_pacing(
    *, source: str, words: list[str], duration: float | None, is_short: bool,
    exact_quote: str, voice_over: str, provenance: dict[str, Any],
) -> dict[str, Any]:
    word_count = len(words)
    spoken_seconds = round(word_count / 2.5, 1) if word_count else 0
    transition_count = len(_TRANSITIONS.findall(source))
    repeated = _repeated_sentences(source)
    payoff_match = _PAYOFF_MARKERS.search(source)
    payoff_word = len(unicode_words(source[:payoff_match.start()])) if payoff_match else None
    risks: list[dict[str, Any]] = []
    density = None
    if duration:
        density = round(spoken_seconds / duration, 2)
        if voice_over != "none" and density > 1.15:
            risks.append(_risk("spoken_content_overload", "high", "development", f"Estimated spoken time is {spoken_seconds}s for a supplied {duration:g}s duration.", f"{word_count} words", "Cut repeated setup or extend the intended duration; do not accelerate beyond clear delivery."))
        elif voice_over != "none" and density < 0.35 and word_count > 15:
            risks.append(_risk("low_information_interval", "medium", "development", "The supplied duration is much longer than the estimated spoken content.", f"{word_count} words across {duration:g}s", "Plan intentional visual beats, examples, or a clean shorter edit instead of leaving unexplained dead time."))
    if repeated:
        risks.append(_risk("repeated_idea", "medium", "development", f"{len(repeated)} sentence idea(s) are repeated or near-duplicated.", repeated[0], "Keep the clearest version and use the saved time for proof or payoff."))
    if word_count > 0 and transition_count == 0 and word_count > (70 if is_short else 180):
        risks.append(_risk("abrupt_or_flat_transitions", "medium", "development", "The script has no clear contrast or section transitions.", f"{word_count} words; 0 transition markers", "Add a truthful contrast, example, or section break where the idea changes."))
    if payoff_word is not None and payoff_word > (45 if is_short else max(100, int(word_count * 0.5))):
        risks.append(_risk("late_payoff", "high" if is_short else "medium", "payoff", f"The first explicit payoff marker appears after roughly {payoff_word} words.", source[:payoff_match.start()], "State or preview the payoff earlier, then provide the explanation."))
    if is_short and word_count > 90:
        risks.append(_risk("short_form_overload", "high", "development", f"The Short input contains {word_count} words.", str(word_count), "Remove secondary explanations and keep one opening, one development beat, and one payoff."))
    return {"summary": {
        "status": "available", "format_assessment": "short_form" if is_short else "long_form_or_unspecified",
        "word_count": word_count, "estimated_spoken_seconds": spoken_seconds,
        "duration_seconds": duration, "duration_source": _source(provenance, "duration_seconds") if duration else "unavailable",
        "spoken_duration_load": density, "transition_count": transition_count,
        "repeated_idea_count": len(repeated), "payoff_position_words": payoff_word,
        "timing_confidence": "duration_based_heuristic" if duration else "relative_stage_only",
        "provenance": "creator_script_plus_local_heuristic",
    }, "risks": risks}


def _analyze_quote(
    *, source: str, exact_quote: str, on_screen_text: str, voice_over: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    risks: list[dict[str, Any]] = []
    positive_voice_marker = _VOICE_MARKERS.search(source)
    explicit_no_voice = bool(re.search(r"\b(?:no|without)\s+(?:dialogue|voice[- ]?over|narration)\b", source, re.IGNORECASE))
    if voice_over == "none" and positive_voice_marker and not explicit_no_voice:
        risks.append(_risk("voice_over_visual_contradiction", "high", "opening", "The brief says no voice-over, but the supplied content describes narration or listening.", positive_voice_marker.group(0), "Confirm the finished audio plan and remove the contradictory instruction."))
    if not exact_quote:
        return {"summary": {"status": "not_applicable", "reason": "No exact quote was supplied or detected.", "provenance": "unavailable"}, "risks": risks}
    word_count = len(unicode_words(exact_quote))
    reading_seconds = _reading_seconds(word_count)
    position = source.find(exact_quote)
    prefix_words = len(unicode_words(source[:position])) if position > 0 else 0
    if word_count > 24:
        risks.append(_risk("quote_reading_burden", "high", "opening", f"The exact quote contains {word_count} words and needs about {reading_seconds:.1f} seconds for one read.", exact_quote, "Preserve the quote exactly, but split its visual reveal or use voice-over to reduce simultaneous reading burden."))
    elif word_count > 14:
        risks.append(_risk("quote_reading_burden", "medium", "opening", f"The exact quote contains {word_count} words.", exact_quote, "Show it early with strong contrast and allow at least the estimated reading time."))
    if voice_over == "none" and on_screen_text and word_count > 20:
        risks.append(_risk("quote_visual_only_load", "medium", "opening", "A long exact quote must be understood visually because the brief says no voice-over.", exact_quote, "Use a progressive reveal and hold the complete quote long enough for a second glance."))
    quote_preserved = normalize_unicode(on_screen_text) == exact_quote if on_screen_text else None
    if quote_preserved is False:
        risks.append(_risk("quote_text_conflict", "high", "opening", "The on-screen text differs from the exact quote field.", on_screen_text, "Choose which field is authoritative; never silently rewrite the exact quote."))
    return {"summary": {
        "status": "available", "word_count": word_count,
        "estimated_single_read_seconds": reading_seconds, "context_words_before_quote": prefix_words,
        "voice_over": voice_over, "exact_text_preserved_on_screen": quote_preserved,
        "attribution": "unavailable", "attribution_note": "No quote attribution is invented.",
        "provenance": _source(provenance, "exact_quote"),
    }, "risks": risks}


def _risk_map(risks: list[dict[str, Any]], *, duration: float | None, is_short: bool) -> list[dict[str, Any]]:
    if duration is not None:
        if is_short:
            stages = [
                ("0-3 seconds", "opening"), ("3-10 seconds", "development"),
                ("10-30 seconds", "payoff"), ("ending", "ending"),
            ]
        else:
            stages = [
                ("0-3 seconds", "opening"), ("3-10 seconds", "setup"),
                ("10-30 seconds", "development"), ("middle", "development"),
                ("reveal/payoff", "payoff"), ("ending", "ending"),
            ]
        basis = "duration_supplied_timing_bands"
    else:
        stages = [(name, name) for name in ("opening", "setup", "development", "payoff", "ending")]
        basis = "relative_stage_only"
    result = []
    for label, stage in stages:
        matching = [item for item in risks if item.get("stage") == stage or (stage == "setup" and item.get("stage") == "opening")]
        result.append({
            "stage": label, "timing_basis": basis,
            "status": "risk_identified" if matching else "no_specific_risk_identified",
            "risks": matching,
            "note": "Absence of a heuristic finding is not measured retention evidence.",
        })
    return result


def _recommendations(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in risks:
        recommendation = str(item.get("recommendation") or "").strip()
        if not recommendation or any(existing["recommendation"] == recommendation for existing in result):
            continue
        result.append({
            "priority": item.get("severity"), "risk_code": item.get("risk_code"),
            "recommendation": recommendation, "basis": "deterministic_local_heuristic",
            "provenance": "generated_recommendation", "guarantee": False,
        })
    if not result:
        result.append({
            "priority": "low", "risk_code": "manual_review",
            "recommendation": "Manually confirm that the first visible and spoken beat matches the selected package promise.",
            "basis": "manual_safety_check", "provenance": "heuristic", "guarantee": False,
        })
    return result[:8]


def _alternatives(*, risks: list[dict[str, Any]], exact_quote: str, opening: str, on_screen_text: str, visual: str) -> list[dict[str, Any]]:
    codes = {str(item.get("risk_code")) for item in risks}
    alternatives: list[dict[str, Any]] = []
    if "generic_opening" in codes:
        alternatives.append(_alternative("subject_first", "Open on the core subject or visible result; move greetings after the first useful beat.", opening))
    if "quote_context_delay" in codes or "quote_reading_burden" in codes:
        alternatives.append(_alternative("quote_first", "Reveal the creator's exact quote immediately, then add only the context needed to understand it.", exact_quote))
    if "first_frame_text_overload" in codes or "first_frame_text_dense" in codes:
        alternatives.append(_alternative("progressive_text_reveal", "Keep the exact wording but reveal it in readable phrases, then hold the complete text.", on_screen_text))
    if "late_payoff" in codes:
        alternatives.append(_alternative("preview_payoff", "Preview the supported payoff in the opening, explain it, then show the full payoff.", "creator script"))
    if "spoken_content_overload" in codes or "short_form_overload" in codes:
        alternatives.append(_alternative("single_beat_cut", "Keep one opening claim, one supporting beat, and one payoff; remove secondary explanations.", "creator script"))
    if visual and not alternatives:
        alternatives.append(_alternative("visual_subject_first", "Begin with the clearest supplied visual subject and keep the first text layer minimal.", visual))
    return alternatives[:4]


def _package_alignment(packages: list[dict[str, Any]], opening: str, topic: str, promise: str) -> list[dict[str, Any]]:
    source = f"{opening} {topic} {promise}".strip()
    return [{
        "package_id": str(item.get("package_id") or item.get("package") or "unknown"),
        "title": str(item.get("title") or ""),
        "opening_similarity": title_similarity(str(item.get("title") or ""), source),
        "status": "aligned" if title_similarity(str(item.get("title") or ""), source) >= 0.18 else "review",
        "basis": "local_unicode_text_similarity", "provenance": "generated_package_plus_creator_source",
    } for item in packages if item.get("title")]


def _normalize_learning(value: dict[str, Any] | None) -> dict[str, Any]:
    learning = value if isinstance(value, dict) else {}
    if not learning.get("learning_allowed"):
        return {
            "status": "insufficient_evidence", "learning_allowed": False,
            "sample_size": int(learning.get("sample_size") or 0),
            "minimum_samples": int(learning.get("minimum_samples") or 5),
            "confidence": learning.get("confidence_label") or "Collecting evidence",
            "patterns": [],
            "message": learning.get("message") or "Insufficient mature comparable retention evidence; no winning hook or pacing pattern is claimed.",
            "provenance": "post_publish_evidence_policy",
        }
    return {
        "status": "observed_correlations", "learning_allowed": True,
        "sample_size": int(learning.get("sample_size") or 0),
        "minimum_samples": int(learning.get("minimum_samples") or 5),
        "confidence": learning.get("confidence_label") or "Early signal",
        "snapshot_window": learning.get("snapshot_window"),
        "patterns": list(learning.get("patterns") or []),
        "message": learning.get("message") or "Eligible creator-history correlations are shown; causation is not claimed.",
        "provenance": "post_publish_evidence",
    }


def _unavailable_result(learning: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "status": "unavailable", "rule_version": RULE_VERSION,
        "analysis_basis": "deterministic_local_heuristic",
        "disclaimer": "No script or content source was available; no hook, pacing, timing, or retention result was fabricated.",
        "input_availability": {"script": _availability(False, "unavailable")},
        "opening": {"status": "unavailable", "score": None},
        "first_frame": {"status": "unavailable", "score": None},
        "pacing": {"status": "unavailable"},
        "quote_presentation": {"status": "unavailable"},
        "risk_level": "unknown", "risk_map": [], "recommendations": [],
        "alternatives": [], "package_alignment": [],
        "retention_learning": _normalize_learning(learning),
        "trace": {"inputs_used": [], "timing_basis": "unavailable", "finding_count": 0},
    }


def _risk(code: str, severity: str, stage: str, explanation: str, evidence: Any, recommendation: str) -> dict[str, Any]:
    return {
        "risk_code": code, "severity": severity, "stage": stage,
        "explanation": normalize_unicode(explanation),
        "evidence": normalize_unicode(evidence)[:500] or "unavailable",
        "recommendation": normalize_unicode(recommendation),
        "confidence": "heuristic", "basis": "deterministic_rule",
        "provenance": "creator_input_plus_local_heuristic",
    }


def _alternative(code: str, structure: str, preserves: str) -> dict[str, Any]:
    return {
        "alternative_code": code, "structure": structure,
        "preserves_source": normalize_unicode(preserves)[:500] or "creator source",
        "provenance": "generated_recommendation", "guarantee": False,
    }


def _opening_text(source: str) -> str:
    clean = re.sub(r"\s+", " ", source).strip()
    sentence = re.split(r"(?<=[.!?])\s+|\n+", clean, maxsplit=1)[0]
    words = sentence.split()
    return " ".join(words[:60])


def _extract_quote(source: str) -> str:
    matches = re.findall(r'["\u201c]([^"\u201c\u201d]{6,})["\u201d]', source)
    if not matches:
        matches = re.findall(r"(?<![A-Za-z])'([^'\n]{6,})'(?![A-Za-z])", source)
    return max((normalize_unicode(item) for item in matches), key=len, default="")


def _reading_seconds(word_count: int) -> float:
    return round(max(1.0, word_count / 2.8), 1)


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _repeated_sentences(source: str) -> list[str]:
    sentences = [item.strip() for item in re.split(r"[.!?]+", source) if len(unicode_words(item)) >= 4]
    repeated: list[str] = []
    for index, sentence in enumerate(sentences):
        if any(title_similarity(sentence, previous) >= 0.86 for previous in sentences[:index]):
            repeated.append(sentence)
    return repeated


def _deduplicate_risks(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in risks:
        key = (str(item.get("risk_code")), str(item.get("stage")))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _source(provenance: dict[str, Any], field: str) -> str:
    item = provenance.get(field) if isinstance(provenance.get(field), dict) else {}
    return str(item.get("source") or "unknown")


def _availability(available: bool, provenance: str) -> dict[str, Any]:
    return {"status": "available" if available else "unavailable", "provenance": provenance}
