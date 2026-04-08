from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class HistoryStore:
    """SQLite-backed snapshot store for repeated video metric collection."""

    def __init__(self, database_path: str) -> None:
        self._database_path = Path(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    published_at TEXT,
                    view_count INTEGER DEFAULT 0,
                    like_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    subscriber_count INTEGER DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_video_snapshots_video_time
                ON video_snapshots(video_id, captured_at)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    intent TEXT,
                    content_angle TEXT,
                    title TEXT,
                    title_score REAL DEFAULT 0,
                    retention_risk TEXT,
                    opportunity_label TEXT,
                    opportunity_score REAL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at
                ON analysis_runs(created_at)
                """
            )

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
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_runs (
                    query, created_at, intent, content_angle, title,
                    title_score, retention_risk, opportunity_label, opportunity_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

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
                SELECT title, title_score, opportunity_score, created_at
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
                    "title": row[0],
                    "title_score": round(float(row[1] or 0), 2),
                    "opportunity_score": round(float(row[2] or 0), 2),
                    "created_at": row[3],
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

    def system_status(self) -> dict[str, Any]:
        try:
            with self._connect() as connection:
                snapshot_count = connection.execute("SELECT COUNT(*) FROM video_snapshots").fetchone()[0]
                analysis_count = connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
            return {
                "database_path": str(self._database_path),
                "database_ok": True,
                "snapshot_count": int(snapshot_count or 0),
                "analysis_count": int(analysis_count or 0),
            }
        except sqlite3.Error as exc:
            return {
                "database_path": str(self._database_path),
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
