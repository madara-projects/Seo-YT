from __future__ import annotations

import re
from typing import Any


def audit_content_package(
    script: str,
    title: str,
    primary_topic: str,
    secondary_topic: str,
    content_angle: str,
    video_format: str = "",
    context_text: str = "",
    exact_quote: str = "",
) -> dict[str, Any]:
    """Heuristic package audit for hook, retention, and alignment."""

    first_150_words = _first_words(script, 150)
    short_format = any(term in video_format.lower() for term in ("short", "reel"))
    if exact_quote.strip() and short_format:
        # A single on-screen line: judge reading load, not long-form cues.
        return _audit_quote_short(first_150_words, title, exact_quote)
    is_quote_short = _is_quote_short(script, video_format)
    if not is_quote_short:
        return _audit_long_form(script, title, primary_topic, secondary_topic, context_text)
    hook_audit = {
        "first_150_words": first_150_words,
        "keyword_in_opening": _contains_topic(first_150_words, primary_topic, secondary_topic),
        "stakes_present": _has_stakes(first_150_words) or is_quote_short,
        "hook_strength": _quote_hook_strength(script) if is_quote_short else _hook_strength(first_150_words, content_angle),
    }

    alignment_source = " ".join(part for part in (script, context_text) if part)
    alignment = {
        "title_script_alignment": _alignment_score(title, alignment_source, primary_topic, secondary_topic),
        "package_match": _package_match_label(title, alignment_source, primary_topic, secondary_topic),
    }

    first_30_second_simulator = {
        "predicted_dropoff_risk": _quote_dropoff_risk(script) if is_quote_short else _dropoff_risk(first_150_words),
        "engagement_strength": _quote_engagement_strength(script) if is_quote_short else _engagement_strength(first_150_words),
    }

    pattern_interrupts = {
        "count": _quote_pattern_count(script) if is_quote_short else _pattern_interrupt_count(script),
        "assessment": _quote_pattern_label(script) if is_quote_short else _pattern_interrupt_label(script),
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

    words = re.findall(r"[^\W_]+(?:['’][^\W_]+)?", quote)
    read_seconds = round(len(words) / _ON_SCREEN_WORDS_PER_SECOND, 1)
    hook = "HIGH" if len(words) <= 12 else "MEDIUM" if len(words) <= 25 else "LOW"
    risk = "LOW" if read_seconds <= 5 else "MEDIUM" if read_seconds <= 10 else "HIGH"
    quote_terms = {word.casefold() for word in words if len(word) >= 3} - _QUOTE_ALIGNMENT_STOPWORDS
    title_terms = {
        word.casefold() for word in re.findall(r"[^\W_]+(?:['’][^\W_]+)?", title) if len(word) >= 3
    } - _QUOTE_ALIGNMENT_STOPWORDS
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
    # Half the topic's words in the opening. (_contains_topic is always true
    # when a topic is empty, because "" is in every string.)
    topic_words = [word for word in re.findall(r"[^\W_]+", primary_topic.casefold()) if len(word) >= 3]
    opening_folded = opening.casefold()
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
    primary_normalized = _normalize_text(primary_topic)
    secondary_normalized = _normalize_text(secondary_topic)
    return primary_normalized in lowered or secondary_normalized in lowered


def _has_stakes(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "grow",
        "views",
        "result",
        "worked",
        "failed",
        "mistake",
        "strategy",
        "improve",
        "what happened",
        "tried",
        "tested",
        "honest result",
        "worth it",
        "overhyped",
        "benefit",
        "downside",
        "should you",
        "honest",
    ]
    return any(marker in lowered for marker in markers)


def _hook_strength(text: str, content_angle: str) -> str:
    lowered = text.lower()
    score = 0
    if any(token in lowered for token in ["today", "in this video", "i tested", "i tried", "what happened"]):
        score += 1
    if any(token in lowered for token in ["worked", "failed", "result", "mistake", "strategy"]):
        score += 1
    if content_angle in {"Experiment", "Curiosity", "Story"}:
        score += 1

    if score >= 3:
        return "HIGH"
    if score == 2:
        return "MEDIUM"
    return "LOW"


def _alignment_score(title: str, script: str, primary_topic: str, secondary_topic: str) -> float:
    lowered_title = _normalize_text(title)
    lowered_script = _normalize_text(script)
    primary_normalized = _normalize_text(primary_topic)
    secondary_normalized = _normalize_text(secondary_topic)
    score = 0.0
    if primary_normalized in lowered_title and primary_normalized in lowered_script:
        score += 0.5
    if secondary_normalized in lowered_title and secondary_normalized in lowered_script:
        score += 0.3
    alignment_stopwords = {
        "and", "are", "for", "from", "how", "the", "their", "them", "then",
        "this", "when", "with", "you", "your", "exact", "moment", "one",
        "painful", "truth",
    }
    title_words = {
        word
        for word in re.findall(r"[a-z0-9]+", lowered_title)
        if len(word) >= 3 and word not in alignment_stopwords
    }
    script_words = set(re.findall(r"[a-z0-9]+", lowered_script))
    if title_words:
        score += min(0.7, (len(title_words & script_words) / len(title_words)) * 0.7)
    return round(min(score, 1.0), 2)


def _is_quote_short(script: str, video_format: str) -> bool:
    lowered = f"{video_format} {script}".lower()
    has_quote = bool(re.search(r'["\u201c\u201d]([^"\u201c\u201d]{12,})["\u201c\u201d]', script))
    if not has_quote:
        has_quote = bool(re.search(r"(?<![A-Za-z])'([^'\n]{12,})'(?![A-Za-z])", script))
    if not has_quote:
        has_quote = bool(re.search(r"(?:on-screen text|quote|exact quote)\s*:\s*([^\n]{12,})", script, re.IGNORECASE))
    return has_quote and any(
        term in lowered for term in ("short", "reel", "quote", "typewriter", "on-screen", "on screen")
    )


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


def _quote_engagement_strength(script: str) -> str:
    return "HIGH" if _quote_hook_strength(script) == "HIGH" else "MEDIUM"


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


def _dropoff_risk(text: str) -> str:
    lowered = text.lower()
    if not any(
        marker in lowered
        for marker in ["result", "strategy", "worked", "failed", "show", "explain", "worth it", "overhyped", "what happened"]
    ):
        return "HIGH"
    if len(text.split()) < 40:
        return "MEDIUM"
    return "LOW"


def _engagement_strength(text: str) -> str:
    lowered = text.lower()
    score = 0
    if any(marker in lowered for marker in ["i tested", "i tried", "case study", "show you"]):
        score += 1
    if any(marker in lowered for marker in ["worked", "failed", "best", "result"]):
        score += 1
    if len(text.split()) >= 60:
        score += 1
    return "HIGH" if score >= 3 else "MEDIUM" if score == 2 else "LOW"


def _pattern_interrupt_count(script: str) -> int:
    lowered = script.lower()
    markers = ["but", "however", "instead", "then", "next", "also", "because", "if you"]
    return sum(lowered.count(marker) for marker in markers)


def _pattern_interrupt_label(script: str) -> str:
    count = _pattern_interrupt_count(script)
    if count >= 6:
        return "STRONG"
    if count >= 3:
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
    if not hook_audit["stakes_present"]:
        notes.append("State the stakes or promised outcome earlier.")
    if first_30_second_simulator["predicted_dropoff_risk"] == "HIGH":
        notes.append("The opening may lose viewers before the payoff is clear.")
    if pattern_interrupts["assessment"] == "WEAK":
        notes.append("Add more transitions or pattern interrupts to keep momentum.")
    if not notes:
        notes.append("The opening structure is solid for a first-pass heuristic.")
    return notes


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9\s]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered
