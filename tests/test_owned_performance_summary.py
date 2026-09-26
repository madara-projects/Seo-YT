"""Linked-video totals count each video once, not once per snapshot."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from win_engine.feedback import migrations
from win_engine.feedback.channel_learning import learning_summary, save_video_snapshots
from win_engine.feedback.history_store import HistoryStore


class OwnedPerformanceSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "history.db")
        self.store = HistoryStore(self.path)
        published = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        # A saved package links to one published video, so each gets its own.
        for video_id in ("summaryvid1", "summaryvid2"):
            with self.store._connect() as connection:
                run_id = int(
                    connection.execute(
                        "INSERT INTO analysis_runs (query, created_at, title) VALUES (?, ?, ?)",
                        (video_id, datetime.now(timezone.utc).isoformat(), f"Package for {video_id}"),
                    ).lastrowid
                )
            self.store.link_published_video(run_id, video_id, published)

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_cumulative_snapshots_are_not_added_together(self):
        # 24h, 7d and current snapshots of one video: 31 minutes in total, not 71.
        self.store.record_performance_snapshot("summaryvid1", 24, views=100, watch_time_minutes=10, snapshot_window="24h")
        self.store.record_performance_snapshot("summaryvid1", 168, views=250, watch_time_minutes=30, snapshot_window="7d")
        self.store.record_performance_snapshot("summaryvid1", 240, views=260, watch_time_minutes=31, snapshot_window="current")
        self.store.record_performance_snapshot("summaryvid2", 24, views=40, watch_time_minutes=5, snapshot_window="24h")

        summary = self.store.owned_performance_summary()

        self.assertEqual(summary["linked_videos_count"], 2)
        self.assertEqual(summary["linked_videos_with_watch_time"], 2)
        self.assertEqual(summary["estimated_watch_minutes"], 36)

    def test_no_measured_watch_time_is_unavailable_not_zero(self):
        self.store.record_performance_snapshot("summaryvid1", 24, views=100, snapshot_window="24h")

        summary = self.store.owned_performance_summary()

        self.assertEqual(summary["linked_videos_count"], 2)
        self.assertEqual(summary["linked_videos_with_watch_time"], 0)
        self.assertIsNone(summary["estimated_watch_minutes"])

    def connect(self, channel_id: str) -> None:
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO youtube_channel_connection
                       (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at)
                   VALUES (1, 'token', ?, 'Channel', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')
                   ON CONFLICT(id) DO UPDATE SET channel_id = excluded.channel_id""",
                (channel_id,),
            )

    def test_without_a_channel_sync_no_channel_number_is_invented(self):
        # Lifetime views of recent uploads are not 28-day views.
        self.connect("UC-now")
        save_video_snapshots(self.path, [{"video_id": "upload1", "title": "Upload", "views": 5000}], channel_id="UC-now")
        summary = self.store.owned_performance_summary()

        for key in ("total_views", "views_28_days", "total_likes", "lifetime_views", "subscribers", "video_count"):
            self.assertIsNone(summary[key], key)
        self.assertIsNone(summary["latest_sync"])
        self.assertEqual(summary["max_views"], 5000)

    def test_a_sync_from_before_a_disconnect_is_not_current(self):
        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES (?, ?)",
                ("2026-09-01T00:00:00Z", '{"channel": {"id": "UC-old"}, "current_28_days": {"views": 10}}'),
            )
            connection.execute(
                "INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES (?, ?)",
                ("2026-09-02T00:00:00Z", "not json"),
            )
        self.assertIsNone(self.store.owned_performance_summary()["latest_sync"])

        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO youtube_channel_connection (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at) "
                "VALUES (1, 'token', 'UC-old', 'Old', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')"
            )
        # An unreadable newer sync is skipped rather than hiding the valid one.
        summary = self.store.owned_performance_summary()
        self.assertEqual(summary["views_28_days"], 10)

    def test_uploads_of_a_channel_connected_before_are_not_shown(self):
        save_video_snapshots(self.path, [{"video_id": "oldupload01", "title": "Old", "views": 10}], channel_id="UC-before")
        save_video_snapshots(self.path, [{"video_id": "newupload01", "title": "New", "views": 20}], channel_id="UC-now")
        self.assertEqual(self.store.owned_performance_summary()["videos"], [])

        self.connect("UC-now")
        summary = self.store.owned_performance_summary()
        self.assertEqual([video["video_id"] for video in summary["videos"]], ["newupload01"])
        self.assertEqual(summary["max_views"], 20)
        self.assertEqual(learning_summary(self.path)["connected_video_count"], 1)

    def test_version_10_gives_earlier_uploads_the_channel_whose_sync_listed_them(self):
        path = Path(self.dir.name) / "v9.db"
        migrations.prepare_database(str(path))
        connection = sqlite3.connect(path)
        connection.execute("ALTER TABLE owned_video_snapshots DROP COLUMN channel_id")
        connection.execute("ALTER TABLE cloud_sync_conflicts DROP COLUMN local_payload_json")
        connection.executemany(
            "INSERT INTO owned_video_snapshots (video_id, captured_at, title, views) VALUES (?, '2026-08-01', ?, 1)",
            [("listedvid01", "Listed"), ("unlisted001", "No sync lists it")],
        )
        payload = {"channel": {"id": "UC-now"}, "recent_videos": {"rows": [{"video_id": "listedvid01"}]}}
        connection.execute("INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES ('2026-08-01', ?)", (json.dumps(payload),))
        connection.execute("INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES ('2026-08-02', 'not json')")
        connection.execute("DELETE FROM schema_migrations WHERE version = 10")
        connection.execute("PRAGMA user_version = 9")
        connection.commit()
        connection.close()

        migrations.prepare_database(str(path))

        connection = sqlite3.connect(path)
        try:
            owners = connection.execute("SELECT video_id, channel_id FROM owned_video_snapshots ORDER BY video_id").fetchall()
        finally:
            connection.close()
        self.assertEqual(owners, [("listedvid01", "UC-now"), ("unlisted001", None)])


if __name__ == "__main__":
    unittest.main()
