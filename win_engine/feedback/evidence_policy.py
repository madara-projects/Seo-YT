"""Single source of truth for mature, comparable personal learning evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


EARLY_SIGNAL_MIN_SAMPLES = 5
MODERATE_EVIDENCE_MIN_SAMPLES = 10
STRONG_EVIDENCE_MIN_SAMPLES = 20
MATURE_SNAPSHOT_WINDOWS = ("24h", "7d", "28d")


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
    return bool(str(link.get("format") or "").strip() and str(link.get("language") or "").strip())


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
