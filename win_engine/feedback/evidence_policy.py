"""Thresholds and eligibility rules for mature, comparable personal learning evidence.

The cohort queries in history_store apply the same rules in SQL (its
_VERIFIED_LINK_SQL, _COMPARABLE_LABELS_SQL and _MATURE_SNAPSHOT_SQL); keep them in step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


EARLY_SIGNAL_MIN_SAMPLES = 5
MODERATE_EVIDENCE_MIN_SAMPLES = 10
STRONG_EVIDENCE_MIN_SAMPLES = 20
MATURE_SNAPSHOT_WINDOWS = ("24h", "7d", "28d")
# A leading group of videos is a pattern worth imitating only in a cohort this
# large, and only when its median beats the rest's by this share. Five videos
# used to put the top three, and their tags, into the writer's prompt however
# little separated them from the others.
LEADING_GROUP_SIZE = 3
PATTERN_MIN_SAMPLES = 10
PATTERN_MIN_MARGIN = 0.25


@dataclass(frozen=True)
class EvidenceLevel:
    key: str
    label: str
    minimum_samples: int
    learning_allowed: bool


def evidence_level(sample_size: int) -> EvidenceLevel:
    sample = max(0, int(sample_size or 0))
    if sample >= STRONG_EVIDENCE_MIN_SAMPLES:
        return EvidenceLevel(
            "strong_evidence", "Strong historical pattern", STRONG_EVIDENCE_MIN_SAMPLES, True
        )
    if sample >= MODERATE_EVIDENCE_MIN_SAMPLES:
        return EvidenceLevel(
            "moderate_evidence", "Moderate evidence", MODERATE_EVIDENCE_MIN_SAMPLES, True
        )
    if sample >= EARLY_SIGNAL_MIN_SAMPLES:
        return EvidenceLevel(
            "early_signal", "Early signal", EARLY_SIGNAL_MIN_SAMPLES, True
        )
    return EvidenceLevel(
        "display_only", "Collecting evidence", EARLY_SIGNAL_MIN_SAMPLES, False
    )


def verified_ownership(link: dict[str, Any]) -> bool:
    return bool(
        link.get("ownership_state") == "verified"
        and link.get("ownership_verified")
        and str(link.get("verified_channel_id") or "").strip()
        and str(link.get("ownership_verified_at") or "").strip()
    )


def mature_snapshot(snapshot: dict[str, Any] | None, expected_window: str | None = None) -> bool:
    if not snapshot:
        return False
    window = str(snapshot.get("snapshot_window") or "")
    if window not in MATURE_SNAPSHOT_WINDOWS:
        return False
    if expected_window and window != expected_window:
        return False
    return bool(
        snapshot.get("snapshot_status") == "complete"
        and snapshot.get("completed_at")
        and snapshot.get("views") is not None
    )


def comparable_metadata(link: dict[str, Any]) -> bool:
    # "unknown" is the stored placeholder for a missing label, not a cohort of its own.
    return all(str(link.get(field) or "").strip() not in {"", "unknown"} for field in ("format", "language"))


def sample_is_eligible(
    link: dict[str, Any],
    snapshot: dict[str, Any] | None,
    *,
    expected_window: str,
) -> bool:
    return bool(
        verified_ownership(link)
        and comparable_metadata(link)
        and mature_snapshot(snapshot, expected_window)
    )


def _median(values: list[float]) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    return float(ordered[middle]) if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0


def pattern_signal(outcomes: list[float], *, comparable: bool, measure: str = "views per day") -> dict[str, Any]:
    """Whether the leading videos stand apart from the rest by more than noise.

    ``outcomes`` are a cohort's outcomes, best first. The leading three are a
    pattern only when the cohort is comparable (one format and one language),
    has PATTERN_MIN_SAMPLES videos, and their median beats the rest's by
    PATTERN_MIN_MARGIN. A channel whose Shorts all sit within 12% of each
    other has no leading group, however its top three happen to be ordered.
    """
    leading, rest = outcomes[:LEADING_GROUP_SIZE], outcomes[LEADING_GROUP_SIZE:]
    leading_median, rest_median = _median(leading), _median(rest)
    margin = round(leading_median / rest_median - 1.0, 3) if leading_median is not None and rest_median else None
    # A rest with a median of 0 has no ratio to beat; any lead over it is one.
    leads_an_empty_rest = rest_median == 0 and bool(leading_median)
    signal: dict[str, Any] = {
        "sample_size": len(outcomes), "measure": measure, "leading_median": leading_median,
        "rest_median": rest_median, "margin": margin,
        "minimum_samples": PATTERN_MIN_SAMPLES, "minimum_margin": PATTERN_MIN_MARGIN,
    }
    if not comparable:
        status, reason = "mixed_cohort", (
            "a mixed cohort: the linked videos span more than one format or language, so their outcomes are not compared."
        )
    elif len(outcomes) < PATTERN_MIN_SAMPLES:
        status, reason = "insufficient_sample", (
            f"a leading group needs {PATTERN_MIN_SAMPLES} comparable videos to stand apart from noise; "
            f"there are {len(outcomes)}."
        )
    elif leads_an_empty_rest:
        status, reason = "pattern", (
            f"the leading three videos' median {measure} ({leading_median:,.0f}) beats the rest's (0)."
        )
    elif margin is None or margin < PATTERN_MIN_MARGIN:
        status, reason = "no_pattern", (
            f"the leading three videos' median {measure} ({leading_median:,.0f}) is within "
            f"{PATTERN_MIN_MARGIN:.0%} of the rest's ({rest_median:,.0f}), a spread noise explains."
        )
    else:
        status, reason = "pattern", (
            f"the leading three videos' median {measure} ({leading_median:,.0f}) beats the rest's "
            f"({rest_median:,.0f}) by {margin:.0%}."
        )
    return {**signal, "status": status, "reason": reason}


def confidence_payload(sample_size: int) -> dict[str, Any]:
    level = evidence_level(sample_size)
    return {
        "evidence_level": level.key,
        "confidence_label": level.label,
        "learning_allowed": level.learning_allowed,
        "next_threshold": (
            None
            if level.key == "strong_evidence"
            else STRONG_EVIDENCE_MIN_SAMPLES
            if level.key == "moderate_evidence"
            else MODERATE_EVIDENCE_MIN_SAMPLES
            if level.key == "early_signal"
            else EARLY_SIGNAL_MIN_SAMPLES
        ),
    }
