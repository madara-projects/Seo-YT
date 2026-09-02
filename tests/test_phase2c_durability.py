from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from win_engine.core.config import Settings
from win_engine.feedback.cloud_sync import CloudSyncService, _hash
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.migrations import CURRENT_SCHEMA_VERSION, prepare_database


class _PushCursor:
    def __init__(self, remote): self.remote = remote
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, _sql, params):
        sync_uuid = str(params[0])
        self.remote.calls.append(sync_uuid)
        if sync_uuid in self.remote.failures:
            raise ConnectionError("simulated outage")
        self.remote.rows[sync_uuid] = params


class _PushRemote:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.rows = {}
        self.calls: list[str] = []
    def cursor(self): return _PushCursor(self)
    def commit(self): return None
    def rollback(self): return None


class _PullCursor:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, _sql): return None
    def fetchall(self): return self.rows


class _PullRemote:
    def __init__(self, rows): self.rows = rows
    def cursor(self): return _PullCursor(self.rows)


class Phase2CDurabilityTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.store = HistoryStore(self.path)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try: os.unlink(self.path + suffix)
            except FileNotFoundError: pass

    def settings(self, **overrides):
        values = {
            "database_path": self.path, "cloud_sync_enabled": True,
            "cloud_sync_device_id": "device-a", "cloud_sync_host": "mysql.example",
            "cloud_sync_database": "seo_yt_sync", "cloud_sync_user": "app",
            "cloud_sync_password": "not-used-by-tests", "cloud_sync_ssl_ca_path": __file__,
        }
        values.update(overrides)
        return Settings(**values)

    def _run(self, title="Durable package"):
        return self.store.record_analysis_run(
            title + " script", "browse", "Story", title, 8.0, "LOW", "WORKABLE", 60.0,
            {"title": title, "description": title + " description", "tags": [title.lower()]},
        )

    def _staged(self, title="Durable package"):
        run_id = self._run(title)
        service = CloudSyncService(self.settings())
        self.assertEqual(service._stage_local_packages(), 1)
        with sqlite3.connect(self.path) as connection:
            sync_uuid = connection.execute("SELECT sync_uuid FROM cloud_sync_packages WHERE analysis_run_id=?", (run_id,)).fetchone()[0]
        return service, run_id, str(sync_uuid)

    def _remote_row(self, service, run_id, *, revision=1, mutate=None):
        with sqlite3.connect(self.path) as connection:
            payload = service._package_payload(connection, run_id)
            sync_uuid = connection.execute("SELECT sync_uuid FROM cloud_sync_packages WHERE analysis_run_id=?", (run_id,)).fetchone()[0]
        if mutate:
            mutate(payload)
        payload_json = json.dumps(payload, ensure_ascii=False)
        return (sync_uuid, "device-b", revision, _hash(payload), payload_json, "2026-08-28T10:00:00+00:00", None)

    def test_local_write_survives_cloud_failure_restart_and_reconnect(self):
        service, run_id, sync_uuid = self._staged()
        failing = _PushRemote({sync_uuid})
        self.assertEqual(service._push(failing), 0)
        with sqlite3.connect(self.path) as connection:
            pending = connection.execute("SELECT attempt_count,last_error FROM cloud_sync_outbox WHERE sync_uuid=?", (sync_uuid,)).fetchone()
            self.assertIsNotNone(connection.execute("SELECT 1 FROM analysis_runs WHERE id=?", (run_id,)).fetchone())
        self.assertEqual(pending, (1, "ConnectionError"))

        restarted = CloudSyncService(self.settings())
        remote = _PushRemote()
        self.assertEqual(restarted._push(remote), 1)
        self.assertEqual(len(remote.rows), 1)
        with sqlite3.connect(self.path) as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM cloud_sync_outbox WHERE sync_uuid=?", (sync_uuid,)).fetchone())

    def test_connection_outage_marks_durable_pending_state_without_losing_local_run(self):
        run_id = self._run("Outage package")
        service = CloudSyncService(self.settings())
        with patch.object(service, "_remote_connection", side_effect=TimeoutError("simulated")):
            result = service.run_once()
        self.assertEqual(result["state"], "offline/pending")
        with sqlite3.connect(self.path) as connection:
            outbox = connection.execute("SELECT attempt_count,last_error FROM cloud_sync_outbox").fetchone()
            local_run = connection.execute("SELECT 1 FROM analysis_runs WHERE id=?", (run_id,)).fetchone()
        self.assertEqual(outbox, (1, "TimeoutError"))
        self.assertIsNotNone(local_run)

    def test_partial_batch_failure_acknowledges_peers_and_retries_only_failed_item(self):
        service = CloudSyncService(self.settings())
        run_ids = [self._run("Package " + label) for label in ("A", "B", "C")]
        self.assertEqual(service._stage_local_packages(), 3)
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT sync_uuid,analysis_run_id FROM cloud_sync_packages ORDER BY analysis_run_id").fetchall()
        failed_uuid = str(rows[1][0])
        remote = _PushRemote({failed_uuid})
        self.assertEqual(service._push(remote), 2)
        self.assertEqual(service._last_push_failures, 1)
        with sqlite3.connect(self.path) as connection:
            pending = connection.execute("SELECT sync_uuid FROM cloud_sync_outbox").fetchall()
        self.assertEqual(pending, [(failed_uuid,)])
        remote.failures.clear()
        self.assertEqual(service._push(remote), 1)
        self.assertEqual(set(remote.rows), {str(row[0]) for row in rows})
        self.assertEqual(len(run_ids), 3)

    def test_duplicate_replay_after_remote_success_is_idempotent(self):
        service, _run_id, sync_uuid = self._staged()
        remote = _PushRemote()
        # Simulates a crash after the remote transaction committed but before
        # the local outbox acknowledgement: the same UUID remains pending.
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT revision,payload_json,content_hash FROM cloud_sync_outbox WHERE sync_uuid=?", (sync_uuid,)).fetchone()
        self.assertEqual(service._push(remote), 1)
        with sqlite3.connect(self.path) as connection:
            connection.execute("INSERT INTO cloud_sync_outbox(sync_uuid,revision,payload_json,content_hash,queued_at) VALUES(?,?,?,?,?)", (sync_uuid, row[0], row[1], row[2], "restart"))
        self.assertEqual(service._push(remote), 1)
        self.assertEqual(set(remote.rows), {sync_uuid})

    def test_pull_conflict_uses_revision_then_hash_and_records_decision(self):
        service, run_id, sync_uuid = self._staged()
        remote_row = self._remote_row(service, run_id)
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE cloud_sync_packages SET content_hash=?, revision=1 WHERE sync_uuid=?", ("0" * 64, sync_uuid))
        self.assertEqual(service._pull(_PullRemote([remote_row])), 1)
        with sqlite3.connect(self.path) as connection:
            conflict = connection.execute("SELECT winner FROM cloud_sync_conflicts WHERE sync_uuid=?", (sync_uuid,)).fetchone()
            restored_hash = connection.execute("SELECT content_hash FROM cloud_sync_packages WHERE sync_uuid=?", (sync_uuid,)).fetchone()[0]
        self.assertEqual(conflict, ("remote",))
        self.assertEqual(restored_hash, remote_row[3])

        # Equal revisions with a lexicographically lower remote hash leave the
        # local payload in place and write an explicit local-winner audit row.
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE cloud_sync_packages SET content_hash=? WHERE sync_uuid=?", ("f" * 64, sync_uuid))
        lower_remote = (sync_uuid, "device-b", 1, remote_row[3], remote_row[4], remote_row[5], None)
        self.assertEqual(service._pull(_PullRemote([lower_remote])), 0)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT winner FROM cloud_sync_conflicts WHERE sync_uuid=? ORDER BY id DESC LIMIT 1", (sync_uuid,)).fetchone(), ("local",))

        # A lower remote revision never overwrites the newer local mapping.
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE cloud_sync_packages SET revision=3 WHERE sync_uuid=?", (sync_uuid,))
        self.assertEqual(service._pull(_PullRemote([(sync_uuid, "device-b", 2, remote_row[3], remote_row[4], remote_row[5], None)])), 0)

    def test_tombstone_blocks_stale_active_replay_and_is_idempotent(self):
        service, run_id, sync_uuid = self._staged()
        active = self._remote_row(service, run_id)
        self.assertTrue(self.store.delete_analysis_run(run_id))
        tombstone = (sync_uuid, "device-a", 2, "tombstone", "{}", "2026-08-28T10:00:00+00:00", "2026-08-28T10:00:00+00:00")
        self.assertEqual(service._pull(_PullRemote([tombstone])), 0)
        self.assertEqual(service._pull(_PullRemote([active, tombstone])), 0)
        with sqlite3.connect(self.path) as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM analysis_runs WHERE id=?", (run_id,)).fetchone())
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM cloud_sync_tombstones WHERE sync_uuid=?", (sync_uuid,)).fetchone()[0], 1)

    def test_repeated_tombstone_push_uses_one_remote_identity(self):
        service, run_id, sync_uuid = self._staged("Delete replay")
        self.assertTrue(self.store.delete_analysis_run(run_id))
        remote = _PushRemote()
        self.assertEqual(service._push(remote), 1)
        with sqlite3.connect(self.path) as connection:
            connection.execute("UPDATE cloud_sync_tombstones SET pending=1 WHERE sync_uuid=?", (sync_uuid,))
        self.assertEqual(service._push(remote), 1)
        self.assertEqual(set(remote.rows), {sync_uuid})

    def test_restore_is_idempotent_and_preserves_completed_local_evidence(self):
        source, run_id, _sync_uuid = self._staged("Observed package")
        link_id = self.store.link_published_video(run_id, "video-2", "2026-08-20T00:00:00+00:00")
        self.store.record_performance_snapshot("video-2", 24, views=100, likes=10, snapshot_window="24h")
        self.assertEqual(source._stage_local_packages(), 1)
        remote_row = self._remote_row(source, run_id, revision=2)

        target_handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        target_path = target_handle.name
        target_handle.close()
        self.addCleanup(lambda: os.path.exists(target_path) and os.unlink(target_path))
        HistoryStore(target_path)
        target = CloudSyncService(self.settings(database_path=target_path, cloud_sync_device_id="device-b"))
        self.assertEqual(target._pull(_PullRemote([remote_row])), 1)
        self.assertEqual(target._pull(_PullRemote([remote_row])), 0)
        with sqlite3.connect(target_path) as connection:
            snapshot = connection.execute("SELECT views FROM video_performance_snapshots WHERE youtube_video_id='video-2' AND snapshot_window='24h'").fetchone()
        self.assertEqual(snapshot, (100,))
        self.assertGreater(link_id, 0)

    def test_cloud_disabled_keeps_local_history_operational(self):
        disabled = CloudSyncService(self.settings(cloud_sync_enabled=False))
        run_id = self._run("Offline package")
        self.assertEqual(disabled.run_once()["state"], "disabled")
        self.assertEqual(self.store.history_run(run_id)["title"], "Offline package")

    def test_payload_is_limited_to_the_documented_history_projection(self):
        service, run_id, _sync_uuid = self._staged("Scoped package")
        with sqlite3.connect(self.path) as connection:
            payload = service._package_payload(connection, run_id)
        self.assertEqual(set(payload), {"schema", "analysis", "selection", "linked_video"})
        serialized = json.dumps(payload).casefold()
        self.assertNotIn("oauth", serialized)
        self.assertNotIn("cloud_sync_password", serialized)
        self.assertNotIn("watchlist", serialized)
        self.assertNotIn("experiment", serialized)

    def test_invalid_remote_payload_is_skipped_without_local_mutation(self):
        service, run_id, sync_uuid = self._staged("Safe package")
        with sqlite3.connect(self.path) as connection:
            before = connection.execute("SELECT title FROM analysis_runs WHERE id=?", (run_id,)).fetchone()[0]
        bad = (sync_uuid, "device-b", 2, "not-a-valid-hash", "{bad json", "2026-08-28T10:00:00+00:00", None)
        self.assertEqual(service._pull(_PullRemote([bad])), 0)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("SELECT title FROM analysis_runs WHERE id=?", (run_id,)).fetchone()[0], before)

    def test_v8_database_migrates_conflict_audit_without_data_reset(self):
        run_id = self._run("Migration package")
        with sqlite3.connect(self.path) as connection:
            connection.execute("DROP TABLE cloud_sync_conflicts")
            connection.execute("PRAGMA user_version = 8")
        result = prepare_database(self.path)
        self.assertEqual(result.new_version, CURRENT_SCHEMA_VERSION)
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 9)
            self.assertIsNotNone(connection.execute("SELECT 1 FROM analysis_runs WHERE id=?", (run_id,)).fetchone())
            self.assertIsNotNone(connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cloud_sync_conflicts'").fetchone())


if __name__ == "__main__":
    unittest.main()
