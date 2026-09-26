from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from win_engine.analysis.source_cues import format_key
from win_engine.analysis.text_tokens import unicode_words
from win_engine.feedback.migrations import (
    connect_managed,
    initialize_memory_database,
    prepare_database,
)
from win_engine.feedback.evidence_policy import (
    EARLY_SIGNAL_MIN_SAMPLES, confidence_payload, mature_snapshot, sample_is_eligible,
)

logger = logging.getLogger(__name__)
_INITIALIZED_DATABASES: set[str] = set()
_INITIALIZATION_LOCK = Lock()
# A database that failed to prepare is retried at most this often, not on
# every request: each attempt can take a full backup before migrating.
_PREPARE_RETRY_SECONDS = 60.0
_PREPARE_FAILURES: dict[str, tuple[float, str]] = {}
_SCHEDULED_WINDOWS = {"24h", "7d", "28d"}
# Each scheduled window and the hours after publication it covers.
SNAPSHOT_WINDOWS = (("24h", 24.0), ("7d", 168.0), ("28d", 672.0))
_MAX_SNAPSHOT_ATTEMPTS = 5
_SNAPSHOT_COLUMNS = (
    "age_hours", "views", "watch_time_minutes", "avg_view_duration_seconds",
    "avg_view_percentage", "likes", "comments", "shares", "subscribers_gained",
    "impressions", "impressions_ctr", "snapshot_window", "captured_at",
    "snapshot_status", "attempt_count", "last_failure_reason",
    "last_attempted_at", "completed_at", "source_start_date", "source_end_date", "youtube_video_id",
)
COMPARABLE_FIELDS = ("language", "format", "duration_bucket", "topic_category")
# The stored spelling of each format. Cohorts group by exact values, so every
# writer stores this spelling and every reader compares it (comparable_format).
FORMAT_VALUES = {
    "youtube_shorts",
    "long_form",
    "talking_head",
    "tutorial",
    "vlog",
    "review",
    "quote",
    "story",
    "challenge",
    "other",
    "unknown",
}
# A "long_form" filter selects every known format that is not a Short; a quote
# video is a Short here (see retention_assistant).
_LONG_FORM_VALUES = frozenset(FORMAT_VALUES - {"youtube_shorts", "quote", "unknown"})
# YouTube Analytics reports whole days in Pacific time, up to yesterday.
ANALYTICS_ZONE = ZoneInfo("America/Los_Angeles")
# evidence_policy.sample_is_eligible in SQL, for links `p`, their comparable
# metadata `m` and a completed snapshot `x`; keep them in step.
_VERIFIED_LINK_SQL = """p.ownership_state = 'verified' AND p.ownership_verified = 1
    AND TRIM(COALESCE(p.verified_channel_id, '')) != '' AND TRIM(COALESCE(p.ownership_verified_at, '')) != ''"""
_COMPARABLE_LABELS_SQL = "TRIM(m.format) NOT IN ('', 'unknown') AND TRIM(m.language) NOT IN ('', 'unknown')"
_MATURE_SNAPSHOT_SQL = "x.snapshot_status = 'complete' AND COALESCE(x.completed_at, '') != '' AND x.views IS NOT NULL"
DURATION_VALUES ={"under_60s", "60_to_180s", "3_to_10m", "over_10m", "unknown"}
IDEA_STATUSES = {"idea", "scripted", "package_generated", "published", "archived"}
IDEA_CREATOR_FIELDS = {
    "topic", "notes", "format", "language", "region", "visual_or_background",
    "on_screen_text", "target_duration_seconds", "emotion_or_intent",
    "search_angle", "browse_angle", "audience_angle", "status",
}


class DatabaseUnavailable(RuntimeError):
    """The database could not be prepared; requests fail fast until the next retry."""


class RelinkWouldDeleteEvidence(ValueError):
    """Relinking a package would delete evidence collected for its current video."""

    def __init__(self, youtube_video_id: str, evidence: dict[str, int]) -> None:
        described = ", ".join(f"{count} {label}" for label, count in evidence.items() if count)
        super().__init__(
            f"This package is linked to {youtube_video_id}, which has collected evidence ({described}). "
            "Linking another video deletes that evidence. Confirm the replacement to continue."
        )
        self.youtube_video_id = youtube_video_id
        self.evidence = evidence


class HistoryStore:
    """SQLite-backed snapshot store for repeated video metric collection."""

    def __init__(self, database_path: str) -> None:
        self._database_path_raw = database_path
        self._database_path = Path(database_path) if database_path != ":memory:" else None
        self._memory_connection: sqlite3.Connection | None = None
        if database_path == ":memory:":
            self._memory_connection = sqlite3.connect(":memory:", check_same_thread=False)
            initialize_memory_database(self._memory_connection)
        else:
            database_key = str(self._database_path.resolve()) if self._database_path else database_path
            if database_key not in _INITIALIZED_DATABASES:
                with _INITIALIZATION_LOCK:
                    if database_key not in _INITIALIZED_DATABASES:
                        self._prepare(database_key)

    def _prepare(self, database_key: str) -> None:
        failure = _PREPARE_FAILURES.get(database_key)
        if failure and time.monotonic() - failure[0] < _PREPARE_RETRY_SECONDS:
            raise DatabaseUnavailable(f"The database could not be prepared ({failure[1]}). It will be retried shortly.")
        try:
            prepare_database(self._database_path_raw)
        except Exception as exc:
            _PREPARE_FAILURES[database_key] = (time.monotonic(), type(exc).__name__)
            # The first failure is reported like the ones after it (a 503), so
            # its reason is logged here.
            logger.error("The database could not be prepared: %s: %s", type(exc).__name__, exc)
            raise DatabaseUnavailable(
                f"The database could not be prepared ({type(exc).__name__}). It will be retried shortly."
            ) from exc
        _PREPARE_FAILURES.pop(database_key, None)
        _INITIALIZED_DATABASES.add(database_key)

    @property
    def database_path(self) -> str:
        return self._database_path_raw

    def _connect(self) -> sqlite3.Connection:
        if self._memory_connection is not None:
            return self._memory_connection
        if self._database_path is None:
            raise RuntimeError("Database path is unavailable.")
        return connect_managed(str(self._database_path), timeout=10)

    def record_snapshots(self, query: str, youtube_results: list[dict[str, Any]]) -> None:
        captured_at = datetime.now(timezone.utc).isoformat()
        # A count YouTube did not report (hidden, or a failed lookup) stays
        # unknown, and each row keeps the time its statistics were fetched.
        rows = [
            (
                result.get("video_id"),
                str(result.get("research_query") or query),
                result.get("captured_at") or captured_at,
                result.get("published_at"),
                _optional_int(result.get("view_count")),
                _optional_int(result.get("like_count")),
                _optional_int(result.get("comment_count")),
                _optional_int(result.get("subscriber_count")),
            )
            for result in youtube_results
            if result.get("video_id")
        ]

        if not rows:
            return

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO video_snapshots (
                    video_id, query, captured_at, published_at, view_count,
                    like_count, comment_count, subscriber_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def record_analysis_run(
        self,
        query: str,
        intent: str,
        content_angle: str,
        title: str,
        title_score: float,
        retention_risk: str,
        opportunity_label: str,
        opportunity_score: float,
        payload: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO analysis_runs (
                    query, created_at, intent, content_angle, title,
                    title_score, retention_risk, opportunity_label, opportunity_score, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query,
                    datetime.now(timezone.utc).isoformat(),
                    intent,
                    content_angle,
                    title,
                    title_score,
                    retention_risk,
                    opportunity_label,
                    opportunity_score,
                    json.dumps(payload) if payload is not None else None,
                ),
            )
        return int(cursor.lastrowid)

    def update_analysis_payload(
        self, run_id: int, title: str, payload: dict[str, Any], title_score: float | None = None
    ) -> None:
        """Replace an intermediate package with the exact final API response.

        Refinement can change the title, so its score is replaced with it.
        """
        with self._connect() as connection:
            connection.execute(
                "UPDATE analysis_runs SET title = ?, payload_json = ?, title_score = COALESCE(?, title_score) WHERE id = ?",
                (title, json.dumps(payload), title_score, run_id),
            )

    # --- Stage G1: Idea backlog and topic opportunity workspace ---

    def create_content_idea(self, values: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        status = str(values.get("status") or "idea")
        if status not in IDEA_STATUSES:
            raise ValueError("Unknown idea status.")
        if status in {"package_generated", "published"}:
            raise ValueError("A new idea cannot skip its generated-package and verified-publication lifecycle.")
        topic = str(values.get("topic") or "").strip()
        if not topic:
            raise ValueError("Idea topic is required.")
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO content_ideas (
                       topic, notes, format, language, region, visual_or_background,
                       on_screen_text, target_duration_seconds, emotion_or_intent,
                       search_angle, browse_angle, audience_angle, evidence_json,
                       status, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?)""",
                (
                    topic, values.get("notes") or "", values.get("format") or "unknown",
                    values.get("language") or "english", values.get("region") or "global",
                    values.get("visual_or_background") or "", values.get("on_screen_text") or "",
                    values.get("target_duration_seconds"), values.get("emotion_or_intent") or "",
                    values.get("search_angle") or "", values.get("browse_angle") or "",
                    values.get("audience_angle") or "", status, now, now,
                ),
            )
            idea_id = int(cursor.lastrowid)
        return self.content_idea(idea_id) or {}

    def content_ideas(self, *, status: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        if status and status not in IDEA_STATUSES:
            raise ValueError("Unknown idea status filter.")
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        where = "WHERE i.status = ?" if status else ""
        params: tuple[Any, ...] = (status,) if status else ()
        with self._connect() as connection:
            total = int(connection.execute(f"SELECT COUNT(*) FROM content_ideas i {where}", params).fetchone()[0])
            # The list needs two fields of the evidence, not the whole document.
            rows = connection.execute(
                f"""SELECT i.id, i.topic, i.status, i.format, i.language, i.region,
                           i.created_at, i.updated_at, i.analysis_run_id, i.published_video_link_id,
                           CASE WHEN json_valid(i.evidence_json) THEN json_extract(i.evidence_json, '$.opportunity_explanation') END,
                           CASE WHEN json_valid(i.evidence_json) THEN json_extract(i.evidence_json, '$.personal_evidence.status') END,
                           (SELECT MAX(s.captured_at) FROM content_idea_research_snapshots s
                            WHERE s.content_idea_id = i.id),
                           (SELECT COUNT(*) FROM content_idea_research_snapshots s
                            WHERE s.content_idea_id = i.id)
                    FROM content_ideas i {where}
                    ORDER BY i.created_at DESC, i.id DESC LIMIT ? OFFSET ?""",
                (*params, safe_limit, safe_offset),
            ).fetchall()
        ideas = []
        for row in rows:
            ideas.append({
                "id": row[0], "topic": row[1], "status": row[2], "format": row[3],
                "language": row[4], "region": row[5], "created_at": row[6], "updated_at": row[7],
                "analysis_run_id": row[8], "published_video_link_id": row[9],
                "last_researched_at": row[12], "research_snapshot_count": int(row[13] or 0),
                "opportunity_explanation": row[10] if isinstance(row[10], str) and row[10] else "Research has not been run for this idea.",
                "personal_evidence_status": row[11] if isinstance(row[11], str) and row[11] else "insufficient_evidence",
            })
        return {"ideas": ideas, "total": total, "limit": safe_limit, "offset": safe_offset, "status": status}

    def content_idea(self, idea_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id, topic, notes, format, language, region, visual_or_background,
                          on_screen_text, target_duration_seconds, emotion_or_intent,
                          search_angle, browse_angle, audience_angle, evidence_json, status,
                          analysis_run_id, published_video_link_id, created_at, updated_at
                   FROM content_ideas WHERE id = ?""",
                (idea_id,),
            ).fetchone()
            if not row:
                return None
            snapshots = connection.execute(
                """SELECT id, captured_at, evidence_json FROM content_idea_research_snapshots
                   WHERE content_idea_id = ? ORDER BY captured_at DESC, id DESC LIMIT 20""",
                (idea_id,),
            ).fetchall()
            demand_rows = connection.execute(
                """SELECT id, classification, evidence_json, captured_at, idea_fingerprint
                   FROM demand_research_snapshots WHERE idea_id = ? ORDER BY captured_at DESC, id DESC LIMIT 20""",
                (idea_id,),
            ).fetchall()
        keys = (
            "id", "topic", "notes", "format", "language", "region", "visual_or_background",
            "on_screen_text", "target_duration_seconds", "emotion_or_intent", "search_angle",
            "browse_angle", "audience_angle", "evidence", "status", "analysis_run_id",
            "published_video_link_id", "created_at", "updated_at",
        )
        result = dict(zip(keys, row, strict=True))
        result["evidence"] = _json_value(row[13])
        result["research_snapshots"] = [
            {"id": item[0], "captured_at": item[1], "evidence": _json_value(item[2])}
            for item in snapshots
        ]
        result["latest_research"] = result["research_snapshots"][0] if result["evidence"] and result["research_snapshots"] else None
        result["research_is_stale"] = bool(result["research_snapshots"] and not result["evidence"])
        from win_engine.analysis.demand_explorer import idea_fingerprint
        current_fingerprint = idea_fingerprint(result)
        result["demand_research"] = [
            {"id": row[0], "classification": row[1], "evidence": _json_value(row[2]),
             "captured_at": row[3], "stale": row[4] != current_fingerprint}
            for row in demand_rows
        ]
        result["latest_demand_research"] = result["demand_research"][0] if result["demand_research"] else None
        return result

    def update_content_idea(self, idea_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
        unknown = set(changes) - IDEA_CREATOR_FIELDS
        if unknown:
            raise ValueError("Unsupported idea field(s): " + ", ".join(sorted(unknown)))
        if not changes:
            raise ValueError("Provide at least one idea field to update.")
        if any(value is None for value in changes.values()):
            raise ValueError("Idea fields cannot be set to null.")
        status = changes.get("status")
        if status is not None and status not in IDEA_STATUSES:
            raise ValueError("Unknown idea status.")
        if "topic" in changes and not str(changes["topic"]).strip():
            raise ValueError("Idea topic is required.")
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT analysis_run_id, published_video_link_id FROM content_ideas WHERE id = ?", (idea_id,)
            ).fetchone()
            if not existing:
                return None
            if status == "package_generated" and not existing[0]:
                raise ValueError("Generate a package before setting package_generated status.")
            if status == "published" and not existing[1]:
                raise ValueError("Link the generated package to an owned YouTube video before marking this idea published.")
            assignments = [f"{field} = ?" for field in changes]
            research_inputs_changed = bool(set(changes) - {"status"})
            if research_inputs_changed:
                assignments.append("evidence_json = '{}'")
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                f"UPDATE content_ideas SET {', '.join(assignments)}, updated_at = ? WHERE id = ?",
                (*changes.values(), now, idea_id),
            )
        return self.content_idea(idea_id)

    def save_content_idea_research(self, idea_id: int, evidence: dict[str, Any]) -> dict[str, Any] | None:
        captured_at = str(evidence.get("captured_at") or datetime.now(timezone.utc).isoformat())
        serialized = json.dumps(evidence)
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM content_ideas WHERE id = ?", (idea_id,)).fetchone():
                return None
            cursor = connection.execute(
                "INSERT INTO content_idea_research_snapshots (content_idea_id, captured_at, evidence_json) VALUES (?, ?, ?)",
                (idea_id, captured_at, serialized),
            )
            connection.execute(
                "UPDATE content_ideas SET evidence_json = ?, updated_at = ? WHERE id = ?",
                (serialized, captured_at, idea_id),
            )
            snapshot_id = int(cursor.lastrowid)
        return {"id": snapshot_id, "content_idea_id": idea_id, "captured_at": captured_at, "evidence": evidence}

    def attach_content_idea_analysis(self, idea_id: int, analysis_run_id: int) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM analysis_runs WHERE id = ?", (analysis_run_id,)).fetchone():
                raise ValueError("Generated analysis run does not exist.")
            cursor = connection.execute(
                """UPDATE content_ideas SET analysis_run_id = ?, status = 'package_generated', updated_at = ?
                   WHERE id = ?""",
                (analysis_run_id, now, idea_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.content_idea(idea_id)

    def history_run_count(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0])

    def history_runs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Return saved packages in newest-first order without the large payload."""
        with self._connect() as connection:
            # analysis_run_id is unique in both joined tables, so plain joins
            # match at most one row each.
            rows = connection.execute(
                """
                SELECT a.id, a.created_at, a.title, a.opportunity_score, a.title_score,
                       a.query, a.payload_json IS NOT NULL, p.id, p.youtube_video_id,
                       ps.generated_package_id, ps.selected_at, a.content_angle, a.intent
                FROM analysis_runs a
                LEFT JOIN analysis_package_selections ps ON ps.analysis_run_id = a.id
                LEFT JOIN published_video_links p ON p.analysis_run_id = a.id
                ORDER BY a.created_at DESC, a.id DESC LIMIT ? OFFSET ?
                """
                , (max(1, min(limit, 100)), max(0, offset))
            ).fetchall()
        return [
            {
                "id": row[0], "created_at": row[1], "title": row[2],
                "opportunity_score": _rounded(row[3]),
                "title_score": _rounded(row[4]), "query": row[5],
                "has_full_package": bool(row[6]),
                "linked_video_link_id": row[7],
                "linked_youtube_video_id": row[8],
                "selected_package_id": row[9],
                "package_selected_at": row[10],
                # Shown on each row and searched, as the legacy list always expected.
                "content_angle": row[11],
                "intent": row[12],
            }
            for row in rows
        ]

    def recent_generated_titles(self, limit: int = 10) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT title FROM analysis_runs
                   WHERE title IS NOT NULL AND TRIM(title) != ''
                   ORDER BY created_at DESC LIMIT ?""",
                (max(1, min(limit, 50)),),
            ).fetchall()
        return [str(row[0]).strip() for row in rows if row[0] and str(row[0]).strip()]

    def recent_published_titles(self, limit: int = 10) -> list[str]:
        """Return observed uploaded titles without inferring package selection."""
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT COALESCE(json_extract(youtube_metadata_json, '$.title'), selected_title)
                   FROM published_video_links
                   WHERE COALESCE(json_extract(youtube_metadata_json, '$.title'), selected_title) IS NOT NULL
                   ORDER BY updated_at DESC LIMIT ?""",
                (max(1, min(limit, 50)),),
            ).fetchall()
        return [str(row[0]).strip() for row in rows if row[0] and str(row[0]).strip()]

    def retention_learning_summary(
        self,
        *,
        format_filter: str | None = None,
        language_filter: str | None = None,
        snapshot_window: str = "24h",
    ) -> dict[str, Any]:
        """Derive cautious retention correlations from eligible Phase 5 History only."""
        if snapshot_window not in _SCHEDULED_WINDOWS:
            raise ValueError("Retention learning requires a 24h, 7d, or 28d evidence window.")
        # One pass over three queries: this runs inside every generation, and
        # loading each package (tens of kilobytes) per link does not scale.
        snapshots = {
            item["youtube_video_id"]: item
            for item in self._snapshots(
                "snapshot_window = ? AND snapshot_status = 'complete'", (snapshot_window,), "captured_at ASC, id ASC"
            )
        }
        with self._connect() as connection:
            run_rows = connection.execute(
                """SELECT a.id,
                          CASE WHEN json_valid(a.payload_json) THEN json_extract(a.payload_json, '$.retention_assistant') END,
                          s.generated_package_id
                   FROM analysis_runs a
                   JOIN published_video_links p ON p.analysis_run_id = a.id
                   LEFT JOIN analysis_package_selections s ON s.analysis_run_id = a.id"""
            ).fetchall()
        runs = {int(row[0]): (_json_value(row[1]), row[2]) for row in run_rows}
        formats = format_filter_values(format_filter)
        language_filter = known_filter(language_filter)
        eligible: list[dict[str, Any]] = []
        for link in self.published_video_links_list():
            comparable = link.get("comparable_metadata") if isinstance(link.get("comparable_metadata"), dict) else {}
            effective_format = comparable_format(comparable.get("format") or link.get("format")) or "unknown"
            effective_language = str(comparable.get("language") or link.get("language") or "unknown")
            if formats is not None and effective_format not in formats:
                continue
            if language_filter and effective_language != language_filter:
                continue
            snapshot = snapshots.get(str(link.get("youtube_video_id") or ""))
            policy_link = dict(link)
            policy_link["format"] = effective_format
            policy_link["language"] = effective_language
            if not sample_is_eligible(policy_link, snapshot, expected_window=snapshot_window):
                continue
            retention = _optional_number((snapshot or {}).get("avg_view_percentage"))
            if retention is None:
                continue
            assistant, selected_package_id = runs.get(int(link.get("analysis_run_id") or 0), ({}, None))
            if assistant.get("rule_version") != "phase5-v1":
                continue
            opening = assistant.get("opening") if isinstance(assistant.get("opening"), dict) else {}
            pacing = assistant.get("pacing") if isinstance(assistant.get("pacing"), dict) else {}
            quote = assistant.get("quote_presentation") if isinstance(assistant.get("quote_presentation"), dict) else {}
            hook_structure = (
                "generic_setup" if opening.get("generic_setup") else
                "subject_clear" if opening.get("clarity") == "clear" else "subject_needs_review"
            )
            quote_structure = "quote_present" if quote.get("status") == "available" else "no_exact_quote"
            eligible.append({
                "analysis_run_id": link.get("analysis_run_id"),
                "youtube_video_id": link.get("youtube_video_id"),
                "selected_package_id": selected_package_id,
                "hook_structure": hook_structure,
                "pacing_structure": str(pacing.get("format_assessment") or "unknown"),
                "quote_structure": quote_structure,
                "average_view_percentage": retention,
            })
        sample_size = len(eligible)
        policy = confidence_payload(sample_size)
        if not policy["learning_allowed"]:
            return {
                "status": "insufficient_evidence", "learning_allowed": False,
                "sample_size": sample_size, "minimum_samples": EARLY_SIGNAL_MIN_SAMPLES,
                "confidence_label": policy["confidence_label"],
                "snapshot_window": snapshot_window, "patterns": [],
                "retention_curve_status": "unavailable",
                "message": (
                    f"Only {sample_size} verified comparable Phase 5 video(s) have completed {snapshot_window} "
                    f"retention evidence; at least {EARLY_SIGNAL_MIN_SAMPLES} are required before surfacing correlations."
                ),
            }
        patterns: list[dict[str, Any]] = []
        for feature in ("hook_structure", "pacing_structure", "quote_structure"):
            groups: dict[str, list[float]] = {}
            for item in eligible:
                groups.setdefault(str(item[feature]), []).append(float(item["average_view_percentage"]))
            for value, measurements in groups.items():
                patterns.append({
                    "feature": feature, "value": value, "sample_size": len(measurements),
                    "median_average_viewed_percentage": _median(sorted(measurements)),
                    "observation": (
                        f"In {len(measurements)} eligible creator video(s), {feature.replace('_', ' ')} "
                        f"'{value}' has a median average viewed value of {_median(sorted(measurements)):.1f}%."
                    ),
                    "interpretation": "observed_correlation_not_causation",
                    "provenance": "verified_completed_youtube_analytics_snapshot",
                })
        patterns.sort(key=lambda item: (-int(item["sample_size"]), -float(item["median_average_viewed_percentage"] or 0)))
        return {
            "status": "observed_correlations", "learning_allowed": True,
            "sample_size": sample_size, "minimum_samples": EARLY_SIGNAL_MIN_SAMPLES,
            "confidence_label": policy["confidence_label"],
            "snapshot_window": snapshot_window, "patterns": patterns,
            "retention_curve_status": "unavailable",
            "message": (
                "Eligible creator-history correlations are available. YouTube average viewed data does not "
                "identify a causal hook effect or exact drop timestamp."
            ),
        }

    def package_selection(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT s.generated_package_id, s.package_json, s.quality_gate_json,
                          s.selection_source, s.selected_at, s.updated_at, p.id, p.youtube_video_id
                   FROM analysis_package_selections s
                   LEFT JOIN published_video_links p ON p.analysis_run_id = s.analysis_run_id
                   WHERE s.analysis_run_id = ?""",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "analysis_run_id": run_id, "generated_package_id": row[0],
            "package": _json_object(row[1]), "quality_gate": _json_object(row[2]),
            "selection_source": row[3], "selected_at": row[4], "updated_at": row[5],
            "linked_video_link_id": row[6], "linked_youtube_video_id": row[7],
            "later_associated_with_video": bool(row[7]),
        }

    def select_generated_package(self, run_id: int, package_id: str) -> dict[str, Any] | None:
        """Persist a server-known generated package; client metadata is never trusted."""
        run = self.history_run(run_id)
        if not run:
            return None
        payload = run.get("package") if isinstance(run.get("package"), dict) else {}
        match: dict[str, Any] | None = None
        for index, candidate in enumerate(payload.get("title_thumbnail_packages") or []):
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(candidate.get("package_id") or f"package-{chr(97 + index)}")
            if candidate_id == package_id:
                match = dict(candidate)
                match["package_id"] = candidate_id
                break
        if match is None:
            raise ValueError("The selected package is not part of this saved generation run.")
        for field in ("description", "tags", "hashtags", "selected_language"):
            if field in payload:
                match[field] = payload[field]
        assistant = payload.get("retention_assistant") if isinstance(payload.get("retention_assistant"), dict) else {}
        matching_alignment = next(
            (
                item for item in (assistant.get("package_alignment") or [])
                if isinstance(item, dict) and str(item.get("package_id")) == package_id
            ),
            None,
        )
        if assistant:
            match["retention_trace"] = {
                "rule_version": assistant.get("rule_version"),
                "risk_level": assistant.get("risk_level"),
                "package_alignment": matching_alignment,
                "evidence_status": (assistant.get("retention_learning") or {}).get("status"),
            }
        gate = match.get("quality_gate") or payload.get("generation_quality") or {}
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO analysis_package_selections
                       (analysis_run_id, generated_package_id, package_json, quality_gate_json,
                        selection_source, selected_at, updated_at)
                   VALUES (?, ?, ?, ?, 'creator', ?, ?)
                   ON CONFLICT(analysis_run_id) DO UPDATE SET
                       generated_package_id = excluded.generated_package_id,
                       package_json = excluded.package_json,
                       quality_gate_json = excluded.quality_gate_json,
                       selection_source = 'creator', updated_at = excluded.updated_at""",
                (run_id, package_id, json.dumps(match), json.dumps(gate), now, now),
            )
        return self.package_selection(run_id)

    def history_run(self, run_id: int) -> dict[str, Any] | None:
        """Return a saved SEO package and its historical metadata."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, created_at, query, intent, content_angle, title, title_score,
                       retention_risk, opportunity_label, opportunity_score, payload_json
                FROM analysis_runs WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if not row:
            return None
        try:
            package = json.loads(row[10]) if row[10] else None
        except json.JSONDecodeError:
            package = None
        stored_query = str(row[2] or "")
        creator_content = ""
        if isinstance(package, dict):
            brief = package.get("creator_brief")
            if isinstance(brief, dict):
                creator_content = str(brief.get("content") or "")
        # Older builds stored only the first 120 characters in `query`. The
        # complete creator input is still present in the saved package, so use
        # it for History detail without rewriting or changing that package.
        full_query = creator_content if len(creator_content) > len(stored_query) else stored_query
        result = {
            "id": row[0], "created_at": row[1], "query": full_query, "intent": row[3],
            "content_angle": row[4], "title": row[5], "title_score": _rounded(row[6]),
            "retention_risk": row[7], "opportunity_label": row[8],
            "opportunity_score": _rounded(row[9]), "package": package,
        }
        result["selected_package"] = self.package_selection(run_id)
        return result

    def delete_analysis_run(self, run_id: int) -> bool:
        """Atomically delete a package and queue its cloud tombstone, or roll back all."""
        return bool(self.delete_analysis_runs([run_id]))

    def delete_analysis_runs(self, run_ids: list[int]) -> list[int]:
        """Atomically delete several packages and queue one durable tombstone per synced package."""

        ids = list(dict.fromkeys(int(run_id) for run_id in run_ids if int(run_id) > 0))
        if not ids:
            return []
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            now = datetime.now(timezone.utc).isoformat()
            placeholders = ",".join("?" for _ in ids)
            existing = {
                int(row[0]) for row in connection.execute(
                    f"SELECT id FROM analysis_runs WHERE id IN ({placeholders})", ids
                ).fetchall()
            }
            if existing != set(ids):
                return []
            for run_id in ids:
                mapping = connection.execute(
                    """SELECT sync_uuid, origin_device_id, revision
                       FROM cloud_sync_packages WHERE analysis_run_id = ?""", (run_id,),
                ).fetchone()
                if mapping:
                    connection.execute(
                        """INSERT INTO cloud_sync_tombstones
                               (sync_uuid, origin_device_id, revision, deleted_at, pending,
                                attempt_count, last_attempted_at, last_error)
                           VALUES (?, ?, ?, ?, 1, 0, NULL, NULL)
                           ON CONFLICT(sync_uuid) DO UPDATE SET
                               revision = MAX(cloud_sync_tombstones.revision, excluded.revision),
                               deleted_at = excluded.deleted_at, pending = 1, attempt_count = 0,
                               last_attempted_at = NULL, last_error = NULL""",
                        (str(mapping[0]), str(mapping[1]), int(mapping[2]) + 1, now),
                    )
                connection.execute(
                    """UPDATE content_ideas SET analysis_run_id = NULL, published_video_link_id = NULL,
                              status = CASE WHEN status IN ('package_generated', 'published') THEN 'scripted' ELSE status END,
                              updated_at = ? WHERE analysis_run_id = ?""", (now, run_id),
                )
            # Foreign keys are enforced on every statement, so a DELETE that
            # would orphan a row fails by itself and rolls the batch back.
            connection.execute(f"DELETE FROM analysis_runs WHERE id IN ({placeholders})", ids)
            return ids

    def latest_channel_sync(self, channel_id: str) -> dict[str, Any] | None:
        """The newest readable sync of this channel, as {"synced_at", "data"}.

        A sync describes one channel, so another channel's sync, or one taken
        before a disconnect, is never presented as current.
        """
        if not channel_id:
            return None
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, synced_at, payload_json FROM youtube_channel_syncs ORDER BY id DESC LIMIT 50"
            ).fetchall()
        for sync_id, synced_at, payload_json in rows:
            try:
                payload = json.loads(payload_json)
            except (TypeError, ValueError):
                payload = None
            if not isinstance(payload, dict) or not isinstance(payload.get("channel") or {}, dict):
                logger.warning("Skipping unreadable channel sync %s.", sync_id)
                continue
            if (payload.get("channel") or {}).get("id") == channel_id:
                return {"synced_at": synced_at, "data": payload}
        return None

    def owned_performance_summary(self) -> dict[str, Any]:
        """The connected channel's latest sync, its uploads, and linked-video totals.

        Every number is None when it was not measured: lifetime views of recent
        uploads are never presented as 28-day views, and no zero is invented.
        """
        with self._connect() as connection:
            ch_row = connection.execute(
                "SELECT channel_id, channel_title, connected_at FROM youtube_channel_connection WHERE id = 1"
            ).fetchone()
        channel_info = {"id": ch_row[0], "title": ch_row[1], "connected_at": ch_row[2]} if ch_row else None
        sync = self.latest_channel_sync(str(ch_row[0] or "")) if ch_row else None
        sync_info = None
        if sync:
            payload = sync["data"]
            sync_info = {
                "synced_at": sync["synced_at"],
                "channel": payload.get("channel") or {},
                "period": payload.get("period") or {},
                "current_28_days": payload.get("current_28_days") or {},
                "timezone": payload.get("timezone") or (payload.get("channel") or {}).get("timezone"),
                "audience_activity": payload.get("audience_activity") or {},
                "partial_failures": payload.get("partial_failures") or [],
            }

        with self._connect() as connection:
            # The connected channel's uploads only: a channel connected before
            # left its own, and none are shown without a connection.
            channel_id = str(ch_row[0] or "") if ch_row else ""
            latest = connection.execute(
                """
                SELECT s.video_id, s.title, s.views, s.likes, s.captured_at, s.published_at,
                       s.watch_minutes, s.comments, s.average_view_percentage
                FROM owned_video_snapshots s
                INNER JOIN (
                    SELECT video_id, MAX(captured_at) AS max_cap
                    FROM owned_video_snapshots
                    WHERE channel_id = ?
                    GROUP BY video_id
                ) latest ON s.video_id = latest.video_id AND s.captured_at = latest.max_cap
                WHERE s.channel_id = ?
                ORDER BY COALESCE(s.published_at, '') DESC, s.video_id ASC
                """,
                (channel_id, channel_id),
            ).fetchall()

            # Snapshots are cumulative (24h, 7d, 28d, current), so each linked
            # video counts once, at its highest recorded value. Summing every
            # snapshot counted the same watch time once per snapshot.
            linked_row = connection.execute(
                """
                SELECT COUNT(*), COUNT(best_watch), SUM(best_watch)
                FROM (
                    SELECT l.youtube_video_id, MAX(s.watch_time_minutes) AS best_watch
                    FROM published_video_links l
                    LEFT JOIN video_performance_snapshots s ON l.youtube_video_id = s.youtube_video_id
                    GROUP BY l.youtube_video_id
                )
                """
            ).fetchone()

        measured_views = [int(r[2]) for r in latest if r[2] is not None]
        sync_channel = sync_info["channel"] if sync_info else {}
        analytics = sync_info["current_28_days"] if sync_info else {}
        views_28_days = _optional_int(analytics.get("views"))
        likes_28_days = _optional_int(analytics.get("likes"))
        linked_count, linked_with_watch, linked_watch = (int(linked_row[0] or 0), int(linked_row[1] or 0), linked_row[2])
        # The channel's 28-day total when Analytics answered; otherwise the
        # linked videos' own totals, labelled as such by the UI.
        watch_minutes = _optional_number(analytics.get("estimatedMinutesWatched"))
        if watch_minutes is None and linked_with_watch:
            watch_minutes = float(linked_watch)

        return {
            "channel": channel_info,
            "latest_sync": sync_info,
            "total_views": views_28_days,
            "total_likes": likes_28_days,
            "views_28_days": views_28_days,
            "likes_28_days": likes_28_days,
            "lifetime_views": _optional_int(sync_channel.get("real_total_views")),
            "subscribers": _optional_int(sync_channel.get("subscribers")),
            "video_count": _optional_int(sync_channel.get("video_count")),
            "max_views": max(measured_views, default=None),
            "estimated_watch_minutes": watch_minutes,
            "linked_videos_count": linked_count,
            "linked_videos_with_watch_time": linked_with_watch,
            "videos": [
                {
                    "video_id": r[0],
                    "title": r[1],
                    "views": r[2],
                    "likes": r[3],
                    "captured_at": r[4],
                    "published_at": r[5],
                    "comments": r[7],
                    "average_view_percentage": r[8],
                }
                for r in latest
            ],
        }

    def learning_summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            angle_rows = connection.execute(
                """
                SELECT content_angle, COUNT(*) as total_runs, AVG(title_score) as avg_title_score
                FROM analysis_runs
                WHERE content_angle IS NOT NULL
                GROUP BY content_angle
                ORDER BY avg_title_score DESC, total_runs DESC
                """
            ).fetchall()
            title_rows = connection.execute(
                """
                SELECT title, title_score, opportunity_label
                FROM analysis_runs
                ORDER BY title_score DESC, created_at DESC
                LIMIT 5
                """
            ).fetchall()
            retention_rows = connection.execute(
                """
                SELECT retention_risk, COUNT(*)
                FROM analysis_runs
                GROUP BY retention_risk
                ORDER BY COUNT(*) DESC
                """
            ).fetchall()
            recent_rows = connection.execute(
                """
                SELECT id, title, title_score, opportunity_score, created_at
                FROM analysis_runs
                ORDER BY created_at DESC
                LIMIT 5
                """
            ).fetchall()

        return {
            "angle_effectiveness": [
                {
                    "content_angle": row[0],
                    "run_count": row[1],
                    "avg_title_score": _rounded(row[2]),
                }
                for row in angle_rows
            ],
            "winning_titles": [
                {
                    "title": row[0],
                    "title_score": _rounded(row[1]),
                    "opportunity_label": row[2],
                }
                for row in title_rows
            ],
            "retention_pattern": [
                {
                    "retention_risk": row[0],
                    "count": row[1],
                }
                for row in retention_rows
            ],
            "recent_runs": [
                {
                    "id": row[0],
                    "title": row[1],
                    "title_score": _rounded(row[2]),
                    "opportunity_score": _rounded(row[3]),
                    "created_at": row[4],
                }
                for row in recent_rows
            ],
        }

    def internal_scorecard(self) -> dict[str, Any]:
        with self._connect() as connection:
            aggregate_row = connection.execute(
                """
                SELECT
                    COUNT(*),
                    AVG(title_score),
                    AVG(opportunity_score)
                FROM analysis_runs
                """
            ).fetchone()
            recent_avg_row = connection.execute(
                """
                SELECT AVG(title_score), AVG(opportunity_score)
                FROM (
                    SELECT title_score, opportunity_score
                    FROM analysis_runs
                    ORDER BY created_at DESC
                    LIMIT 5
                )
                """
            ).fetchone()
            previous_avg_row = connection.execute(
                """
                SELECT AVG(title_score), AVG(opportunity_score)
                FROM (
                    SELECT title_score, opportunity_score
                    FROM analysis_runs
                    ORDER BY created_at DESC
                    LIMIT 5 OFFSET 5
                )
                """
            ).fetchone()
            label_rows = connection.execute(
                """
                SELECT opportunity_label, COUNT(*)
                FROM analysis_runs
                GROUP BY opportunity_label
                ORDER BY COUNT(*) DESC
                """
            ).fetchall()
            risk_rows = connection.execute(
                """
                SELECT retention_risk, COUNT(*)
                FROM analysis_runs
                GROUP BY retention_risk
                ORDER BY COUNT(*) DESC
                """
            ).fetchall()

        total_runs = int(aggregate_row[0] or 0) if aggregate_row else 0
        # AVG over no scored runs is NULL: unavailable, not a score of 0.
        recent = recent_avg_row or (None, None)
        previous = previous_avg_row or (None, None)
        title_delta = _delta(recent[0], previous[0]) if total_runs > 5 else None
        opportunity_delta = _delta(recent[1], previous[1]) if total_runs > 5 else None

        return {
            "total_runs": total_runs,
            "avg_title_score": _rounded(aggregate_row[1] if aggregate_row else None),
            "avg_opportunity_score": _rounded(aggregate_row[2] if aggregate_row else None),
            "recent_title_score_avg": _rounded(recent[0]),
            "recent_opportunity_score_avg": _rounded(recent[1]),
            "title_score_delta_vs_previous_window": title_delta,
            "opportunity_delta_vs_previous_window": opportunity_delta,
            "dominant_opportunity_label": label_rows[0][0] if label_rows else "UNKNOWN",
            "dominant_retention_risk": risk_rows[0][0] if risk_rows else "UNKNOWN",
            "score_trend": _describe_trend(title_delta, opportunity_delta, total_runs),
        }

    def reset_database(self) -> None:
        """Clear all historical test data for a fresh workspace setup."""
        with self._connect() as connection:
            connection.execute("DELETE FROM experiment_result_snapshots")
            connection.execute("DELETE FROM experiment_video_assignments")
            connection.execute("DELETE FROM experiments")
            connection.execute("DELETE FROM published_video_audits")
            connection.execute("DELETE FROM demand_research_snapshots")
            connection.execute("DELETE FROM watchlist_outlier_analyses")
            connection.execute("DELETE FROM watchlist_video_snapshots")
            connection.execute("DELETE FROM watchlist_videos")
            connection.execute("DELETE FROM watchlist_channel_snapshots")
            connection.execute("DELETE FROM watchlist_channels")
            connection.execute("DELETE FROM content_idea_research_snapshots")
            connection.execute("DELETE FROM content_ideas")
            connection.execute("DELETE FROM video_snapshots")
            connection.execute("DELETE FROM owned_video_snapshots")
            connection.execute("DELETE FROM youtube_channel_syncs")
            connection.execute("DELETE FROM analysis_runs")
            connection.execute("DELETE FROM published_video_links")
            connection.execute("DELETE FROM video_performance_snapshots")
            connection.execute("DELETE FROM package_experiments")

    # --- Stage A: Published Video Linking Methods ---

    def link_published_video(
        self,
        analysis_run_id: int,
        youtube_video_id: str,
        published_at: str,
        selected_title: str | None = None,
        selected_thumbnail_package: str | None = None,
        selected_description: str | None = None,
        selected_tags_json: str | None = None,
        selected_hashtags_json: str | None = None,
        format_val: str | None = None,
        language: str | None = None,
        region: str | None = None,
        notes: str | None = None,
        ownership_state: str = "unverified",
        ownership_verified: bool = False,
        verified_channel_id: str | None = None,
        ownership_verified_at: str | None = None,
        replace_existing_evidence: bool = False,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        # Cohorts group by exact values: the brief's spelling ("Short") is
        # stored as the cohort one, and free text counts as unknown there.
        package_format = comparable_format(format_val)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            # A generated package represents one upload, so linking another
            # video removes the old link. Its snapshots, experiments, audits and
            # assignments cascade with it, so that needs explicit consent.
            conflict = None if replace_existing_evidence else _relink_conflict(connection, analysis_run_id, youtube_video_id)
            if conflict:
                raise conflict
            previous = _previous_link(connection, analysis_run_id, youtube_video_id)
            if previous:
                connection.execute("DELETE FROM published_video_links WHERE id = ?", (int(previous[0]),))
            # Relinking without a connected channel must not undo an ownership
            # check that already succeeded; only a new verification replaces it.
            cursor = connection.execute(
                """
                INSERT INTO published_video_links (
                    analysis_run_id, youtube_video_id, published_at,
                    selected_title, selected_thumbnail_package, selected_description,
                    selected_tags_json, selected_hashtags_json, format, language, region, notes,
                    linked_at, updated_at, ownership_state, ownership_verified,
                    verified_channel_id, ownership_verified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(youtube_video_id) DO UPDATE SET
                    analysis_run_id = excluded.analysis_run_id,
                    published_at = excluded.published_at,
                    selected_title = excluded.selected_title,
                    selected_thumbnail_package = excluded.selected_thumbnail_package,
                    selected_description = excluded.selected_description,
                    selected_tags_json = excluded.selected_tags_json,
                    selected_hashtags_json = excluded.selected_hashtags_json,
                    format = excluded.format,
                    language = excluded.language,
                    region = excluded.region,
                    notes = excluded.notes,
                    ownership_state = CASE WHEN excluded.ownership_verified = 1 OR published_video_links.ownership_verified = 0
                        THEN excluded.ownership_state ELSE published_video_links.ownership_state END,
                    verified_channel_id = CASE WHEN excluded.ownership_verified = 1 OR published_video_links.ownership_verified = 0
                        THEN excluded.verified_channel_id ELSE published_video_links.verified_channel_id END,
                    ownership_verified_at = CASE WHEN excluded.ownership_verified = 1 OR published_video_links.ownership_verified = 0
                        THEN excluded.ownership_verified_at ELSE published_video_links.ownership_verified_at END,
                    ownership_verified = MAX(excluded.ownership_verified, published_video_links.ownership_verified),
                    updated_at = excluded.updated_at
                """,
                (
                    analysis_run_id,
                    youtube_video_id,
                    published_at,
                    selected_title,
                    selected_thumbnail_package,
                    selected_description,
                    selected_tags_json,
                    selected_hashtags_json,
                    format_val,
                    language,
                    region,
                    notes,
                    now,
                    now,
                    ownership_state,
                    1 if ownership_verified else 0,
                    verified_channel_id,
                    ownership_verified_at,
                ),
            )
            row = connection.execute(
                "SELECT id FROM published_video_links WHERE youtube_video_id = ?",
                (youtube_video_id,),
            ).fetchone()
            link_id = int(row[0]) if row else int(cursor.lastrowid or 0)
            connection.execute(
                """UPDATE content_ideas SET published_video_link_id = NULL,
                          status = CASE WHEN status = 'published' THEN 'package_generated' ELSE status END,
                          updated_at = ?
                   WHERE published_video_link_id = ? AND analysis_run_id != ?""",
                (now, link_id, analysis_run_id),
            )
            connection.execute(
                """INSERT OR IGNORE INTO published_video_comparable_metadata
                   (published_video_link_id, language, format, duration_bucket, topic_category,
                    language_source, format_source, duration_bucket_source, topic_category_source,
                    created_at, updated_at)
                   VALUES (?, 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', ?, ?)""",
                (link_id, now, now),
            )
            # The package's values follow a relink; a creator's own edits never change.
            for field, value in (("language", language), ("format", package_format)):
                connection.execute(
                    f"""UPDATE published_video_comparable_metadata
                        SET {field} = ?, {field}_source = ?, updated_at = ?
                        WHERE published_video_link_id = ? AND {field}_source IN ('package', 'unknown')""",
                    (value or "unknown", "package" if value else "unknown", now, link_id),
                )
            connection.execute(
                """UPDATE content_ideas
                   SET published_video_link_id = ?, status = 'published', updated_at = ?
                   WHERE analysis_run_id = ?""",
                (link_id, now, analysis_run_id),
            )
            return link_id

    def published_video_links_list(self) -> list[dict[str, Any]]:
        return self._published_links()

    def _published_links(self, link_id: int | None = None) -> list[dict[str, Any]]:
        where, params = ("WHERE p.id = ?", (link_id,)) if link_id is not None else ("", ())
        with self._connect() as connection:
            # The latest snapshot that holds data: a failed retry records an
            # attempt, not a measurement, and must not hide the last real one.
            rows = connection.execute(
                f"""
                SELECT p.id, p.analysis_run_id, p.youtube_video_id, p.published_at,
                       p.selected_title, p.selected_thumbnail_package, p.selected_description,
                       p.format, p.language, p.region, p.notes, p.linked_at, p.updated_at,
                       COALESCE(a.title, a.query, 'Saved Package'), a.opportunity_score, a.title_score,
                       s.age_hours, s.views, s.avg_view_percentage, s.impressions_ctr, s.snapshot_window, s.captured_at,
                       p.selected_tags_json, p.selected_hashtags_json, p.youtube_metadata_json, p.metadata_synced_at,
                       p.ownership_state, p.ownership_verified, p.verified_channel_id, p.ownership_verified_at
                FROM published_video_links p
                LEFT JOIN analysis_runs a ON p.analysis_run_id = a.id
                LEFT JOIN video_performance_snapshots s ON s.id = (
                    SELECT vs.id FROM video_performance_snapshots vs
                    WHERE vs.youtube_video_id = p.youtube_video_id AND vs.views IS NOT NULL
                    ORDER BY vs.captured_at DESC, vs.id DESC LIMIT 1
                )
                {where}
                ORDER BY p.published_at DESC, p.id DESC
                """,
                params,
            ).fetchall()
            result = [
                {
                    "id": r[0],
                    "analysis_run_id": r[1],
                    "youtube_video_id": r[2],
                    "published_at": r[3],
                    "selected_title": r[4],
                    "selected_thumbnail_package": r[5],
                    "selected_description": r[6],
                    "format": r[7],
                    "language": r[8],
                    "region": r[9],
                    "notes": r[10],
                    "linked_at": r[11],
                    "updated_at": r[12],
                    "package_topic": r[13],
                    "package_opportunity_score": r[14],
                    "package_title_score": r[15],
                    "latest_performance": {
                        "age_hours": r[16], "views": r[17], "avg_view_percentage": r[18],
                        "impressions_ctr": r[19], "snapshot_window": r[20], "captured_at": r[21],
                    } if r[21] else None,
                    "selected_tags": _json_list(r[22]),
                    "selected_hashtags": _json_list(r[23]),
                    "youtube_metadata": _json_value(r[24]),
                    "metadata_synced_at": r[25],
                    "ownership_state": r[26],
                    "ownership_verified": bool(r[27]),
                    "verified_channel_id": r[28],
                    "ownership_verified_at": r[29],
                }
                for r in rows
            ]
            metadata_where = "WHERE published_video_link_id = ?" if link_id is not None else ""
            metadata_rows = connection.execute(
                "SELECT published_video_link_id, language, format, duration_bucket, topic_category, language_source, "
                "format_source, duration_bucket_source, topic_category_source, updated_at "
                f"FROM published_video_comparable_metadata {metadata_where}",
                params,
            ).fetchall()
            metadata_by_link = {
                r[0]: {"language": r[1], "format": r[2], "duration_bucket": r[3], "topic_category": r[4], "sources": {"language": r[5], "format": r[6], "duration_bucket": r[7], "topic_category": r[8]}, "updated_at": r[9]}
                for r in metadata_rows
            }
            for item in result:
                item["comparable_metadata"] = metadata_by_link.get(item["id"])
            return result

    def published_video_link_by_run(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, analysis_run_id, youtube_video_id, published_at,
                       selected_title, selected_thumbnail_package, selected_description,
                       format, language, region, notes, linked_at, updated_at,
                       selected_tags_json, selected_hashtags_json, youtube_metadata_json, metadata_synced_at,
                       ownership_state, ownership_verified, verified_channel_id, ownership_verified_at
                FROM published_video_links
                WHERE analysis_run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "analysis_run_id": row[1],
                "youtube_video_id": row[2],
                "published_at": row[3],
                "selected_title": row[4],
                "selected_thumbnail_package": row[5],
                "selected_description": row[6],
                "format": row[7],
                "language": row[8],
                "region": row[9],
                "notes": row[10],
                "linked_at": row[11],
                "updated_at": row[12],
                "selected_tags": _json_list(row[13]),
                "selected_hashtags": _json_list(row[14]),
                "youtube_metadata": _json_value(row[15]),
                "metadata_synced_at": row[16],
                "ownership_state": row[17],
                "ownership_verified": bool(row[18]),
                "verified_channel_id": row[19],
                "ownership_verified_at": row[20],
            }

    def update_linked_video_metadata(self, link_id: int, metadata: dict[str, Any]) -> bool:
        """Merge a fresh lookup into the stored metadata.

        A partial source (oEmbed has no description, tags or date) reports those
        fields as None; they keep their earlier values instead of being erased.
        The Data API reports every field, so its None is current: a like count
        YouTube now hides is unknown, not the last number it showed.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT youtube_metadata_json FROM published_video_links WHERE id = ?", (link_id,)
            ).fetchone()
            if not row:
                return False
            complete = metadata.get("metadata_source") == "youtube_data_api"
            merged = {**_json_value(row[0]), **{key: value for key, value in metadata.items() if complete or value is not None}}
            connection.execute(
                """UPDATE published_video_links
                   SET youtube_metadata_json = ?, metadata_synced_at = ?, updated_at = ?
                   WHERE id = ?""",
                (json.dumps(merged), now, now, link_id),
            )
            return True

    def mark_link_ownership_verified(self, link_id: int, channel_id: str) -> bool:
        if not channel_id:
            return False
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE published_video_links
                   SET ownership_state = 'verified', ownership_verified = 1,
                       verified_channel_id = ?, ownership_verified_at = ?, updated_at = ?
                   WHERE id = ?""",
                (channel_id, now, now, link_id),
            )
            return cursor.rowcount > 0

    def published_video_link(self, link_id: int) -> dict[str, Any] | None:
        links = self._published_links(int(link_id))
        return links[0] if links else None

    def linked_run_for_video(self, youtube_video_id: str) -> int | None:
        """The saved package a video is linked to, if any."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT analysis_run_id FROM published_video_links WHERE youtube_video_id = ?", (youtube_video_id,)
            ).fetchone()
        return int(row[0]) if row else None

    def check_relink(self, analysis_run_id: int, youtube_video_id: str) -> None:
        """Raise RelinkWouldDeleteEvidence when linking this video needs the creator's consent.

        Read-only, so a request can ask before spending a YouTube lookup; the
        link itself checks again inside its transaction.
        """
        with self._connect() as connection:
            conflict = _relink_conflict(connection, analysis_run_id, youtube_video_id)
        if conflict:
            raise conflict

    def mark_link_ownership_failed(self, link_id: int) -> bool:
        """Stop collecting a video YouTube no longer shows under the connected channel."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE published_video_links
                   SET ownership_state = 'failed', ownership_verified = 0, updated_at = ?
                   WHERE id = ?""",
                (now, link_id),
            )
            return cursor.rowcount > 0

    def comparable_metadata(self, link_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT published_video_link_id, language, format, duration_bucket, topic_category,
                          language_source, format_source, duration_bucket_source, topic_category_source,
                          created_at, updated_at
                   FROM published_video_comparable_metadata WHERE published_video_link_id = ?""",
                (link_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "link_id": row[0],
            "language": row[1], "format": row[2], "duration_bucket": row[3], "topic_category": row[4],
            "sources": {"language": row[5], "format": row[6], "duration_bucket": row[7], "topic_category": row[8]},
            "created_at": row[9], "updated_at": row[10],
            "edits": self.comparable_metadata_edits(link_id),
        }

    def comparable_metadata_edits(self, link_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, field_name, old_value, new_value, source, changed_at
                   FROM published_video_metadata_edits WHERE published_video_link_id = ?
                   ORDER BY id DESC LIMIT ?""", (link_id, max(1, min(limit, 500)))
            ).fetchall()
        return [{"id": r[0], "field": r[1], "old_value": r[2], "new_value": r[3], "source": r[4], "changed_at": r[5]} for r in rows]

    def update_comparable_metadata(self, link_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        if not values or set(values) - set(COMPARABLE_FIELDS):
            raise ValueError("At least one supported comparable metadata field is required.")
        for field, value in values.items():
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field} cannot be empty.")
            if field == "duration_bucket" and value is not None and value not in DURATION_VALUES:
                raise ValueError("Invalid duration bucket.")
            # Another spelling of a format ("short") is stored as the cohort one.
            if field == "format" and value is not None and value.strip() != "unknown" and not comparable_format(value):
                raise ValueError("Invalid format.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            if not connection.execute("SELECT 1 FROM published_video_links WHERE id = ?", (link_id,)).fetchone():
                return None
            connection.execute(
                """INSERT OR IGNORE INTO published_video_comparable_metadata
                   (published_video_link_id, language, format, duration_bucket, topic_category,
                    language_source, format_source, duration_bucket_source, topic_category_source,
                    created_at, updated_at) VALUES (?, 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', 'unknown', ?, ?)""",
                (link_id, now, now),
            )
            row = connection.execute("SELECT language, format, duration_bucket, topic_category FROM published_video_comparable_metadata WHERE published_video_link_id = ?", (link_id,)).fetchone()
            indexes = {"language": 0, "format": 1, "duration_bucket": 2, "topic_category": 3}
            for field, raw in values.items():
                new_value = (
                    comparable_format(raw) if field == "format" else raw.strip() if isinstance(raw, str) else None
                ) or "unknown"
                old_value = row[indexes[field]] or "unknown"
                connection.execute(f"UPDATE published_video_comparable_metadata SET {field} = ?, {field}_source = ?, updated_at = ? WHERE published_video_link_id = ?", (new_value, "unknown" if new_value == "unknown" else "creator", now, link_id))
                if old_value != new_value:
                    connection.execute("INSERT INTO published_video_metadata_edits (published_video_link_id, field_name, old_value, new_value, source, changed_at) VALUES (?, ?, ?, ?, 'creator', ?)", (link_id, field, old_value, new_value, now))
        return self.comparable_metadata(link_id)

    def update_published_video_link(
        self,
        link_id: int,
        selected_title: str | None = None,
        selected_thumbnail_package: str | None = None,
        selected_description: str | None = None,
        notes: str | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE published_video_links
                SET selected_title = COALESCE(?, selected_title),
                    selected_thumbnail_package = COALESCE(?, selected_thumbnail_package),
                    selected_description = COALESCE(?, selected_description),
                    notes = COALESCE(?, notes),
                    updated_at = ?
                WHERE id = ?
                """,
                (selected_title, selected_thumbnail_package, selected_description, notes, now, link_id),
            )
            return cursor.rowcount > 0

    # --- Stage B: Age-Based Performance Snapshots ---

    def record_performance_snapshot(
        self,
        youtube_video_id: str,
        age_hours: float,
        views: int | None = None,
        watch_time_minutes: float | None = None,
        avg_view_duration_seconds: float | None = None,
        avg_view_percentage: float | None = None,
        likes: int | None = None,
        comments: int | None = None,
        shares: int | None = None,
        subscribers_gained: int | None = None,
        impressions: int | None = None,
        impressions_ctr: float | None = None,
        snapshot_window: str | None = None,
        replace_window: bool = False,
        snapshot_status: str | None = None,
        failure_reason: str | None = None,
        source_start_date: str | None = None,
        source_end_date: str | None = None,
    ) -> int:
        captured_at = datetime.now(timezone.utc).isoformat()
        if snapshot_status is None:
            if snapshot_window == "current":
                snapshot_status = "display_only"
            elif snapshot_window in _SCHEDULED_WINDOWS:
                snapshot_status = "complete" if views is not None else "empty_retryable"
            else:
                snapshot_status = "legacy_unverified"
        if snapshot_status == "complete" and views is None:
            snapshot_status = "empty_retryable"
            failure_reason = failure_reason or "analytics_returned_no_rows"

        with self._connect() as connection:
            # The collector and a manual refresh can write the same window at
            # once; taking the write lock first makes read-then-write atomic.
            connection.execute("BEGIN IMMEDIATE")
            if snapshot_window in _SCHEDULED_WINDOWS:
                existing = connection.execute(
                    """SELECT id, snapshot_status, attempt_count
                       FROM video_performance_snapshots
                       WHERE youtube_video_id = ? AND snapshot_window = ?
                       ORDER BY captured_at DESC, id DESC LIMIT 1""",
                    (youtube_video_id, snapshot_window),
                ).fetchone()
                if existing and existing[1] == "complete" and not replace_window:
                    return int(existing[0])
                attempt_count = min(int(existing[2] or 0) + 1, _MAX_SNAPSHOT_ATTEMPTS) if existing else 1
                completed_at = captured_at if snapshot_status == "complete" else None
                if existing:
                    connection.execute(
                        """UPDATE video_performance_snapshots
                           SET published_video_link_id = COALESCE(
                                   published_video_link_id,
                                   (SELECT id FROM published_video_links WHERE youtube_video_id = ?)
                               ),
                               age_hours = ?, views = ?, watch_time_minutes = ?,
                               avg_view_duration_seconds = ?, avg_view_percentage = ?,
                               likes = ?, comments = ?, shares = ?, subscribers_gained = ?,
                               impressions = ?, impressions_ctr = ?, snapshot_status = ?,
                               attempt_count = ?, last_failure_reason = ?, last_attempted_at = ?,
                               completed_at = ?, source_start_date = ?, source_end_date = ?,
                               captured_at = CASE WHEN ? = 'complete' THEN ? ELSE captured_at END
                           WHERE id = ?""",
                        (
                            youtube_video_id, age_hours, views, watch_time_minutes,
                            avg_view_duration_seconds, avg_view_percentage, likes, comments,
                            shares, subscribers_gained, impressions, impressions_ctr,
                            snapshot_status, attempt_count, failure_reason, captured_at,
                            completed_at, source_start_date, source_end_date,
                            snapshot_status, captured_at,
                            int(existing[0]),
                        ),
                    )
                    return int(existing[0])

            if replace_window and snapshot_window:
                connection.execute(
                    "DELETE FROM video_performance_snapshots WHERE youtube_video_id = ? AND snapshot_window = ?",
                    (youtube_video_id, snapshot_window),
                )
            cursor = connection.execute(
                """
                INSERT INTO video_performance_snapshots (
                    published_video_link_id, youtube_video_id, age_hours, views, watch_time_minutes,
                    avg_view_duration_seconds, avg_view_percentage, likes, comments,
                    shares, subscribers_gained, impressions, impressions_ctr, snapshot_window,
                    snapshot_status, attempt_count, last_failure_reason, last_attempted_at,
                    completed_at, source_start_date, source_end_date, captured_at
                ) VALUES ((SELECT id FROM published_video_links WHERE youtube_video_id = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    youtube_video_id,
                    youtube_video_id,
                    age_hours,
                    views,
                    watch_time_minutes,
                    avg_view_duration_seconds,
                    avg_view_percentage,
                    likes,
                    comments,
                    shares,
                    subscribers_gained,
                    impressions,
                    impressions_ctr,
                    snapshot_window,
                    snapshot_status,
                    1 if snapshot_window in _SCHEDULED_WINDOWS else 0,
                    failure_reason,
                    captured_at if snapshot_window in _SCHEDULED_WINDOWS else None,
                    captured_at if snapshot_status == "complete" else None,
                    source_start_date,
                    source_end_date,
                    captured_at,
                ),
            )
            return int(cursor.lastrowid or 0)

    def has_snapshot_window(self, youtube_video_id: str, snapshot_window: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT 1 FROM video_performance_snapshots
                   WHERE youtube_video_id = ? AND snapshot_window = ?
                     AND snapshot_status = 'complete' LIMIT 1""",
                (youtube_video_id, snapshot_window),
            ).fetchone()
        return bool(row)

    def record_snapshot_attempt(
        self,
        youtube_video_id: str,
        snapshot_window: str,
        *,
        status: str,
        failure_reason: str,
        age_hours: float = 0.0,
        source_start_date: str | None = None,
        source_end_date: str | None = None,
    ) -> int:
        if snapshot_window not in _SCHEDULED_WINDOWS:
            raise ValueError("Snapshot attempts are supported only for 24h, 7d, and 28d windows.")
        if status not in {"empty_retryable", "failed_retryable"}:
            raise ValueError("Snapshot attempt status is not retryable.")
        return self.record_performance_snapshot(
            youtube_video_id=youtube_video_id,
            age_hours=age_hours,
            snapshot_window=snapshot_window,
            snapshot_status=status,
            failure_reason=failure_reason,
            source_start_date=source_start_date,
            source_end_date=source_end_date,
        )

    def postpone_snapshot_window(
        self,
        youtube_video_id: str,
        snapshot_window: str,
        *,
        failure_reason: str,
        age_hours: float = 0.0,
    ) -> None:
        """Note a try that failed for a reason outside this video, without spending an attempt.

        Counting an outage or a bug against the video would end its collection
        after a few bad runs. The time is still noted, so the window cools
        down and the collector takes other videos first.
        """
        if snapshot_window not in _SCHEDULED_WINDOWS:
            raise ValueError("Snapshot attempts are supported only for 24h, 7d, and 28d windows.")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT id, snapshot_status FROM video_performance_snapshots
                   WHERE youtube_video_id = ? AND snapshot_window = ?
                   ORDER BY captured_at DESC, id DESC LIMIT 1""",
                (youtube_video_id, snapshot_window),
            ).fetchone()
            if existing:
                if existing[1] != "complete":
                    connection.execute(
                        "UPDATE video_performance_snapshots SET last_failure_reason = ?, last_attempted_at = ? WHERE id = ?",
                        (failure_reason, now, int(existing[0])),
                    )
                return
            connection.execute(
                """INSERT INTO video_performance_snapshots (
                       published_video_link_id, youtube_video_id, age_hours, snapshot_window, snapshot_status,
                       attempt_count, last_failure_reason, last_attempted_at, captured_at
                   ) VALUES ((SELECT id FROM published_video_links WHERE youtube_video_id = ?), ?, ?, ?,
                             'failed_retryable', 0, ?, ?, ?)""",
                (youtube_video_id, youtube_video_id, age_hours, snapshot_window, failure_reason, now, now),
            )

    def snapshot_window_state(self, youtube_video_id: str, snapshot_window: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT snapshot_status, attempt_count, last_failure_reason,
                          last_attempted_at, completed_at, source_start_date,
                          source_end_date, captured_at
                   FROM video_performance_snapshots
                   WHERE youtube_video_id = ? AND snapshot_window = ?
                   ORDER BY captured_at DESC, id DESC LIMIT 1""",
                (youtube_video_id, snapshot_window),
            ).fetchone()
        if not row:
            return {
                "window": snapshot_window,
                "status": "pending",
                "attempt_count": 0,
                "retry_allowed": True,
                "last_failure_reason": None,
            }
        status = str(row[0] or "pending")
        attempts = int(row[1] or 0)
        return {
            "window": snapshot_window,
            "status": status,
            "attempt_count": attempts,
            "retry_allowed": status != "complete" and attempts < _MAX_SNAPSHOT_ATTEMPTS,
            "last_failure_reason": row[2],
            "last_attempted_at": row[3],
            "completed_at": row[4],
            "source_start_date": row[5],
            "source_end_date": row[6],
            "captured_at": row[7],
        }

    def snapshot_retry_allowed(self, youtube_video_id: str, snapshot_window: str) -> bool:
        return bool(self.snapshot_window_state(youtube_video_id, snapshot_window).get("retry_allowed"))

    def due_snapshot_links(
        self,
        *,
        now: datetime | None = None,
        retry_cooldown_seconds: int = 0,
        retry_max_seconds: int | None = None,
        channel_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Verified links with a window to collect, least recently attempted first.

        That order is round-robin: a few videos that keep failing cannot take
        every run's slots and starve the rest. A window is due once YouTube
        has reported all of it, as the refresh requires. With `channel_id`,
        videos verified for another channel are left out: they cannot be
        collected through this connection (one without a recorded channel
        stays, and its refresh records it).
        """
        now = now or datetime.now(timezone.utc)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, youtube_video_id, published_at
                   FROM published_video_links
                   WHERE ownership_state = 'verified' AND ownership_verified = 1
                     AND (? IS NULL OR verified_channel_id = ? OR COALESCE(verified_channel_id, '') = '')""",
                (channel_id, channel_id),
            ).fetchall()
            state_rows = connection.execute(
                """SELECT s.youtube_video_id, s.snapshot_window, s.snapshot_status, s.attempt_count, s.last_attempted_at
                   FROM video_performance_snapshots s
                   JOIN published_video_links p ON p.youtube_video_id = s.youtube_video_id
                   WHERE p.ownership_state = 'verified' AND p.ownership_verified = 1
                     AND s.snapshot_window IN ('24h', '7d', '28d')
                   ORDER BY s.captured_at ASC, s.id ASC"""
            ).fetchall()
        # The newest row of each window wins, as in snapshot_window_state.
        states = {(row[0], row[1]): (str(row[2] or "pending"), int(row[3] or 0), row[4]) for row in state_rows}
        due: list[tuple[str, str, int, dict[str, Any]]] = []
        for link_id, video_id, published_at in rows:
            parsed = _parse_datetime_safe(str(published_at or ""))
            if not parsed:
                continue
            age_hours = max(0.0, (now - parsed).total_seconds() / 3600)
            due_windows: list[str] = []
            # Links sort by their most recent attempt. ISO timestamps sort in
            # time order, and "" (never attempted) comes first.
            attempt_keys: list[str] = []
            for label, hours in SNAPSHOT_WINDOWS:
                if not reportable_window(parsed, hours, now):
                    continue
                status, attempts, last = states.get((video_id, label), ("pending", 0, None))
                if status == "complete" or attempts >= _MAX_SNAPSHOT_ATTEMPTS:
                    continue
                attempted = _parse_datetime_safe(str(last or ""))
                if retry_cooldown_seconds and attempted:
                    retry_delay = retry_cooldown_seconds * (2 ** max(0, (attempts or 1) - 1))
                    if retry_max_seconds:
                        retry_delay = min(retry_delay, retry_max_seconds)
                    if (now - attempted).total_seconds() < retry_delay:
                        continue
                due_windows.append(label)
                attempt_keys.append(attempted.astimezone(timezone.utc).isoformat() if attempted else "")
            if due_windows:
                due.append((max(attempt_keys), str(published_at), int(link_id), {
                    "id": link_id, "youtube_video_id": video_id, "published_at": published_at,
                    "age_hours": round(age_hours, 2), "due_windows": due_windows,
                }))
        return [item for *_, item in sorted(due, key=lambda entry: entry[:3])]

    def performance_snapshots(self, youtube_video_id: str) -> list[dict[str, Any]]:
        return self._snapshots("youtube_video_id = ?", (youtube_video_id,), "captured_at ASC, id ASC")

    def _snapshots(self, where: str, params: tuple[Any, ...], order: str, limit: int | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT {', '.join(_SNAPSHOT_COLUMNS)}
                    FROM video_performance_snapshots WHERE {where}
                    ORDER BY {order}{f' LIMIT {int(limit)}' if limit else ''}""",
                params,
            ).fetchall()
        snapshots = [dict(zip(_SNAPSHOT_COLUMNS, row, strict=True)) for row in rows]
        for snapshot in snapshots:
            # Only the scheduled windows are collected again; "current" is replaced on each refresh.
            snapshot["retry_allowed"] = (
                snapshot.get("snapshot_window") in _SCHEDULED_WINDOWS
                and snapshot.get("snapshot_status") != "complete"
                and int(snapshot.get("attempt_count") or 0) < _MAX_SNAPSHOT_ATTEMPTS
            )
        return snapshots

    def completed_evidence_snapshot(
        self, youtube_video_id: str, snapshot_window: str
    ) -> dict[str, Any] | None:
        rows = self._snapshots(
            "youtube_video_id = ? AND snapshot_window = ? AND snapshot_status = 'complete'",
            (youtube_video_id, snapshot_window), "captured_at DESC, id DESC", limit=1,
        )
        return rows[0] if rows else None

    def latest_performance_snapshot(self, youtube_video_id: str) -> dict[str, Any] | None:
        """The newest measurement: a completed window first, else a current count.

        Failed attempts are records of trying, not data, so they never count.
        """
        rows = self._snapshots(
            "youtube_video_id = ? AND views IS NOT NULL AND snapshot_status IN ('complete', 'display_only')",
            (youtube_video_id,),
            "CASE snapshot_status WHEN 'complete' THEN 0 ELSE 1 END, captured_at DESC, id DESC",
            limit=1,
        )
        return rows[0] if rows else None

    def current_performance_snapshot(self, youtube_video_id: str) -> dict[str, Any] | None:
        """The newest current count: the video's lifetime figures when last refreshed, for display."""
        rows = self._snapshots(
            "youtube_video_id = ? AND snapshot_window = 'current' AND snapshot_status = 'display_only' AND views IS NOT NULL",
            (youtube_video_id,),
            "captured_at DESC, id DESC",
            limit=1,
        )
        return rows[0] if rows else None

    def linked_package_report(self, run_id: int, run: dict[str, Any] | None = None) -> dict[str, Any]:
        """Join a generated package to its uploaded metadata and measured performance.

        `run` may be passed when the caller has already loaded it.
        """
        run = run or self.history_run(run_id)
        link = self.published_video_link_by_run(run_id)
        if not run or not link:
            return {"linked": False}

        package = run.get("package") if isinstance(run.get("package"), dict) else {}
        selection = run.get("selected_package") if isinstance(run.get("selected_package"), dict) else None
        selected_package = selection.get("package") if selection and isinstance(selection.get("package"), dict) else {}
        metadata = link.get("youtube_metadata") if isinstance(link.get("youtube_metadata"), dict) else {}
        snapshots = self.performance_snapshots(str(link.get("youtube_video_id") or ""))
        newest_first = list(reversed(snapshots))
        current = next(
            (item for item in newest_first if item["snapshot_window"] == "current" and item["snapshot_status"] == "display_only"),
            {},
        )
        # The most mature completed window is the evidence; "current" is a
        # lifetime count for display and is never compared with a window.
        evidence = next(
            (
                item for window in ("28d", "7d", "24h") for item in newest_first
                if item["snapshot_window"] == window and item["snapshot_status"] == "complete"
            ),
            {},
        )
        latest = current or evidence
        published_at = _parse_datetime_safe(str(link.get("published_at") or ""))
        age_hours = max(0.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600) if published_at else 0.0

        primary_generated_title = str(package.get("title") or run.get("title") or "").strip()
        generated_title = str(selected_package.get("title") or primary_generated_title).strip()
        uploaded_title = str(metadata.get("title") or link.get("selected_title") or "").strip()
        generated_description = str(selected_package.get("description") or package.get("description") or link.get("selected_description") or "").strip()
        uploaded_description = str(metadata.get("description") or "").strip()
        generated_tags = _normalized_list(selected_package.get("tags") or package.get("tags") or link.get("selected_tags") or [])
        uploaded_tags = _normalized_list(metadata.get("tags") or [])
        generated_hashtags = _normalized_list(selected_package.get("hashtags") or package.get("hashtags") or link.get("selected_hashtags") or [])
        uploaded_hashtags = _normalized_list(re.findall(r"#([^\s#]+)", uploaded_description))

        matching_tags = [tag for tag in generated_tags if tag in set(uploaded_tags)]
        missing_tags = [tag for tag in generated_tags if tag not in set(uploaded_tags)]
        extra_tags = [tag for tag in uploaded_tags if tag not in set(generated_tags)]
        matching_hashtags = [tag for tag in generated_hashtags if tag in set(uploaded_hashtags)]
        description_match = _word_overlap_percent(generated_description, uploaded_description)

        views = _first_number(latest.get("views"), metadata.get("view_count"))
        likes = _first_number(latest.get("likes"), metadata.get("like_count"))
        comments = _first_number(latest.get("comments"), metadata.get("comment_count"))
        shares = _first_number(latest.get("shares"))
        retention = _optional_number(latest.get("avg_view_percentage"))
        avg_duration = _optional_number(latest.get("avg_view_duration_seconds"))
        like_rate = _rate(likes, views)
        comment_rate = _rate(comments, views)

        # Legacy links may predate comparable metadata.  They remain valid
        # published-video records; absence of this optional record must not
        # prevent a channel refresh or an audit snapshot from being saved.
        comparable = self.comparable_metadata(int(link.get("id") or 0)) or {}
        comparable_ready = all(str(comparable.get(field) or "unknown") != "unknown" for field in COMPARABLE_FIELDS)
        baseline = self._comparable_snapshot_baseline(link, evidence, comparable)
        evidence_views = _optional_int(evidence.get("views"))
        verdict, worked, improve = _performance_diagnosis(
            age_hours=age_hours,
            views=evidence_views,
            retention=_optional_number(evidence.get("avg_view_percentage")),
            like_rate=_rate(_optional_int(evidence.get("likes")), evidence_views),
            baseline=baseline,
            title_match=_normalize_text(uploaded_title) == _normalize_text(generated_title),
            matching_tags=len(matching_tags),
            generated_tag_count=len(generated_tags),
        )

        diagnosis_policy = confidence_payload(baseline.get("sample_size", 0))
        try:
            retention_learning = self.retention_learning_summary(
                format_filter=comparable.get("format"),
                language_filter=comparable.get("language"),
                snapshot_window=str(evidence.get("snapshot_window") or "24h") if evidence else "24h",
            )
        except (ValueError, sqlite3.Error):
            retention_learning = {
                "status": "insufficient_evidence", "learning_allowed": False,
                "sample_size": 0, "minimum_samples": EARLY_SIGNAL_MIN_SAMPLES, "patterns": [],
                "message": "Retention learning is unavailable; no pattern is inferred.",
            }
        return {
            "linked": True,
            "link_id": link.get("id"),
            "video_id": link.get("youtube_video_id"),
            "video_url": f"https://www.youtube.com/watch?v={link.get('youtube_video_id')}",
            "ownership_state": link.get("ownership_state") or "unverified",
            "ownership_verified": bool(link.get("ownership_verified")),
            "verified_channel_id": link.get("verified_channel_id"),
            "published_at": link.get("published_at"),
            "age_hours": round(age_hours, 1),
            "metadata_synced_at": link.get("metadata_synced_at"),
            "youtube": metadata,
            "comparable_metadata": comparable,
            "package_usage": {
                "attribution_status": "creator_selected" if selection else "unknown",
                "generated_primary_title": primary_generated_title,
                "selected_package_id": selection.get("generated_package_id") if selection else None,
                "selected_package": selected_package if selection else None,
                "attribution_note": (
                    "The creator explicitly recorded this generated package before linkage."
                    if selection else
                    "No package selection was recorded. The system cannot infer which generated alternative was published."
                ),
                "generated_title": generated_title,
                "uploaded_title": uploaded_title,
                "title_match": _normalize_text(uploaded_title) == _normalize_text(generated_title),
                "description_match_percent": description_match,
                "generated_tags": generated_tags,
                "uploaded_tags": uploaded_tags,
                "matching_tags": matching_tags,
                "missing_generated_tags": missing_tags,
                "extra_uploaded_tags": extra_tags,
                "generated_hashtags": generated_hashtags,
                "uploaded_hashtags": uploaded_hashtags,
                "matching_hashtags": matching_hashtags,
            },
            "performance": {
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "like_rate_percent": like_rate,
                "comment_rate_percent": comment_rate,
                "average_view_duration_seconds": avg_duration,
                "average_view_percentage": retention,
                "subscribers_gained": _optional_number(latest.get("subscribers_gained")),
                "snapshot_window": latest.get("snapshot_window"),
                "captured_at": latest.get("captured_at"),
                "snapshot_status": latest.get("snapshot_status"),
            },
            "current_performance": current or None,
            "learning_evidence": evidence or None,
            "retention_learning": retention_learning,
            "baseline": baseline,
            "diagnosis": {
                "verdict": verdict,
                "what_worked": worked,
                "needs_improvement": improve,
                "confidence": diagnosis_policy["confidence_label"],
                "evidence_level": diagnosis_policy["evidence_level"],
                "learning_eligible": bool(
                    link.get("ownership_state") == "verified"
                    and link.get("ownership_verified")
                    and mature_snapshot(evidence)
                    and diagnosis_policy["learning_allowed"]
                    and comparable_ready
                ),
                "attribution_note": (
                    "YouTube APIs report video-level performance, not views caused by individual tags. "
                    "The tool learns reliable packaging patterns only after comparable linked videos accumulate."
                ),
            },
            "snapshots": snapshots,
        }

    def _comparable_snapshot_baseline(
        self, link: dict[str, Any], latest: dict[str, Any], comparable: dict[str, Any]
    ) -> dict[str, Any]:
        window = str(latest.get("snapshot_window") or "")
        if not mature_snapshot(latest):
            return {"sample_size": 0, "window": window or "none", "median_views": None, "median_retention_percentage": None}
        # Comparable labels are optional for older links.  A missing label
        # simply means no cohort baseline can be calculated yet.
        if any(str(comparable.get(field) or "unknown") == "unknown" for field in COMPARABLE_FIELDS):
            return {"sample_size": 0, "window": window, "median_views": None, "median_retention_percentage": None}
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT s.views, s.avg_view_percentage
                   FROM video_performance_snapshots s
                   JOIN published_video_links p ON p.youtube_video_id = s.youtube_video_id
                   JOIN published_video_comparable_metadata m ON m.published_video_link_id = p.id
                   WHERE s.snapshot_window = ? AND s.youtube_video_id != ?
                     AND {_VERIFIED_LINK_SQL}
                     AND m.format = ? AND m.language = ?
                     AND m.duration_bucket = ? AND m.topic_category = ?
                     AND s.id = (
                         SELECT x.id FROM video_performance_snapshots x
                         WHERE x.youtube_video_id = s.youtube_video_id
                           AND x.snapshot_window = s.snapshot_window
                           AND {_MATURE_SNAPSHOT_SQL}
                         ORDER BY x.completed_at DESC, x.id DESC LIMIT 1
                     )""",
                (window, link.get("youtube_video_id"), comparable.get("format"), comparable.get("language"),
                 comparable.get("duration_bucket"), comparable.get("topic_category")),
            ).fetchall()
        views = sorted(float(row[0]) for row in rows if row[0] is not None)
        retention = sorted(float(row[1]) for row in rows if row[1] is not None)
        return {
            "sample_size": len(rows),
            "window": window,
            "median_views": _median(views),
            "median_retention_percentage": _median(retention),
        }

    # --- Stage C: Evidence & Cohort Calculation Engine ---

    def cohort_analytics(
        self,
        format_filter: str | None = None,
        language_filter: str | None = None,
        duration_bucket_filter: str | None = None,
        topic_category_filter: str | None = None,
        snapshot_window: str = "24h",
        exclude_video_id: str | None = None,
    ) -> dict[str, Any]:
        """Verified videos with completed evidence that match every given filter.

        `exclude_video_id` leaves one video out of the count and the medians, so
        a video is compared with its peers rather than with itself. A blank or
        "unknown" filter selects every video (known_filter), and a format filter
        is read as format_filter_values reads it.
        """
        if snapshot_window not in _SCHEDULED_WINDOWS:
            raise ValueError("Cohorts require a 24h, 7d, or 28d evidence window.")
        formats = format_filter_values(format_filter)
        format_filter = comparable_format(format_filter) or known_filter(format_filter)
        language_filter = known_filter(language_filter)
        duration_bucket_filter = known_filter(duration_bucket_filter)
        topic_category_filter = known_filter(topic_category_filter)
        # The same filters narrow the cohort and the count of links it was drawn from.
        filters = ""
        filter_params: list[Any] = []
        if formats is not None:
            filters += f" AND m.format IN ({', '.join('?' for _ in formats)})" if formats else " AND 0"
            filter_params.extend(sorted(formats))
        for column, value in (("language", language_filter), ("duration_bucket", duration_bucket_filter),
                              ("topic_category", topic_category_filter)):
            if value:
                filters += f" AND m.{column} = ?"
                filter_params.append(value)
        if exclude_video_id:
            filters += " AND p.youtube_video_id != ?"
            filter_params.append(exclude_video_id)
        with self._connect() as connection:
            query = f"""
                SELECT p.youtube_video_id, m.format, m.language, m.duration_bucket, m.topic_category,
                       s.views, s.likes, s.avg_view_percentage,
                       m.format_source, m.language_source, m.duration_bucket_source, m.topic_category_source
                FROM published_video_links p
                JOIN published_video_comparable_metadata m ON m.published_video_link_id = p.id
                JOIN video_performance_snapshots s ON s.id = (
                    SELECT x.id FROM video_performance_snapshots x
                    WHERE x.youtube_video_id = p.youtube_video_id
                      AND x.snapshot_window = ?
                      AND {_MATURE_SNAPSHOT_SQL}
                    ORDER BY x.completed_at DESC, x.id DESC LIMIT 1
                )
                WHERE {_VERIFIED_LINK_SQL}
                  AND {_COMPARABLE_LABELS_SQL}
            """
            rows = connection.execute(query + filters, [snapshot_window, *filter_params]).fetchall()
            count = len(rows)
            policy = confidence_payload(count)

            # Links that match the same filters, whether or not they qualify:
            # the difference is what was excluded, not a different cohort.
            total_query = """SELECT COUNT(DISTINCT p.youtube_video_id)
                             FROM published_video_links p
                             LEFT JOIN published_video_comparable_metadata m ON m.published_video_link_id = p.id
                             WHERE 1=1"""
            total_links = int(connection.execute(total_query + filters, filter_params).fetchone()[0] or 0)

            views_list = sorted([r[5] for r in rows if r[5] is not None])
            retention_list = sorted([r[7] for r in rows if r[7] is not None])
            likes_list = sorted([r[6] for r in rows if r[6] is not None])
            median_views = _median(views_list)
            median_retention = _median(retention_list)
            median_likes = _median(likes_list)

            recommendation = (
                f"Collect verified completed {snapshot_window} snapshots until at least {EARLY_SIGNAL_MIN_SAMPLES} comparable videos are available."
            )
            if policy["learning_allowed"] and median_retention is not None:
                recommendation = (
                    f"{policy['confidence_label']}: use this {format_filter or 'format'} / "
                    f"{language_filter or 'language'} {snapshot_window} cohort as a cautious comparison baseline. "
                    f"Median average viewed is {median_retention:.1f}%."
                )

            return {
                "format": format_filter or "all",
                "language": language_filter or "all",
                "duration_bucket": duration_bucket_filter or "all",
                "topic_category": topic_category_filter or "all",
                "snapshot_window": snapshot_window,
                "sample_size": count,
                "confidence_label": policy["confidence_label"],
                "confidence_level": policy["evidence_level"],
                "learning_allowed": policy["learning_allowed"],
                "next_threshold": policy["next_threshold"],
                "median_views": median_views,
                "median_retention_percentage": median_retention,
                "median_likes": median_likes,
                "total_linked": count,
                "total_links_considered": total_links,
                "excluded_count": max(0, total_links - count),
                "metadata_sources": {
                    "format": sorted({r[8] for r in rows}),
                    "language": sorted({r[9] for r in rows}),
                    "duration_bucket": sorted({r[10] for r in rows}),
                    "topic_category": sorted({r[11] for r in rows}),
                },
                "recommendation": recommendation,
            }

    # --- Stage D: Package Experiments ---

    def record_package_experiment(
        self,
        youtube_video_id: str,
        old_title: str | None = None,
        new_title: str | None = None,
        old_thumbnail: str | None = None,
        new_thumbnail: str | None = None,
        reason: str | None = None,
        performance_before_json: str | None = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO package_experiments (
                    published_video_link_id, youtube_video_id, changed_at, old_title, new_title,
                    old_thumbnail, new_thumbnail, reason, performance_before_json
                ) VALUES ((SELECT id FROM published_video_links WHERE youtube_video_id = ?), ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    youtube_video_id,
                    youtube_video_id,
                    now,
                    old_title,
                    new_title,
                    old_thumbnail,
                    new_thumbnail,
                    reason,
                    performance_before_json,
                ),
            )
            return cursor.lastrowid or 0

    def get_package_experiments(self, youtube_video_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, youtube_video_id, changed_at, old_title, new_title,
                       old_thumbnail, new_thumbnail, reason, performance_before_json, performance_after_json
                FROM package_experiments
                WHERE youtube_video_id = ?
                ORDER BY changed_at DESC
                """,
                (youtube_video_id,),
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "youtube_video_id": r[1],
                    "changed_at": r[2],
                    "old_title": r[3],
                    "new_title": r[4],
                    "old_thumbnail": r[5],
                    "new_thumbnail": r[6],
                    "reason": r[7],
                    "performance_before": _json_value(r[8]),
                    "performance_after": _json_value(r[9]),
                }
                for r in rows
            ]

    def complete_due_experiment_snapshots(self, youtube_video_id: str, after: dict[str, Any]) -> int:
        """Record a completed window as the "after" figure of changes it covers.

        Windows count from publication, so only one that ends after the change
        can say anything about it; the stored coverage makes plain that it
        still includes the days before the change.
        """
        end_date = str(after.get("source_end_date") or "")
        if not end_date:
            return 0
        after_with_coverage = {
            **after,
            "coverage": {
                "window": after.get("snapshot_window"),
                "source_start_date": after.get("source_start_date"),
                "source_end_date": end_date,
                "includes_days_before_change": True,
            },
        }
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE package_experiments SET performance_after_json = ?
                   WHERE youtube_video_id = ? AND performance_after_json IS NULL
                   AND substr(changed_at, 1, 10) < ?""",
                (json.dumps(after_with_coverage), youtube_video_id, end_date),
            )
        return cursor.rowcount

    def record_counts(self) -> dict[str, Any]:
        """Schema version and record counts, for the settings page."""
        tables = {
            "packages": "analysis_runs",
            "ideas": "content_ideas",
            "published_links": "published_video_links",
            "performance_snapshots": "video_performance_snapshots",
        }
        with self._connect() as connection:
            return {
                "schema_version": int(connection.execute("PRAGMA user_version").fetchone()[0]),
                "counts": {
                    label: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    for label, table in tables.items()
                },
            }

    def system_status(self) -> dict[str, Any]:
        # No path or error text: this is served to the browser. The error type
        # is enough to tell a locked database from a missing table.
        try:
            with self._connect() as connection:
                snapshot_count = connection.execute("SELECT COUNT(*) FROM video_snapshots").fetchone()[0]
                analysis_count = connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
            return {
                "database_ok": True,
                "snapshot_count": int(snapshot_count or 0),
                "analysis_count": int(analysis_count or 0),
            }
        except sqlite3.Error as exc:
            logger.warning("Database status check failed: %s", type(exc).__name__)
            return {
                "database_ok": False,
                "snapshot_count": None,
                "analysis_count": None,
                "error": type(exc).__name__,
            }



def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _median(values: list[float | int]) -> float | None:
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return round(float(values[middle]), 2)
    return round((float(values[middle - 1]) + float(values[middle])) / 2, 2)


def _json_value(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _normalize_text(value: str) -> str:
    # Every word in any script counts, single characters included: "Part 1"
    # and "Part 2" are different titles, and so are two Tamil titles.
    return " ".join(unicode_words(value, min_length=1))


def _normalized_list(values: Any) -> list[str]:
    out: list[str] = []
    for value in values if isinstance(values, list) else []:
        normalized = _normalize_text(str(value).lstrip("#"))
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def _word_overlap_percent(left: str, right: str) -> float:
    left_words = set(_normalize_text(left).split())
    right_words = set(_normalize_text(right).split())
    if not left_words or not right_words:
        return 0.0
    return round((len(left_words & right_words) / len(left_words)) * 100, 1)


def _optional_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(*values: Any) -> int | None:
    for value in values:
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


def _rate(part: int | None, views: int | None) -> float | None:
    return round((part / views) * 100, 2) if part is not None and views else None


def known_filter(value: Any) -> str | None:
    """A cohort filter value, or None: blank and "unknown" are the absence of a value, not a cohort.

    As a filter, "unknown" would match only videos without that label, which
    cohorts exclude, so it would always select nothing.
    """
    text = str(value or "").strip()
    return text if text and text != "unknown" else None


def comparable_format(value: Any) -> str | None:
    """The stored spelling of a format, or None when it is not a known format.

    Other spellings ("Short", "YouTube Shorts", "reels") are read by
    source_cues.format_key, which the Short resolver uses too. Free text would
    form a cohort of one, so it counts as unknown, except text that starts with
    the platform's own name for the format ("YouTube Short quote video").
    migrations._v10_format keeps its own copy of the rule as version 10 shipped it.
    """
    key = format_key(value)
    return key if key in FORMAT_VALUES and key != "unknown" else None


def format_filter_values(value: Any) -> frozenset[str] | None:
    """The stored formats a format filter selects, or None when it selects every format.

    A value that is not a known format selects nothing rather than everything.
    """
    if known_filter(value) is None:
        return None
    key = comparable_format(value)
    if key == "long_form":
        return _LONG_FORM_VALUES
    return frozenset({key} if key else ())


def reportable_window(published_at: datetime, hours: float, now: datetime) -> tuple[date, date] | None:
    """The Pacific days a snapshot window covers, once YouTube Analytics has reported them all.

    A window is due only then: a partial range stored as complete would never
    be collected again. The collector plans with this and the refresh queries
    with it, so a planned window is always one the refresh collects.
    """
    if now - published_at < timedelta(hours=hours):
        return None
    last_day = (published_at + timedelta(hours=hours)).astimezone(ANALYTICS_ZONE).date()
    if last_day > now.astimezone(ANALYTICS_ZONE).date() - timedelta(days=1):
        return None
    return published_at.astimezone(ANALYTICS_ZONE).date(), last_day


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_datetime_safe(value: str) -> datetime | None:
    try:
        return _parse_datetime(value)
    except (TypeError, ValueError):
        return None


def _performance_diagnosis(
    *,
    age_hours: float,
    views: int | None,
    retention: float | None,
    like_rate: float | None,
    baseline: dict[str, Any],
    title_match: bool,
    matching_tags: int,
    generated_tag_count: int,
) -> tuple[str, list[str], list[str]]:
    worked: list[str] = []
    improve: list[str] = []
    if title_match:
        worked.append(
            "The uploaded title exactly matches the generated recommendation, preserving title attribution "
            "if enough comparable evidence accumulates."
        )
    else:
        improve.append("The uploaded title differs from the generated title; treat this as a test of the uploaded title, not the original recommendation.")
    if generated_tag_count and matching_tags:
        worked.append(f"You used {matching_tags} of {generated_tag_count} generated tags.")
    elif generated_tag_count:
        improve.append("The uploaded metadata does not currently contain the generated tags, so tag-package adoption cannot be evaluated.")

    sample_size = int(baseline.get("sample_size") or 0)
    baseline_policy = confidence_payload(sample_size)
    median_views = baseline.get("median_views")
    median_retention = baseline.get("median_retention_percentage")
    if baseline_policy["learning_allowed"] and median_views is not None and views is not None:
        if views >= float(median_views):
            worked.append(f"Views are at or above the {baseline.get('window')} comparable median ({int(median_views)}).")
        else:
            improve.append(f"Views are below the {baseline.get('window')} comparable median ({int(median_views)}); test a stronger opening or packaging angle next time.")
    else:
        improve.append(
            "There are not yet five verified comparable videos at the same completed window, "
            "so no winner/loser claim is made."
        )

    if retention is not None:
        if median_retention is not None and baseline_policy["learning_allowed"]:
            if retention >= float(median_retention):
                worked.append(f"Average percentage viewed ({retention:.1f}%) is at or above the comparable median.")
            else:
                improve.append(f"Average percentage viewed ({retention:.1f}%) is below the comparable median; improve first-frame readability and looping.")
        elif retention >= 90:
            worked.append(f"Average percentage viewed is currently {retention:.1f}%, a promising observation for a Short.")
        elif age_hours >= 24 and retention < 70:
            improve.append(f"Average percentage viewed is currently {retention:.1f}%; test faster text reveal, clearer contrast, and a cleaner loop.")
    if like_rate is not None:
        worked.append(f"Observed like rate is {like_rate:.2f}% ({views} views); this is descriptive, not proof of a title or tag effect.")

    if age_hours < 24:
        verdict = "TOO EARLY — collecting the first 24-hour evidence"
    elif not baseline_policy["learning_allowed"] or median_views is None or views is None:
        verdict = "OBSERVATION ONLY — more comparable linked videos are needed"
    else:
        verdict = "ABOVE BASELINE" if views >= float(median_views) else "BELOW BASELINE"
    return verdict, worked, improve


def _previous_link(connection: sqlite3.Connection, analysis_run_id: int, youtube_video_id: str) -> tuple | None:
    """The package's link to a different video, which linking this one replaces."""
    return connection.execute(
        "SELECT id, youtube_video_id FROM published_video_links WHERE analysis_run_id = ? AND youtube_video_id != ?",
        (analysis_run_id, youtube_video_id),
    ).fetchone()


def _relink_conflict(connection: sqlite3.Connection, analysis_run_id: int, youtube_video_id: str) -> RelinkWouldDeleteEvidence | None:
    """The consent a link needs: replacing the package's video would delete its evidence."""
    previous = _previous_link(connection, analysis_run_id, youtube_video_id)
    if not previous:
        return None
    evidence = _link_evidence(connection, int(previous[0]), str(previous[1]))
    return RelinkWouldDeleteEvidence(str(previous[1]), evidence) if any(evidence.values()) else None


def _link_evidence(connection: sqlite3.Connection, link_id: int, youtube_video_id: str) -> dict[str, int]:
    """What deleting a link would delete with it (every child table cascades)."""
    counts = (
        ("snapshots", "SELECT COUNT(*) FROM video_performance_snapshots WHERE youtube_video_id = ? AND views IS NOT NULL", youtube_video_id),
        ("experiments", "SELECT COUNT(*) FROM package_experiments WHERE youtube_video_id = ?", youtube_video_id),
        ("audits", "SELECT COUNT(*) FROM published_video_audits WHERE published_video_link_id = ?", link_id),
        ("experiment assignments", "SELECT COUNT(*) FROM experiment_video_assignments WHERE published_video_link_id = ?", link_id),
        ("metadata edits", "SELECT COUNT(*) FROM published_video_metadata_edits WHERE published_video_link_id = ?", link_id),
    )
    return {label: int(connection.execute(sql, (value,)).fetchone()[0]) for label, sql, value in counts}


def _rounded(value: Any) -> float | None:
    number = _optional_number(value)
    return round(number, 2) if number is not None else None


def _delta(recent: Any, previous: Any) -> float | None:
    recent_number, previous_number = _optional_number(recent), _optional_number(previous)
    if recent_number is None or previous_number is None:
        return None
    return round(recent_number - previous_number, 2)


def _optional_int(value: Any) -> int | None:
    number = _optional_number(value)
    return int(number) if number is not None else None


def _describe_trend(title_delta: float | None, opportunity_delta: float | None, total_runs: int) -> str:
    if total_runs < 6:
        return "Not enough analysis history yet to calculate a reliable trend."
    if (title_delta or 0) > 0 and (opportunity_delta or 0) > 0:
        return "Recent analyses are trending stronger than the previous window."
    if (title_delta or 0) < 0 and (opportunity_delta or 0) < 0:
        return "Recent analyses are weaker than the previous window and should be reviewed."
    return "Recent analyses are mixed versus the previous window."
