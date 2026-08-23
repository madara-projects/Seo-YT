"""Truthful deterministic Phase 8 published-audit and experiment comparisons."""

from __future__ import annotations

import re
import json
from statistics import mean, median
from typing import Any

from win_engine.feedback.evidence_policy import confidence_payload, mature_snapshot


AUDIT_RULE_VERSION = "phase8-audit-v1"
EXPERIMENT_RULE_VERSION = "phase8-experiment-v1"
SUPPORTED_METRICS = {"views", "average_view_percentage", "likes", "comments", "engagement_rate"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _items(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                value = parsed
            else:
                value = [raw]
        except json.JSONDecodeError:
            # Older linked records may contain one opaque space-separated tag
            # string. Preserve it as observed instead of inventing boundaries.
            value = [item.strip() for item in re.split(r"[,\n]", raw) if item.strip()] or [raw]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalized(value: Any) -> Any:
    if isinstance(value, list):
        return sorted({_text(item).casefold() for item in value if _text(item)})
    return re.sub(r"\s+", " ", _text(value)).casefold()


def _field_state(left: Any, right: Any, *, left_available: bool, right_available: bool) -> str:
    if not left_available or not right_available:
        return "unavailable"
    if left is None or right is None:
        return "unknown"
    if isinstance(left, list) and not left:
        return "missing"
    if isinstance(right, list) and not right:
        return "missing"
    if not _text(left) and not isinstance(left, list):
        return "missing"
    if not _text(right) and not isinstance(right, list):
        return "missing"
    return "exact_match" if _normalized(left) == _normalized(right) else "changed"


def _comparison(name: str, generated: Any, selected: Any, published: Any, selection_exists: bool, published_available: bool) -> dict[str, Any]:
    return {
        "field": name,
        "generated": generated,
        "selected": selected if selection_exists else None,
        "published": published if published_available else None,
        "provenance": {"generated": "saved_analysis_payload", "selected": "creator_selection" if selection_exists else "unavailable", "published": "youtube_owned_metadata" if published_available else "unavailable"},
        "generated_to_selected": _field_state(generated, selected, left_available=True, right_available=selection_exists),
        "selected_to_published": _field_state(selected, published, left_available=selection_exists, right_available=published_available),
        "generated_to_published": _field_state(generated, published, left_available=True, right_available=published_available),
    }


def build_published_audit(context: dict[str, Any]) -> dict[str, Any]:
    run, link = context["run"], context["link"]
    package = run.get("package") if isinstance(run.get("package"), dict) else {}
    selection = run.get("selected_package") if isinstance(run.get("selected_package"), dict) else None
    selected = selection.get("package") if selection and isinstance(selection.get("package"), dict) else {}
    published = link.get("youtube_metadata") if isinstance(link.get("youtube_metadata"), dict) else {}
    published_available = bool(published and link.get("metadata_synced_at"))
    published_description = _text(published.get("description"))

    generated = {
        "title": _text(package.get("title") or run.get("title")),
        "description": _text(package.get("description")),
        "tags": _items(package.get("tags")),
        "hashtags": _items(package.get("hashtags")),
    }
    selected_values = {
        "title": _text(selected.get("title")) or None,
        "description": _text(selected.get("description")) or None,
        "tags": _items(selected.get("tags")) if selection else None,
        "hashtags": _items(selected.get("hashtags")) if selection else None,
    }
    published_values = {
        "title": _text(published.get("title")) or None,
        "description": published_description or None,
        "tags": _items(published.get("tags")),
        "hashtags": re.findall(r"#[\w]+", published_description, flags=re.UNICODE),
    }
    comparisons = [
        _comparison(field, generated[field], selected_values[field], published_values[field], bool(selection), published_available)
        for field in ("title", "description", "tags", "hashtags")
    ]

    snapshots = context.get("snapshots") or []
    mature = [item for item in snapshots if mature_snapshot(item)]
    current = next((item for item in reversed(snapshots) if item.get("snapshot_window") == "current"), None)
    latest_mature = mature[-1] if mature else None
    observed = current or latest_mature
    report = context.get("linked_report") or {}
    retention = package.get("retention_assistant") if isinstance(package.get("retention_assistant"), dict) else {}
    quality = package.get("generation_quality") if isinstance(package.get("generation_quality"), dict) else {}
    findings: list[dict[str, Any]] = []

    def finding(code: str, severity: str, category: str, explanation: str, evidence: str, state: str, interpretation: str) -> None:
        findings.append({"code": code, "severity": severity, "category": category, "explanation": explanation, "evidence": evidence, "evidence_state": state, "recommended_interpretation": interpretation})

    if not selection:
        finding("selection_unknown", "review", "attribution", "No explicit generated-package selection was recorded.", "analysis_package_selections: unavailable", "unknown", "Do not infer that the primary generated package was published.")
    if not published_available:
        finding("published_metadata_unavailable", "review", "published_reality", "Owned YouTube metadata has not been captured for this link.", "published_video_links.youtube_metadata_json: unavailable", "unavailable", "Refresh the linked video before comparing intent with published reality.")
    else:
        title = next(item for item in comparisons if item["field"] == "title")
        if selection and title["selected_to_published"] == "exact_match":
            finding("selected_title_preserved", "info", "metadata", "Published title preserved the explicitly selected title.", "creator selection + owned YouTube metadata", "observed", "This confirms attribution only; it does not show that the title caused performance.")
        elif selection:
            finding("published_title_changed", "review", "metadata", "Published title differed from the explicitly selected title.", "creator selection + owned YouTube metadata", "observed", "Treat performance as evidence about the published title, not the selected draft.")
        else:
            finding("generated_vs_published_only", "info", "metadata", "Generated and published metadata can be compared, but selected-package attribution is unknown.", "saved generation + owned YouTube metadata", "observed", "A difference is observable but the creator's intended package cannot be inferred.")
        changed = [item["field"] for item in comparisons if item["generated_to_published"] == "changed"]
        if changed:
            finding("published_metadata_changed", "review", "metadata", "Published metadata differed from the primary generated package: " + ", ".join(changed) + ".", "saved generation + owned YouTube metadata", "observed", "Use the actual published values for post-publication learning.")
    if retention.get("risk_level") in {"high", "medium"}:
        finding("opening_risk_recorded", "review", "pre_publish", f"The saved retention assistant recorded {retention.get('risk_level')} structural risk.", "historical retention_assistant payload", "heuristic", "This was pre-publish guidance, not measured retention.")
    if quality:
        finding("generation_quality_trace", "info", "pre_publish", f"The saved generation-quality state was {_text(quality.get('status')) or 'available'}.", "historical generation_quality payload", "heuristic", "Quality checks describe package consistency, not expected reach.")
    if not mature:
        finding("mature_evidence_missing", "review", "performance", "No completed 24h, 7d, or 28d observation window is available.", "video_performance_snapshots", "insufficient_evidence", "Continue collecting evidence; current counts are display observations only.")
    else:
        finding("mature_observation_available", "info", "performance", f"{len(mature)} completed observation window(s) are available.", "verified completed YouTube Analytics snapshots", "mature_observation", "The observations support comparison, not causality.")

    cohort = context.get("cohort") or {}
    learning_allowed = bool(cohort.get("learning_allowed"))
    brief = package.get("creator_brief") if isinstance(package.get("creator_brief"), dict) else {}
    candidate_state = "mature_comparable_evidence" if learning_allowed and mature else "hypothesis_only" if mature else "insufficient_evidence"
    candidates = []
    for variable, value in (
        ("format", (context.get("comparable") or {}).get("format") or link.get("format")),
        ("language", (context.get("comparable") or {}).get("language") or link.get("language")),
        ("topic", brief.get("topic") or run.get("query")),
        ("title_mechanism", selected.get("mechanism") if selection else None),
        ("discovery_surface", selected.get("surface") if selection else None),
    ):
        if value:
            candidates.append({"variable": variable, "value": value, "evidence_state": candidate_state, "sample_size": int(cohort.get("sample_size") or 0), "interpretation": "Observed association candidate; never causal proof.", "provenance": "saved_package_and_shared_evidence_policy"})

    if not published_available:
        summary_state = "not_enough_data"
    elif not snapshots:
        summary_state = "collecting_evidence"
    elif mature and learning_allowed:
        summary_state = "actionable_observation"
    elif mature:
        summary_state = "mature_observation"
    elif observed:
        summary_state = "observable"
    else:
        summary_state = "inconclusive"

    return {
        "rule_version": AUDIT_RULE_VERSION,
        "summary": {"state": summary_state, "message": "Historical intent, actual published metadata, and available observations are separated. No finding establishes causality."},
        "video": {"link_id": link.get("id"), "analysis_run_id": run.get("id"), "youtube_video_id": link.get("youtube_video_id"), "published_at": link.get("published_at"), "format": link.get("format"), "language": link.get("language"), "duration": published.get("duration"), "ownership_state": link.get("ownership_state"), "provenance": "verified_owned_video_link", "field_provenance": {"format": (context.get("comparable") or {}).get("sources", {}).get("format", "unknown"), "language": (context.get("comparable") or {}).get("sources", {}).get("language", "unknown"), "duration": "youtube_owned_metadata" if published.get("duration") else "unavailable"}},
        "intent": {"original_query": run.get("query"), "generated_package": generated, "selected_package": selected_values if selection else None, "selection_attribution": "creator_selected" if selection else "unknown", "selected_package_id": selection.get("generated_package_id") if selection else None},
        "published_reality": {**published_values, "available": published_available, "captured_at": link.get("metadata_synced_at"), "provenance": "youtube_owned_metadata" if published_available else "unavailable"},
        "comparisons": comparisons,
        "before_publication": {"generation_quality": quality or {"status": "unavailable"}, "retention_assistant": retention or {"status": "unavailable"}, "selected_package_trace": selected or None, "idea": context.get("idea"), "idea_research": context.get("idea_research"), "demand_research": context.get("demand_research"), "watchlist_context": ((context.get("demand_research") or {}).get("evidence") or {}).get("matching_watchlist"), "personal_evidence": package.get("personalization_trace") or {"status": "unavailable"}, "provenance": "saved_historical_payloads_only"},
        "observed_performance": {"current": current, "completed_windows": mature, "latest_observation": observed, "linked_report_performance": report.get("performance"), "maturity": "mature_observation" if mature else "collecting_evidence" if snapshots else "unavailable", "causality": "not_established"},
        "findings": findings,
        "learning_candidates": candidates,
        "evidence": {"snapshot_count": len(snapshots), "mature_window_count": len(mature), "cohort": cohort, "retention_learning": report.get("retention_learning"), "provenance": ["saved_analysis_payload", "creator_selection_or_unknown", "youtube_owned_metadata", "youtube_performance_snapshots", "shared_evidence_policy"]},
        "limitations": ["YouTube video-level metrics do not isolate the effect of title, tags, thumbnail, hook, or timing.", "Unavailable fields remain unavailable; retention curves and competitor private analytics are not inferred.", "A mature observation can support comparison but does not prove causation."],
    }


def _metric_value(snapshot: dict[str, Any], metric: str) -> float | None:
    key = "avg_view_percentage" if metric == "average_view_percentage" else metric
    if metric == "engagement_rate":
        views = snapshot.get("views")
        if not views:
            return None
        return 100.0 * sum(float(snapshot.get(k) or 0) for k in ("likes", "comments", "shares")) / float(views)
    value = snapshot.get(key)
    return float(value) if value is not None else None


def compare_experiment(experiment: dict[str, Any], assignments: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [experiment["success_metric"], *experiment.get("secondary_metrics", [])]
    metrics = list(dict.fromkeys(metric for metric in metrics if metric in SUPPORTED_METRICS))
    groups = {"control": [], "variant": []}
    reference_count = 0
    missing_metrics: list[dict[str, Any]] = []
    for item in assignments:
        role = item.get("role")
        if role == "observational_reference":
            reference_count += 1
            continue
        snapshot = item.get("evidence_snapshot")
        if role in groups and mature_snapshot(snapshot, experiment.get("observation_window")):
            groups[role].append(item)
        elif role in groups:
            missing_metrics.append({"link_id": item.get("published_video_link_id"), "role": role, "reason": "completed comparable window unavailable"})

    metric_results = []
    directions = []
    for metric in metrics:
        control = [value for item in groups["control"] if (value := _metric_value(item["evidence_snapshot"], metric)) is not None]
        variant = [value for item in groups["variant"] if (value := _metric_value(item["evidence_snapshot"], metric)) is not None]
        cm, vm = (median(control) if control else None), (median(variant) if variant else None)
        difference = (vm - cm) if cm is not None and vm is not None else None
        relative = (difference / abs(cm) * 100.0) if difference is not None and cm else None
        direction = "variant" if difference is not None and difference > 0 else "control" if difference is not None and difference < 0 else "even"
        if relative is not None and abs(relative) >= 5:
            directions.append(direction)
        metric_results.append({"metric": metric, "control": {"sample_size": len(control), "median": cm, "mean": mean(control) if control else None}, "variant": {"sample_size": len(variant), "median": vm, "mean": mean(variant) if variant else None}, "difference": difference, "relative_difference_percent": round(relative, 2) if relative is not None else None, "observed_direction": direction, "provenance": "verified_completed_youtube_analytics_snapshot"})

    assigned_control = sum(item.get("role") == "control" for item in assignments)
    assigned_variant = sum(item.get("role") == "variant" for item in assignments)
    minimum = max(5, int(experiment.get("minimum_sample_size") or 5))
    enough = len(groups["control"]) >= minimum and len(groups["variant"]) >= minimum
    if not enough:
        state = "insufficient_evidence"
    elif experiment.get("mode") == "observational":
        state = "observational_pattern"
    elif "control" in directions and "variant" in directions:
        state = "mixed_results"
    else:
        primary = metric_results[0] if metric_results else {}
        relative = primary.get("relative_difference_percent")
        if relative is None or abs(relative) < 5:
            state = "inconclusive"
        else:
            state = "directional_variant" if relative > 0 else "directional_control"

    policy = confidence_payload(len(groups["control"]) + len(groups["variant"]))
    learning = None
    if enough and state not in {"insufficient_evidence", "inconclusive"}:
        learning = {"variable": experiment.get("variable"), "observation": state, "evidence_state": "observed_association" if experiment.get("mode") == "observational" else "directional", "sample_size": len(groups["control"]) + len(groups["variant"]), "source_experiment": experiment.get("id"), "future_generation_allowed": bool(policy["learning_allowed"]), "interpretation": "Associated with the observed result in this sample; not causal proof."}
    label = "OBSERVATIONAL — NOT A CONTROLLED EXPERIMENT" if experiment.get("mode") == "observational" else "PLANNED EXPERIMENT — DIRECTIONAL, NOT CAUSAL PROOF"
    return {"rule_version": EXPERIMENT_RULE_VERSION, "state": state, "mode": experiment.get("mode"), "label": label, "sample": {"assigned_control": assigned_control, "assigned_variant": assigned_variant, "eligible_control": len(groups["control"]), "eligible_variant": len(groups["variant"]), "mature_control": len(groups["control"]), "mature_variant": len(groups["variant"]), "observational_references": reference_count, "minimum_per_group": minimum, "missing_metrics": missing_metrics}, "metrics": metric_results, "evidence": {**policy, "observation_window": experiment.get("observation_window"), "status": "directional_evidence" if enough else "insufficient_evidence"}, "interpretation": _experiment_interpretation(state), "limitations": ["Assignment records intent but does not eliminate distribution, topic, audience, timing, or content confounders.", "No fake statistical significance or causal claim is calculated.", "Only verified completed snapshots in the selected window are eligible."], "learning_candidate": learning, "next_recommendation": "Collect more eligible control and variant videos." if not enough else "Treat this as a candidate explanation and repeat the comparison before changing generation policy."}


def _experiment_interpretation(state: str) -> str:
    return {
        "insufficient_evidence": "The sample is too small or lacks comparable completed metrics; no direction is claimed.",
        "directional_control": "The control was associated with a higher observed primary metric in this sample.",
        "directional_variant": "The variant was associated with a higher observed primary metric in this sample.",
        "inconclusive": "The observed primary metric difference is too small or unavailable to support a direction.",
        "mixed_results": "Available metrics point in different directions; the result is mixed and not a winner.",
        "observational_pattern": "A historical association is visible, but this was not a controlled experiment.",
    }[state]
