from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class HistoryStore:
    """SQLite-backed snapshot store for repeated video metric collection."""

    def __init__(self, database_path: str) -> None:
        self._database_path_raw = database_path
        self._database_path = Path(database_path) if database_path != ":memory:" else None
        self._memory_connection: sqlite3.Connection | None = None
        if database_path == ":memory:":
            self._memory_connection = sqlite3.connect(":memory:", check_same_thread=False)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self._memory_connection is not None:
            return self._memory_connection
        if self._database_path is None:
            raise RuntimeError("Database path is unavailable.")
        connection = sqlite3.connect(self._database_path, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
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
                CREATE TABLE IF NOT EXISTS owned_video_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    published_at TEXT,
                    title TEXT,
                    views INTEGER DEFAULT 0,
                    watch_minutes REAL DEFAULT 0,
                    average_view_duration REAL DEFAULT 0,
                    average_view_percentage REAL DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    subscribers_gained INTEGER DEFAULT 0
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_owned_video_snapshots_video_time ON owned_video_snapshots(video_id, captured_at)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS youtube_channel_connection (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    encrypted_refresh_token TEXT NOT NULL,
                    channel_id TEXT,
                    channel_title TEXT,
                    connected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS youtube_channel_syncs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    synced_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
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
                    opportunity_score REAL DEFAULT 0,
                    payload_json TEXT
                )
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(analysis_runs)").fetchall()}
            if "payload_json" not in columns:
                connection.execute("ALTER TABLE analysis_runs ADD COLUMN payload_json TEXT")
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

    def history_runs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Return saved packages in newest-first order without the large payload."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, title, opportunity_score, title_score, query, payload_json
                FROM analysis_runs ORDER BY created_at DESC LIMIT ? OFFSET ?
                """
                , (max(1, min(limit, 100)), max(0, offset))
            ).fetchall()
        return [
            {
                "id": row[0], "created_at": row[1], "title": row[2],
                "opportunity_score": round(float(row[3] or 0), 2),
                "title_score": round(float(row[4] or 0), 2), "query": row[5],
                "has_full_package": bool(row[6]),
            }
            for row in rows
        ]

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
        return {
            "id": row[0], "created_at": row[1], "query": row[2], "intent": row[3],
            "content_angle": row[4], "title": row[5], "title_score": round(float(row[6] or 0), 2),
            "retention_risk": row[7], "opportunity_label": row[8],
            "opportunity_score": round(float(row[9] or 0), 2), "package": package,
        }

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
        """Aggregate metrics of creator's video snapshots recorded in database."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT SUM(views), SUM(likes), COUNT(*), MAX(views)
                FROM owned_video_snapshots
                """
            ).fetchone()
            latest = connection.execute(
                """
                SELECT title, views, likes, captured_at
                FROM owned_video_snapshots
                ORDER BY captured_at DESC
                LIMIT 5
                """
            ).fetchall()
        total_views = int(row[0] or 0) if row and row[0] is not None else 0
        total_likes = int(row[1] or 0) if row and row[1] is not None else 0
        video_count = int(row[2] or 0) if row and row[2] is not None else 0
        max_views = int(row[3] or 0) if row and row[3] is not None else 0

        return {
            "total_views": total_views,
            "total_likes": total_likes,
            "video_count": video_count,
            "max_views": max_views,
            "videos": [
                {
                    "title": r[0],
                    "views": r[1],
                    "likes": r[2],
                    "captured_at": r[3],
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

    def reset_database(self) -> None:
        """Clear all historical test data for a fresh workspace setup."""
        with self._connect() as connection:
            connection.execute("DELETE FROM video_snapshots")
            connection.execute("DELETE FROM owned_video_snapshots")
            connection.execute("DELETE FROM youtube_channel_syncs")
            connection.execute("DELETE FROM analysis_runs")

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
