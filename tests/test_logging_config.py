"""Debug logging stays safe to turn on, and the level setting accepts any case."""
from __future__ import annotations

import logging
import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

# The app's imports create the libraries' real loggers, as in a running server.
import win_engine.api.app  # noqa: F401
from win_engine.core.config import Settings
from win_engine.core.logging import configure_logging

# Libraries that print OAuth codes, client secrets, tokens or API keys in
# their DEBUG (httpx: INFO) lines, and chatty transports.
QUIET_LOGGERS = (
    "requests_oauthlib.oauth2_session",
    "oauthlib.oauth2.rfc6749",
    "googleapiclient.discovery",
    "google_auth_httplib2",
    "httplib2",
    "google.auth.transport.requests",
    "google.oauth2._client",
    "google_auth_oauthlib.flow",
    "urllib3.connectionpool",
    "httpx",
    "httpcore.http11",
    "uvicorn.access",
)


class DebugLoggingTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_logging("INFO")

    def test_debug_level_keeps_secret_printing_libraries_at_warning(self):
        configure_logging("DEBUG")

        self.assertTrue(logging.getLogger("win_engine.api.app").isEnabledFor(logging.DEBUG))
        for name in QUIET_LOGGERS:
            with self.subTest(logger=name):
                self.assertEqual(logging.getLogger(name).getEffectiveLevel(), logging.WARNING)
                self.assertFalse(logging.getLogger(name).isEnabledFor(logging.INFO))


class LogLevelSettingTests(unittest.TestCase):
    def test_the_level_is_case_insensitive(self):
        self.assertEqual(Settings(log_level="info").log_level, "INFO")
        self.assertEqual(Settings(log_level=" Debug ").log_level, "DEBUG")
        with patch.dict(os.environ, {"WIN_ENGINE_LOG_LEVEL": "warning"}):
            self.assertEqual(Settings().log_level, "WARNING")

    def test_an_unknown_level_still_stops_startup(self):
        with self.assertRaises(ValidationError):
            Settings(log_level="verbose")


if __name__ == "__main__":
    unittest.main()
