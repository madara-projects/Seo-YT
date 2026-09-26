"""Two devices syncing through a fake cloud converge without churn, blocked pulls or lost evidence."""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import unittest

from win_engine.core.config import Settings
from win_engine.feedback.audit_experiment_store import AuditExperimentStore
from win_engine.feedback.cloud_sync import CloudSyncService
from win_engine.feedback.history_store import HistoryStore


class FakeCloud:
    """The cloud table in SQLite. The service's MySQL statements are translated
    token for token, so the tests exercise the upsert rules it really sends."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.execute("""CREATE TABLE seo_yt_synced_packages (
            sync_uuid TEXT PRIMARY KEY, origin_device_id TEXT NOT NULL, revision INTEGER NOT NULL,
            content_hash TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, deleted_at TEXT)""")
        self.pull_filters: list = []
        self.schema_checks = 0

    def connect(self):
        return _FakeConnection(self)

    def rows(self):
        return self.db.execute("SELECT revision, deleted_at FROM seo_yt_synced_packages ORDER BY sync_uuid").fetchall()


class _FakeConnection:
    def __init__(self, cloud):
        self.cloud = cloud

    def cursor(self):
        return _FakeCursor(self.cloud)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class _FakeCursor:
    def __init__(self, cloud):
        self.cloud = cloud
        self.result: list = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        statement = " ".join(sql.split())
        if statement.startswith(("CREATE TABLE", "SHOW COLUMNS", "ALTER TABLE")):
            self.cloud.schema_checks += statement.startswith("CREATE TABLE")
            self.result = [("deleted_at",)]
            return 0
        statement = statement.replace("%s", "?")
        if statement.startswith("SELECT sync_uuid"):
            self.cloud.pull_filters.append(params[0] if params else None)
        if not statement.startswith("INSERT"):
            self.result = self.cloud.db.execute(statement, params).fetchall()
            return len(self.result)
        # MySQL runs ON DUPLICATE KEY assignments left to right, but every
        # condition in these statements reads columns assigned after it, so
        # SQLite's all-at-once UPDATE gives the same result.
        statement = statement.replace("ON DUPLICATE KEY UPDATE", "ON CONFLICT(sync_uuid) DO UPDATE SET")
        statement = re.sub(r"VALUES\((\w+)\)", r"excluded.\1", statement)
        statement = statement.replace("IF(", "iif(").replace("GREATEST(", "max(")
        select = "SELECT * FROM seo_yt_synced_packages WHERE sync_uuid = ?"
        before = self.cloud.db.execute(select, (params[0],)).fetchone()
        self.cloud.db.execute(statement, params)
        after = self.cloud.db.execute(select, (params[0],)).fetchone()
        # MySQL's affected rows without CLIENT_FOUND_ROWS: 1 inserted, 2 changed, 0 unchanged.
        return 1 if before is None else 2 if after != before else 0

    def fetchall(self):
        return list(self.result)

    def fetchone(self):
        return self.result[0] if self.result else None


class TwoDeviceSyncTests(unittest.TestCase):
    def setUp(self):
        self.cloud = FakeCloud()
        self.store_a, self.device_a = self._device("device-a")
        self.store_b, self.device_b = self._device("device-b")

    def _device(self, name):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        self.addCleanup(self._remove, path)
        store = HistoryStore(path)
        service = CloudSyncService(Settings(
            database_path=path, cloud_sync_enabled=True, cloud_sync_device_id=name,
            cloud_sync_host="mysql.example", cloud_sync_database="seo_yt_sync", cloud_sync_user="app",
            cloud_sync_password="not-used", cloud_sync_ssl_ca_path=__file__,
        ))
        service._remote_connection = self.cloud.connect
        return store, service

    @staticmethod
    def _remove(path):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(path + suffix)
            except FileNotFoundError:
                pass

    def _package(self, store, query):
        return store.record_analysis_run(query, "browse", "emotion", query.title(), 7.0, "LOW", "WORKABLE", 50, {"d": query})

    def _runs(self, store):
        return {run["query"]: run["id"] for run in store.history_runs()}

    def _query(self, store, sql, params=()):
        with sqlite3.connect(store.database_path) as connection:
            return connection.execute(sql, params).fetchall()

    def _revisions(self):
        return [revision for revision, _deleted_at in self.cloud.rows()]

    def test_a_newer_display_snapshot_reaches_the_other_device_without_revision_churn(self):
        run_id = self._package(self.store_a, "rain")
        self.store_a.link_published_video(run_id, "video-0001", "2026-08-01T10:00:00+00:00", format_val="youtube_shorts",
                                          language="english")
        self.store_a.record_performance_snapshot("video-0001", 5, views=100, snapshot_window="current", replace_window=True)
        self.device_a.run_once()
        self.device_b.run_once()
        self.store_a.record_performance_snapshot("video-0001", 30, views=900, snapshot_window="current", replace_window=True)
        self.device_a.run_once()
        self.device_b.run_once()
        revisions = self._revisions()

        for _ in range(3):
            self.assertEqual(self.device_a.run_once()["counts"]["queued"], 0)
            self.assertEqual(self.device_b.run_once()["counts"]["queued"], 0)

        self.assertEqual(self._revisions(), revisions)
        self.assertEqual(self._query(self.store_b, "SELECT views FROM video_performance_snapshots WHERE snapshot_window='current'"), [(900,)])

    def test_each_device_keeps_its_own_completed_window_without_churn(self):
        run_id = self._package(self.store_a, "rain")
        self.store_a.link_published_video(run_id, "video-0001", "2026-08-01T10:00:00+00:00")
        self.device_a.run_once()
        self.device_b.run_once()
        self.store_a.record_performance_snapshot("video-0001", 24, views=500, snapshot_window="24h")
        self.store_b.record_performance_snapshot("video-0001", 24, views=510, snapshot_window="24h")
        for _ in range(2):
            self.device_a.run_once()
            self.device_b.run_once()
        revisions = self._revisions()

        for _ in range(3):
            self.assertEqual(self.device_a.run_once()["counts"]["queued"], 0)
            self.assertEqual(self.device_b.run_once()["counts"]["queued"], 0)

        self.assertEqual(self._revisions(), revisions)
        window = "SELECT views FROM video_performance_snapshots WHERE snapshot_window='24h'"
        self.assertEqual(self._query(self.store_a, window), [(500,)])
        self.assertEqual(self._query(self.store_b, window), [(510,)])

    def test_moving_a_video_to_an_older_package_does_not_block_later_pulls(self):
        self._package(self.store_a, "old package")
        newer = self._package(self.store_a, "new package")
        self.store_a.link_published_video(newer, "video-0002", "2026-08-01T10:00:00+00:00")
        self.device_a.run_once()
        self.device_b.run_once()
        self.store_b.link_published_video(self._runs(self.store_b)["old package"], "video-0002", "2026-08-01T10:00:00+00:00")
        self._package(self.store_b, "unrelated")
        self.device_b.run_once()

        result = self.device_a.run_once()

        self.assertEqual(result["state"], "healthy/idle")
        self.assertEqual(self.device_a.status()["consecutive_failures"], 0)
        self.assertIn("unrelated", self._runs(self.store_a))
        owner = "SELECT a.query FROM published_video_links p JOIN analysis_runs a ON a.id = p.analysis_run_id"
        self.assertEqual(self._query(self.store_a, owner), [("old package",)])

    def test_moving_a_video_keeps_evidence_recorded_only_on_the_pulling_device(self):
        older = self._package(self.store_a, "old package")
        self._package(self.store_a, "new package")
        link_id = self.store_a.link_published_video(older, "video-0008", "2026-08-01T10:00:00+00:00",
                                                    ownership_state="verified", ownership_verified=True,
                                                    verified_channel_id="channel-1")
        audits = AuditExperimentStore(self.store_a)
        audits.refresh_audit(link_id)
        experiment = audits.create_experiment({"name": "n", "hypothesis": "h", "variable": "title",
                                               "control_definition": "c", "variant_definition": "v"})
        audits.assign_video(experiment["id"], link_id, "control")
        self.device_a.run_once()
        self.device_b.run_once()
        self.store_b.link_published_video(self._runs(self.store_b)["new package"], "video-0008", "2026-08-01T10:00:00+00:00")
        self.device_b.run_once()

        self.device_a.run_once()

        self.assertEqual(self._query(self.store_a, "SELECT COUNT(*) FROM published_video_audits"), [(1,)])
        self.assertEqual(self._query(self.store_a, "SELECT COUNT(*) FROM experiment_video_assignments"), [(1,)])
        owner = "SELECT p.id, a.query FROM published_video_links p JOIN analysis_runs a ON a.id = p.analysis_run_id"
        self.assertEqual(self._query(self.store_a, owner), [(link_id, "new package")])

    def test_moving_a_video_then_deleting_its_old_package_keeps_the_evidence(self):
        older = self._package(self.store_a, "old package")
        self._package(self.store_a, "new package")
        link_id = self.store_a.link_published_video(older, "video-0009", "2026-08-01T10:00:00+00:00",
                                                    ownership_state="verified", ownership_verified=True,
                                                    verified_channel_id="channel-1")
        audits = AuditExperimentStore(self.store_a)
        audits.refresh_audit(link_id)
        experiment = audits.create_experiment({"name": "n", "hypothesis": "h", "variable": "title",
                                               "control_definition": "c", "variant_definition": "v"})
        audits.assign_video(experiment["id"], link_id, "control")
        self.device_a.run_once()
        self.device_b.run_once()
        runs_b = self._runs(self.store_b)
        self.store_b.link_published_video(runs_b["new package"], "video-0009", "2026-08-01T10:00:00+00:00")
        self.assertTrue(self.store_b.delete_analysis_run(runs_b["old package"]))

        self.device_b.run_once()
        # The package that takes the video reaches the cloud before the deletion,
        # so a device that pulls between the two never deletes the link first.
        newest = self.cloud.db.execute(
            "SELECT deleted_at IS NOT NULL FROM seo_yt_synced_packages ORDER BY updated_at DESC LIMIT 2").fetchall()
        self.assertEqual(newest, [(1,), (0,)])

        self.device_a.run_once()

        owner = "SELECT p.id, a.query FROM published_video_links p JOIN analysis_runs a ON a.id = p.analysis_run_id"
        self.assertEqual(self._query(self.store_a, owner), [(link_id, "new package")])
        self.assertEqual(self._query(self.store_a, "SELECT COUNT(*) FROM experiment_video_assignments"), [(1,)])
        self.assertNotIn("old package", self._runs(self.store_a))
        # An audit reviewed the deleted package, so it goes with it, as on the device that deleted it.
        self.assertEqual(self._query(self.store_a, "SELECT COUNT(*) FROM published_video_audits"), [(0,)])

    def test_a_deletion_that_arrives_before_the_package_taking_its_video_keeps_the_link(self):
        older = self._package(self.store_a, "old package")
        newer = self._package(self.store_a, "new package")
        link_id = self.store_a.link_published_video(older, "video-0010", "2026-08-01T10:00:00+00:00")
        # A creator's edit, kept only on this device and owned by the link.
        self.store_a.update_comparable_metadata(link_id, {"topic_category": "rain"})
        self.device_a.run_once()
        self.device_b.run_once()
        runs_b = self._runs(self.store_b)
        self.store_b.link_published_video(runs_b["new package"], "video-0010", "2026-08-01T10:00:00+00:00")
        self.assertTrue(self.store_b.delete_analysis_run(runs_b["old package"]))
        self.device_b.run_once()
        # An older version wrote the deletion first, and the hourly full pull reads both in one batch.
        self.cloud.db.execute("UPDATE seo_yt_synced_packages SET updated_at = '2000-01-01' WHERE deleted_at IS NOT NULL")
        self.device_a._pull_watermark = None

        self.device_a.run_once()

        self.assertEqual(self._query(self.store_a, "SELECT id, analysis_run_id FROM published_video_links"), [(link_id, newer)])
        self.assertEqual(self._query(self.store_a, "SELECT field_name, new_value FROM published_video_metadata_edits"),
                         [("topic_category", "rain")])

    def test_a_delete_from_a_device_behind_on_revisions_reaches_every_device(self):
        run_id = self._package(self.store_a, "shared")
        self.device_a.run_once()
        self.device_b.run_once()
        run_b = self._runs(self.store_b)["shared"]
        for title in ("Edit 1", "Edit 2"):
            self._query(self.store_b, "UPDATE analysis_runs SET title=? WHERE id=?", (title, run_b))
            self.device_b.run_once()
        self.assertTrue(self.store_a.delete_analysis_run(run_id))

        self.device_a.run_once()
        self.device_b.run_once()

        self.assertEqual(self._runs(self.store_a), {})
        self.assertEqual(self._runs(self.store_b), {})
        self.assertTrue(all(deleted_at for _revision, deleted_at in self.cloud.rows()))
        self.assertEqual(self._query(self.store_a, "SELECT pending, origin_device_id FROM cloud_sync_tombstones"), [(0, "device-a")])

    def test_an_unpushed_edit_that_loses_to_a_later_revision_is_recorded(self):
        run_id = self._package(self.store_a, "shared")
        self.device_a.run_once()
        self.device_b.run_once()
        run_b = self._runs(self.store_b)["shared"]
        for title in ("B edit 1", "B edit 2"):
            self._query(self.store_b, "UPDATE analysis_runs SET title=? WHERE id=?", (title, run_b))
            self.device_b.run_once()
        self._query(self.store_a, "UPDATE analysis_runs SET title='A edit' WHERE id=?", (run_id,))

        result = self.device_a.run_once()

        self.assertEqual(result["counts"]["pushed"], 0)
        self.assertEqual(result["counts"]["conflicts"], 1)
        self.assertEqual(self._query(self.store_a, "SELECT title FROM analysis_runs"), [("B edit 2",)])
        self.assertEqual(self._query(self.store_a, "SELECT winner, local_revision, remote_revision FROM cloud_sync_conflicts"),
                         [("remote", 2, 3)])
        self.assertEqual(self._query(self.store_a, "SELECT COUNT(*) FROM cloud_sync_outbox"), [(0,)])

    def test_a_pulled_link_without_metadata_joins_cohorts_with_default_values(self):
        run_id = self._package(self.store_a, "rain")
        link_id = self.store_a.link_published_video(run_id, "video-0003", "2026-08-01T10:00:00+00:00",
                                                    format_val="youtube_shorts", language="tamil")
        self._query(self.store_a, "DELETE FROM published_video_comparable_metadata WHERE published_video_link_id=?", (link_id,))
        self.device_a.run_once()

        self.device_b.run_once()

        self.assertEqual(self._query(self.store_b, """SELECT language, format, duration_bucket, language_source, format_source
                                                      FROM published_video_comparable_metadata"""),
                         [("tamil", "youtube_shorts", "unknown", "package", "package")])

    def test_later_pulls_fetch_only_recent_rows_and_the_table_is_checked_once(self):
        for query in ("one", "two", "three"):
            self._package(self.store_a, query)

        for _ in range(3):
            self.device_a.run_once()

        self.assertIsNone(self.cloud.pull_filters[0])
        self.assertTrue(all(self.cloud.pull_filters[1:]))
        self.assertEqual(self.cloud.schema_checks, 1)


if __name__ == "__main__":
    unittest.main()
