from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from win_engine.feedback.migrations import (
    connect_managed,
    configure_connection,
    initialize_memory_database,
    prepare_database,
)
from win_engine.feedback.evidence_policy import confidence_payload, mature_snapshot, sample_is_eligible

_INITIALIZED_DATABASES: set[str] = set()
_INITIALIZATION_LOCK = Lock()
_SCHEDULED_WINDOWS = {"24h", "7d", "28d"}
_MAX_SNAPSHOT_ATTEMPTS = 5
COMPARABLE_FIELDS = ("language", "format", "duration_bucket", "topic_category")
FORMAT_VALUES = {
    "short",
    "youtube_shorts",
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
DURATION_VALUES = {"under_60s", "60_to_180s", "3_to_10m", "over_10m", "unknown"}
IDEA_STATUSES = {"idea", "scripted", "package_generated", "published", "archived"}
IDEA_CREATOR_FIELDS = {
    "topic", "notes", "format", "language", "region", "visual_or_background",
    "on_screen_text", "target_duration_seconds", "emotion_or_intent",
    "search_angle", "browse_angle", "audience_angle", "status",
}


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
                        prepare_database(database_path)
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

    def _initialize(self) -> None:
        # Retained as a compatibility hook for callers from older versions.
        if self._memory_connection is not None:
            initialize_memory_database(self._memory_connection)
        else:
            prepare_database(self._database_path_raw)

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    def record_snapshots(self, query: str, youtube_results: list[dict[str, Any]]) -> None:
        captured_at = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                result.get("video_id"),
                query,
                captured_at,
                result.get("published_at"),
                _to_int(result.get("view_count")),
                _to_int(result.get("like_count")),
                _to_int(result.get("comment_count")),
                _to_int(result.get("subscriber_count")),
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

    def velocity_signals(self, video_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT captured_at, view_count
                FROM video_snapshots
                WHERE video_id = ?
                ORDER BY captured_at DESC
                """,
                (video_id,),
            ).fetchall()

        if len(rows) < 2:
            return {
                "velocity_24h": None,
                "velocity_48h": None,
                "velocity_7d": None,
                "history_points": len(rows),
            }

        now = _parse_datetime(rows[0][0])
        windows = {
            "velocity_24h": timedelta(hours=24),
            "velocity_48h": timedelta(hours=48),
            "velocity_7d": timedelta(days=7),
        }
        values: dict[str, Any] = {"history_points": len(rows)}

        for label, window in windows.items():
            values[label] = self._delta_within_window(rows, now, window)

        return values

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

    def update_analysis_payload(self, run_id: int, title: str, payload: dict[str, Any]) -> None:
        """Replace an intermediate package with the exact final API response."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE analysis_runs SET title = ?, payload_json = ? WHERE id = ?",
                (title, json.dumps(payload), run_id),
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
            rows = connection.execute(
                f"""SELECT i.id, i.topic, i.status, i.format, i.language, i.region,
                           i.created_at, i.updated_at, i.analysis_run_id, i.published_video_link_id,
                           i.evidence_json,
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
            evidence = _json_value(row[10])
            ideas.append({
                "id": row[0], "topic": row[1], "status": row[2], "format": row[3],
                "language": row[4], "region": row[5], "created_at": row[6], "updated_at": row[7],
                "analysis_run_id": row[8], "published_video_link_id": row[9],
                "last_researched_at": row[11], "research_snapshot_count": int(row[12] or 0),
                "opportunity_explanation": evidence.get("opportunity_explanation") or "Research has not been run for this idea.",
                "personal_evidence_status": (evidence.get("personal_evidence") or {}).get("status", "insufficient_evidence"),
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
        result = dict(zip(keys, row))
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

    def history_runs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Return saved packages in newest-first order without the large payload."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.id, a.created_at, a.title, a.opportunity_score, a.title_score,
                       a.query, a.payload_json, p.id, p.youtube_video_id,
                       ps.generated_package_id, ps.selected_at
                FROM analysis_runs a
                LEFT JOIN analysis_package_selections ps ON ps.analysis_run_id = a.id
                LEFT JOIN published_video_links p ON p.id = (
                    SELECT linked.id FROM published_video_links linked
                    WHERE linked.analysis_run_id = a.id
                    ORDER BY linked.updated_at DESC LIMIT 1
                )
                ORDER BY a.created_at DESC LIMIT ? OFFSET ?
                """
                , (max(1, min(limit, 100)), max(0, offset))
            ).fetchall()
        return [
            {
                "id": row[0], "created_at": row[1], "title": row[2],
                "opportunity_score": round(float(row[3] or 0), 2),
                "title_score": round(float(row[4] or 0), 2), "query": row[5],
                "has_full_package": bool(row[6]),
                "linked_video_link_id": row[7],
                "linked_youtube_video_id": row[8],
                "selected_package_id": row[9],
                "package_selected_at": row[10],
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
        eligible: list[dict[str, Any]] = []
        for link in self.published_video_links_list():
            comparable = link.get("comparable_metadata") if isinstance(link.get("comparable_metadata"), dict) else {}
            effective_format = str(comparable.get("format") or link.get("format") or "unknown")
            effective_language = str(comparable.get("language") or link.get("language") or "unknown")
            if format_filter and effective_format != format_filter:
                continue
            if language_filter and effective_language != language_filter:
                continue
            snapshot = self.completed_evidence_snapshot(str(link.get("youtube_video_id") or ""), snapshot_window)
            policy_link = dict(link)
            policy_link["format"] = effective_format
            policy_link["language"] = effective_language
            if not sample_is_eligible(policy_link, snapshot, expected_window=snapshot_window):
                continue
            retention = _optional_number((snapshot or {}).get("avg_view_percentage"))
            if retention is None:
                continue
            run = self.history_run(int(link.get("analysis_run_id") or 0))
            payload = run.get("package") if run and isinstance(run.get("package"), dict) else {}
            assistant = payload.get("retention_assistant") if isinstance(payload.get("retention_assistant"), dict) else {}
            if assistant.get("rule_version") != "phase5-v1":
                continue
            opening = assistant.get("opening") if isinstance(assistant.get("opening"), dict) else {}
            pacing = assistant.get("pacing") if isinstance(assistant.get("pacing"), dict) else {}
            quote = assistant.get("quote_presentation") if isinstance(assistant.get("quote_presentation"), dict) else {}
            selection = run.get("selected_package") if run and isinstance(run.get("selected_package"), dict) else None
            hook_structure = (
                "generic_setup" if opening.get("generic_setup") else
                "subject_clear" if opening.get("clarity") == "clear" else "subject_needs_review"
            )
            quote_structure = "quote_present" if quote.get("status") == "available" else "no_exact_quote"
            eligible.append({
                "analysis_run_id": link.get("analysis_run_id"),
                "youtube_video_id": link.get("youtube_video_id"),
                "selected_package_id": selection.get("generated_package_id") if selection else None,
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
                "sample_size": sample_size, "minimum_samples": 5,
                "confidence_label": policy["confidence_label"],
                "snapshot_window": snapshot_window, "patterns": [],
                "retention_curve_status": "unavailable",
                "message": (
                    f"Only {sample_size} verified comparable Phase 5 video(s) have completed {snapshot_window} "
                    "retention evidence; at least 5 are required before surfacing correlations."
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
            "sample_size": sample_size, "minimum_samples": 5,
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
                   LEFT JOIN published_video_links p ON p.id = (
                       SELECT linked.id FROM published_video_links linked
                       WHERE linked.analysis_run_id = s.analysis_run_id
                       ORDER BY linked.updated_at DESC LIMIT 1)
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
            "content_angle": row[4], "title": row[5], "title_score": round(float(row[6] or 0), 2),
            "retention_risk": row[7], "opportunity_label": row[8],
            "opportunity_score": round(float(row[9] or 0), 2), "package": package,
        }
        result["selected_package"] = self.package_selection(run_id)
        return result

    def delete_analysis_run(self, run_id: int) -> bool:
        """Atomically delete a package and link-owned dependents, or roll back all."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """UPDATE content_ideas SET analysis_run_id = NULL, published_video_link_id = NULL,
                          status = CASE WHEN status IN ('package_generated', 'published') THEN 'scripted' ELSE status END,
                          updated_at = ?
                   WHERE analysis_run_id = ?""",
                (datetime.now(timezone.utc).isoformat(), run_id),
            )
            cursor = connection.execute("DELETE FROM analysis_runs WHERE id = ?", (run_id,))
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise sqlite3.IntegrityError(
                    f"Deletion would leave {len(violations)} foreign-key violation(s)."
                )
            return cursor.rowcount > 0

    def record_owned_snapshot(self, title: str, views: int, likes: int) -> None:
        """Record performance snapshot of creator's video for self-learning."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO owned_video_snapshots (
                    video_id, captured_at, title, views, likes
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    f"perf_{int(datetime.now(timezone.utc).timestamp())}",
                    datetime.now(timezone.utc).isoformat(),
                    title,
                    views,
                    likes,
                ),
            )

    def owned_performance_summary(self) -> dict[str, Any]:
        """Aggregate metrics of creator's video snapshots and connected channel syncs recorded in database."""
        with self._connect() as connection:
            ch_row = connection.execute(
                "SELECT channel_id, channel_title, connected_at FROM youtube_channel_connection WHERE id = 1"
            ).fetchone()
            channel_info = None
            if ch_row:
                channel_info = {
                    "id": ch_row[0],
                    "title": ch_row[1],
                    "connected_at": ch_row[2],
                }

            sync_row = connection.execute(
                "SELECT synced_at, payload_json FROM youtube_channel_syncs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            sync_info = None
            if sync_row:
                try:
                    payload = json.loads(sync_row[1])
                    sync_info = {
                        "synced_at": sync_row[0],
                        "channel": payload.get("channel", {}),
                        "period": payload.get("period", {}),
                        "current_28_days": payload.get("current_28_days", {}),
                    }
                except Exception:
                    pass

            latest = connection.execute(
                """
                SELECT s.video_id, s.title, s.views, s.likes, s.captured_at, s.published_at,
                       s.watch_minutes, s.comments, s.average_view_percentage
                FROM owned_video_snapshots s
                INNER JOIN (
                    SELECT video_id, MAX(captured_at) AS max_cap
                    FROM owned_video_snapshots
                    GROUP BY video_id
                ) latest ON s.video_id = latest.video_id AND s.captured_at = latest.max_cap
                ORDER BY COALESCE(s.published_at, '') DESC, s.video_id ASC
                """
            ).fetchall()

            linked_row = connection.execute(
                """
                SELECT COUNT(DISTINCT l.youtube_video_id), SUM(s.views), SUM(s.watch_time_minutes)
                FROM published_video_links l
                LEFT JOIN video_performance_snapshots s ON l.youtube_video_id = s.youtube_video_id
                """
            ).fetchone()

        snapshot_video_count = len(latest)
        snapshot_views = sum(int(r[2] or 0) for r in latest)
        snapshot_likes = sum(int(r[3] or 0) for r in latest)
        max_views = max((int(r[2] or 0) for r in latest), default=0)

        sync_channel = sync_info.get("channel", {}) if sync_info else {}
        real_channel_views = sync_channel.get("real_total_views")
        subscriber_count = sync_channel.get("subscribers")
        channel_video_count = sync_channel.get("video_count")
        sync_28d_views = sync_info.get("current_28_days", {}).get("views") if sync_info else None
        sync_28d_likes = sync_info.get("current_28_days", {}).get("likes") if sync_info else None
        sync_28d_watch = sync_info.get("current_28_days", {}).get("estimatedMinutesWatched") if sync_info else None

        views_28_days = int(sync_28d_views) if sync_28d_views is not None else snapshot_views
        likes_28_days = int(sync_28d_likes) if sync_28d_likes is not None else snapshot_likes
        effective_watch = sync_28d_watch if sync_28d_watch is not None else (int(linked_row[2] or 0) if linked_row else 0)

        return {
            "channel": channel_info,
            "latest_sync": sync_info,
            "total_views": views_28_days,
            "total_likes": likes_28_days,
            "views_28_days": views_28_days,
            "likes_28_days": likes_28_days,
            "lifetime_views": int(real_channel_views) if real_channel_views is not None else None,
            "subscribers": int(subscriber_count) if subscriber_count is not None else None,
            "video_count": int(channel_video_count) if channel_video_count is not None else snapshot_video_count,
            "max_views": max_views,
            "estimated_watch_minutes": effective_watch,
            "linked_videos_count": int(linked_row[0] or 0) if linked_row else 0,
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
                    "avg_title_score": round(float(row[2] or 0), 2),
                }
                for row in angle_rows
            ],
            "winning_titles": [
                {
                    "title": row[0],
                    "title_score": round(float(row[1] or 0), 2),
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
                    "title_score": round(float(row[2] or 0), 2),
                    "opportunity_score": round(float(row[3] or 0), 2),
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
        avg_title_score = round(float((aggregate_row[1] or 0) if aggregate_row else 0), 2)
        avg_opportunity_score = round(float((aggregate_row[2] or 0) if aggregate_row else 0), 2)
        recent_title_avg = round(float((recent_avg_row[0] or 0) if recent_avg_row else 0), 2)
        recent_opportunity_avg = round(float((recent_avg_row[1] or 0) if recent_avg_row else 0), 2)
        previous_title_avg = round(float((previous_avg_row[0] or 0) if previous_avg_row else 0), 2)
        previous_opportunity_avg = round(float((previous_avg_row[1] or 0) if previous_avg_row else 0), 2)
        title_delta = round(recent_title_avg - previous_title_avg, 2) if total_runs > 5 else None
        opportunity_delta = round(recent_opportunity_avg - previous_opportunity_avg, 2) if total_runs > 5 else None

        return {
            "total_runs": total_runs,
            "avg_title_score": avg_title_score,
            "avg_opportunity_score": avg_opportunity_score,
            "recent_title_score_avg": recent_title_avg,
            "recent_opportunity_score_avg": recent_opportunity_avg,
            "title_score_delta_vs_previous_window": title_delta,
            "opportunity_delta_vs_previous_window": opportunity_delta,
            "dominant_opportunity_label": label_rows[0][0] if label_rows else "UNKNOWN",
            "dominant_retention_risk": risk_rows[0][0] if risk_rows else "UNKNOWN",
            "score_trend": _describe_trend(title_delta, opportunity_delta, total_runs),
        }

    def upload_timing_insights(self, youtube_results: list[dict[str, Any]]) -> dict[str, Any]:
        hours: list[int] = []
        weekdays: list[str] = []

        for result in youtube_results:
            published_at = result.get("published_at")
            if not published_at:
                continue

            published_dt = _parse_datetime(published_at)
            hours.append(published_dt.hour)
            weekdays.append(published_dt.strftime("%A"))

        if not hours:
            return {
                "top_hours": [],
                "top_weekdays": [],
                "recommendation": "Not enough publish-time data yet.",
            }

        top_hours = _top_counts(hours)
        top_weekdays = _top_counts(weekdays)
        recommendation = (
            f"Recent high-signal videos cluster around {', '.join(str(item) for item in top_hours[:3])}:00 UTC "
            f"and days like {', '.join(top_weekdays[:2])}."
        )
        return {
            "top_hours": top_hours,
            "top_weekdays": top_weekdays,
            "recommendation": recommendation,
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
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            # A generated package represents one upload. Changing its link
            # replaces the association while historical metric rows stay intact.
            connection.execute(
                "DELETE FROM published_video_links WHERE analysis_run_id = ? AND youtube_video_id != ?",
                (analysis_run_id, youtube_video_id),
            )
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
                    ownership_state = excluded.ownership_state,
                    ownership_verified = excluded.ownership_verified,
                    verified_channel_id = excluded.verified_channel_id,
                    ownership_verified_at = excluded.ownership_verified_at,
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
                   VALUES (?, ?, ?, 'unknown', 'unknown', ?, ?, 'unknown', 'unknown', ?, ?)""",
                (link_id, language or "unknown", format_val or "unknown",
                 "package" if language else "unknown", "package" if format_val else "unknown", now, now),
            )
            connection.execute(
                """UPDATE content_ideas
                   SET published_video_link_id = ?, status = 'published', updated_at = ?
                   WHERE analysis_run_id = ?""",
                (link_id, now, analysis_run_id),
            )
            return link_id

    def published_video_links_list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
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
                    WHERE vs.youtube_video_id = p.youtube_video_id
                    ORDER BY vs.captured_at DESC LIMIT 1
                )
                ORDER BY p.published_at DESC
                """
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
                    "youtube_metadata": _json_dict(r[24]),
                    "metadata_synced_at": r[25],
                    "ownership_state": r[26],
                    "ownership_verified": bool(r[27]),
                    "verified_channel_id": r[28],
                    "ownership_verified_at": r[29],
                }
                for r in rows
            ]
            metadata_rows = connection.execute("SELECT published_video_link_id, language, format, duration_bucket, topic_category, language_source, format_source, duration_bucket_source, topic_category_source, updated_at FROM published_video_comparable_metadata").fetchall()
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
                ORDER BY updated_at DESC
                LIMIT 1
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
                "youtube_metadata": _json_dict(row[15]),
                "metadata_synced_at": row[16],
                "ownership_state": row[17],
                "ownership_verified": bool(row[18]),
                "verified_channel_id": row[19],
                "ownership_verified_at": row[20],
            }

    def update_linked_video_metadata(self, link_id: int, metadata: dict[str, Any]) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE published_video_links
                   SET youtube_metadata_json = ?, metadata_synced_at = ?, updated_at = ?
                   WHERE id = ?""",
                (json.dumps(metadata), now, now, link_id),
            )
            return cursor.rowcount > 0

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
        for link in self.published_video_links_list():
            if link["id"] == link_id:
                return link
        return None

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
            if field == "format" and value is not None and value not in FORMAT_VALUES:
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
                new_value = (raw.strip() if isinstance(raw, str) else None) or "unknown"
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
                               completed_at = ?, source_start_date = ?, source_end_date = ?, captured_at = ?
                           WHERE id = ?""",
                        (
                            youtube_video_id, age_hours, views, watch_time_minutes,
                            avg_view_duration_seconds, avg_view_percentage, likes, comments,
                            shares, subscribers_gained, impressions, impressions_ctr,
                            snapshot_status, attempt_count, failure_reason, captured_at,
                            completed_at, source_start_date, source_end_date, captured_at,
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
        if status not in {"pending", "collecting", "empty_retryable", "failed_retryable"}:
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

    def due_snapshot_links(self, *, now: datetime | None = None, retry_cooldown_seconds: int = 0, retry_max_seconds: int | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT id, youtube_video_id, published_at, ownership_state, ownership_verified
                   FROM published_video_links
                   WHERE ownership_state = 'verified' AND ownership_verified = 1
                   ORDER BY published_at ASC, id ASC"""
            ).fetchall()
        due: list[dict[str, Any]] = []
        windows = (("24h", 24.0), ("7d", 168.0), ("28d", 672.0))
        for link_id, video_id, published_at, *_ in rows:
            try:
                parsed = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            age_hours = max(0.0, (now - parsed).total_seconds() / 3600)
            due_windows: list[str] = []
            for label, hours in windows:
                if age_hours < hours:
                    continue
                state = self.snapshot_window_state(str(video_id), label)
                if state["status"] == "complete" or not state["retry_allowed"]:
                    continue
                last = state.get("last_attempted_at")
                if retry_cooldown_seconds and last:
                    retry_delay = retry_cooldown_seconds * (2 ** max(0, int(state.get("attempt_count") or 1) - 1))
                    if retry_max_seconds:
                        retry_delay = min(retry_delay, retry_max_seconds)
                    try:
                        attempted = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                        if attempted.tzinfo is None:
                            attempted = attempted.replace(tzinfo=timezone.utc)
                        if (now - attempted).total_seconds() < retry_delay:
                            continue
                    except ValueError:
                        pass
                due_windows.append(label)
            if due_windows:
                due.append({"id": link_id, "youtube_video_id": video_id, "published_at": published_at, "age_hours": round(age_hours, 2), "due_windows": due_windows})
        return due

    def performance_snapshots(self, youtube_video_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT age_hours, views, watch_time_minutes, avg_view_duration_seconds,
                          avg_view_percentage, likes, comments, shares, subscribers_gained,
                          impressions, impressions_ctr, snapshot_window, captured_at,
                          snapshot_status, attempt_count, last_failure_reason,
                          last_attempted_at, completed_at, source_start_date, source_end_date
                   FROM video_performance_snapshots WHERE youtube_video_id = ?
                   ORDER BY captured_at ASC""",
                (youtube_video_id,),
            ).fetchall()
        keys = ("age_hours", "views", "watch_time_minutes", "avg_view_duration_seconds",
                "avg_view_percentage", "likes", "comments", "shares", "subscribers_gained",
                "impressions", "impressions_ctr", "snapshot_window", "captured_at",
                "snapshot_status", "attempt_count", "last_failure_reason",
                "last_attempted_at", "completed_at", "source_start_date", "source_end_date")
        snapshots = [dict(zip(keys, row)) for row in rows]
        for snapshot in snapshots:
            snapshot["retry_allowed"] = (
                snapshot.get("snapshot_status") != "complete"
                and int(snapshot.get("attempt_count") or 0) < _MAX_SNAPSHOT_ATTEMPTS
            )
        return snapshots

    def current_performance_snapshot(self, youtube_video_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id FROM video_performance_snapshots
                   WHERE youtube_video_id = ? AND snapshot_window = 'current'
                     AND snapshot_status = 'display_only'
                   ORDER BY captured_at DESC, id DESC LIMIT 1""",
                (youtube_video_id,),
            ).fetchone()
        if not row:
            return None
        return next(
            (
                item for item in reversed(self.performance_snapshots(youtube_video_id))
                if item.get("snapshot_window") == "current"
                and item.get("snapshot_status") == "display_only"
            ),
            None,
        )

    def completed_evidence_snapshot(
        self, youtube_video_id: str, snapshot_window: str
    ) -> dict[str, Any] | None:
        return next(
            (
                item for item in reversed(self.performance_snapshots(youtube_video_id))
                if item.get("snapshot_window") == snapshot_window
                and item.get("snapshot_status") == "complete"
            ),
            None,
        )

    def latest_performance_snapshot(self, youtube_video_id: str) -> dict[str, Any] | None:
        snapshots = self.performance_snapshots(youtube_video_id)
        return snapshots[-1] if snapshots else None

    def linked_package_report(self, run_id: int) -> dict[str, Any]:
        """Join a generated package to its uploaded metadata and measured performance."""
        run = self.history_run(run_id)
        link = self.published_video_link_by_run(run_id)
        if not run or not link:
            return {"linked": False}

        package = run.get("package") if isinstance(run.get("package"), dict) else {}
        selection = run.get("selected_package") if isinstance(run.get("selected_package"), dict) else None
        selected_package = selection.get("package") if selection and isinstance(selection.get("package"), dict) else {}
        metadata = link.get("youtube_metadata") if isinstance(link.get("youtube_metadata"), dict) else {}
        snapshots = self.performance_snapshots(str(link.get("youtube_video_id") or ""))
        current = self.current_performance_snapshot(str(link.get("youtube_video_id") or "")) or {}
        evidence: dict[str, Any] = {}
        for window in ("28d", "7d", "24h"):
            candidate = self.completed_evidence_snapshot(
                str(link.get("youtube_video_id") or ""), window
            )
            if candidate:
                evidence = candidate
                break
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
        uploaded_hashtags = _normalized_list(__import__("re").findall(r"#[A-Za-z0-9_]+", uploaded_description))

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
        like_rate = round((likes / views) * 100, 2) if views else None
        comment_rate = round((comments / views) * 100, 2) if views else None

        baseline = self._comparable_snapshot_baseline(link, evidence)
        verdict, worked, improve = _performance_diagnosis(
            age_hours=age_hours,
            views=views,
            retention=retention,
            like_rate=like_rate,
            baseline=baseline,
            title_match=_normalize_text(uploaded_title) == _normalize_text(generated_title),
            matching_tags=len(matching_tags),
            generated_tag_count=len(generated_tags),
        )

        diagnosis_policy = confidence_payload(baseline.get("sample_size", 0))
        comparable = self.comparable_metadata(int(link.get("id") or 0))
        comparable_ready = all(str(comparable.get(field) or "unknown") != "unknown" for field in COMPARABLE_FIELDS)
        try:
            retention_learning = self.retention_learning_summary(
                format_filter=str(comparable.get("format") or "").strip() or None,
                language_filter=str(comparable.get("language") or "").strip() or None,
                snapshot_window=str(evidence.get("snapshot_window") or "24h") if evidence else "24h",
            )
        except (ValueError, sqlite3.Error):
            retention_learning = {
                "status": "insufficient_evidence", "learning_allowed": False,
                "sample_size": 0, "minimum_samples": 5, "patterns": [],
                "message": "Retention learning is unavailable; no pattern is inferred.",
            }
        return {
            "linked": True,
            "link_id": link.get("id"),
            "video_id": link.get("youtube_video_id"),
            "video_url": f"https://www.youtube.com/watch?v={link.get('youtube_video_id')}",
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

    def _comparable_snapshot_baseline(self, link: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
        window = str(latest.get("snapshot_window") or "")
        if not mature_snapshot(latest):
            return {"sample_size": 0, "window": window or "none", "median_views": None, "median_retention_percentage": None}
        comparable = self.comparable_metadata(int(link.get("id") or 0))
        if any(str(comparable.get(field) or "unknown") == "unknown" for field in COMPARABLE_FIELDS):
            return {"sample_size": 0, "window": window, "median_views": None, "median_retention_percentage": None}
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT s.views, s.avg_view_percentage
                   FROM video_performance_snapshots s
                   JOIN published_video_links p ON p.youtube_video_id = s.youtube_video_id
                   JOIN published_video_comparable_metadata m ON m.published_video_link_id = p.id
                   WHERE s.snapshot_window = ? AND s.youtube_video_id != ?
                     AND s.snapshot_status = 'complete'
                     AND p.ownership_state = 'verified' AND p.ownership_verified = 1
                     AND m.format = ? AND m.language = ?
                     AND m.duration_bucket = ? AND m.topic_category = ?
                     AND s.id = (
                         SELECT x.id FROM video_performance_snapshots x
                         WHERE x.youtube_video_id = s.youtube_video_id
                           AND x.snapshot_window = s.snapshot_window
                           AND x.snapshot_status = 'complete'
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
    ) -> dict[str, Any]:
        if snapshot_window not in _SCHEDULED_WINDOWS:
            raise ValueError("Cohorts require a 24h, 7d, or 28d evidence window.")
        with self._connect() as connection:
            query = """
                SELECT p.youtube_video_id, m.format, m.language, m.duration_bucket, m.topic_category,
                       s.views, s.likes, s.avg_view_percentage,
                       m.format_source, m.language_source, m.duration_bucket_source, m.topic_category_source
                FROM published_video_links p
                JOIN published_video_comparable_metadata m ON m.published_video_link_id = p.id
                JOIN video_performance_snapshots s ON s.id = (
                    SELECT x.id FROM video_performance_snapshots x
                    WHERE x.youtube_video_id = p.youtube_video_id
                      AND x.snapshot_window = ?
                      AND x.snapshot_status = 'complete'
                    ORDER BY x.completed_at DESC, x.id DESC LIMIT 1
                )
                WHERE p.ownership_state = 'verified'
                  AND p.ownership_verified = 1
                  AND p.verified_channel_id IS NOT NULL
                  AND p.ownership_verified_at IS NOT NULL
                  AND m.format != 'unknown'
                  AND m.language != 'unknown'
            """
            params: list[Any] = [snapshot_window]
            if format_filter:
                query += " AND m.format = ?"
                params.append(format_filter)
            if language_filter:
                query += " AND m.language = ?"
                params.append(language_filter)
            if duration_bucket_filter:
                query += " AND m.duration_bucket = ?"
                params.append(duration_bucket_filter)
            if topic_category_filter:
                query += " AND m.topic_category = ?"
                params.append(topic_category_filter)

            rows = connection.execute(query, params).fetchall()
            count = len(rows)
            policy = confidence_payload(count)

            total_query = "SELECT COUNT(DISTINCT youtube_video_id) FROM published_video_links WHERE 1=1"
            total_params: list[Any] = []
            if format_filter:
                total_query += " AND format = ?"
                total_params.append(format_filter)
            if language_filter:
                total_query += " AND language = ?"
                total_params.append(language_filter)
            total_links = int(connection.execute(total_query, total_params).fetchone()[0] or 0)

            views_list = sorted([r[5] for r in rows if r[5] is not None])
            retention_list = sorted([r[7] for r in rows if r[7] is not None])
            likes_list = sorted([r[6] for r in rows if r[6] is not None])
            median_views = _median(views_list)
            median_retention = _median(retention_list)
            median_likes = _median(likes_list)

            recommendation = (
                f"Collect verified completed {snapshot_window} snapshots until at least 5 comparable videos are available."
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
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE package_experiments SET performance_after_json = ?
                   WHERE youtube_video_id = ? AND performance_after_json IS NULL
                   AND changed_at <= ?""",
                (json.dumps(after), youtube_video_id, now),
            )
        return cursor.rowcount

    def system_status(self) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                snapshot_count = connection.execute("SELECT COUNT(*) FROM video_snapshots").fetchone()[0]
                analysis_count = connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
            return {
                "database_path": self._database_path_raw,
                "database_ok": True,
                "snapshot_count": int(snapshot_count or 0),
                "analysis_count": int(analysis_count or 0),
            }
        except sqlite3.Error as exc:
            return {
                "database_path": self._database_path_raw,
                "database_ok": False,
                "snapshot_count": 0,
                "analysis_count": 0,
                "error": str(exc),
            }



    def _delta_within_window(
        self,
        rows: list[tuple[str, int]],
        current_time: datetime,
        window: timedelta,
    ) -> int | None:
        current_views = _to_int(rows[0][1])
        for captured_at, view_count in rows[1:]:
            snapshot_time = _parse_datetime(captured_at)
            if current_time - snapshot_time >= window:
                return current_views - _to_int(view_count)
        return None


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _median(values: list[float | int]) -> float | None:
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return float(values[middle])
    return round((float(values[middle - 1]) + float(values[middle])) / 2, 2)


def _json_value(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _json_dict(value: str | None) -> dict[str, Any]:
    return _json_value(value)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _normalize_text(value: str) -> str:
    import re
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


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


def _first_number(*values: Any) -> int:
    for value in values:
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return 0


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
    views: int,
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
    if baseline_policy["learning_allowed"] and median_views is not None:
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
    elif not baseline_policy["learning_allowed"]:
        verdict = "OBSERVATION ONLY — more comparable linked videos are needed"
    else:
        verdict = "ABOVE BASELINE" if median_views is not None and views >= float(median_views) else "BELOW BASELINE"
    return verdict, worked, improve


def _top_counts(values: list[Any]) -> list[Any]:
    counts: dict[Any, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return [item for item, _count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]


def _describe_trend(title_delta: float | None, opportunity_delta: float | None, total_runs: int) -> str:
    if total_runs < 6:
        return "Not enough analysis history yet to calculate a reliable trend."
    if (title_delta or 0) > 0 and (opportunity_delta or 0) > 0:
        return "Recent analyses are trending stronger than the previous window."
    if (title_delta or 0) < 0 and (opportunity_delta or 0) < 0:
        return "Recent analyses are weaker than the previous window and should be reviewed."
    return "Recent analyses are mixed versus the previous window."
