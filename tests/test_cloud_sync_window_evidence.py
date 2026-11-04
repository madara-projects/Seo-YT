"""A synced completed window keeps the coverage and uploaded metadata it was captured with."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest

from win_engine.core.config import Settings
from win_engine.feedback.cloud_sync import CloudSyncService, _hash
from win_engine.feedback.history_store import HistoryStore

UPDATED_AT = "2026-08-28T10:00:00+00:00"
METADATA = {"title": "Captured title", "tags": ["alpha", "beta"], "description": "Captured description"}


class _PullCursor:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, _sql, _params=None): return None
    def fetchall(self): return self.rows


class _PullRemote:
    def __init__(self, rows): self.rows = rows
    def cursor(self): return _PullCursor(self.rows)


class CloudSyncWindowEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source_store, self.source = self._device("device-a")
        self.store, self.service = self._device("device-b")
        self.run_id = self.source_store.record_analysis_run(
            "window evidence", "browse", "emotion", "Window Evidence", 7.0, "LOW", "WORKABLE", 50, {"d": 1})
        self.source_store.link_published_video(self.run_id, "video-1", "2026-08-01T10:00:00+00:00")
        self.source_store.record_performance_snapshot(
            "video-1", 36, views=300, snapshot_window="24h", snapshot_status="complete",
            source_start_date="2026-08-01", source_end_date="2026-08-02")
        # The coverage and metadata the capture stored, set directly so the test
        # holds whatever the capture computes.
        with sqlite3.connect(self.source_store.database_path) as connection:
            connection.execute(
                "UPDATE video_performance_snapshots SET covered_hours = 36, metadata_json = ? WHERE youtube_video_id = ?",
                (json.dumps(METADATA), "video-1"),
            )
        self.source._stage_local_packages()

    def _device(self, name):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.addCleanup(self._remove, handle.name)
        store = HistoryStore(handle.name)
        service = CloudSyncService(Settings(
            database_path=handle.name, cloud_sync_enabled=True, cloud_sync_device_id=name,
            cloud_sync_host="mysql.example", cloud_sync_database="seo_yt_sync", cloud_sync_user="app",
            cloud_sync_password="not-used", cloud_sync_ssl_ca_path=__file__,
        ))
        return store, service

    @staticmethod
    def _remove(path):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(path + suffix)
            except FileNotFoundError:
                pass

    def _payload(self):
        with sqlite3.connect(self.source_store.database_path) as connection:
            return self.source._package_payload(connection, self.run_id)

    def _remote_row(self, *, revision=1, mutate=None):
        payload = self._payload()
        with sqlite3.connect(self.source_store.database_path) as connection:
            sync_uuid = connection.execute(
                "SELECT sync_uuid FROM cloud_sync_packages WHERE analysis_run_id=?", (self.run_id,)
            ).fetchone()[0]
        if mutate:
            mutate(payload)
        return (sync_uuid, "device-a", revision, _hash(payload), json.dumps(payload), UPDATED_AT, None)

    def _local_window(self):
        with sqlite3.connect(self.store.database_path) as connection:
            return connection.execute(
                """SELECT views, covered_hours, metadata_json, snapshot_status FROM video_performance_snapshots
                   WHERE youtube_video_id = 'video-1' AND snapshot_window = '24h'"""
            ).fetchall()

    @staticmethod
    def _old_format(payload):
        for snapshot in payload["linked_video"]["snapshots"]:
            snapshot.pop("covered_hours", None)
            snapshot.pop("uploaded_metadata", None)

    def test_export_carries_the_stored_coverage_and_metadata(self):
        snapshot = self._payload()["linked_video"]["snapshots"][0]
        self.assertEqual(snapshot["covered_hours"], 36.0)
        self.assertEqual(snapshot["uploaded_metadata"], METADATA)

    def test_a_window_without_coverage_or_metadata_keeps_its_older_payload_shape(self):
        with sqlite3.connect(self.source_store.database_path) as connection:
            connection.execute("UPDATE video_performance_snapshots SET covered_hours = NULL, metadata_json = NULL")
        snapshot = self._payload()["linked_video"]["snapshots"][0]
        self.assertNotIn("covered_hours", snapshot)
        self.assertNotIn("uploaded_metadata", snapshot)

    def test_a_round_trip_keeps_the_stored_coverage_and_captured_metadata(self):
        self.assertEqual(self.service._pull(_PullRemote([self._remote_row()])), 1)

        rows = self._local_window()
        self.assertEqual(len(rows), 1)
        views, covered_hours, metadata_json, status = rows[0]
        self.assertEqual((views, covered_hours, status), (300, 36.0, "complete"))
        self.assertEqual(json.loads(metadata_json), METADATA)

    def test_an_old_format_payload_still_imports_with_unknown_coverage_and_metadata(self):
        self.assertEqual(self.service._pull(_PullRemote([self._remote_row(mutate=self._old_format)])), 1)

        self.assertEqual(self._local_window(), [(300, None, None, "complete")])

    def test_a_pulled_window_fills_only_what_the_local_completed_window_lacks(self):
        self.service._pull(_PullRemote([self._remote_row(mutate=self._old_format)]))
        self.assertEqual(self._local_window(), [(300, None, None, "complete")])

        # The same window from a newer device fills the missing evidence, but
        # never the primary metrics the local window already observed.
        def newer(payload):
            payload["linked_video"]["snapshots"][0]["views"] = 999
        self.service._pull(_PullRemote([self._remote_row(revision=2, mutate=newer)]))
        views, covered_hours, metadata_json, _status = self._local_window()[0]
        self.assertEqual((views, covered_hours), (300, 36.0))
        self.assertEqual(json.loads(metadata_json), METADATA)

        # Established local evidence is never replaced.
        local_metadata = {"title": "Local title", "tags": ["local"], "description": ""}
        with sqlite3.connect(self.store.database_path) as connection:
            connection.execute("UPDATE video_performance_snapshots SET covered_hours = 30, metadata_json = ?",
                               (json.dumps(local_metadata),))
        self.service._pull(_PullRemote([self._remote_row(revision=3)]))
        views, covered_hours, metadata_json, _status = self._local_window()[0]
        self.assertEqual((views, covered_hours), (300, 30.0))
        self.assertEqual(json.loads(metadata_json), local_metadata)

    def test_a_window_over_another_day_range_does_not_fill_the_local_one(self):
        self.service._pull(_PullRemote([self._remote_row(mutate=self._old_format)]))

        def other_range(payload):
            payload["linked_video"]["snapshots"][0]["source_end_date"] = "2026-08-03"
        self.service._pull(_PullRemote([self._remote_row(revision=2, mutate=other_range)]))

        self.assertEqual(self._local_window(), [(300, None, None, "complete")])


if __name__ == "__main__":
    unittest.main()
