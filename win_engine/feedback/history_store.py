from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

_INITIALIZED_DATABASES: set[str] = set()
_INITIALIZATION_LOCK = Lock()


class HistoryStore:
    """SQLite-backed snapshot store for repeated video metric collection."""

    def __init__(self, database_path: str) -> None:
        self._database_path_raw = database_path
        self._database_path = Path(database_path) if database_path != ":memory:" else None
        self._memory_connection: sqlite3.Connection | None = None
        if database_path == ":memory:":
            self._memory_connection = sqlite3.connect(":memory:", check_same_thread=False)
            self._initialize()
        else:
            database_key = str(self._database_path.resolve()) if self._database_path else database_path
            if database_key not in _INITIALIZED_DATABASES:
                with _INITIALIZATION_LOCK:
                    if database_key not in _INITIALIZED_DATABASES:
                        self._initialize()
                        _INITIALIZED_DATABASES.add(database_key)

    @property
    def database_path(self) -> str:
        return self._database_path_raw

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

            # Stage A: Link saved package to published video
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS published_video_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id INTEGER NOT NULL,
                    youtube_video_id TEXT NOT NULL UNIQUE,
                    published_at TEXT NOT NULL,
                    selected_title TEXT,
                    selected_thumbnail_package TEXT,
                    selected_description TEXT,
                    selected_tags_json TEXT,
                    selected_hashtags_json TEXT,
                    format TEXT,
                    language TEXT,
                    region TEXT,
                    notes TEXT,
                    linked_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id)
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_pub_links_run_id ON published_video_links(analysis_run_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_pub_links_yt_id ON published_video_links(youtube_video_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_pub_links_pub_at ON published_video_links(published_at)")
            self._ensure_column(connection, "published_video_links", "youtube_metadata_json", "TEXT")
            self._ensure_column(connection, "published_video_links", "metadata_synced_at", "TEXT")

            # Stage B: Comparable age-based performance snapshots
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_performance_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    youtube_video_id TEXT NOT NULL,
                    age_hours REAL NOT NULL,
                    views INTEGER DEFAULT 0,
                    watch_time_minutes REAL DEFAULT 0,
                    avg_view_duration_seconds REAL DEFAULT 0,
                    avg_view_percentage REAL DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    subscribers_gained INTEGER DEFAULT 0,
                    impressions INTEGER DEFAULT 0,
                    impressions_ctr REAL DEFAULT 0,
                    snapshot_window TEXT,
                    captured_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(connection, "video_performance_snapshots", "snapshot_window", "TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_perf_snaps_yt_id ON video_performance_snapshots(youtube_video_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_perf_snaps_yt_window ON video_performance_snapshots(youtube_video_id, snapshot_window)")

            # Stage D: Package experiments & post-publish changes
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS package_experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    youtube_video_id TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    old_title TEXT,
                    new_title TEXT,
                    old_thumbnail TEXT,
                    new_thumbnail TEXT,
                    reason TEXT,
                    performance_before_json TEXT,
                    performance_after_json TEXT
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_pkg_exp_yt_id ON package_experiments(youtube_video_id)")

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

    def history_runs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Return saved packages in newest-first order without the large payload."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.id, a.created_at, a.title, a.opportunity_score, a.title_score,
                       a.query, a.payload_json, p.id, p.youtube_video_id
                FROM analysis_runs a
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

    def delete_analysis_run(self, run_id: int) -> bool:
        """Delete a recorded analysis run from the SQLite database."""
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM analysis_runs WHERE id = ?", (run_id,))
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
                    linked_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            row = connection.execute(
                "SELECT id FROM published_video_links WHERE youtube_video_id = ?",
                (youtube_video_id,),
            ).fetchone()
            return int(row[0]) if row else int(cursor.lastrowid or 0)

    def published_video_links_list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.id, p.analysis_run_id, p.youtube_video_id, p.published_at,
                       p.selected_title, p.selected_thumbnail_package, p.selected_description,
                       p.format, p.language, p.region, p.notes, p.linked_at, p.updated_at,
                       COALESCE(a.title, a.query, 'Saved Package'), a.opportunity_score, a.title_score,
                       s.age_hours, s.views, s.avg_view_percentage, s.impressions_ctr, s.snapshot_window, s.captured_at,
                       p.selected_tags_json, p.selected_hashtags_json, p.youtube_metadata_json, p.metadata_synced_at
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
            return [
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
                }
                for r in rows
            ]

    def published_video_link_by_run(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, analysis_run_id, youtube_video_id, published_at,
                       selected_title, selected_thumbnail_package, selected_description,
                       format, language, region, notes, linked_at, updated_at,
                       selected_tags_json, selected_hashtags_json, youtube_metadata_json, metadata_synced_at
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

    def published_video_link(self, link_id: int) -> dict[str, Any] | None:
        for link in self.published_video_links_list():
            if link["id"] == link_id:
                return link
        return None

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
    ) -> int:
        captured_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            if replace_window and snapshot_window:
                connection.execute(
                    "DELETE FROM video_performance_snapshots WHERE youtube_video_id = ? AND snapshot_window = ?",
                    (youtube_video_id, snapshot_window),
                )
            cursor = connection.execute(
                """
                INSERT INTO video_performance_snapshots (
                    youtube_video_id, age_hours, views, watch_time_minutes,
                    avg_view_duration_seconds, avg_view_percentage, likes, comments,
                    shares, subscribers_gained, impressions, impressions_ctr, snapshot_window, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
                    captured_at,
                ),
            )
            return int(cursor.lastrowid or 0)

    def has_snapshot_window(self, youtube_video_id: str, snapshot_window: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM video_performance_snapshots WHERE youtube_video_id = ? AND snapshot_window = ? LIMIT 1",
                (youtube_video_id, snapshot_window),
            ).fetchone()
        return bool(row)

    def performance_snapshots(self, youtube_video_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT age_hours, views, watch_time_minutes, avg_view_duration_seconds,
                          avg_view_percentage, likes, comments, shares, subscribers_gained,
                          impressions, impressions_ctr, snapshot_window, captured_at
                   FROM video_performance_snapshots WHERE youtube_video_id = ?
                   ORDER BY captured_at ASC""",
                (youtube_video_id,),
            ).fetchall()
        keys = ("age_hours", "views", "watch_time_minutes", "avg_view_duration_seconds",
                "avg_view_percentage", "likes", "comments", "shares", "subscribers_gained",
                "impressions", "impressions_ctr", "snapshot_window", "captured_at")
        return [dict(zip(keys, row)) for row in rows]

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
        metadata = link.get("youtube_metadata") if isinstance(link.get("youtube_metadata"), dict) else {}
        snapshots = self.performance_snapshots(str(link.get("youtube_video_id") or ""))
        latest = snapshots[-1] if snapshots else {}
        published_at = _parse_datetime_safe(str(link.get("published_at") or ""))
        age_hours = max(0.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600) if published_at else 0.0

        generated_title = str(package.get("title") or run.get("title") or "").strip()
        uploaded_title = str(metadata.get("title") or link.get("selected_title") or "").strip()
        generated_description = str(package.get("description") or link.get("selected_description") or "").strip()
        uploaded_description = str(metadata.get("description") or "").strip()
        generated_tags = _normalized_list(package.get("tags") or link.get("selected_tags") or [])
        uploaded_tags = _normalized_list(metadata.get("tags") or [])
        generated_hashtags = _normalized_list(package.get("hashtags") or link.get("selected_hashtags") or [])
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

        baseline = self._comparable_snapshot_baseline(link, latest)
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

        return {
            "linked": True,
            "link_id": link.get("id"),
            "video_id": link.get("youtube_video_id"),
            "video_url": f"https://www.youtube.com/watch?v={link.get('youtube_video_id')}",
            "published_at": link.get("published_at"),
            "age_hours": round(age_hours, 1),
            "metadata_synced_at": link.get("metadata_synced_at"),
            "youtube": metadata,
            "package_usage": {
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
            },
            "baseline": baseline,
            "diagnosis": {
                "verdict": verdict,
                "what_worked": worked,
                "needs_improvement": improve,
                "confidence": "LOW" if age_hours < 24 or baseline.get("sample_size", 0) < 3 else "MEDIUM",
                "learning_eligible": bool(age_hours >= 24 and latest),
                "attribution_note": (
                    "YouTube APIs report video-level performance, not views caused by individual tags. "
                    "The tool learns reliable packaging patterns only after comparable linked videos accumulate."
                ),
            },
            "snapshots": snapshots,
        }

    def _comparable_snapshot_baseline(self, link: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
        window = str(latest.get("snapshot_window") or "")
        if not window or window == "current":
            return {"sample_size": 0, "window": window or "none", "median_views": None, "median_retention_percentage": None}
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT s.views, s.avg_view_percentage
                   FROM video_performance_snapshots s
                   JOIN published_video_links p ON p.youtube_video_id = s.youtube_video_id
                   WHERE s.snapshot_window = ? AND s.youtube_video_id != ?
                     AND COALESCE(p.format, '') = COALESCE(?, '')
                     AND COALESCE(p.language, '') = COALESCE(?, '')""",
                (window, link.get("youtube_video_id"), link.get("format"), link.get("language")),
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

    def cohort_analytics(self, format_filter: str | None = None, language_filter: str | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            query = """
                SELECT p.youtube_video_id, p.format, p.language,
                       COALESCE(s.views, o.views, 0) as views,
                       COALESCE(s.likes, o.likes, 0) as likes,
                       COALESCE(s.avg_view_percentage, o.average_view_percentage, 0) as avg_view_percentage
                FROM published_video_links p
                LEFT JOIN owned_video_snapshots o ON p.youtube_video_id = o.video_id
                LEFT JOIN (
                    SELECT youtube_video_id, views, likes, avg_view_percentage,
                           ROW_NUMBER() OVER(PARTITION BY youtube_video_id ORDER BY captured_at DESC) as rn
                    FROM video_performance_snapshots
                ) s ON p.youtube_video_id = s.youtube_video_id AND s.rn = 1
                WHERE 1=1
            """
            params: list[Any] = []
            if format_filter:
                query += " AND p.format = ?"
                params.append(format_filter)
            if language_filter:
                query += " AND p.language = ?"
                params.append(language_filter)

            rows = connection.execute(query, params).fetchall()
            count = len(rows)

            if count == 0:
                confidence = "Collecting evidence"
                confidence_level = "none"
            elif count < 5:
                confidence = f"Collecting evidence ({count}/5 linked videos)"
                confidence_level = "low"
            elif count < 10:
                confidence = f"Directional observation ({count} linked videos)"
                confidence_level = "medium-low"
            elif count < 20:
                confidence = f"Moderate-confidence pattern ({count} linked videos)"
                confidence_level = "moderate"
            else:
                confidence = f"Evidence-based recommendation ({count} linked videos)"
                confidence_level = "high"

            views_list = sorted([r[3] for r in rows if r[3] is not None])
            retention_list = sorted([r[5] for r in rows if r[5] is not None])
            likes_list = sorted([r[4] for r in rows if r[4] is not None])
            median_views = _median(views_list)
            median_retention = _median(retention_list)
            median_likes = _median(likes_list)

            recommendation = "Collect linked-video snapshots before using personal performance patterns."
            if count >= 5 and median_retention is not None:
                recommendation = (
                    f"Use this {format_filter or 'format'} / {language_filter or 'language'} cohort as a comparison baseline. "
                    f"Median retention at the latest comparable snapshot is {median_retention:.1f}%."
                )

            return {
                "format": format_filter or "all",
                "language": language_filter or "all",
                "sample_size": count,
                "confidence_label": confidence,
                "confidence_level": confidence_level,
                "median_views": median_views,
                "median_retention_percentage": median_retention,
                "median_likes": median_likes,
                "total_linked": count,
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
                    youtube_video_id, changed_at, old_title, new_title,
                    old_thumbnail, new_thumbnail, reason, performance_before_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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
        worked.append("The uploaded title exactly matches the generated recommendation, so its result can inform title learning.")
    else:
        improve.append("The uploaded title differs from the generated title; treat this as a test of the uploaded title, not the original recommendation.")
    if generated_tag_count and matching_tags:
        worked.append(f"You used {matching_tags} of {generated_tag_count} generated tags.")
    elif generated_tag_count:
        improve.append("The uploaded metadata does not currently contain the generated tags, so tag-package adoption cannot be evaluated.")

    sample_size = int(baseline.get("sample_size") or 0)
    median_views = baseline.get("median_views")
    median_retention = baseline.get("median_retention_percentage")
    if sample_size >= 3 and median_views is not None:
        if views >= float(median_views):
            worked.append(f"Views are at or above the {baseline.get('window')} comparable median ({int(median_views)}).")
        else:
            improve.append(f"Views are below the {baseline.get('window')} comparable median ({int(median_views)}); test a stronger opening or packaging angle next time.")
    else:
        improve.append("There are not yet three comparable linked videos at the same age window, so no reliable winner/loser claim is made.")

    if retention is not None:
        if median_retention is not None and sample_size >= 3:
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
    elif sample_size < 3:
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
