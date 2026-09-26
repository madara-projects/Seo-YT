from __future__ import annotations

import re
from typing import Any

from win_engine.analysis.source_cues import is_short_video, source_quote
from win_engine.analysis.text_tokens import normalize_unicode, unicode_words


def audit_content_package(
    script: str,
    title: str,
    primary_topic: str,
    secondary_topic: str,
    video_format: str = "",
    context_text: str = "",
    exact_quote: str = "",
) -> dict[str, Any]:
    """Heuristic package audit for hook, retention, and alignment."""

    first_150_words = _first_words(script, 150)
    format_brief = {"video_format": video_format}
    short_format = is_short_video(script, format_brief)
    if exact_quote.strip() and short_format:
        # A single on-screen line: judge reading load, not long-form cues.
        return _audit_quote_short(first_150_words, title, exact_quote)
    if not (short_format and source_quote(script, format_brief)):
        return _audit_long_form(script, title, primary_topic, secondary_topic, context_text)
    hook_audit = {
        "first_150_words": first_150_words,
        "keyword_in_opening": _contains_topic(first_150_words, primary_topic, secondary_topic),
        # The quote on screen is the stakes of a quote Short.
        "stakes_present": True,
        "hook_strength": _quote_hook_strength(script),
    }

    alignment_source = " ".join(part for part in (script, context_text) if part)
    alignment = {
        "title_script_alignment": _alignment_score(title, alignment_source, primary_topic, secondary_topic),
        "package_match": _package_match_label(title, alignment_source, primary_topic, secondary_topic),
    }

    first_30_second_simulator = {
        "predicted_dropoff_risk": _quote_dropoff_risk(script),
        # Mood words such as "rain" or "music" say nothing about likes or comments.
        "engagement_strength": "UNKNOWN",
        "basis": "Derived from the script's production cues only; not a measurement of retention or engagement.",
    }

    pattern_interrupts = {
        "count": _quote_pattern_count(script),
        "assessment": _quote_pattern_label(script),
    }

    retention_risk = {
        "level": _retention_risk_level(hook_audit, first_30_second_simulator, pattern_interrupts),
        "notes": _retention_notes(hook_audit, first_30_second_simulator, pattern_interrupts),
    }

    return {
        "hook_audit": hook_audit,
        "alignment": alignment,
        "first_30_second_simulator": first_30_second_simulator,
        "pattern_interrupts": pattern_interrupts,
        "retention_risk": retention_risk,
    }


# Reading speed for on-screen text, in words per second (about 150 wpm).
_ON_SCREEN_WORDS_PER_SECOND = 2.5
_QUOTE_ALIGNMENT_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "you", "your", "are", "was", "when", "what", "there",
    "than", "into", "from", "they", "them", "their", "have", "has", "been", "being", "more", "most",
    "shorts", "short",
}


def _audit_quote_short(first_150_words: str, title: str, quote: str) -> dict[str, Any]:
    """Audit a quote Short by what decides it: can the line be read in time.

    The long-form heuristics scored a 19-word quote "hook LOW, 30-second
    drop-off HIGH" and asked for pattern interrupts, contradicting the pacing
    and retention sections for the same video.
    """

    # Whole words in every script: [^\W_]+ split Tamil at each vowel sign, so a
    # 7-word Tamil quote counted as 17 and read as a heavy, slow hook.
    words = unicode_words(quote, min_length=1)
    read_seconds = round(len(words) / _ON_SCREEN_WORDS_PER_SECOND, 1)
    hook = "HIGH" if len(words) <= 12 else "MEDIUM" if len(words) <= 25 else "LOW"
    risk = "LOW" if read_seconds <= 5 else "MEDIUM" if read_seconds <= 10 else "HIGH"
    quote_terms = {word for word in words if len(word) >= 3} - _QUOTE_ALIGNMENT_STOPWORDS
    title_terms = {word for word in unicode_words(title, min_length=1) if len(word) >= 3} - _QUOTE_ALIGNMENT_STOPWORDS
    overlap = round(len(title_terms & quote_terms) / len(title_terms), 2) if title_terms else 0.0
    hold_seconds = int(read_seconds + 2.5)
    return {
        "hook_audit": {
            "first_150_words": first_150_words,
            "keyword_in_opening": True,
            "stakes_present": True,
            "hook_strength": hook,
            "basis": f"The quote is the hook; {len(words)} words is {'a quick' if hook == 'HIGH' else 'a moderate' if hook == 'MEDIUM' else 'a heavy'} read.",
        },
        "alignment": {
            "title_script_alignment": overlap,
            "package_match": "STRONG" if overlap >= 0.5 else "MEDIUM" if overlap > 0 else "WEAK",
            "basis": "Share of title words taken from the quote; a title should echo the quote's theme without copying it.",
        },
        "first_30_second_simulator": {
            "predicted_dropoff_risk": risk,
            "engagement_strength": "UNKNOWN",
            "basis": f"About {read_seconds}s to read the quote once; the risk is viewers swiping before they finish it.",
        },
        "pattern_interrupts": {
            "count": 0,
            "assessment": "NOT_APPLICABLE",
            "note": "A single-quote Short carries one idea; cuts or pattern interrupts are not needed.",
        },
        "retention_risk": {
            "level": risk,
            "notes": [
                f"Show the full quote within the first second and keep it on screen for at least {hold_seconds} seconds.",
                "Use high-contrast text that stays readable on a phone over the moving background.",
            ],
        },
    }


# A concrete promise in the opening: what the viewer gets, learns or sees.
_PAYOFF_CUE_RE = re.compile(
    r"\b(?:how to|show you|i show|learn|you'?ll|i tested|i tried|tested|review|compare[sd]?|comparison|vs|verdict|"
    r"results?|why|what happened|steps?|guide|recipe|make|build|fix|save|mistakes?|tips?|worth|breakdown|budget|"
    r"itinerary|explained?)\b",
    re.IGNORECASE,
)
_TRANSITION_RE = re.compile(
    r"\b(?:first|then|next|after that|finally|at the end|but|however|instead|also|because|step)\b", re.IGNORECASE,
)
# Below this, the input is a summary rather than a script; pacing cannot be judged.
_MIN_WORDS_FOR_PACING = 150


def _audit_long_form(
    script: str, title: str, primary_topic: str, secondary_topic: str, context_text: str,
) -> dict[str, Any]:
    """Audit an ordinary video's opening by signals that hold in any genre or language.

    The previous hook check needed an "Experiment" or "Story" angle and words
    like "result" or "failed", so every tutorial, review, vlog and Tamil
    script scored "hook LOW, retention risk HIGH".
    """

    words = re.findall(r"\S+", script)
    opening = " ".join(words[:40])
    first_sentence = re.split(r"(?<=[.!?।])\s+", script.strip(), maxsplit=1)[0]
    # Half the topic's words in the opening. Tamil words stay whole: split at
    # vowel signs, a Tamil topic had no words and was never "named early".
    topic_words = [word for word in unicode_words(primary_topic) if len(word) >= 3]
    # Normalised like the topic words: a script typed with decomposed Tamil
    # vowel signs never contained the composed topic.
    opening_folded = normalize_unicode(opening).casefold()
    topic_early = bool(topic_words) and sum(word in opening_folded for word in topic_words) >= max(1, len(topic_words) // 2)
    payoff = bool(_PAYOFF_CUE_RE.search(opening) or re.search(r"\d", opening))
    concise = len(first_sentence.split()) <= 25
    points = int(topic_early) + int(payoff) + int(concise)
    hook = "HIGH" if points >= 3 else "MEDIUM" if points == 2 else "LOW"
    dropoff = {"HIGH": "LOW", "MEDIUM": "MEDIUM", "LOW": "HIGH"}[hook]

    alignment_source = " ".join(part for part in (script, context_text) if part)
    transitions = len(_TRANSITION_RE.findall(script))
    if len(words) < _MIN_WORDS_FOR_PACING:
        interrupts = {
            "count": transitions, "assessment": "NOT_ASSESSED",
            "note": f"{len(words)} words is a summary, not a full script; paste the script to judge pacing.",
        }
    else:
        interrupts = {"count": transitions, "assessment": "STRONG" if transitions >= 6 else "MEDIUM" if transitions >= 3 else "WEAK"}
    risk = dropoff if interrupts["assessment"] != "WEAK" or dropoff == "HIGH" else "MEDIUM"

    notes: list[str] = []
    if not topic_early:
        notes.append("Name the topic in the first sentence so viewers know they are in the right place.")
    if not payoff:
        notes.append("State what the viewer will get (the result, the steps, or the verdict) in the opening.")
    if not concise:
        notes.append("Shorten the first sentence; a long lead-in delays the promise.")
    if interrupts["assessment"] == "WEAK":
        notes.append("Signal the structure as you go (first, next, finally) so viewers can follow along.")
    if not notes:
        notes.append("The opening states the topic and the payoff quickly.")
    return {
        "hook_audit": {
            "first_150_words": _first_words(script, 150),
            "keyword_in_opening": topic_early,
            "stakes_present": payoff,
            "hook_strength": hook,
            "basis": "topic named early, concrete payoff or number, concise first sentence",
        },
        "alignment": {
            "title_script_alignment": _alignment_score(title, alignment_source, primary_topic, secondary_topic),
            "package_match": _package_match_label(title, alignment_source, primary_topic, secondary_topic),
        },
        "first_30_second_simulator": {
            "predicted_dropoff_risk": dropoff,
            "engagement_strength": "UNKNOWN",
            "basis": "Derived from the opening only; not a measurement of retention.",
        },
        "pattern_interrupts": interrupts,
        "retention_risk": {"level": risk, "notes": notes},
    }


def _first_words(text: str, limit: int) -> str:
    words = re.findall(r"\S+", text)
    return " ".join(words[:limit])


def _contains_topic(text: str, primary_topic: str, secondary_topic: str) -> bool:
    lowered = _normalize_text(text)
    # An empty topic is "in" every string, so it must not count as present.
    return any(
        topic and topic in lowered
        for topic in (_normalize_text(primary_topic), _normalize_text(secondary_topic))
    )


def _alignment_score(title: str, script: str, primary_topic: str, secondary_topic: str) -> float:
    lowered_title = _normalize_text(title)
    lowered_script = _normalize_text(script)
    primary_normalized = _normalize_text(primary_topic)
    secondary_normalized = _normalize_text(secondary_topic)
    score = 0.0
    # An empty topic is in every string; a Tamil topic used to normalise to ""
    # and gave an unrelated title 0.8 ("STRONG").
    if primary_normalized and primary_normalized in lowered_title and primary_normalized in lowered_script:
        score += 0.5
    if secondary_normalized and secondary_normalized in lowered_title and secondary_normalized in lowered_script:
        score += 0.3
    alignment_stopwords = {
        "and", "are", "for", "from", "how", "the", "their", "them", "then",
        "this", "when", "with", "you", "your", "exact", "moment", "one",
        "painful", "truth",
    }
    title_words = {
        word
        for word in lowered_title.split()
        if len(word) >= 3 and word not in alignment_stopwords
    }
    script_words = set(lowered_script.split())
    if title_words:
        score += min(0.7, (len(title_words & script_words) / len(title_words)) * 0.7)
    return round(min(score, 1.0), 2)


def _quote_hook_strength(script: str) -> str:
    lowered = script.lower()
    score = int(any(term in lowered for term in ("typewriter", "phrase at a time", "phrase by phrase", "rain", "dusk", "lofi", "mood", "cinematic", "visual", "aesthetic", "window", "drops", "heartbreak", "hope", "cruel", "waiting")))
    score += int(any(term in lowered for term in ("brief pause", "anticipation", "empty briefly", "starts empty", "hold", "silence", "slow", "fade", "alone", "dark")))
    score += int(any(term in lowered for term in ("ambient music", "sound", "music", "lofi", "audio", "track", "silent", "melancholic", "somber")))
    return "HIGH" if score >= 2 else "MEDIUM" if score == 1 else "LOW"


def _quote_dropoff_risk(script: str) -> str:
    strength = _quote_hook_strength(script)
    if strength == "HIGH" and len(script.split()) <= 120:
        return "LOW"
    return "MEDIUM" if strength == "MEDIUM" else "HIGH"


def _quote_pattern_count(script: str) -> int:
    lowered = script.lower()
    markers = ("typewriter", "phrase at a time", "phrase by phrase", "hold", "fade", "music", "pause", "rain", "dusk", "lofi", "mood", "slow", "reveal", "silent")
    return sum(1 for marker in markers if marker in lowered)


def _quote_pattern_label(script: str) -> str:
    count = _quote_pattern_count(script)
    return "STRONG" if count >= 3 else "MEDIUM" if count >= 2 else "WEAK"


def _package_match_label(title: str, script: str, primary_topic: str, secondary_topic: str) -> str:
    score = _alignment_score(title, script, primary_topic, secondary_topic)
    if score >= 0.75:
        return "STRONG"
    if score >= 0.45:
        return "MEDIUM"
    return "WEAK"


def _retention_risk_level(
    hook_audit: dict[str, Any],
    first_30_second_simulator: dict[str, Any],
    pattern_interrupts: dict[str, Any],
) -> str:
    if hook_audit["hook_strength"] == "LOW" or first_30_second_simulator["predicted_dropoff_risk"] == "HIGH":
        return "HIGH"
    if pattern_interrupts["assessment"] == "WEAK":
        return "MEDIUM"
    return "LOW"


def _retention_notes(
    hook_audit: dict[str, Any],
    first_30_second_simulator: dict[str, Any],
    pattern_interrupts: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    if not hook_audit["keyword_in_opening"]:
        notes.append("Bring the main topic into the first few lines faster.")
    if first_30_second_simulator["predicted_dropoff_risk"] == "HIGH":
        notes.append("The opening may lose viewers before the payoff is clear.")
    if pattern_interrupts["assessment"] == "WEAK":
        notes.append("Add more transitions or pattern interrupts to keep momentum.")
    if not notes:
        notes.append("The opening structure is solid for a first-pass heuristic.")
    return notes


def _normalize_text(text: str) -> str:
    # Words from every script: an ASCII-only pattern erased Tamil entirely.
    return " ".join(unicode_words(text))
