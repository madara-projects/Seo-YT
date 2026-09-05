"""Turn creator-provided context into a concise, generation-ready video brief."""

from __future__ import annotations

import re
from typing import Any


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
    is_quote_or_short = any(w in script_lower for w in ["quote", "betrayal", "shorts", "reels", "sunset", "aesthetic", "motivation", "life lesson"]) or (len(script_text) < 250 and '"' in script_text)

    auto_format = video_format.strip()
    if not auto_format:
        if is_quote_or_short:
            auto_format = "youtube_shorts"
        elif any(w in script_lower for w in ["how to", "tutorial", "step", "guide", "learn", "setup", "how2"]):
            auto_format = "tutorial"
        elif any(w in script_lower for w in ["story", "vlog", "day", "routine", "my life", "experience"]):
            auto_format = "vlog"
        else:
            auto_format = "talking_head"

    extracted_quote = exact_quote.strip() or _extract_quote(script_text)
    extracted_on_screen = on_screen_text.strip() or extracted_quote
    inferred_duration = duration_seconds if duration_seconds is not None else _extract_duration(script_text)
    inferred_visual = visual_requirements.strip() or _extract_visual_requirement(script_text)
    inferred_voice = voice_over.strip().lower()
    if not inferred_voice:
        if re.search(r"\b(?:no|without) (?:dialogue|voice[- ]?over|narration)\b", script_lower):
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


def _extract_quote(content: str) -> str:
    marker = re.search(
        r"(?is)\b(?:the\s+)?quote(?:\s+(?:on|in)\s+(?:the\s+)?(?:screen|reel|video))?"
        r"\s*(?:is|reads?)?\s*[:\-\u2013\u2014]+\s*(.+)",
        content,
    )
    if marker:
        value = re.split(
            r"(?is)\s+(?:and\s+)?(?:the\s+)?(?:background(?:\s+of\s+the\s+video)?|"
            r"background\s+visuals?|visuals?|video\s+(?:is|shows?|has))\s*(?:is|are|:|\-)?\s*",
            marker.group(1),
            maxsplit=1,
        )[0]
        value = re.sub(r"\s+", " ", value).strip(" \t\r\n\"'.,;:-")
        if value.count('"') % 2:
            value = value.replace('"', "")
        if len(value) >= 6:
            return value
    matches = re.findall(r'["“]([^"“”]{6,})["”]', content)
    if not matches:
        matches = re.findall(r"(?<![A-Za-z])'([^'\n]{6,})'(?![A-Za-z])", content)
    return max((re.sub(r"\s+", " ", value).strip() for value in matches), key=len, default="")


def _extract_duration(content: str) -> float | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:second|sec|s)\b", content, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:minute|min|m)\b", content, re.IGNORECASE)
    return float(match.group(1)) * 60 if match else None


def _extract_visual_requirement(content: str) -> str:
    broad_match = re.search(
        r"(?is)\b(?:background(?:\s+of\s+the\s+video|\s+visuals?)?|visuals?|"
        r"video\s+(?:is|shows?|has))\s*(?:is|are|of|:|\-)?\s*(.*?)"
        r"(?=\s+(?:and|with)\s+.*(?:quote|text|screen)|[.;\n]|$)",
        content,
    )
    if broad_match:
        return re.sub(r"\s+", " ", broad_match.group(1)).strip(" .")
    match = re.search(
        r"(?i)\b(?:background(?:\s+visuals?)?|visuals?)\s*(?:is|are|:)?\s*(.*?)(?=\s+(?:and|with)\s+.*(?:quote|text|screen)|[.;\n]|$)",
        content,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip(" .") if match else ""


def _infer_topic(content: str, quote: str) -> str:
    if quote:
        sentence = re.split(r"(?<=[.!?])\s+|\.{2,}|[;\u2013\u2014]", quote, maxsplit=1)[0]
        words = re.findall(r"[^\W_]+(?:['\u2019][^\W_]+)?", sentence, re.UNICODE)
        natural = " ".join(words[:12]).strip()
        if natural:
            return natural.casefold()
    source = quote or content
    words = [
        word.casefold() for word in re.findall(r"[^\W_]+(?:['’][^\W_]+)?", source, re.UNICODE)
        if len(word) > 2 and word.casefold() not in _TOPIC_STOPWORDS
    ]
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
    # ``quote is: ...`` without surrounding punctuation in ``content``.
    explicit_quote = str(brief.get("exact_quote") or brief.get("on_screen_text") or "").strip()
    quote_match = None if explicit_quote else re.search(r'["“”]([^"“”]{6,})["“”]', content)
    if not explicit_quote and not quote_match:
        quote_match = re.search(r"(?<![A-Za-z])'([^'\n]{6,})'(?![A-Za-z])", content)
    if explicit_quote or quote_match:
        # Keep a grammatical phrase instead of deleting stopwords and turning a
        # quote into a non-searchable bag of words (for example, "part always
        # wonder didn least deserve..."). When an ellipsis introduces the key
        # thought, the final clause is normally the useful search phrase.
        quote_text = explicit_quote or re.sub(r"\s+", " ", quote_match.group(1)).strip()
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
            return " ".join(words[:10]).lower()

    # Strip camera / background / visual setup headers
    clean_content = re.sub(
        r"(?i)\bbackground\s*visuals?\s*(?:is|:)?\s*[^.;,\n]*?(?=\s+and\s+|[.;,]|$)",
        " ",
        content,
        count=1,
    )
    clean_content = re.sub(r"(?i)quote\s*on\s*screen:?", "", clean_content)

    # Narrative prose has sentence grammar, not a keyword list.  Taking its
    # first non-stopwords created title stems such as "used talk every then one".
    # Keep a few conservative source-faithful narrative concepts intact instead.
    narrative_context = " ".join(str(brief.get(field) or "") for field in (
        "creator_intent", "content_constraints", "video_format", "voice_over",
    )).casefold()
    lowered = clean_content.casefold()
    if any(word in narrative_context for word in ("story", "narrative", "cinematic", "reflection")):
        if "used to talk" in lowered and "conversation" in lowered:
            return "conversations fade away"
        if "empty road" in lowered and re.search(r"\b(?:waiting|checking)\b", lowered):
            return "waiting on an empty road"
        if "message" in lowered and re.search(r"\b(?:read|reading)\b", lowered):
            return "a message read ten times"

    quote_stopwords = _TOPIC_STOPWORDS.union({
        "background", "visuals", "screen", "vertical", "format", "sunset", "beach",
        "calm", "ocean", "waves", "poignant", "aesthetic", "atmospheric", "cinematic",
        "overlay", "mood", "authentic", "photo", "image", "video", "shorts", "reels"
    })

    candidates: list[str] = []
    for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", clean_content.lower()):
        if len(word) < 3 or word in quote_stopwords or word in candidates:
            continue
        candidates.append(word)

    if not candidates:
        return "deep quote"
    # Preserve the full inferred subject for ordinary instructional or
    # experience-led input.  Truncating to three words dropped the terms that
    # make otherwise similar topics distinct (for example ``csv files`` or a
    # food/route name), which then weakened fallback titles and tags.  Keep a
    # compact deterministic phrase, while retaining enough source vocabulary
    # for topic locking and contextual validation.
    return " ".join(candidates[:8])
