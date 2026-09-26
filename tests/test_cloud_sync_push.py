"""A push only acknowledges versions the cloud kept, never blocks local writers, and stops on a dead session."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

import pymysql

from win_engine.core.config import Settings
from win_engine.feedback.cloud_sync import CloudSyncService
from win_engine.feedback.history_store import HistoryStore


class _PushCursor:
    def __init__(self, remote):
        self.remote = remote
        self.result = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        if " ".join(sql.split()).startswith("SELECT content_hash"):
            self.result = [self.remote.cloud_version] if self.remote.cloud_version else []
            return len(self.result)
        if not sql.lstrip().startswith("INSERT"):
            self.result = []
            return 0
        self.remote.pushed.append(params)
        if self.remote.during_push:
            self.remote.during_push()
        if self.remote.error:
            raise self.remote.error
        return self.remote.affected

    def fetchone(self):
        return self.result[0] if self.result else None


class _PushRemote:
    def __init__(self, *, affected=1, cloud_version=None, error=None, during_push=None):
        self.affected = affected
        self.cloud_version = cloud_version
        self.error = error
        self.during_push = during_push
        self.pushed: list = []

    def cursor(self):
        return _PushCursor(self)

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


class CloudPushTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.path = handle.name
        self.addCleanup(self._remove)
        self.store = HistoryStore(self.path)
        self.service = self._service("device-b")

    def _remove(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.path + suffix)
            except FileNotFoundError:
                pass

    def _service(self, device_id):
        return CloudSyncService(Settings(
            database_path=self.path, cloud_sync_enabled=True, cloud_sync_device_id=device_id,
            cloud_sync_host="mysql.example", cloud_sync_database="seo_yt_sync", cloud_sync_user="app",
            cloud_sync_password="not-used", cloud_sync_ssl_ca_path=__file__,
        ))

    def _package(self, query, video_id=None):
        run_id = self.store.record_analysis_run(query, "browse", "emotion", query.title(), 7.0, "LOW", "WORKABLE", 50, {"d": query})
        if video_id:
            self.store.link_published_video(run_id, video_id, "2026-08-01T10:00:00+00:00")
        return run_id

    def _query(self, sql, params=()):
        with sqlite3.connect(self.path) as connection:
            return connection.execute(sql, params).fetchall()

    def _sync_uuid(self, run_id):
        return self._query("SELECT sync_uuid FROM cloud_sync_packages WHERE analysis_run_id=?", (run_id,))[0][0]

    def test_a_version_the_cloud_did_not_keep_stays_queued_and_forces_one_full_pull(self):
        self._package("shared package")
        self.service._stage_local_packages()
        self.service._pull_watermark = "2026-08-28T10:00:00+00:00"
        remote = _PushRemote(affected=0, cloud_version=("f" * 64, None))

        self.assertEqual(self.service._push(remote), 0)

        self.assertEqual(self._query("SELECT last_error FROM cloud_sync_outbox"), [("superseded",)])
        self.assertIsNone(self.service._pull_since())
        self.service._full_pull_needed = False
        self.service._push(remote)
        self.assertFalse(self.service._full_pull_needed)

    def test_a_replayed_version_the_cloud_already_holds_counts_as_pushed(self):
        run_id = self._package("shared package")
        self.service._stage_local_packages()
        content_hash = self._query("SELECT content_hash FROM cloud_sync_outbox")[0][0]

        self.assertEqual(self.service._push(_PushRemote(affected=0, cloud_version=(content_hash, None))), 1)

        self.assertEqual(self._query("SELECT COUNT(*) FROM cloud_sync_outbox"), [(0,)])
        self.assertEqual(self._query("SELECT last_synced_hash FROM cloud_sync_packages WHERE analysis_run_id=?", (run_id,)),
                         [(content_hash,)])

    def test_pushing_never_holds_the_local_write_lock_during_a_cloud_call(self):
        for query in ("first package", "second package"):
            self._package(query)
        self.service._stage_local_packages()
        writes = []

        def write_from_a_request():
            connection = sqlite3.connect(self.path, timeout=0.2)
            try:
                connection.execute("INSERT INTO content_ideas(topic,created_at,updated_at) VALUES('idea','t','t')")
                connection.commit()
                writes.append("ok")
            except sqlite3.OperationalError as exc:
                writes.append(str(exc))
            finally:
                connection.close()

        self.assertEqual(self.service._push(_PushRemote(during_push=write_from_a_request)), 2)

        self.assertEqual(writes, ["ok", "ok"])

    def test_a_lost_connection_stops_the_push_and_fails_the_run(self):
        for query in ("first package", "second package"):
            self._package(query)
        remote = _PushRemote(error=pymysql.err.OperationalError(2013, "Lost connection to MySQL server during query"))
        self.service._remote_connection = lambda: remote

        result = self.service.run_once()

        self.assertEqual(result["state"], "offline/pending")
        self.assertEqual(len(remote.pushed), 1)
        status = self.service.status()
        self.assertEqual(status["last_error"], "OperationalError")
        self.assertEqual(status["consecutive_failures"], 1)

    def test_packages_that_carry_a_link_are_pushed_first(self):
        self._package("unlinked package")
        linked = self._package("linked package", video_id="video-1")
        self.service._stage_local_packages()
        remote = _PushRemote()

        self.service._push(remote)

        self.assertEqual(remote.pushed[0][0], self._sync_uuid(linked))

    def test_a_pushed_delete_records_this_device_as_its_origin(self):
        run_id = self._package("synced elsewhere")
        self._service("device-a")._stage_local_packages()
        self.assertTrue(self.store.delete_analysis_run(run_id))
        remote = _PushRemote()

        self.assertEqual(self.service._push(remote), 1)

        self.assertEqual(remote.pushed[0][1], "device-b")
        self.assertEqual(self._query("SELECT origin_device_id, pending FROM cloud_sync_tombstones"), [("device-b", 0)])

    def test_a_failed_row_is_logged_by_class_and_short_id_only(self):
        run_id = self._package("shared package")
        self.service._stage_local_packages()
        remote = _PushRemote(error=ValueError("mysql.example:3306 user=app password=secret"))

        with self.assertLogs("win_engine.feedback.cloud_sync", level="WARNING") as logs:
            self.assertEqual(self.service._push(remote), 0)

        self.assertIn("ValueError", logs.output[0])
        self.assertIn(self._sync_uuid(run_id)[:8], logs.output[0])
        self.assertNotIn("secret", "".join(logs.output))


if __name__ == "__main__":
    unittest.main()
