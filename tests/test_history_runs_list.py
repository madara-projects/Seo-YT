"""The saved-package list carries the angle and intent the UI shows and searches."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from win_engine.feedback.ai_shorts_store import AiShortsStore
from win_engine.feedback.history_store import HistoryStore

AI_SHORTS_MARKER = {"plan_id": 7, "parts": 2, "total_seconds": 16, "language": "english", "generation_source": "gemini"}


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

    def _insert_payload(self, title: str, payload_json: str) -> int:
        with self.store._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title, payload_json) VALUES (?, ?, ?, ?)",
                (title.lower(), datetime.now(timezone.utc).isoformat(), title, payload_json),
            )
        return int(cursor.lastrowid)

    def _saved_ai_short(self, title: str) -> tuple[int, int]:
        """A run and its plan as the AI Shorts path saves them: (run id, plan id)."""
        run_id = self.store.record_analysis_run(title.lower(), "browse", "quote", title, 7.0, "LOW", "UNMEASURED", None,
                                                {"title": title})
        plan_id = AiShortsStore(self.store).save_plan(
            analysis_run_id=run_id, quote="Stop explaining yourself", language="english", parts=2,
            plan={"total_seconds": 16, "generation_source": "gemini", "shots": []}, package={"title": title},
        )
        return run_id, plan_id

    def test_an_ai_shorts_row_carries_its_page_mark_without_the_payload(self):
        # The mark lives inside payload_json (ai_shorts_store.save_plan); the list
        # row shows it so History can tell the package apart without loading the payload.
        self._insert("A quote short", "Story", "SUGGESTED")
        _, plan_id = self._saved_ai_short("AI Short")
        self._insert_payload("Creator package", json.dumps({"title": "Creator package", "tags": ["x"]}))
        self._insert_payload("Damaged payload", "{not json")
        odd = {
            "A list": "[1, 2]", "A string": '"text"', "Null": "null", "A number": "5",
            "Wrong types": json.dumps({"source_page": 5, "ai_shorts": "x"}),
            "Empty mark": json.dumps({"source_page": "", "ai_shorts": {}}),
        }
        for title, payload_json in odd.items():
            self._insert_payload(title, payload_json)

        rows = {run["title"]: run for run in self.store.history_runs()}

        self.assertEqual((rows["AI Short"]["source_page"], rows["AI Short"]["ai_shorts"]),
                         ("ai_shorts", {**AI_SHORTS_MARKER, "plan_id": plan_id}))
        for title in ("A quote short", "Creator package", "Damaged payload", *odd):
            with self.subTest(title=title):
                self.assertEqual((rows[title]["source_page"], rows[title]["ai_shorts"]), (None, None))
        self.assertTrue(rows["Damaged payload"]["has_full_package"])  # as before: present, even if unreadable

    def test_a_package_synced_from_another_device_names_no_plan_of_this_one(self):
        # Plans stay on the device that made them; a pulled package's mark names
        # that device's plan id, which here is another run's plan or none at all.
        local_run, local_plan = self._saved_ai_short("Made here")
        synced_runs = {
            "Pulled": self._insert_payload("Pulled", json.dumps({
                "title": "Pulled", "source_page": "ai_shorts",
                "ai_shorts": {**AI_SHORTS_MARKER, "plan_id": local_plan, "shots": ["not for a list row"]},
            })),
            "Pulled, unknown plan": self._insert_payload("Pulled, unknown plan", json.dumps({
                "title": "Pulled, unknown plan", "source_page": "ai_shorts",
                "ai_shorts": {**AI_SHORTS_MARKER, "plan_id": 999},
            })),
        }
        plain_run = self._insert_payload("Creator package", json.dumps({"title": "Creator package"}))

        rows = {run["title"]: run for run in self.store.history_runs()}

        self.assertEqual(rows["Made here"]["ai_shorts"]["plan_id"], local_plan)
        for title, run_id in synced_runs.items():
            with self.subTest(title=title):
                # The chip stays and links nowhere; the row carries the mark's own keys only.
                self.assertEqual((rows[title]["source_page"], rows[title]["ai_shorts"]),
                                 ("ai_shorts", {**AI_SHORTS_MARKER, "plan_id": None}))
                detail = self.store.history_run(run_id)
                self.assertEqual((detail["source_page"], detail["ai_shorts"]),
                                 ("ai_shorts", {**AI_SHORTS_MARKER, "plan_id": None}))
        detail = self.store.history_run(local_run)
        self.assertEqual((detail["source_page"], detail["ai_shorts"]),
                         ("ai_shorts", {**AI_SHORTS_MARKER, "plan_id": local_plan}))
        self.assertEqual(detail["package"]["ai_shorts"]["plan_id"], local_plan)  # the saved payload is unchanged
        detail = self.store.history_run(plain_run)
        self.assertEqual((detail["source_page"], detail["ai_shorts"]), (None, None))
        damaged = self.store.history_run(self._insert_payload("Damaged", "{not json"))
        self.assertEqual((damaged["package"], damaged["source_page"], damaged["ai_shorts"]), (None, None, None))

    def test_a_payload_that_lost_its_mark_still_shows_the_plan_kept_here(self):
        # A cloud pull can overwrite the payload with a copy that has no mark; the
        # plan row on this device still says the run is an AI Short and which plan.
        runs = {}
        for title, payload_json in (
            ("Overwritten", json.dumps({"title": "Overwritten", "tags": ["x"]})),
            ("Damaged", "{not json"),
            ("Emptied", None),
        ):
            run_id, plan_id = self._saved_ai_short(title)
            with self.store._connect() as connection:
                connection.execute("UPDATE analysis_runs SET payload_json = ? WHERE id = ?", (payload_json, run_id))
            runs[title] = (run_id, ("ai_shorts", {**AI_SHORTS_MARKER, "plan_id": plan_id}))

        rows = {run["title"]: run for run in self.store.history_runs()}
        for title, (run_id, mark) in runs.items():
            with self.subTest(title=title):
                self.assertEqual((rows[title]["source_page"], rows[title]["ai_shorts"]), mark)
                detail = self.store.history_run(run_id)
                self.assertEqual((detail["source_page"], detail["ai_shorts"]), mark)


if __name__ == "__main__":
    unittest.main()
