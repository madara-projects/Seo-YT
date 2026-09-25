"""The saved-package list carries the angle and intent the UI shows and searches."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from win_engine.feedback.history_store import HistoryStore


class HistoryRunsListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.store = HistoryStore(str(Path(self.dir.name) / "history.db"))

    def tearDown(self) -> None:
        self.dir.cleanup()

    def _insert(self, title: str, content_angle: str | None, intent: str | None) -> None:
        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title, content_angle, intent) VALUES (?, ?, ?, ?, ?)",
                (title.lower(), datetime.now(timezone.utc).isoformat(), title, content_angle, intent),
            )

    def test_each_row_includes_its_angle_and_intent(self):
        self._insert("A quote short", "Story", "SUGGESTED")

        run = self.store.history_runs()[0]

        self.assertEqual(run["content_angle"], "Story")
        self.assertEqual(run["intent"], "SUGGESTED")

    def test_older_rows_without_them_report_none_rather_than_a_guess(self):
        self._insert("An older record", None, None)

        run = self.store.history_runs()[0]

        self.assertIsNone(run["content_angle"])
        self.assertIsNone(run["intent"])


if __name__ == "__main__":
    unittest.main()
