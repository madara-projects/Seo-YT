from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.migrations import (
    CURRENT_SCHEMA_VERSION,
    MigrationError,
    online_backup,
    prepare_database,
)


class Phase1MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_fresh_database_is_initialized_at_current_version(self):
        path = self.root / "fresh.db"
        result = prepare_database(str(path))
        self.assertEqual(result.old_version, 0)
        self.assertEqual(result.new_version, CURRENT_SCHEMA_VERSION)
        self.assertIsNone(result.backup_path)

        store = HistoryStore(str(path))
        with store._connect() as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], CURRENT_SCHEMA_VERSION)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_online_backup_reopens_and_preserves_rows(self):
        path = self.root / "source.db"
        store = HistoryStore(str(path))
        with store._connect() as connection:
            connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES ('q', 'now', 'title')"
            )

        backup_path = online_backup(str(path), str(self.root / "backups"))

        self.assertTrue(Path(backup_path).exists())
        backup = sqlite3.connect(f"file:{Path(backup_path).as_posix()}?mode=ro", uri=True)
        try:
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(backup.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0], 1)
        finally:
            backup.close()

    def test_v0_migration_is_backup_first_and_preserves_relationship_rows(self):
        path = self.root / "legacy.db"
        self._create_v0_database(path)

        result = prepare_database(str(path), backup_before_migration=True)

        self.assertEqual((result.old_version, result.new_version), (0, CURRENT_SCHEMA_VERSION))
        self.assertTrue(result.migrated)
        self.assertIsNotNone(result.backup_path)
        self.assertTrue(Path(result.backup_path or "").exists())
        connection = sqlite3.connect(path)
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], CURRENT_SCHEMA_VERSION)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0], 1)
            ownership = connection.execute(
                "SELECT ownership_state, ownership_verified FROM published_video_links"
            ).fetchone()
            self.assertEqual(ownership, ("unverified", 0))
            snapshot = connection.execute(
                "SELECT published_video_link_id, snapshot_status FROM video_performance_snapshots"
            ).fetchone()
            self.assertEqual(snapshot, (1, "display_only"))
            experiment_link = connection.execute(
                "SELECT published_video_link_id FROM package_experiments"
            ).fetchone()[0]
            self.assertEqual(experiment_link, 1)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        finally:
            connection.close()

        backup = sqlite3.connect(result.backup_path or "")
        try:
            self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(backup.execute("SELECT COUNT(*) FROM published_video_links").fetchone()[0], 1)
        finally:
            backup.close()

    def test_current_version_prepare_is_idempotent_and_creates_no_second_backup(self):
        path = self.root / "current.db"
        first = prepare_database(str(path))
        second = prepare_database(str(path))
        self.assertTrue(first.migrated)
        self.assertFalse(second.migrated)
        self.assertIsNone(second.backup_path)

    def test_incomplete_legacy_schema_stops_without_changing_version(self):
        path = self.root / "broken.db"
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE analysis_runs (id INTEGER PRIMARY KEY)")
        connection.commit()
        connection.close()

        with self.assertRaises(MigrationError):
            prepare_database(str(path))

        check = sqlite3.connect(path)
        try:
            self.assertEqual(check.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(check.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0], 0)
        finally:
            check.close()

    @staticmethod
    def _create_v0_database(path: Path) -> None:
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE video_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT NOT NULL,
                query TEXT NOT NULL, captured_at TEXT NOT NULL, published_at TEXT,
                view_count INTEGER DEFAULT 0, like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0, subscriber_count INTEGER DEFAULT 0
            );
            CREATE TABLE owned_video_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT NOT NULL,
                captured_at TEXT NOT NULL, published_at TEXT, title TEXT,
                views INTEGER DEFAULT 0, watch_minutes REAL DEFAULT 0,
                average_view_duration REAL DEFAULT 0, average_view_percentage REAL DEFAULT 0,
                likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0, subscribers_gained INTEGER DEFAULT 0
            );
            CREATE TABLE youtube_channel_connection (
                id INTEGER PRIMARY KEY CHECK (id = 1), encrypted_refresh_token TEXT NOT NULL,
                channel_id TEXT, channel_title TEXT, connected_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE youtube_channel_syncs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, synced_at TEXT NOT NULL, payload_json TEXT NOT NULL
            );
            CREATE TABLE analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT NOT NULL, created_at TEXT NOT NULL,
                intent TEXT, content_angle TEXT, title TEXT, title_score REAL DEFAULT 0,
                retention_risk TEXT, opportunity_label TEXT, opportunity_score REAL DEFAULT 0,
                payload_json TEXT
            );
            CREATE TABLE published_video_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT, analysis_run_id INTEGER NOT NULL,
                youtube_video_id TEXT NOT NULL UNIQUE, published_at TEXT NOT NULL,
                selected_title TEXT, selected_thumbnail_package TEXT, selected_description TEXT,
                selected_tags_json TEXT, selected_hashtags_json TEXT, format TEXT,
                language TEXT, region TEXT, notes TEXT, linked_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, youtube_metadata_json TEXT, metadata_synced_at TEXT,
                FOREIGN KEY(analysis_run_id) REFERENCES analysis_runs(id)
            );
            CREATE TABLE video_performance_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, youtube_video_id TEXT NOT NULL,
                age_hours REAL NOT NULL, views INTEGER DEFAULT 0, watch_time_minutes REAL DEFAULT 0,
                avg_view_duration_seconds REAL DEFAULT 0, avg_view_percentage REAL DEFAULT 0,
                likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0, shares INTEGER DEFAULT 0,
                subscribers_gained INTEGER DEFAULT 0, impressions INTEGER DEFAULT 0,
                impressions_ctr REAL DEFAULT 0, snapshot_window TEXT, captured_at TEXT NOT NULL
            );
            CREATE TABLE package_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, youtube_video_id TEXT NOT NULL,
                changed_at TEXT NOT NULL, old_title TEXT, new_title TEXT,
                old_thumbnail TEXT, new_thumbnail TEXT, reason TEXT,
                performance_before_json TEXT, performance_after_json TEXT
            );

            INSERT INTO analysis_runs (id, query, created_at, title) VALUES (1, 'q', 'now', 'title');
            INSERT INTO published_video_links (
                id, analysis_run_id, youtube_video_id, published_at, linked_at, updated_at
            ) VALUES (1, 1, 'phase1vid01', '2026-08-01T00:00:00Z', 'now', 'now');
            INSERT INTO video_performance_snapshots (
                id, youtube_video_id, age_hours, views, snapshot_window, captured_at
            ) VALUES (1, 'phase1vid01', 48, 100, 'current', 'now');
            INSERT INTO package_experiments (
                id, youtube_video_id, changed_at, old_title, new_title
            ) VALUES (1, 'phase1vid01', 'now', 'before', 'after');
            PRAGMA user_version = 0;
            """
        )
        connection.commit()
        connection.close()


if __name__ == "__main__":
    unittest.main()
