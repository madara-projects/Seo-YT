"""Does the Opportunity Score track the creator's own published results?

A saved package's Opportunity Score is compared with what its published video
did, but only against comparable packages: the same format and language, each
video ownership-verified, each measured at the same completed snapshot window
(evidence_policy's rules), so every outcome has the same age. Within a group
the packages above the group's median score are compared with those below it,
and a Spearman rank correlation is reported once a group is large enough.

Whatever it finds is an association between a local heuristic and past views,
not a cause, and not a prediction of views.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from win_engine.feedback.evidence_policy import (
    EARLY_SIGNAL_MIN_SAMPLES,
    MATURE_SNAPSHOT_WINDOWS,
    evidence_level,
    sample_is_eligible,
    verified_ownership,
)
from win_engine.feedback.history_store import HistoryStore, comparable_format, known_filter

# A correlation weaker than this is never called a relationship, however many
# videos there are.
MIN_ASSOCIATION = 0.3
_EXCLUSION_REASONS = ("not_ownership_verified", "missing_format_or_language", "score_not_measured", "no_completed_snapshot")
_VERDICT_LABELS = {
    "insufficient_evidence": "Not enough comparable videos yet",
    "no_clear_relationship": "No clear relationship",
    "higher_scores_did_better": "Higher scores did better",
    "lower_scores_did_better": "Lower scores did better",
}
_RECOMMENDATIONS = {
    "keep": "Keep the score as a rough guide, and keep checking it as more videos mature.",
    "recalibrate": (
        "Recalibrate the score: its weights did not separate your better and worse results. "
        "Treat it as a checklist of inputs rather than a ranking until it is reweighted."
    ),
    "retire": "Retire the score as a ranking: in your own results it did not point to the videos that did better.",
}
CAVEATS = (
    "This is an association in your own past videos, not causation: topics, timing and packaging also differ between videos.",
    "The Opportunity Score is a local heuristic, not a prediction of views.",
    "Only packages in the same format and language, measured at the same completed window, are compared.",
)


def opportunity_score_calibration(history_store: HistoryStore, snapshot_window: str | None = None) -> dict[str, Any]:
    """The calibration for one window: the one asked for, else the one with the most comparable videos."""
    if snapshot_window is not None and snapshot_window not in MATURE_SNAPSHOT_WINDOWS:
        raise ValueError("Calibration requires a 24h, 7d, or 28d evidence window.")
    links = history_store.published_video_links_list()
    labels = _package_labels(history_store)
    collected = {window: _collect(history_store, links, labels, window) for window in MATURE_SNAPSHOT_WINDOWS}
    # Ties go to the longer window: a more mature outcome.
    chosen = snapshot_window or max(
        MATURE_SNAPSHOT_WINDOWS, key=lambda window: (len(collected[window][0]), MATURE_SNAPSHOT_WINDOWS.index(window))
    )
    samples, excluded = collected[chosen]
    result = calibrate_opportunity_score(samples, snapshot_window=chosen)
    result["windows"] = {window: len(collected[window][0]) for window in MATURE_SNAPSHOT_WINDOWS}
    result["excluded"] = excluded
    result["links_considered"] = len(links)
    result["breakdown_stored_count"] = sum(1 for sample in samples if sample.get("breakdown_stored"))
    return result


def calibrate_opportunity_score(samples: list[dict[str, Any]], *, snapshot_window: str) -> dict[str, Any]:
    """Compare scores with outcomes within each comparable group, and say what that allows."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for sample in samples:
        groups.setdefault((str(sample["format"]), str(sample["language"])), []).append(sample)
    group_results = [_group_result(fmt, language, members) for (fmt, language), members in sorted(groups.items())]
    compared = [group for group in group_results if group["spearman_rho"] is not None]
    compared_size = sum(group["sample_size"] for group in compared)
    largest = max((group["sample_size"] for group in group_results), default=0)

    rho = threshold = None
    if not compared:
        status = "insufficient_evidence"
    else:
        # Each group's correlation, weighted by its size: groups are never pooled.
        rho = round(sum(group["spearman_rho"] * group["sample_size"] for group in compared) / compared_size, 3)
        # Below about 1.96 / sqrt(n - 1) a rank correlation is within chance for n videos.
        threshold = round(max(MIN_ASSOCIATION, 1.96 / math.sqrt(compared_size - 1)), 3)
        directions = {group["direction"] for group in compared}
        if rho >= threshold and directions == {"higher"}:
            status = "higher_scores_did_better"
        elif rho <= -threshold and directions == {"lower"}:
            status = "lower_scores_did_better"
        else:
            status = "no_clear_relationship"

    level = evidence_level(compared_size)
    recommendation = _recommendation(status, level.key, rho, compared_size)
    return {
        "status": status,
        "verdict_label": _VERDICT_LABELS[status],
        "interpretation": "association_not_causation",
        "snapshot_window": snapshot_window,
        "outcome": "views_at_completed_window",
        "outcome_label": f"Views at the completed {snapshot_window} window",
        "sample_size": len(samples),
        "compared_sample_size": compared_size,
        "minimum_group_samples": EARLY_SIGNAL_MIN_SAMPLES,
        "evidence_level": level.key if compared else "display_only",
        "confidence_label": level.label if compared else "Collecting evidence",
        "spearman_rho": rho,
        "association_threshold": threshold,
        "groups": group_results,
        "recommendation": recommendation,
        "recommendation_text": _RECOMMENDATIONS.get(recommendation or ""),
        "summary": _summary(status, rho, compared_size, level.key, snapshot_window),
        "needed": _needed(status, largest, level.key, snapshot_window),
        "caveats": list(CAVEATS),
    }


def spearman_rho(xs: list[float], ys: list[float]) -> float | None:
    """Spearman's rank correlation with average ranks for ties, or None when it is undefined."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    x_ranks, y_ranks = _ranks(xs), _ranks(ys)
    x_mean, y_mean = sum(x_ranks) / len(x_ranks), sum(y_ranks) / len(y_ranks)
    covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks))
    x_spread = sum((x - x_mean) ** 2 for x in x_ranks)
    y_spread = sum((y - y_mean) ** 2 for y in y_ranks)
    if not x_spread or not y_spread:
        return None
    return round(covariance / math.sqrt(x_spread * y_spread), 4)


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for position in range(start, end + 1):
            ranks[order[position]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def _group_result(fmt: str, language: str, members: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(member["opportunity_score"]) for member in members]
    median_score = median(scores)
    higher = [float(m["views"]) for m in members if float(m["opportunity_score"]) > median_score]
    lower = [float(m["views"]) for m in members if float(m["opportunity_score"]) < median_score]
    enough = len(members) >= EARLY_SIGNAL_MIN_SAMPLES
    rho = spearman_rho(scores, [float(m["views"]) for m in members]) if enough else None
    higher_median = median(higher) if higher else None
    lower_median = median(lower) if lower else None
    direction = None
    if higher_median is not None and lower_median is not None:
        direction = "higher" if higher_median > lower_median else "lower" if higher_median < lower_median else "tie"
    return {
        "format": fmt,
        "language": language,
        "sample_size": len(members),
        "enough_samples": enough,
        "median_score": round(median_score, 2),
        "higher_scoring": {"sample_size": len(higher), "median_views": higher_median},
        "lower_scoring": {"sample_size": len(lower), "median_views": lower_median},
        "spearman_rho": rho,
        # Groups with too few videos show their medians but take no part in the verdict.
        "direction": direction if rho is not None else None,
    }


def _recommendation(status: str, level: str, rho: float | None, compared_size: int) -> str | None:
    # A recommendation needs at least moderate evidence; an early signal only reports.
    if status == "insufficient_evidence" or level in {"display_only", "early_signal"} or rho is None:
        return None
    if status == "higher_scores_did_better":
        return "keep"
    if status == "lower_scores_did_better":
        return "retire"
    # Missing the threshold is not proof the score is useless: it is retired only
    # when even the correlation plus its margin stays below a useful association.
    margin = 1.96 / math.sqrt(compared_size - 1)
    return "retire" if rho + margin < MIN_ASSOCIATION else "recalibrate"


def _summary(status: str, rho: float | None, compared: int, level: str, window: str) -> str:
    if status == "insufficient_evidence":
        return (
            "There are not yet enough comparable published videos to tell whether higher Opportunity Scores "
            "went with more views, so no association is claimed."
        )
    described = {
        "higher_scores_did_better": "higher-scoring packages went with more views",
        "lower_scores_did_better": "lower-scoring packages went with more views",
        "no_clear_relationship": "the score did not consistently separate videos with more and fewer views",
    }[status]
    early = " This is an early signal only." if level == "early_signal" else ""
    return (
        f"In {compared} comparable video(s) measured at the completed {window} window, {described} "
        f"(rank correlation {rho:+.2f}). This is an association, not causation.{early}"
    )


def _needed(status: str, largest: int, level: str, window: str) -> str | None:
    if status == "insufficient_evidence":
        return (
            f"Needs at least {EARLY_SIGNAL_MIN_SAMPLES} published videos with different scores in one format and language "
            f"group, each linked to its saved package, ownership-verified, and with a completed {window} snapshot. "
            f"The largest group has {largest}."
        )
    if level == "early_signal":
        return "A keep, recalibrate or retire recommendation needs at least 10 comparable videos."
    return None


def _package_labels(history_store: HistoryStore) -> dict[int, tuple[str, bool]]:
    """Each package's opportunity label, and whether it stored a score breakdown."""
    with history_store._connect() as connection:
        rows = connection.execute(
            """SELECT id, opportunity_label,
                      CASE WHEN json_valid(payload_json)
                           THEN json_extract(payload_json, '$.opportunity_gap_analysis.opportunity_score.breakdown.version') END
               FROM analysis_runs"""
        ).fetchall()
    return {int(row[0]): (str(row[1] or ""), bool(row[2])) for row in rows}


def _collect(
    history_store: HistoryStore, links: list[dict[str, Any]], labels: dict[int, tuple[str, bool]], window: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The eligible samples at one window, and why each other link was left out."""
    samples: list[dict[str, Any]] = []
    excluded = dict.fromkeys(_EXCLUSION_REASONS, 0)
    for link in links:
        comparable = link.get("comparable_metadata") if isinstance(link.get("comparable_metadata"), dict) else {}
        policy_link = dict(link)
        policy_link["format"] = comparable_format(comparable.get("format") or link.get("format")) or "unknown"
        policy_link["language"] = known_filter(comparable.get("language") or link.get("language")) or "unknown"
        label, breakdown_stored = labels.get(int(link.get("analysis_run_id") or 0), ("", False))
        score = link.get("package_opportunity_score")
        if not verified_ownership(policy_link):
            excluded["not_ownership_verified"] += 1
            continue
        if "unknown" in (policy_link["format"], policy_link["language"]):
            excluded["missing_format_or_language"] += 1
            continue
        # An unmeasured score was once stored as 0; the label says it never was one.
        if score is None or label.upper() == "UNMEASURED":
            excluded["score_not_measured"] += 1
            continue
        snapshot = history_store.completed_evidence_snapshot(str(link.get("youtube_video_id") or ""), window)
        if not sample_is_eligible(policy_link, snapshot, expected_window=window):
            excluded["no_completed_snapshot"] += 1
            continue
        samples.append({
            "analysis_run_id": link.get("analysis_run_id"),
            "youtube_video_id": link.get("youtube_video_id"),
            "opportunity_score": float(score),
            "views": float(snapshot["views"]),
            "format": policy_link["format"],
            "language": policy_link["language"],
            "breakdown_stored": breakdown_stored,
        })
    return samples, excluded
