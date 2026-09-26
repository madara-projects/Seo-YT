"""The sync thread survives local failures, answers requests without blocking, and reschedules sensibly."""
from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from win_engine.api import app as app_module
from win_engine.core.config import Settings
from win_engine.feedback import cloud_sync
from win_engine.feedback.cloud_sync import CloudSyncService
from win_engine.feedback.history_store import DatabaseUnavailable, HistoryStore


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        return None

    def fetchone(self):
        return (0,)


class _Remote:
    def cursor(self):
        return _Cursor()

    def close(self):
        return None


def _wait_for(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


class CloudSyncLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = str(Path(self.dir.name) / "sync.db")
        self.store = HistoryStore(self.path)

    def _service(self, **overrides):
        values = {
            "database_path": self.path, "cloud_sync_enabled": True, "cloud_sync_device_id": "test-device",
            "cloud_sync_host": "mysql.example", "cloud_sync_database": "seo_yt_sync", "cloud_sync_user": "app",
            "cloud_sync_password": "not-used", "cloud_sync_ssl_ca_path": __file__,
            "cloud_sync_interval_seconds": 60, "cloud_sync_retry_max_seconds": 900,
            "cloud_sync_initial_delay_seconds": 3600,
        }
        values.update(overrides)
        service = CloudSyncService(Settings(**values))
        self.addCleanup(service.stop)
        return service

    def _succeed_against_the_cloud(self, service):
        service._remote_connection = lambda: _Remote()
        service._ensure_remote_schema = Mock()
        service._push = Mock(return_value=0)
        service._pull = Mock(return_value=0)

    def test_a_failure_while_recording_a_failed_run_does_not_end_the_thread(self):
        service = self._service(cloud_sync_initial_delay_seconds=0)
        locked = sqlite3.OperationalError("database is locked")
        service._stage_local_packages = Mock(side_effect=locked)
        service._mark_all_pending_failures = Mock(side_effect=locked)

        service.start()

        self.assertTrue(_wait_for(lambda: service.status()["retry_delay_seconds"] is not None))
        self.assertTrue(service._thread.is_alive())
        status = service.status()
        self.assertEqual(status["state"], "offline/pending")
        self.assertFalse(status["running"])

    def test_request_run_wakes_the_thread_and_returns_the_status_at_once(self):
        service = self._service()
        ran = threading.Event()
        service._run = Mock(side_effect=lambda **_kwargs: ran.set())
        service.start()

        result = service.request_run()

        self.assertTrue(result["run_requested"])
        self.assertIn("pending_uploads", result)
        self.assertTrue(ran.wait(5))

    def test_request_run_without_a_running_thread_only_returns_the_status(self):
        service = self._service()
        service._run = Mock()

        result = service.request_run()

        self.assertFalse(result["run_requested"])
        self.assertEqual(result["state"], "waiting")
        service._run.assert_not_called()

    def test_a_manual_run_that_reaches_the_cloud_ends_the_backoff_wait(self):
        service = self._service(cloud_sync_initial_delay_seconds=0)
        service._remote_connection = Mock(side_effect=ConnectionError("offline"))
        service.start()
        self.assertTrue(_wait_for(lambda: service.status()["retry_delay_seconds"] == 120))
        self._succeed_against_the_cloud(service)

        service.run_once()

        status = service.status()
        self.assertEqual(status["consecutive_failures"], 0)
        self.assertEqual(status["retry_delay_seconds"], 60)
        next_run = datetime.fromisoformat(status["next_run_at"])
        self.assertLess(next_run, datetime.now(timezone.utc) + timedelta(seconds=61))

    def test_a_stopped_service_can_start_again(self):
        service = self._service()
        service.start()
        service.stop()
        self.assertIsNone(service._thread)

        service.start()
        time.sleep(0.2)

        self.assertTrue(service._thread.is_alive())

    def test_starting_again_after_a_stop_that_timed_out_leaves_one_running_loop(self):
        service = self._service()
        service.start()
        loop = service._thread
        service._stop.set()  # what stop() leaves behind when its join times out during a run

        service.start()

        self.assertTrue(service._loop_alive())
        service._wake.set()  # the old loop wakes, sees its own stop signal and ends
        loop.join(5)
        self.assertFalse(loop.is_alive())
        self.assertTrue(service._loop_alive())

    def test_a_restart_while_the_old_loop_is_ending_leaves_a_running_loop(self):
        service = self._service()
        ending, release = threading.Event(), threading.Event()
        run_loop = service._loop

        def loop_then_linger(*args):
            run_loop(*args)
            ending.set()
            release.wait(5)  # still alive, but past its last look at the stop signal

        service._loop = loop_then_linger
        service.start()
        old_loop = service._thread
        service._stop.set()  # what stop() leaves behind when its join times out
        service._wake.set()
        self.assertTrue(ending.wait(5))

        service.start()
        release.set()
        old_loop.join(5)

        self.assertTrue(service._loop_alive())

    def test_a_run_before_the_database_can_be_prepared_backs_off_without_touching_it(self):
        service = self._service()
        service._stage_local_packages = Mock()
        service._mark_all_pending_failures = Mock()

        with patch.object(cloud_sync, "HistoryStore", side_effect=DatabaseUnavailable("not prepared")):
            result = service._run(blocking=True)

        self.assertEqual(result["state"], "offline/pending")
        self.assertEqual(service.status()["consecutive_failures"], 1)
        service._stage_local_packages.assert_not_called()
        service._mark_all_pending_failures.assert_not_called()

    def test_background_work_starts_even_when_the_database_cannot_be_prepared_at_start_up(self):
        with (
            patch.object(app_module, "HistoryStore", side_effect=DatabaseUnavailable("not prepared")),
            patch.object(app_module.SnapshotCollector, "start") as collector_start,
            patch.object(app_module.CloudSyncService, "start") as cloud_start,
            patch.object(app_module.SnapshotCollector, "stop"),
            patch.object(app_module.CloudSyncService, "stop"),
        ):
            with TestClient(app_module.create_app()):
                pass

        collector_start.assert_called_once()
        cloud_start.assert_called_once()

    def test_a_package_deleted_while_it_is_staged_is_skipped(self):
        gone_before = self.store.record_analysis_run("gone before", "browse", "emotion", "A", 7.0, "LOW", "WORKABLE", 50, {})
        gone_after = self.store.record_analysis_run("gone after", "browse", "emotion", "B", 7.0, "LOW", "WORKABLE", 50, {})
        self.store.record_analysis_run("kept", "browse", "emotion", "C", 7.0, "LOW", "WORKABLE", 50, {})
        service = self._service()
        build = service._package_payload

        def delete_while_staging(connection, run_id):
            if run_id == gone_before:
                self.store.delete_analysis_run(run_id)
            payload = build(connection, run_id)
            if run_id == gone_after:
                self.store.delete_analysis_run(run_id)
            return payload

        service._package_payload = delete_while_staging

        self.assertEqual(service._stage_local_packages(), 1)

    def test_status_logs_when_local_counts_are_unavailable(self):
        service = self._service()

        with patch.object(cloud_sync, "connect_managed", side_effect=sqlite3.OperationalError("disk I/O error")), \
                self.assertLogs("win_engine.feedback.cloud_sync", level="WARNING") as logs:
            status = service.status()

        self.assertIsNone(status["pending_uploads"])
        self.assertIn("OperationalError", logs.output[0])

    def test_the_cloud_table_is_checked_once_and_again_after_a_failed_run(self):
        service = self._service()
        self._succeed_against_the_cloud(service)
        service.run_once()
        service.run_once()
        self.assertEqual(service._ensure_remote_schema.call_count, 1)

        service._push.side_effect = ConnectionError("dropped")
        service.run_once()
        service._push.side_effect = None
        service.run_once()

        self.assertEqual(service._ensure_remote_schema.call_count, 2)


if __name__ == "__main__":
    unittest.main()
