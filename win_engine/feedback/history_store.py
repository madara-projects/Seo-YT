from __future__ import annotations

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
            # Phase 9: Performance Tracking Tables
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    tags TEXT,
                    hashtags TEXT,
                    published_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    view_count INTEGER DEFAULT 0,
                    like_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    watch_time_hours REAL DEFAULT 0,
                    click_through_rate REAL DEFAULT 0,
                    average_view_duration_percent REAL DEFAULT 0,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(video_id) REFERENCES video_uploads(video_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ab_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    variant_a TEXT,
                    variant_b TEXT,
                    variant_a_views INTEGER DEFAULT 0,
                    variant_b_views INTEGER DEFAULT 0,
                    variant_a_ctr REAL DEFAULT 0,
                    variant_b_ctr REAL DEFAULT 0,
                    test_start TEXT,
                    test_end TEXT,
                    status TEXT DEFAULT 'RUNNING'
                )
                """
            )
            # Phase 10: Execution Engine Tables
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    package_id TEXT NOT NULL,
                    metadata TEXT,
                    schedule_time TEXT NOT NULL,
                    status TEXT DEFAULT 'SCHEDULED',
                    created_at TEXT NOT NULL,
                    executed_at TEXT
                )
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

    # === PHASE 8: PATTERN MEMORY SYSTEM ===

    def performance_correlation(self, days_back: int = 30) -> dict[str, Any]:
        """Link analysis recommendations to actual YouTube performance."""
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

        with self._connect() as connection:
            # Get title recommendations and their performance
            correlation_rows = connection.execute(
                """
                SELECT
                    ar.title,
                    ar.title_score,
                    ar.content_angle,
                    ar.opportunity_label,
                    ar.opportunity_score,
                    COUNT(DISTINCT vs.video_id) as snapshot_count,
                    AVG(CAST(vs.view_count AS REAL)) as avg_views,
                    AVG(CAST(vs.like_count AS REAL)) as avg_likes,
                    AVG(CAST(vs.comment_count AS REAL)) as avg_comments
                FROM analysis_runs ar
                LEFT JOIN video_snapshots vs ON ar.query LIKE '%' || vs.query || '%'
                    AND vs.captured_at > ?
                WHERE ar.created_at > ?
                GROUP BY ar.id
                ORDER BY ar.created_at DESC
                LIMIT 10
                """,
                (cutoff_date, cutoff_date),
            ).fetchall()

        correlations = []
        for row in correlation_rows:
            title, title_score, angle, opportunity_label, opportunity_score, snapshot_count, avg_views, avg_likes, avg_comments = row
            if snapshot_count > 0:
                correlations.append(
                    {
                        "title": title,
                        "title_score": round(float(title_score or 0), 2),
                        "content_angle": angle,
                        "opportunity_label": opportunity_label,
                        "opportunity_score": round(float(opportunity_score or 0), 2),
                        "performance": {
                            "snapshot_count": snapshot_count,
                            "average_views": int(avg_views or 0),
                            "average_likes": int(avg_likes or 0),
                            "average_comments": int(avg_comments or 0),
                            "engagement_rate": round(
                                ((avg_likes or 0) + (avg_comments or 0)) / max(avg_views or 1, 1), 4
                            ),
                        },
                    }
                )

        return {
            "period_days": days_back,
            "correlated_runs": len(correlations),
            "correlations": sorted(correlations, key=lambda x: x["performance"]["average_views"], reverse=True),
        }

    def success_formula_recognition(self) -> dict[str, Any]:
        """Identify creator-specific success patterns."""
        with self._connect() as connection:
            # Angle + Opportunity combination analysis
            formula_rows = connection.execute(
                """
                SELECT
                    content_angle,
                    opportunity_label,
                    COUNT(*) as frequency,
                    AVG(title_score) as avg_title_score,
                    AVG(opportunity_score) as avg_opportunity_score
                FROM analysis_runs
                WHERE content_angle IS NOT NULL AND opportunity_label IS NOT NULL
                GROUP BY content_angle, opportunity_label
                ORDER BY frequency DESC, avg_title_score DESC
                LIMIT 5
                """
            ).fetchall()

            # High-performing angle analysis
            angle_performance = connection.execute(
                """
                SELECT
                    content_angle,
                    COUNT(*) as runs,
                    AVG(title_score) as avg_title_score,
                    MIN(opportunity_score) as min_opp_score,
                    MAX(opportunity_score) as max_opp_score
                FROM analysis_runs
                WHERE content_angle IS NOT NULL
                GROUP BY content_angle
                ORDER BY avg_title_score DESC
                LIMIT 3
                """
            ).fetchall()

        formulas = []
        for row in formula_rows:
            angle, opportunity_label, frequency, avg_title, avg_opportunity = row
            formulas.append(
                {
                    "angle": angle,
                    "typical_opportunity": opportunity_label,
                    "frequency": frequency,
                    "avg_title_score": round(float(avg_title or 0), 2),
                    "avg_opportunity_score": round(float(avg_opportunity or 0), 2),
                }
            )

        top_angles = []
        for row in angle_performance:
            angle, runs, avg_title, min_opp, max_opp = row
            top_angles.append(
                {
                    "angle": angle,
                    "runs": runs,
                    "avg_title_score": round(float(avg_title or 0), 2),
                    "opportunity_range": (int(min_opp or 0), int(max_opp or 0)),
                }
            )

        return {
            "top_success_formulas": formulas,
            "strongest_angles": top_angles,
            "observation": (
                f"Your top formula is '{formulas[0]['angle']}' paired with '{formulas[0]['typical_opportunity']}' "
                f"({formulas[0]['frequency']} times, {formulas[0]['avg_title_score']} avg title score)."
                if formulas
                else "Analyze more videos to identify success patterns."
            ),
        }

    def trend_analysis(self, window_days: int = 30) -> dict[str, Any]:
        """Analyze trends in title scores, opportunity scores, and velocity."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

        with self._connect() as connection:
            # Daily title score trend
            title_trend = connection.execute(
                """
                SELECT
                    DATE(created_at) as day,
                    AVG(title_score) as avg_title_score,
                    COUNT(*) as count
                FROM analysis_runs
                WHERE created_at > ?
                GROUP BY DATE(created_at)
                ORDER BY day ASC
                """,
                (cutoff,),
            ).fetchall()

            # Weekly opportunity score trend
            opp_trend = connection.execute(
                """
                SELECT
                    DATE(created_at) as day,
                    AVG(opportunity_score) as avg_opp_score,
                    COUNT(*) as count
                FROM analysis_runs
                WHERE created_at > ?
                GROUP BY DATE(created_at)
                ORDER BY day ASC
                """,
                (cutoff,),
            ).fetchall()

            # Video velocity by topic
            velocity_rows = connection.execute(
                """
                SELECT
                    query,
                    COUNT(*) as snapshot_count,
                    MAX(captured_at) as latest_capture,
                    AVG(view_count) as avg_views
                FROM video_snapshots
                WHERE captured_at > ?
                GROUP BY query
                ORDER BY snapshot_count DESC
                LIMIT 5
                """,
                (cutoff,),
            ).fetchall()

        title_scores = [round(float(row[1] or 0), 2) for row in title_trend]
        opp_scores = [round(float(row[1] or 0), 2) for row in opp_trend]

        # Calculate trend direction
        title_trend_direction = "improving" if len(title_scores) > 1 and title_scores[-1] > title_scores[0] else "declining"
        opp_trend_direction = "improving" if len(opp_scores) > 1 and opp_scores[-1] > opp_scores[0] else "declining"

        velocities = [
            {
                "query": row[0],
                "total_snapshots": row[1],
                "latest_capture": row[2],
                "average_views": int(row[3] or 0),
            }
            for row in velocity_rows
        ]

        return {
            "window_days": window_days,
            "title_score_trend": {
                "direction": title_trend_direction,
                "daily_samples": title_scores,
                "trend_line": round(title_scores[-1] - title_scores[0], 2) if title_scores else 0,
            },
            "opportunity_score_trend": {
                "direction": opp_trend_direction,
                "daily_samples": opp_scores,
                "trend_line": round(opp_scores[-1] - opp_scores[0], 2) if opp_scores else 0,
            },
            "video_velocity": velocities,
        }

    def memory_persistence(self) -> dict[str, Any]:
        """Get comprehensive pattern memory for long-term retention and learning."""
        with self._connect() as connection:
            # Master patterns - what works consistently
            master_patterns = connection.execute(
                """
                SELECT
                    content_angle,
                    COUNT(*) as occurrences,
                    ROUND(AVG(title_score), 2) as avg_score,
                    ROUND(AVG(opportunity_score), 2) as avg_opp,
                    GROUP_CONCAT(DISTINCT opportunity_label) as typical_labels
                FROM analysis_runs
                WHERE content_angle IS NOT NULL
                GROUP BY content_angle
                HAVING COUNT(*) >= 2
                ORDER BY ROUND(AVG(title_score), 2) DESC
                LIMIT 5
                """
            ).fetchall()

            # High-signal titles (best performers)
            best_titles = connection.execute(
                """
                SELECT title, title_score, opportunity_score, created_at
                FROM analysis_runs
                WHERE title_score > 8.0
                ORDER BY title_score DESC
                LIMIT 10
                """
            ).fetchall()

            # Risk patterns to avoid
            risk_patterns = connection.execute(
                """
                SELECT
                    retention_risk,
                    COUNT(*) as frequency,
                    AVG(title_score) as avg_title_score
                FROM analysis_runs
                WHERE retention_risk IS NOT NULL
                GROUP BY retention_risk
                ORDER BY frequency DESC
                """
            ).fetchall()

            # Create timestamp
            storage_date = datetime.now(timezone.utc).isoformat()

        patterns = {
            "master_patterns": [
                {
                    "angle": row[0],
                    "occurrences": row[1],
                    "avg_title_score": row[2],
                    "avg_opportunity_score": row[3],
                    "typical_opportunity_labels": row[4],
                }
                for row in master_patterns
            ],
            "high_signal_titles": [
                {
                    "title": row[0],
                    "title_score": float(row[1]),
                    "opportunity_score": float(row[2]),
                    "date": row[3],
                }
                for row in best_titles
            ],
            "risk_patterns_to_avoid": [
                {
                    "risk_type": row[0],
                    "frequency": row[1],
                    "avg_title_score": round(float(row[2] or 0), 2),
                }
                for row in risk_patterns
            ],
            "persistence_date": storage_date,
        }

        return patterns

    def creator_baseline(self) -> dict[str, Any]:
        """Get personalized baseline metrics for this creator."""
        with self._connect() as connection:
            overall_stats = connection.execute(
                """
                SELECT
                    COUNT(*) as total_videos,
                    ROUND(AVG(title_score), 2) as baseline_title_score,
                    ROUND(AVG(opportunity_score), 2) as baseline_opportunity_score,
                    ROUND(MIN(title_score), 2) as lowest_title_score,
                    ROUND(MAX(title_score), 2) as highest_title_score
                FROM analysis_runs
                """
            ).fetchone()

            monthly_comparison = connection.execute(
                """
                SELECT
                    strftime('%Y-%m', created_at) as month,
                    COUNT(*) as video_count,
                    ROUND(AVG(title_score), 2) as avg_title_score,
                    ROUND(AVG(opportunity_score), 2) as avg_opportunity_score
                FROM analysis_runs
                GROUP BY strftime('%Y-%m', created_at)
                ORDER BY month DESC
                LIMIT 3
                """
            ).fetchall()

        total, baseline_title, baseline_opp, lowest_title, highest_title = overall_stats if overall_stats else (0, 0, 0, 0, 0)

        months_data = [
            {
                "month": row[0],
                "videos": row[1],
                "avg_title_score": row[2],
                "avg_opportunity_score": row[3],
            }
            for row in monthly_comparison
        ]

        return {
            "total_analyses": int(total or 0),
            "baseline_title_score": float(baseline_title or 0),
            "baseline_opportunity_score": float(baseline_opp or 0),
            "score_range": {
                "lowest_title_score": float(lowest_title or 0),
                "highest_title_score": float(highest_title or 0),
            },
            "monthly_progression": months_data,
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
