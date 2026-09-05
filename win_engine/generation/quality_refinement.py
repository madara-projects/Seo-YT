"""Bounded editorial refinement with explicit, measured acceptance targets."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.llm import gemini_client
from win_engine.llm.seo_writer import _generate_one

TARGET = 90.0
SCORE_FIELDS = ("title_score", "description_score", "tag_score")


def enforce_quality_target(gate: dict[str, Any]) -> dict[str, Any]:
    """Annotate shortfalls without replacing scores or treating missing data as zero evidence."""
    result = deepcopy(gate)
    quality = result.setdefault("final_seo_quality", {})
    shortfalls = [field for field in SCORE_FIELDS
                  if quality.get(field) is None or float(quality[field]) < TARGET]
    result["quality_target"] = {"minimum": TARGET, "met": not shortfalls,
                                "shortfalls": shortfalls, "basis": "local_heuristic_not_performance"}
    if shortfalls:
        issue = {"code": "quality_target_not_met", "field": "package", "severity": "warning",
                 "message": "90/90/90 target not met: " + ", ".join(shortfalls) + ". Manual review required."}
        result.setdefault("warnings", []).append(issue)
        quality.setdefault("warnings", []).append(issue)
        if result.get("verdict") != "RED":
            result["verdict"] = quality["verdict"] = "YELLOW"
    return result


def refine_package(package: dict[str, Any], *, script: str, brief: dict[str, Any],
                   language: str, region: str, evidence: dict[str, Any],
                   competitors: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rank existing alternatives, then attempt one repair; retain the stronger valid result."""
    def evaluate(value: dict[str, Any]) -> dict[str, Any]:
        return evaluate_package_quality(value, script=script, creator_brief=brief,
            language=language, require_shorts_tags=False, tag_evidence=evidence,
            competitor_titles=[str(row.get("title") or "") for row in competitors])

    def rank(gate: dict[str, Any]) -> tuple[bool, float, float]:
        scores = gate.get("final_seo_quality", {})
        title = float(scores.get("title_score") or 0)
        description = float(scores.get("description_score") or 0)
        return bool(gate.get("passed")), min(title, description), title + description

    best = deepcopy(package)
    gate = evaluate(best)
    for title in dict.fromkeys([best.get("title", ""), *(best.get("variants") or [])]):
        candidate = {**best, "title": title, "variants": [title, *(best.get("variants") or [])]}
        candidate_gate = evaluate(candidate)
        if rank(candidate_gate) > rank(gate):
            best, gate = candidate, candidate_gate
    trace: dict[str, Any] = {"target": TARGET, "attempted": False, "accepted": False,
                             "before": deepcopy(gate.get("final_seo_quality", {}))}
    scores = gate.get("final_seo_quality", {})
    if gemini_client.is_available() and any(float(scores.get(field) or 0) < TARGET
                                           for field in ("title_score", "description_score")):
        trace["attempted"] = True
        repaired = _generate_one(script, competitors, language=language, region=region,
            audience_type="general", category="quotes" if brief.get("exact_quote") else None,
            creator_brief=brief, temperature=0.2, max_tokens=2200,
            repair_feedback=[{"message":
                "Improve the title and description for source fidelity, natural wording and complementary meaning. "
                "Keep exact on-screen text in the description, followed by one useful non-repetitive sentence. "
                "Avoid vague hooks, invented claims, quote-copy titles and keyword stuffing. "
                f"Measured scores: {scores.get('title_score')}, {scores.get('description_score')}; target 90 each."}],
            previous_package=best)
        if repaired:
            # Writer suggestions cannot bypass the research tag selector.
            repaired["tags"], repaired["hashtags"] = best["tags"], best["hashtags"]
            repaired_gate = evaluate(repaired)
            if rank(repaired_gate) > rank(gate):
                best, gate = repaired, repaired_gate
                trace["accepted"] = True
    trace["after"] = deepcopy(gate.get("final_seo_quality", {}))
    return best, trace
