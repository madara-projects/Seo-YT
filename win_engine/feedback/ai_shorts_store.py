"""AI Shorts plans: the Google Flow prompts planned for a quote, kept beside their History run.

A plan row holds the creator's quote and the planner's whole result as JSON;
the SEO package made with it is the History run the row points at, so the
published Short is linked to that run like any other package.

Plans are local-only. Cloud sync carries the History run (the package, marked
``source_page: "ai_shorts"``), never the plan, so another device sees the
package in History but not the Flow prompts. Deleting the run deletes its plan
(``ON DELETE CASCADE``), and deleting a plan goes through the History deletion
path so the run's cloud tombstone is queued like any other deletion.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from win_engine.feedback.history_store import HistoryStore

SOURCE_PAGE = "ai_shorts"
_LIST_LIMIT = 100
# Fixes the planner made by itself, which plans saved before checks had "adjustments" listed among the warnings.
_ADJUSTMENT_RE = re.compile(
    r"^Part \d+: (?:added |trimmed from \d+ to \d+ words$)|^Part \d+: .*a lone figure was named\.$",
)


class AiShortsStore:
    def __init__(self, history: HistoryStore) -> None:
        self.history = history

    def save_plan(
        self,
        *,
        analysis_run_id: int,
        quote: str,
        language: str,
        parts: int,
        plan: dict[str, Any],
        package: dict[str, Any],
    ) -> int:
        """Insert the plan and mark its History run as this plan's package, in one transaction.

        The run's payload gains ``source_page`` and an ``ai_shorts`` block that
        names the plan, so History can tell the package apart and find the
        plan again. The two writes commit together: a plan without its marker,
        or a marker naming a plan that was never written, is never left behind.
        """
        now = datetime.now(timezone.utc).isoformat()
        generation_source = str(plan.get("generation_source") or "fallback")
        with self.history._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO ai_short_plans
                       (analysis_run_id, quote, language, parts, plan_json, generation_source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(analysis_run_id), quote, language, int(parts), json.dumps(plan), generation_source, now, now),
            )
            plan_id = int(cursor.lastrowid)
            payload = {
                **package,
                "source_page": SOURCE_PAGE,
                "ai_shorts": {
                    "plan_id": plan_id,
                    "parts": int(parts),
                    "total_seconds": plan.get("total_seconds"),
                    "language": language,
                    "generation_source": generation_source,
                },
            }
            # The run's title column is what History lists; it follows the
            # package's final title, so the list and the package never disagree.
            title = str(package.get("title") or "").strip() or None
            connection.execute(
                "UPDATE analysis_runs SET payload_json = ?, title = COALESCE(?, title) WHERE id = ?",
                (json.dumps(payload), title, int(analysis_run_id)),
            )
        return plan_id

    def plans(self, limit: int = 20) -> list[dict[str, Any]]:
        """Saved plans, newest first, without the prompts: enough for a list row."""
        with self.history._connect() as connection:
            rows = connection.execute(
                """SELECT p.id, p.analysis_run_id, p.quote, p.language, p.parts, p.plan_json,
                          p.generation_source, p.created_at, a.title
                   FROM ai_short_plans p JOIN analysis_runs a ON a.id = p.analysis_run_id
                   ORDER BY p.created_at DESC, p.id DESC LIMIT ?""",
                (max(1, min(int(limit), _LIST_LIMIT)),),
            ).fetchall()
        return [
            {
                "id": int(row[0]),
                "analysis_run_id": int(row[1]),
                "quote": row[2],
                "language": row[3],
                "parts": int(row[4]),
                "total_seconds": _plan_json(row[5]).get("total_seconds"),
                "generation_source": row[6],
                "package_title": row[8],
                "created_at": row[7],
            }
            for row in rows
        ]

    def plan(self, plan_id: int) -> dict[str, Any] | None:
        """One plan as the generate route answered it: ids and time, the planner's keys, then the package."""
        with self.history._connect() as connection:
            row = connection.execute(
                """SELECT p.id, p.analysis_run_id, p.created_at, p.plan_json, a.payload_json
                   FROM ai_short_plans p JOIN analysis_runs a ON a.id = p.analysis_run_id
                   WHERE p.id = ?""",
                (int(plan_id),),
            ).fetchone()
        if not row:
            return None
        package = _plan_json(row[4])
        stored = _plan_json(row[3])
        if isinstance(stored.get("checks"), dict):
            stored["checks"] = _with_adjustments(stored["checks"])
        return {
            "id": int(row[0]),
            "analysis_run_id": int(row[1]),
            "created_at": row[2],
            **stored,
            "package": package,
        }

    def delete_plan(self, plan_id: int) -> bool:
        """Delete a plan with its History run; False when there is no such plan.

        The run goes through HistoryStore's deletion so a synced package gets
        its cloud tombstone and a linked idea is released; the plan row follows
        the run by cascade. A plan whose run is already gone is removed alone.
        """
        with self.history._connect() as connection:
            row = connection.execute(
                "SELECT analysis_run_id FROM ai_short_plans WHERE id = ?", (int(plan_id),)
            ).fetchone()
        if not row:
            return False
        if self.history.delete_analysis_run(int(row[0])):
            return True
        with self.history._connect() as connection:
            connection.execute("DELETE FROM ai_short_plans WHERE id = ?", (int(plan_id),))
        return True

    def recent_scenes(self, limit: int = 10) -> list[str]:
        """The scenes of the newest saved plans, so the planner can choose a different one.

        A scene is the creative direction's when the plan has one, else its
        shots' titles. Sixteen quotes in a row came out as about five scenes.
        """
        with self.history._connect() as connection:
            rows = connection.execute(
                "SELECT plan_json FROM ai_short_plans ORDER BY created_at DESC, id DESC LIMIT ?",
                (max(1, min(int(limit), _LIST_LIMIT)),),
            ).fetchall()
        scenes: list[str] = []
        for (value,) in rows:
            plan = _plan_json(value)
            direction = plan.get("creative_direction") if isinstance(plan.get("creative_direction"), dict) else {}
            scene = " ".join(str(direction.get("scene") or "").split())
            if not scene:
                titles = [str(shot.get("title") or "").strip() for shot in plan.get("shots") or []
                          if isinstance(shot, dict) and str(shot.get("title") or "").strip()]
                scene = "; ".join(dict.fromkeys(titles))
            if scene and scene[:300] not in scenes:
                scenes.append(scene[:300])
        return scenes


def _with_adjustments(checks: dict[str, Any]) -> dict[str, Any]:
    """The checks with the planner's own fixes under ``adjustments`` and only what the creator should look at in ``warnings``."""
    warnings = checks["warnings"] if isinstance(checks.get("warnings"), list) else []
    adjustments = checks["adjustments"] if isinstance(checks.get("adjustments"), list) else []
    moved = [item for item in warnings if isinstance(item, str) and _ADJUSTMENT_RE.search(item)]
    result = {**checks, "adjustments": list(dict.fromkeys(
        item for item in [*adjustments, *moved] if isinstance(item, str)
    ))}
    if moved:
        result["warnings"] = [item for item in warnings if item not in moved]
    return result


def _plan_json(value: Any) -> dict[str, Any]:
    """A stored JSON object, or an empty one when the column is empty or damaged."""
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
