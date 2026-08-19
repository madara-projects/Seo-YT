from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.snapshot_collector import SnapshotCollector


class Phase2MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "phase2.db")
        self.store = HistoryStore(self.path)
        with self.store._connect() as c:
            c.execute("INSERT INTO analysis_runs (query, created_at, title) VALUES ('q', 'now', 'Package')")
        self.link_id = self.store.link_published_video(
            1, "abcdefghijk", (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            format_val="short", language="english", ownership_state="verified",
            ownership_verified=True, verified_channel_id="channel", ownership_verified_at="now",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_metadata_sources_and_package_are_separate(self):
        metadata = self.store.comparable_metadata(self.link_id)
        self.assertEqual(metadata["format"], "short")
        self.assertEqual(metadata["sources"]["format"], "package")
        self.store.update_comparable_metadata(self.link_id, {"topic_category": "heartbreak"})
        metadata = self.store.comparable_metadata(self.link_id)
        self.assertEqual(metadata["topic_category"], "heartbreak")
        self.assertEqual(metadata["sources"]["topic_category"], "creator")
        self.assertEqual(metadata["edits"][0]["field"], "topic_category")

    def test_omitted_field_unchanged_and_clear_unknown(self):
        self.store.update_comparable_metadata(self.link_id, {"topic_category": "quotes"})
        self.store.update_comparable_metadata(self.link_id, {"language": None})
        metadata = self.store.comparable_metadata(self.link_id)
        self.assertEqual(metadata["topic_category"], "quotes")
        self.assertEqual(metadata["language"], "unknown")
        self.assertEqual(metadata["sources"]["language"], "unknown")

    def test_invalid_values_rejected(self):
        with self.assertRaises(ValueError):
            self.store.update_comparable_metadata(self.link_id, {"format": "made-up"})
        with self.assertRaises(ValueError):
            self.store.update_comparable_metadata(self.link_id, {"topic_category": ""})

    def test_creator_generated_formats_can_be_confirmed(self):
        for format_value in ("youtube_shorts", "talking_head"):
            metadata = self.store.update_comparable_metadata(
                self.link_id,
                {"format": format_value},
            )
            self.assertEqual(metadata["format"], format_value)
            self.assertEqual(metadata["sources"]["format"], "creator")


class Phase2CollectorTests(unittest.TestCase):
    def test_disabled_and_dry_run_do_not_call_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "collector.db")
            HistoryStore(path)
            disabled = SnapshotCollector(Settings(database_path=path, snapshot_collector_enabled=False))
            self.assertEqual(disabled.run_once()["state"], "disabled")
            dry = SnapshotCollector(Settings(database_path=path, snapshot_collector_enabled=True, snapshot_collector_dry_run=True))
            result = dry.run_once()
            self.assertEqual(result["state"], "dry-run")
            c = sqlite3.connect(path)
            try:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM video_performance_snapshots").fetchone()[0], 0)
            finally:
                c.close()

    def test_due_selection_skips_completed_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "collector.db")
            store = HistoryStore(path)
            with store._connect() as c:
                c.execute("INSERT INTO analysis_runs (query, created_at) VALUES ('q', 'now')")
            link = store.link_published_video(1, "abcdefghijk", (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(), format_val="short", language="english", ownership_state="verified", ownership_verified=True, verified_channel_id="c", ownership_verified_at="now")
            store.record_performance_snapshot("abcdefghijk", 24, views=10, snapshot_window="24h", snapshot_status="complete")
            due = store.due_snapshot_links()
            self.assertEqual(due[0]["due_windows"], ["7d"])


if __name__ == "__main__":
    unittest.main()
