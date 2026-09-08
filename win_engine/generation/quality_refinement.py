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
        tag = float(scores.get("tag_score") or 0)
        return bool(gate.get("passed")), min(title, description, tag), title + description + tag

    def refine_tags_locally(pkg: dict[str, Any]) -> dict[str, Any]:
        pkg_tags = list(pkg.get("tags") or [])
        if not pkg_tags or not evidence:
            return pkg
        selected_keywords = {
            str(item.get("keyword") or "").casefold(): item
            for item in evidence.get("selected_keywords", [])
            if isinstance(item, dict) and item.get("keyword")
        }
        platform_tags = [t for t in pkg_tags if t.lower() in {"yt", "shorts"}]
        topic_tags = [t for t in pkg_tags if t.lower() not in {"yt", "shorts"}]
        scored_topics = []
        for t in topic_tags:
            row = selected_keywords.get(t.lower(), {})
            score = float(row.get("keyword_relevance_score") or 0)
            scored_topics.append((t, score))
        avg = sum(s for _, s in scored_topics) / max(len(scored_topics), 1)
        if avg >= TARGET:
            return pkg
        # Sort ascending to prune the lowest scoring tags pulling down the average
        scored_topics.sort(key=lambda x: x[1])
        pruned = False
        while len(scored_topics) > 2 and (sum(s for _, s in scored_topics) / len(scored_topics)) < TARGET:
            if scored_topics[0][1] < TARGET:
                scored_topics.pop(0)
                pruned = True
            else:
                break
        # If still below TARGET and candidates exist with score >= TARGET, swap out weak tags
        current_avg = sum(s for _, s in scored_topics) / max(len(scored_topics), 1)
        if current_avg < TARGET:
            # Raw candidates include phrases rejected by the final selector.
            # Refinement may prune selected tags, but must never promote a raw
            # candidate and bypass relevance, quote-copy, or diversity checks.
            pass

        if not pruned:
            return pkg
        new_topic_tags = [t for t, _ in scored_topics]
        return {**pkg, "tags": [*new_topic_tags, *platform_tags]}

    best = deepcopy(package)
    gate = evaluate(best)
    # Check local tag refinement first
    candidate_tag_pkg = refine_tags_locally(best)
    if candidate_tag_pkg != best:
        candidate_tag_gate = evaluate(candidate_tag_pkg)
        if rank(candidate_tag_gate) > rank(gate):
            best, gate = candidate_tag_pkg, candidate_tag_gate
    for title in dict.fromkeys([best.get("title", ""), *(best.get("variants") or [])]):
        candidate = {**best, "title": title, "variants": [title, *(best.get("variants") or [])]}
        candidate_gate = evaluate(candidate)
        if rank(candidate_gate) > rank(gate):
            best, gate = candidate, candidate_gate
    trace: dict[str, Any] = {"target": TARGET, "attempted": False, "accepted": False,
                             "before": deepcopy(gate.get("final_seo_quality", {}))}
    scores = gate.get("final_seo_quality", {})
    if gemini_client.is_available() and any(float(scores.get(field) or 0) < TARGET
                                           for field in SCORE_FIELDS):
        trace["attempted"] = True
        repaired = _generate_one(script, competitors, language=language, region=region,
            audience_type="general", category="quotes" if brief.get("exact_quote") else None,
            creator_brief=brief, temperature=0.2, max_tokens=2200,
            repair_feedback=[{"message":
                "Improve the title and description for source fidelity, natural wording and complementary meaning. "
                "Keep exact on-screen text in the description, followed by one useful non-repetitive sentence. "
                "Avoid vague hooks, invented claims, quote-copy titles and keyword stuffing. "
                f"Measured scores: title={scores.get('title_score')}, description={scores.get('description_score')}, tags={scores.get('tag_score')}; target 90 each."}],
            previous_package=best)
        if repaired:
            # Writer suggestions cannot bypass the research tag selector.
            repaired["tags"], repaired["hashtags"] = best["tags"], best["hashtags"]
            repaired_tag_pkg = refine_tags_locally(repaired)
            for title in dict.fromkeys([repaired_tag_pkg.get("title", ""), *(repaired_tag_pkg.get("variants") or [])]):
                candidate = {**repaired_tag_pkg, "title": title, "variants": [title, *(repaired_tag_pkg.get("variants") or [])]}
                cand_gate = evaluate(candidate)
                if rank(cand_gate) > rank(gate):
                    best, gate = candidate, cand_gate
                    trace["accepted"] = True
    trace["after"] = deepcopy(gate.get("final_seo_quality", {}))
    return best, trace
