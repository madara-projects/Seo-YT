"""Cloud sync explains configuration faults and backs off while it cannot connect."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from win_engine.core.config import Settings
from win_engine.feedback.cloud_sync import CloudSyncConfigError, CloudSyncService, _validated_ca_path
from win_engine.feedback.history_store import HistoryStore

PEM = "-----BEGIN CERTIFICATE-----\nMIIBfixture\n-----END CERTIFICATE-----\n"


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args):
        return None

    def fetchone(self):
        return (0,)


class _Remote:
    def cursor(self):
        return _Cursor()

    def close(self):
        return None


class CloudSyncResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.dir.name) / "sync.db")
        HistoryStore(self.db_path)

    def tearDown(self) -> None:
        self.dir.cleanup()

    def _service(self, **overrides) -> CloudSyncService:
        values = {
            "database_path": self.db_path, "cloud_sync_enabled": True,
            "cloud_sync_device_id": "test-device", "cloud_sync_host": "mysql.example",
            "cloud_sync_database": "seo_yt_sync", "cloud_sync_user": "app",
            "cloud_sync_password": "secret", "cloud_sync_ssl_ca_path": "/nowhere/ca.pem",
            "cloud_sync_interval_seconds": 60, "cloud_sync_retry_max_seconds": 300,
        }
        values.update(overrides)
        return CloudSyncService(Settings(**values))

    def _write(self, name: str, text: str) -> str:
        path = Path(self.dir.name) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_the_ca_certificate_must_exist_and_be_pem(self):
        with self.assertRaisesRegex(CloudSyncConfigError, "not found at"):
            _validated_ca_path("/nowhere/ca.pem")
        with self.assertRaisesRegex(CloudSyncConfigError, "empty or is not a PEM"):
            _validated_ca_path(self._write("empty.pem", ""))
        with self.assertRaisesRegex(CloudSyncConfigError, "empty or is not a PEM"):
            _validated_ca_path(self._write("notes.txt", "not a certificate"))
        good = self._write("ca.pem", PEM)
        self.assertEqual(_validated_ca_path(good), Path(good))

    def test_a_wrong_certificate_path_is_reported_in_plain_words(self):
        service = self._service()

        result = service.run_once()
        status = service.status()

        self.assertEqual(result["state"], "offline/pending")
        self.assertIn("CA certificate not found at", status["last_error"])
        self.assertIn("WIN_ENGINE_CLOUD_SYNC_SSL_CA_PATH", status["last_error"])
        self.assertEqual(status["consecutive_failures"], 1)

    def test_driver_errors_still_expose_only_their_type(self):
        service = self._service()
        leak = ConnectionError("mysql.example:3306 user=app password=secret")
        with patch.object(service, "_remote_connection", side_effect=leak):
            service.run_once()

        self.assertEqual(service.status()["last_error"], "ConnectionError")

    def test_failed_runs_double_the_wait_up_to_the_ceiling(self):
        service = self._service()
        self.assertEqual(service.retry_delay(), 60)

        delays = []
        for _ in range(4):
            service.run_once()
            delays.append(service.retry_delay())

        self.assertEqual(delays, [120, 240, 300, 300])

    def test_a_successful_run_resets_the_backoff(self):
        service = self._service()
        service.run_once()
        service.run_once()
        self.assertEqual(service.retry_delay(), 240)

        with (
            patch.object(service, "_remote_connection", return_value=_Remote()),
            patch.object(service, "_ensure_remote_schema"),
            patch.object(service, "_push", return_value=0),
            patch.object(service, "_pull", return_value=0),
        ):
            result = service.run_once()

        self.assertEqual(result["state"], "healthy/idle")
        self.assertEqual(service.status()["consecutive_failures"], 0)
        self.assertIsNone(service.status()["last_error"])
        self.assertEqual(service.retry_delay(), 60)


if __name__ == "__main__":
    unittest.main()
