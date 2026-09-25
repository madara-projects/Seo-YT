"""Linked-video totals count each video once, not once per snapshot."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from win_engine.feedback.history_store import HistoryStore


class OwnedPerformanceSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.store = HistoryStore(str(Path(self.dir.name) / "history.db"))
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
        self.assertEqual(summary["estimated_watch_minutes"], 36)

    def test_videos_without_watch_time_add_nothing(self):
        self.store.record_performance_snapshot("summaryvid1", 24, views=100, snapshot_window="24h")

        summary = self.store.owned_performance_summary()

        self.assertEqual(summary["linked_videos_count"], 2)
        self.assertEqual(summary["estimated_watch_minutes"], 0)


if __name__ == "__main__":
    unittest.main()
