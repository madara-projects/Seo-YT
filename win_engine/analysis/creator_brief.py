"""Turn creator-provided context into a concise, generation-ready video brief."""

from __future__ import annotations

import re
from typing import Any

from win_engine.analysis.source_cues import (
    SHORTS_MAX_SECONDS,
    extract_quote,
    is_short_video,
    labelled_visual,
    looks_like_standalone_quote,
    source_quote,
)
from win_engine.analysis.text_tokens import unicode_words
from win_engine.analysis.topic_lock import source_lead_phrase


_DISPLAY_NAMES = {
    "target_audience": "who the video is for",
    "viewer_promise": "what the viewer will get",
    "unique_angle": "what makes this video different",
    "proof": "proof, footage, result, or personal experience",
}

_TOPIC_STOPWORDS = {
    "a", "an", "and", "the", "this", "that", "with", "for", "from", "my", "our",
    "video", "footage", "show", "shows", "showing", "real", "realistic", "perfect",
    "what", "will", "see", "feel", "learn", "work", "life", "content",
    "day", "own", "not", "but", "into", "your", "their", "quote", "visual",
    "background", "sunset", "aesthetic", "poignant", "atmospheric",
}


def build_creator_brief(
    *,
    script: str,
    target_audience: str = "",
    viewer_promise: str = "",
    unique_angle: str = "",
    proof: str = "",
    video_format: str = "",
    title_style: str = "balanced",
    thumbnail_idea: str = "",
    language: str = "english",
    region: str = "global",
    duration_seconds: float | None = None,
    exact_quote: str = "",
    on_screen_text: str = "",
    voice_over: str = "",
    visual_requirements: str = "",
    factual_claims: str = "",
    claim_restrictions: str = "",
    creator_intent: str = "",
    content_constraints: str = "",
) -> dict[str, Any]:
    """Build a compatible brief with truthful field-level provenance."""
    script_text = script.strip()
    script_lower = script_text.lower()

    # Heuristic auto-inference for missing brief fields
    def mentions(*phrases: str) -> bool:
        # Whole words only: a substring test read "day" in "Today I want to
        # talk..." and labelled a talking-head script a vlog.
        return any(re.search(rf"\b{re.escape(phrase)}\b", script_lower) for phrase in phrases)

    # A bare emotional line over a described background is a quote Short even
    # without quotation marks; it used to be read as a talking-head video.
    standalone_quote = not exact_quote.strip() and looks_like_standalone_quote(script_text, visual_requirements)
    # Only explicit cues infer a Short: a stated length of three minutes or less,
    # the platform's words ("#shorts", "YouTube Short", "reels"), a standalone
    # quote, or the creator calling the text a quote. "sunset", "aesthetic",
    # "motivation" or a quoted `"Error 404"` described a travel vlog, a talk or
    # a tutorial as often as a Short, and made them Shorts.
    stated_long_form = duration_seconds is not None and duration_seconds > SHORTS_MAX_SECONDS
    cue_brief = {"content": script_text, "duration_seconds": duration_seconds, "visual_requirements": visual_requirements}
    is_quote_or_short = not stated_long_form and (
        is_short_video(script_text, cue_brief) or mentions("quote", "quotes")
    )

    auto_format = video_format.strip()
    if not auto_format:
        if is_quote_or_short:
            auto_format = "youtube_shorts"
        elif mentions("how to", "tutorial", "step", "steps", "guide", "learn", "learning", "setup", "how2"):
            auto_format = "tutorial"
        elif mentions("story", "stories", "vlog", "day in my life", "my day", "routine", "my life", "experience"):
            auto_format = "vlog"
        else:
            auto_format = "talking_head"

    # A quoted span is the mandatory quote only when it is labelled or the video
    # is a quote Short; in a tutorial `click "Save changes"` names a button.
    quote_short = is_short_video(script_text, {**cue_brief, "video_format": auto_format})
    extracted_quote = exact_quote.strip() or extract_quote(script_text, short=quote_short)
    if not extracted_quote and standalone_quote:
        extracted_quote = re.sub(r"\s+", " ", script_text).strip(" \t\r\n\"'“”‘’")
    extracted_on_screen = on_screen_text.strip() or extracted_quote
    inferred_duration = duration_seconds if duration_seconds is not None else _extract_duration(script_text)
    inferred_visual = visual_requirements.strip() or labelled_visual(script_text)
    inferred_voice = voice_over.strip().lower()
    if not inferred_voice:
        if (
            re.search(r"\b(?:voice[- ]?over|narration|dialogue|audio)\s*:\s*(?:none|no|absent|false|off|silent|n/a)\b", script_lower)
            or re.search(r"\b(?:no|without)\s+(?:dialogue|voice[- ]?over|narration|spoken)\b", script_lower)
            or re.search(r"\b(?:silent|text[- ]only|instrumental only|music only)\b", script_lower)
        ):
            inferred_voice = "none"
        elif re.search(r"\b(?:voice[- ]?over|narrat(?:e|ed|ion)|spoken dialogue)\b", script_lower):
            inferred_voice = "present"
        else:
            inferred_voice = "unknown"

    topic = _infer_topic(script_text, extracted_quote)
    inferred_intent = creator_intent.strip()
    if not inferred_intent:
        if extracted_quote:
            inferred_intent = "Preserve and package the exact emotional idea without inventing events."
        elif auto_format == "tutorial":
            inferred_intent = "Explain the described process truthfully and clearly."

    restriction = claim_restrictions.strip() or (
        "Do not add facts, events, relationships, evidence, or outcomes not present in the creator source."
    )

    field_provenance: dict[str, dict[str, Any]] = {}

    def add_field(name: str, value: Any, source: str, reason: str = "") -> Any:
        normalized = value.strip() if isinstance(value, str) else value
        state = source
        if normalized in (None, "") and source != "unavailable":
            state = "unknown"
        field_provenance[name] = {"source": state, "value": normalized, "reason": reason}
        return normalized

    add_field("topic", topic, "inferred", "Extracted from the creator's source text.")
    add_field("target_audience", target_audience, "creator_supplied")
    add_field("language", language, "creator_supplied" if language.strip().lower() != "english" else "inferred", "Request default unless changed by the creator.")
    add_field("region", region, "creator_supplied" if region.strip().lower() != "global" else "inferred", "Request default unless changed by the creator.")
    add_field("video_format", auto_format, "creator_supplied" if video_format.strip() else "inferred")
    add_field("duration_seconds", inferred_duration, "creator_supplied" if duration_seconds is not None else ("inferred" if inferred_duration is not None else "unknown"))
    add_field("exact_quote", extracted_quote, "creator_supplied" if exact_quote.strip() else ("inferred" if extracted_quote else "unavailable"))
    add_field("on_screen_text", extracted_on_screen, "creator_supplied" if on_screen_text.strip() else ("inferred" if extracted_on_screen else "unknown"))
    add_field("voice_over", inferred_voice, "creator_supplied" if voice_over.strip() else ("inferred" if inferred_voice != "unknown" else "unknown"))
    add_field("visual_requirements", inferred_visual, "creator_supplied" if visual_requirements.strip() else ("inferred" if inferred_visual else "unknown"))
    add_field("factual_claims", factual_claims, "creator_supplied")
    add_field("claim_restrictions", restriction, "creator_supplied" if claim_restrictions.strip() else "inferred")
    add_field("creator_intent", inferred_intent, "creator_supplied" if creator_intent.strip() else ("inferred" if inferred_intent else "unknown"))
    add_field("content_constraints", content_constraints, "creator_supplied")
    add_field("viewer_promise", viewer_promise, "creator_supplied")
    add_field("unique_angle", unique_angle, "creator_supplied")
    add_field("proof", proof, "creator_supplied")
    add_field("title_style", title_style, "creator_supplied" if title_style.strip() and title_style != "balanced" else "inferred")
    add_field("thumbnail_idea", thumbnail_idea, "creator_supplied")

    brief = {
        "content": script_text,
        "topic": topic,
        "target_audience": target_audience.strip(),
        "viewer_promise": viewer_promise.strip(),
        "unique_angle": unique_angle.strip(),
        "proof": proof.strip(),
        "video_format": auto_format,
        "title_style": title_style.strip() or "balanced",
        "thumbnail_idea": thumbnail_idea.strip(),
        "language": language.strip().lower() or "english",
        "region": region.strip().lower() or "global",
        "duration_seconds": inferred_duration,
        "exact_quote": extracted_quote,
        "on_screen_text": extracted_on_screen,
        "voice_over": inferred_voice,
        "visual_requirements": inferred_visual,
        "factual_claims": factual_claims.strip(),
        "claim_restrictions": restriction,
        "creator_intent": inferred_intent,
        "content_constraints": content_constraints.strip(),
        "field_provenance": field_provenance,
    }

    applicable = [item for item in field_provenance.values() if item["source"] != "unavailable"]
    known = [item for item in applicable if item["source"] in {"creator_supplied", "inferred"}]
    completeness = round((len(known) / max(len(applicable), 1)) * 100)
    missing = [
        field for field in ("target_audience", "viewer_promise", "proof", "voice_over", "visual_requirements")
        if field_provenance[field]["source"] == "unknown"
    ]
    warnings = [f"{_DISPLAY_NAMES.get(field, field.replace('_', ' ').title())} is unknown." for field in missing]

    return {
        **brief,
        "status": "ready" if completeness >= 70 else "needs_review",
        "completeness": completeness,
        "missing_fields": missing,
        "warnings": warnings,
        "recommendation": (
            "Review inferred fields and fill unknowns that materially affect the finished video."
            if missing else
            "Review inferred fields before generation; creator-supplied and inferred values remain distinct."
        ),
    }


def _extract_duration(content: str) -> float | None:
    # Units spelled out or as sec/min, singular or plural. The bare "s" and "m"
    # read "iPhone 5s" as five seconds, while "45 seconds" never matched.
    match = re.search(r"\b(\d+(?:\.\d+)?)[\s-]*(?:seconds?|secs?)\b", content, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"\b(\d+(?:\.\d+)?)[\s-]*(?:minutes?|mins?)\b", content, re.IGNORECASE)
    return float(match.group(1)) * 60 if match else None


# Words that cannot end a topic phrase: cutting "... than to be in love" at a
# word limit left "... than to be in".
_TOPIC_TRAILING_WORDS = {
    "a", "an", "the", "and", "or", "but", "to", "of", "in", "on", "at", "for", "with", "from", "by",
    "than", "that", "which", "who", "if", "when", "as", "be", "is", "are", "was", "were", "been",
    "my", "your", "our", "their", "his", "her", "its", "this", "these", "those", "so", "very", "more",
}


def _clean_topic_phrase(words: list[str], limit: int) -> str:
    words = list(words[:limit])
    while len(words) > 1 and words[-1].casefold() in _TOPIC_TRAILING_WORDS:
        words.pop()
    return " ".join(words).strip()


def _phrase_words(text: str) -> list[str]:
    """Casefolded words in order, one-letter words ("I", "a") included.

    The old ``[^\\W_]+`` pattern split Tamil at every vowel sign, so a Tamil
    quote became letter fragments. unicode_words keeps those words whole but
    drops one-letter words, which a readable topic phrase needs.
    """

    return [
        word.casefold()
        for chunk in text.split()
        for word in (unicode_words(chunk) or re.findall(r"[^\W_]", chunk))
    ]


def _infer_topic(content: str, quote: str) -> str:
    if quote:
        sentence = re.split(r"(?<=[.!?])\s+|\.{2,}|[;\u2013\u2014]", quote, maxsplit=1)[0]
        natural = _clean_topic_phrase(_phrase_words(sentence), 12)
        if natural:
            return natural.casefold()
    source = quote or content
    # Tamil words stay whole; the old pattern left a Tamil script no topic.
    words = [word for word in unicode_words(source) if len(word) > 2 and word not in _TOPIC_STOPWORDS]
    return " ".join(words[:8])


def creator_topic(creator_brief: dict[str, Any] | None) -> str:
    """Make a compact topic for fallbacks and topic locking from the creator's own words."""

    brief = creator_brief or {}
    structured_topic = str(brief.get("topic") or "").strip()
    topic_source = ((brief.get("field_provenance") or {}).get("topic") or {}).get("source")
    if structured_topic and (not brief.get("content") or topic_source == "creator_supplied"):
        return structured_topic
    content = str(brief.get("content") or "").strip()
    # The structured quote fields are more reliable than trying to recover a
    # quote from free-form production directions. A creator can write
    # ``quote is: ...`` without surrounding punctuation in ``content``. A quoted
    # button name in a tutorial (`click "Save changes"`) is not a quote.
    quote_text = str(brief.get("exact_quote") or brief.get("on_screen_text") or "").strip() or source_quote(content, brief)
    if quote_text:
        # Keep a grammatical phrase instead of deleting stopwords and turning a
        # quote into a non-searchable bag of words (for example, "part always
        # wonder didn least deserve..."). When an ellipsis introduces the key
        # thought, the final clause is normally the useful search phrase.
        clauses = [
            part.strip(" \t\r\n.,;:!?—–-")
            for part in re.split(r"\.{2,}|[;—–]", quote_text)
            if part.strip(" \t\r\n.,;:!?—–-")
        ]
        focus = clauses[-1] if len(clauses) > 1 else quote_text
        words = re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)?", focus)
        if words and words[0].lower() in {"a", "an", "the"}:
            words = words[1:]
        if words:
            return _clean_topic_phrase(words, 10).lower()

    # Strip camera / background / visual setup headers
    clean_content = re.sub(
        r"(?i)\bbackground\s*visuals?\s*(?:is|:)?\s*[^.;,\n]*?(?=\s+and\s+|[.;,]|$)",
        " ",
        content,
        count=1,
    )
    clean_content = re.sub(r"(?i)quote\s*on\s*screen:?", "", clean_content)

    # Narrative prose keeps its own grammar through the contiguous lead phrase
    # below. Phrases written for three test stories ("waiting on an empty road",
    # "a message read ten times") named topics no creator had written.
    quote_stopwords = _TOPIC_STOPWORDS.union({
        "background", "visuals", "screen", "vertical", "format", "sunset", "beach",
        "calm", "ocean", "waves", "poignant", "aesthetic", "atmospheric", "cinematic",
        "overlay", "mood", "authentic", "photo", "image", "video", "shorts", "reels"
    })

    # Prefer a contiguous phrase of the creator's words. The word bag below
    # (first eight non-stopwords) produced unreadable topics such as "you how
    # make cold brew coffee home without", which then became the fallback
    # title. It remains only for inputs with no usable leading clause.
    lead = source_lead_phrase(clean_content)
    if len(lead.split()) >= 2:
        return lead

    candidates: list[str] = []
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", clean_content.lower()):
        if len(word) < 3 or word in quote_stopwords or word in candidates:
            continue
        candidates.append(word)

    if not candidates:
        # Never a placeholder: "deep quote" used to leak into Tamil packages
        # as #DeepQuote because Tamil script has no [A-Za-z] words.
        return lead
    # Preserve the full inferred subject for ordinary instructional or
    # experience-led input.  Truncating to three words dropped the terms that
    # make otherwise similar topics distinct (for example ``csv files`` or a
    # food/route name), which then weakened fallback titles and tags.  Keep a
    # compact deterministic phrase, while retaining enough source vocabulary
    # for topic locking and contextual validation.
    return " ".join(candidates[:8])
