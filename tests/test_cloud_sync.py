from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest

from win_engine.core.config import Settings
from win_engine.feedback.cloud_sync import CloudSyncService
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.migrations import CURRENT_SCHEMA_VERSION


class CloudSyncTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.store = HistoryStore(self.path)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.path + suffix)
            except FileNotFoundError:
                pass

    def settings(self, **overrides):
        values = {"database_path": self.path, "cloud_sync_enabled": True,
                  "cloud_sync_device_id": "test-device", "cloud_sync_host": "mysql.example",
                  "cloud_sync_database": "seo_yt_sync", "cloud_sync_user": "app",
                  "cloud_sync_password": "secret", "cloud_sync_ssl_ca_path": __file__}
        values.update(overrides)
        return Settings(**values)

    def test_schema_v8_contains_durable_sync_tables(self):
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], CURRENT_SCHEMA_VERSION)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("cloud_sync_packages", tables)
        self.assertIn("cloud_sync_outbox", tables)
        self.assertIn("cloud_sync_tombstones", tables)

    def test_disabled_and_unconfigured_states_do_not_connect(self):
        disabled = CloudSyncService(self.settings(cloud_sync_enabled=False))
        self.assertEqual(disabled.run_once()["state"], "disabled")
        unconfigured = CloudSyncService(self.settings(cloud_sync_password=None))
        self.assertEqual(unconfigured.run_once()["state"], "unconfigured")

    def test_existing_package_and_selection_are_staged_once(self):
        run_id = self.store.record_analysis_run("quote", "browse", "emotion", "A title", 8.2,
            "LOW", "WORKABLE", 62, {"description": "Complete package", "tags": ["quote"]})
        with self.store._connect() as connection:
            connection.execute("""INSERT INTO analysis_package_selections
                (analysis_run_id,generated_package_id,package_json,quality_gate_json,selection_source,selected_at,updated_at)
                VALUES(?,?,?,?,?,?,?)""", (run_id,"package-a",json.dumps({"title":"A title"}),"{}","creator","now","now"))
        service = CloudSyncService(self.settings())
        self.assertEqual(service._stage_local_packages(), 1)
        self.assertEqual(service._stage_local_packages(), 0)
        status = service.status()
        self.assertEqual(status["local_packages"], 1)
        self.assertEqual(status["mapped_packages"], 1)
        self.assertEqual(status["pending_uploads"], 1)
        self.assertEqual(status["synced_packages"], 0)
        with sqlite3.connect(self.path) as connection:
            payload = json.loads(connection.execute("SELECT payload_json FROM cloud_sync_outbox").fetchone()[0])
        self.assertEqual(payload["analysis"]["package"]["description"], "Complete package")
        self.assertEqual(payload["selection"]["generated_package_id"], "package-a")

    def test_linked_video_metadata_and_snapshots_round_trip_with_package(self):
        run_id = self.store.record_analysis_run(
            "rainy road", "browse", "emotion", "Rainy title", 8.2, "LOW", "WORKABLE", 62,
            {"description": "Complete package", "tags": ["rain"]},
        )
        link_id = self.store.link_published_video(
            run_id, "video-123", "2026-08-20T10:00:00+00:00", selected_title="Rainy title",
            selected_tags_json=json.dumps(["rain"]), format_val="short", language="english",
            ownership_state="verified", ownership_verified=True, verified_channel_id="channel-1",
        )
        self.store.update_linked_video_metadata(link_id, {"title": "Published rainy title", "tags": ["rain"]})
        self.store.update_comparable_metadata(link_id, {"duration_bucket": "under_60s", "topic_category": "quotes"})
        self.store.record_performance_snapshot("video-123", 1, views=125, likes=10, snapshot_window="current")
        self.store.record_performance_snapshot("video-123", 24, views=500, likes=30, avg_view_percentage=68, snapshot_window="24h")
        source_service = CloudSyncService(self.settings())
        self.assertEqual(source_service._stage_local_packages(), 1)
        with sqlite3.connect(self.path) as connection:
            sync_uuid, revision, content_hash, payload_json = connection.execute(
                "SELECT sync_uuid,revision,content_hash,payload_json FROM cloud_sync_outbox"
            ).fetchone()
        payload = json.loads(payload_json)
        self.assertEqual(payload["schema"], 2)
        self.assertEqual(payload["linked_video"]["youtube_video_id"], "video-123")
        self.assertEqual(len(payload["linked_video"]["snapshots"]), 2)

        target_handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        target_path = target_handle.name
        target_handle.close()
        self.addCleanup(lambda: os.path.exists(target_path) and os.unlink(target_path))
        target_service = CloudSyncService(self.settings(database_path=target_path, cloud_sync_device_id="laptop-b"))
        HistoryStore(target_path)

        class RemoteCursor:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, _query): return None
            def fetchall(self):
                return [(sync_uuid, "laptop-a", revision, content_hash, payload_json, "2026-08-20T10:00:00+00:00", None)]

        class Remote:
            def cursor(self): return RemoteCursor()

        self.assertEqual(target_service._pull(Remote()), 1)
        target_store = HistoryStore(target_path)
        synced_run = target_store.history_runs()[0]
        report = target_store.linked_package_report(synced_run["id"])
        self.assertTrue(report["linked"])
        self.assertEqual(report["video_id"], "video-123")
        self.assertEqual(report["youtube"]["title"], "Published rainy title")
        self.assertEqual(len(report["snapshots"]), 2)
        self.assertEqual(report["comparable_metadata"]["duration_bucket"], "under_60s")

    def test_deleting_a_synced_package_queues_a_durable_tombstone(self):
        run_id = self.store.record_analysis_run(
            "temporary test", "browse", "emotion", "Delete me", 7.0,
            "LOW", "WORKABLE", 50, {"description": "Temporary package"},
        )
        service = CloudSyncService(self.settings())
        self.assertEqual(service._stage_local_packages(), 1)
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE cloud_sync_packages SET last_synced_hash = content_hash WHERE analysis_run_id = ?",
                (run_id,),
            )
            sync_uuid = connection.execute(
                "SELECT sync_uuid FROM cloud_sync_packages WHERE analysis_run_id = ?", (run_id,)
            ).fetchone()[0]

        self.assertTrue(self.store.delete_analysis_run(run_id))

        with self.store._connect() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM analysis_runs WHERE id = ?", (run_id,)).fetchone())
            self.assertIsNone(connection.execute("SELECT 1 FROM cloud_sync_packages WHERE sync_uuid = ?", (sync_uuid,)).fetchone())
            tombstone = connection.execute(
                "SELECT revision, pending FROM cloud_sync_tombstones WHERE sync_uuid = ?", (sync_uuid,)
            ).fetchone()
        self.assertEqual(tombstone, (2, 1))

    def test_remote_tombstone_deletes_an_offline_devices_copy(self):
        run_id = self.store.record_analysis_run(
            "temporary test", "browse", "emotion", "Delete everywhere", 7.0,
            "LOW", "WORKABLE", 50, {"description": "Temporary package"},
        )
        service = CloudSyncService(self.settings())
        service._stage_local_packages()
        with self.store._connect() as connection:
            sync_uuid = connection.execute(
                "SELECT sync_uuid FROM cloud_sync_packages WHERE analysis_run_id = ?", (run_id,)
            ).fetchone()[0]

        class RemoteCursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, _query):
                return None

            def fetchall(self):
                return [(sync_uuid, "laptop-a", 2, "deleted-hash", "{}",
                         "2026-08-26T10:00:00+00:00", "2026-08-26T10:00:00+00:00")]

        class Remote:
            def cursor(self):
                return RemoteCursor()

        self.assertEqual(service._pull(Remote()), 1)

        with self.store._connect() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM analysis_runs WHERE id = ?", (run_id,)).fetchone())
            tombstone = connection.execute(
                "SELECT revision,pending FROM cloud_sync_tombstones WHERE sync_uuid = ?", (sync_uuid,)
            ).fetchone()
        self.assertEqual(tombstone, (2, 0))


if __name__ == "__main__":
    unittest.main()
