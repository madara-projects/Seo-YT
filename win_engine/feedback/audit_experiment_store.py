"""Persistence and orchestration for Phase 8 audits and structured experiments."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from win_engine.analysis.audit_experiment import AUDIT_RULE_VERSION, EXPERIMENT_RULE_VERSION, build_published_audit, compare_experiment
from win_engine.feedback.history_store import HistoryStore


EXPERIMENT_STATUSES = {"draft", "planned", "active", "paused", "completed", "cancelled", "inconclusive"}
STATUS_TRANSITIONS = {
    "draft": {"planned", "cancelled"}, "planned": {"active", "paused", "cancelled"},
    "active": {"paused", "completed", "inconclusive", "cancelled"},
    "paused": {"active", "completed", "inconclusive", "cancelled"},
    "completed": set(), "cancelled": set(), "inconclusive": set(),
}


class AuditExperimentStore:
    def __init__(self, history: HistoryStore):
        self.history = history

    def audit_candidates(self, *, evidence_state: str | None = None, audit_state: str | None = None) -> list[dict[str, Any]]:
        with self.history._connect() as connection:
            audit_rows = connection.execute(
                """SELECT a.published_video_link_id, a.id, a.captured_at, a.summary_state
                   FROM published_video_audits a WHERE a.id = (
                       SELECT x.id FROM published_video_audits x
                       WHERE x.published_video_link_id=a.published_video_link_id
                       ORDER BY x.captured_at DESC,x.id DESC LIMIT 1)"""
            ).fetchall()
            idea_rows = connection.execute("SELECT published_video_link_id,id,topic FROM content_ideas WHERE published_video_link_id IS NOT NULL").fetchall()
        audits = {row[0]: {"audit_id": row[1], "audit_captured_at": row[2], "audit_state": row[3]} for row in audit_rows}
        ideas = {row[0]: {"id": row[1], "topic": row[2]} for row in idea_rows}
        result = []
        for link in self.history.published_video_links_list():
            latest = link.get("latest_performance") or {}
            state = "mature" if latest.get("snapshot_window") in {"24h", "7d", "28d"} else "observed" if latest else "unavailable"
            item = {**link, **audits.get(link["id"], {"audit_id": None, "audit_captured_at": None, "audit_state": "not_run"}), "idea": ideas.get(link["id"]), "evidence_state": state, "selection_state": "selected" if self.history.package_selection(int(link["analysis_run_id"])) else "unknown"}
            if evidence_state and state != evidence_state:
                continue
            if audit_state and item["audit_state"] != audit_state:
                continue
            result.append(item)
        return result

    def refresh_audit(self, link_id: int) -> dict[str, Any] | None:
        context = self._audit_context(link_id)
        if not context:
            return None
        audit = build_published_audit(context)
        captured_at = datetime.now(timezone.utc).isoformat()
        with self.history._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO published_video_audits
                   (published_video_link_id,analysis_run_id,captured_at,summary_state,audit_json,provenance_version)
                   VALUES (?,?,?,?,?,?)""",
                (link_id, context["run"]["id"], captured_at, audit["summary"]["state"], json.dumps(audit), AUDIT_RULE_VERSION),
            )
            audit_id = int(cursor.lastrowid)
        return {"id": audit_id, "captured_at": captured_at, **audit}

    def audit(self, link_id: int, audit_id: int | None = None) -> dict[str, Any] | None:
        with self.history._connect() as connection:
            if audit_id is None:
                row = connection.execute(
                    """SELECT id,captured_at,audit_json FROM published_video_audits
                       WHERE published_video_link_id=? ORDER BY captured_at DESC,id DESC LIMIT 1""", (link_id,)
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT id,captured_at,audit_json FROM published_video_audits WHERE id=? AND published_video_link_id=?", (audit_id, link_id)
                ).fetchone()
        if not row:
            return None
        return {"id": row[0], "captured_at": row[1], **_object(row[2])}

    def audit_versions(self, link_id: int) -> list[dict[str, Any]]:
        with self.history._connect() as connection:
            rows = connection.execute(
                "SELECT id,captured_at,summary_state,provenance_version FROM published_video_audits WHERE published_video_link_id=? ORDER BY captured_at DESC,id DESC", (link_id,)
            ).fetchall()
        return [{"id": r[0], "captured_at": r[1], "summary_state": r[2], "provenance_version": r[3]} for r in rows]

    def _audit_context(self, link_id: int) -> dict[str, Any] | None:
        link = self.history.published_video_link(link_id)
        if not link:
            return None
        run = self.history.history_run(int(link["analysis_run_id"]))
        if not run:
            return None
        published_at = str(link.get("published_at") or "9999")
        with self.history._connect() as connection:
            idea_row = connection.execute(
                """SELECT id,topic,notes,format,language,region,visual_or_background,on_screen_text,
                          target_duration_seconds,emotion_or_intent,search_angle,browse_angle,audience_angle,status
                   FROM content_ideas WHERE analysis_run_id=? ORDER BY id DESC LIMIT 1""", (run["id"],)
            ).fetchone()
            idea = None
            idea_research = None
            demand = None
            if idea_row:
                idea = {"id": idea_row[0], "topic": idea_row[1], "notes": idea_row[2], "format": idea_row[3], "language": idea_row[4], "region": idea_row[5], "visual_or_background": idea_row[6], "on_screen_text": idea_row[7], "target_duration_seconds": idea_row[8], "emotion_or_intent": idea_row[9], "search_angle": idea_row[10], "browse_angle": idea_row[11], "audience_angle": idea_row[12], "status": idea_row[13], "provenance": "saved_content_idea"}
                research_row = connection.execute("SELECT id,captured_at,evidence_json FROM content_idea_research_snapshots WHERE content_idea_id=? AND captured_at<=? ORDER BY captured_at DESC,id DESC LIMIT 1", (idea_row[0], published_at)).fetchone()
                if research_row:
                    idea_research = {"id": research_row[0], "captured_at": research_row[1], "evidence": _object(research_row[2]), "provenance": "saved_pre_publish_idea_research"}
                demand_row = connection.execute("SELECT id,captured_at,classification,evidence_json FROM demand_research_snapshots WHERE idea_id=? AND captured_at<=? ORDER BY captured_at DESC,id DESC LIMIT 1", (idea_row[0], published_at)).fetchone()
                if demand_row:
                    demand = {"id": demand_row[0], "captured_at": demand_row[1], "classification": demand_row[2], "evidence": _object(demand_row[3]), "provenance": "saved_pre_publish_demand_research"}
        snapshots = self.history.performance_snapshots(str(link["youtube_video_id"]))
        report = self.history.linked_package_report(run["id"])
        comparable = self.history.comparable_metadata(link_id) or {}
        mature_window = next((window for window in ("28d", "7d", "24h") if self.history.completed_evidence_snapshot(str(link["youtube_video_id"]), window)), "24h")
        try:
            cohort = self.history.cohort_analytics(
                format_filter=None if comparable.get("format") in {None, "unknown"} else comparable.get("format"),
                language_filter=None if comparable.get("language") in {None, "unknown"} else comparable.get("language"),
                duration_bucket_filter=None if comparable.get("duration_bucket") in {None, "unknown"} else comparable.get("duration_bucket"),
                topic_category_filter=None if comparable.get("topic_category") in {None, "unknown"} else comparable.get("topic_category"),
                snapshot_window=mature_window,
            )
        except (ValueError, TypeError):
            cohort = {"sample_size": 0, "learning_allowed": False, "confidence_label": "Collecting evidence"}
        return {"run": run, "link": link, "snapshots": snapshots, "linked_report": report, "comparable": comparable, "cohort": cohort, "idea": idea, "idea_research": idea_research, "demand_research": demand}

    def create_experiment(self, values: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.history._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO experiments
                   (name,description,hypothesis,mode,status,variable,variable_category,control_definition,
                    variant_definition,success_metric,secondary_metrics_json,target_sample_size,
                    minimum_sample_size,observation_window,start_date,end_date,notes,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (values["name"], values.get("description", ""), values["hypothesis"], values.get("mode", "controlled"), values.get("status", "draft"), values["variable"], values.get("variable_category") or values["variable"], values["control_definition"], values["variant_definition"], values.get("success_metric", "views"), json.dumps(values.get("secondary_metrics") or []), values.get("target_sample_size"), values.get("minimum_sample_size", 5), values.get("observation_window", "24h"), values.get("start_date"), values.get("end_date"), values.get("notes", ""), now, now),
            )
            experiment_id = int(cursor.lastrowid)
        return self.experiment(experiment_id) or {}

    def experiments(self, status: str | None = None, mode: str | None = None) -> list[dict[str, Any]]:
        query, params = "SELECT id FROM experiments WHERE 1=1", []
        if status:
            query += " AND status=?"; params.append(status)
        if mode:
            query += " AND mode=?"; params.append(mode)
        query += " ORDER BY updated_at DESC,id DESC"
        with self.history._connect() as connection:
            ids = [int(row[0]) for row in connection.execute(query, params).fetchall()]
        return [item for experiment_id in ids if (item := self.experiment(experiment_id))]

    def experiment(self, experiment_id: int) -> dict[str, Any] | None:
        with self.history._connect() as connection:
            row = connection.execute(
                """SELECT id,name,description,hypothesis,mode,status,variable,variable_category,
                          control_definition,variant_definition,success_metric,secondary_metrics_json,
                          target_sample_size,minimum_sample_size,observation_window,start_date,end_date,
                          notes,created_at,updated_at FROM experiments WHERE id=?""", (experiment_id,)
            ).fetchone()
            if not row:
                return None
            assignment_rows = connection.execute(
                """SELECT a.id,a.published_video_link_id,a.role,a.assigned_at,a.notes,
                          p.youtube_video_id,p.published_at,COALESCE(json_extract(p.youtube_metadata_json,'$.title'),p.selected_title)
                   FROM experiment_video_assignments a JOIN published_video_links p ON p.id=a.published_video_link_id
                   WHERE a.experiment_id=? ORDER BY a.role,a.assigned_at""", (experiment_id,)
            ).fetchall()
            result_row = connection.execute("SELECT id,captured_at,result_json FROM experiment_result_snapshots WHERE experiment_id=? ORDER BY captured_at DESC,id DESC LIMIT 1", (experiment_id,)).fetchone()
        item = {"id": row[0], "name": row[1], "description": row[2], "hypothesis": row[3], "mode": row[4], "status": row[5], "variable": row[6], "variable_category": row[7], "control_definition": row[8], "variant_definition": row[9], "success_metric": row[10], "secondary_metrics": _list(row[11]), "target_sample_size": row[12], "minimum_sample_size": row[13], "observation_window": row[14], "start_date": row[15], "end_date": row[16], "notes": row[17], "created_at": row[18], "updated_at": row[19]}
        item["assignments"] = [{"id": r[0], "published_video_link_id": r[1], "role": r[2], "assigned_at": r[3], "notes": r[4], "youtube_video_id": r[5], "published_at": r[6], "title": r[7]} for r in assignment_rows]
        item["latest_result"] = ({"id": result_row[0], "captured_at": result_row[1], **_object(result_row[2])} if result_row else None)
        item["assignment_counts"] = {role: sum(a["role"] == role for a in item["assignments"]) for role in ("control", "variant", "observational_reference")}
        return item

    def update_experiment(self, experiment_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        current = self.experiment(experiment_id)
        if not current:
            return None
        if "status" in values and values["status"] != current["status"] and values["status"] not in STATUS_TRANSITIONS[current["status"]]:
            raise ValueError(f"Invalid experiment transition from {current['status']} to {values['status']}.")
        allowed = {"name", "description", "hypothesis", "status", "notes", "start_date", "end_date", "target_sample_size"}
        changes = {key: value for key, value in values.items() if key in allowed}
        if not changes:
            raise ValueError("Provide at least one supported experiment update.")
        changes["updated_at"] = datetime.now(timezone.utc).isoformat()
        with self.history._connect() as connection:
            connection.execute("UPDATE experiments SET " + ",".join(f"{key}=?" for key in changes) + " WHERE id=?", (*changes.values(), experiment_id))
        return self.experiment(experiment_id)

    def assign_video(self, experiment_id: int, link_id: int, role: str, notes: str = "") -> dict[str, Any]:
        experiment = self.experiment(experiment_id)
        if not experiment:
            raise LookupError("Experiment not found.")
        if experiment["status"] in {"completed", "cancelled", "inconclusive"}:
            raise ValueError("Closed experiments cannot accept new video assignments.")
        link = self.history.published_video_link(link_id)
        if not link or not link.get("ownership_verified"):
            raise ValueError("Only a verified linked published video can be assigned.")
        if experiment["mode"] == "controlled" and role == "observational_reference":
            raise ValueError("A controlled experiment accepts only explicit control or variant assignments.")
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self.history._connect() as connection:
                connection.execute("INSERT INTO experiment_video_assignments (experiment_id,published_video_link_id,role,assigned_at,notes) VALUES (?,?,?,?,?)", (experiment_id, link_id, role, now, notes))
                connection.execute("UPDATE experiments SET updated_at=? WHERE id=?", (now, experiment_id))
        except Exception as exc:
            if "UNIQUE constraint" in str(exc):
                raise ValueError("This video is already assigned to the experiment.") from exc
            raise
        return self.experiment(experiment_id) or {}

    def remove_assignment(self, experiment_id: int, assignment_id: int) -> bool:
        with self.history._connect() as connection:
            cursor = connection.execute("DELETE FROM experiment_video_assignments WHERE id=? AND experiment_id=?", (assignment_id, experiment_id))
        return cursor.rowcount > 0

    def refresh_experiment_result(self, experiment_id: int) -> dict[str, Any] | None:
        experiment = self.experiment(experiment_id)
        if not experiment:
            return None
        assignments = []
        for assignment in experiment["assignments"]:
            item = dict(assignment)
            item["evidence_snapshot"] = self.history.completed_evidence_snapshot(item["youtube_video_id"], experiment["observation_window"])
            assignments.append(item)
        result = compare_experiment(experiment, assignments)
        captured_at = datetime.now(timezone.utc).isoformat()
        with self.history._connect() as connection:
            cursor = connection.execute("INSERT INTO experiment_result_snapshots (experiment_id,captured_at,result_state,result_json,provenance_version) VALUES (?,?,?,?,?)", (experiment_id, captured_at, result["state"], json.dumps(result), EXPERIMENT_RULE_VERSION))
        return {"id": int(cursor.lastrowid), "captured_at": captured_at, **result}

    def result_versions(self, experiment_id: int) -> list[dict[str, Any]]:
        with self.history._connect() as connection:
            rows = connection.execute("SELECT id,captured_at,result_state,provenance_version FROM experiment_result_snapshots WHERE experiment_id=? ORDER BY captured_at DESC,id DESC", (experiment_id,)).fetchall()
        return [{"id": r[0], "captured_at": r[1], "result_state": r[2], "provenance_version": r[3]} for r in rows]


def _object(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except (TypeError, json.JSONDecodeError):
        return []
