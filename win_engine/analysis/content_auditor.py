from __future__ import annotations

import re
from typing import Any


def audit_content_package(
    script: str,
    title: str,
    primary_topic: str,
    secondary_topic: str,
    content_angle: str,
) -> dict[str, Any]:
    """Heuristic package audit for hook, retention, and alignment."""

    first_150_words = _first_words(script, 150)
    hook_audit = {
        "first_150_words": first_150_words,
        "keyword_in_opening": _contains_topic(first_150_words, primary_topic, secondary_topic),
        "stakes_present": _has_stakes(first_150_words),
        "hook_strength": _hook_strength(first_150_words, content_angle),
    }

    alignment = {
        "title_script_alignment": _alignment_score(title, script, primary_topic, secondary_topic),
        "package_match": _package_match_label(title, script, primary_topic, secondary_topic),
    }

    first_30_second_simulator = {
        "predicted_dropoff_risk": _dropoff_risk(first_150_words),
        "engagement_strength": _engagement_strength(first_150_words),
    }

    pattern_interrupts = {
        "count": _pattern_interrupt_count(script),
        "assessment": _pattern_interrupt_label(script),
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


def _first_words(text: str, limit: int) -> str:
    words = re.findall(r"\S+", text)
    return " ".join(words[:limit])


def _contains_topic(text: str, primary_topic: str, secondary_topic: str) -> bool:
    lowered = text.lower()
    return primary_topic.lower() in lowered or secondary_topic.lower() in lowered


def _has_stakes(text: str) -> bool:
    lowered = text.lower()
    markers = ["grow", "views", "result", "worked", "failed", "mistake", "strategy", "improve"]
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
    lowered_title = title.lower()
    lowered_script = script.lower()
    score = 0.0
    if primary_topic.lower() in lowered_title and primary_topic.lower() in lowered_script:
        score += 0.5
    if secondary_topic.lower() in lowered_title and secondary_topic.lower() in lowered_script:
        score += 0.3
    if any(word in lowered_script for word in re.findall(r"[a-z0-9]+", lowered_title)):
        score += 0.2
    return round(min(score, 1.0), 2)


def _package_match_label(title: str, script: str, primary_topic: str, secondary_topic: str) -> str:
    score = _alignment_score(title, script, primary_topic, secondary_topic)
    if score >= 0.75:
        return "STRONG"
    if score >= 0.45:
        return "MEDIUM"
    return "WEAK"


def _dropoff_risk(text: str) -> str:
    lowered = text.lower()
    if not any(marker in lowered for marker in ["result", "strategy", "worked", "failed", "show", "explain"]):
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
