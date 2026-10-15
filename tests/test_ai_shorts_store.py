"""The AI Shorts plan store: plans live and die with their History run, and damaged rows still read."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from win_engine.feedback.ai_shorts_store import AiShortsStore
from win_engine.feedback.history_store import HistoryStore

PLAN = {"total_seconds": 16, "generation_source": "gemini", "shots": [{"part": 1}, {"part": 2}]}
HINDI = "कभी कभी चुप रहना ही सबसे बड़ा जवाब होता है 🌧️"


class AiShortsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.history = HistoryStore(str(Path(self.dir.name) / "history.db"))
        self.store = AiShortsStore(self.history)

    def _run(self, title: str = "A quote short") -> int:
        return self.history.record_analysis_run(title.lower(), "browse", "quote", title, 7.0, "LOW", "UNMEASURED", None,
                                                {"title": title})

    def _saved(self, quote: str = "Stop explaining yourself", title: str = "A quote short") -> tuple[int, int]:
        run_id = self._run(title)
        plan_id = self.store.save_plan(analysis_run_id=run_id, quote=quote, language="english", parts=2, plan=PLAN,
                                       package={"title": title})
        return run_id, plan_id

    def _count(self, table: str) -> int:
        with self.history._connect() as connection:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def test_the_runs_listed_title_follows_the_saved_packages_title(self):
        # History lists the run's title column; a package finalized after the run
        # was recorded must not leave the list showing an older title.
        run_id = self._run("Draft title")
        self.store.save_plan(analysis_run_id=run_id, quote="q", language="english", parts=1, plan=PLAN,
                             package={"title": "Final title 🖤 #shorts"})
        run = self.history.history_run(run_id)
        self.assertEqual((run["title"], run["package"]["title"]), ("Final title 🖤 #shorts", "Final title 🖤 #shorts"))
        # A package without a title keeps the run's own.
        other = self._run("Kept title")
        self.store.save_plan(analysis_run_id=other, quote="q", language="english", parts=1, plan=PLAN, package={})
        self.assertEqual(self.history.history_run(other)["title"], "Kept title")

    def test_a_plan_for_a_run_that_does_not_exist_is_refused_and_writes_nothing(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_plan(analysis_run_id=999, quote="q", language="english", parts=2, plan=PLAN, package={})
        self.assertEqual(self._count("ai_short_plans"), 0)

    def test_deleting_runs_in_bulk_or_resetting_removes_their_plans(self):
        first, _ = self._saved(title="First")
        second, _ = self._saved(title="Second")
        kept, kept_plan = self._saved(title="Kept")
        plain = self._run("Plain package")

        self.assertEqual(sorted(self.history.delete_analysis_runs([first, second, plain])), sorted([first, second, plain]))

        self.assertEqual([plan["id"] for plan in self.store.plans()], [kept_plan])
        self.history.reset_database()
        self.assertEqual((self._count("ai_short_plans"), self.store.plans(), self.store.plan(kept_plan)), (0, [], None))
        self.assertIsNone(self.history.history_run(kept))

    def test_a_damaged_plan_still_lists_and_reads(self):
        _, plan_id = self._saved()
        for damaged in ("{not json", "[1, 2]", "", "null"):
            with self.subTest(plan_json=damaged):
                with self.history._connect() as connection:
                    connection.execute("UPDATE ai_short_plans SET plan_json = ? WHERE id = ?", (damaged, plan_id))
                self.assertIsNone(self.store.plans()[0]["total_seconds"])
                plan = self.store.plan(plan_id)
                self.assertEqual((plan["id"], plan["package"]["ai_shorts"]["plan_id"]), (plan_id, plan_id))
                self.assertNotIn("shots", plan)

    def test_a_plan_left_behind_by_its_run_is_hidden_and_deleted_alone(self):
        # A run removed without foreign keys (an older tool, a manual edit) leaves its plan behind.
        run_id, plan_id = self._saved()
        connection = sqlite3.connect(self.history.database_path)
        connection.execute("DELETE FROM analysis_runs WHERE id = ?", (run_id,))
        connection.commit()
        connection.close()

        self.assertEqual((self.store.plans(), self.store.plan(plan_id)), ([], None))
        self.assertTrue(self.store.delete_plan(plan_id))
        self.assertEqual(self._count("ai_short_plans"), 0)
        self.assertFalse(self.store.delete_plan(plan_id))

    def test_the_list_is_bounded_and_newest_first(self):
        ids = [self._saved(title=f"Short {index}")[1] for index in range(3)]
        self.assertEqual([plan["id"] for plan in self.store.plans()], ids[::-1])
        self.assertEqual(len(self.store.plans(0)), 1)
        self.assertEqual(len(self.store.plans(-5)), 1)
        self.assertEqual(len(self.store.plans(10 ** 9)), 3)

    def test_a_plan_saved_before_adjustments_reads_its_automatic_fixes_apart(self):
        warnings = [
            "Part 1: added a calm upper-middle, audio line, no dialogue, narration or music",
            "Part 1 repeats a recent scene on this channel (a hill); regenerate for a different one.",
            "Part 2: trimmed from 201 to 180 words",
        ]
        plan_id = self.store.save_plan(analysis_run_id=self._run(), quote="q", language="english", parts=2,
                                       plan={**PLAN, "checks": {"passed": True, "issues": [], "warnings": warnings}},
                                       package={})
        checks = self.store.plan(plan_id)["checks"]
        self.assertEqual(checks["warnings"], [warnings[1]])
        self.assertEqual(checks["adjustments"], [warnings[0], warnings[2]])
        # A plan made since keeps its own split, and damaged checks are left alone.
        newer = {"passed": True, "issues": [], "warnings": [], "adjustments": ["Shared scene: a lens"]}
        plan_id = self.store.save_plan(analysis_run_id=self._run("Newer"), quote="q", language="english", parts=1,
                                       plan={**PLAN, "checks": newer}, package={})
        self.assertEqual(self.store.plan(plan_id)["checks"], newer)
        plan_id = self.store.save_plan(analysis_run_id=self._run("Odd"), quote="q", language="english", parts=1,
                                       plan={**PLAN, "checks": "unreadable"}, package={})
        self.assertEqual(self.store.plan(plan_id)["checks"], "unreadable")

    def test_unicode_quotes_round_trip(self):
        run_id, plan_id = self._saved(quote=HINDI, title="चुप")
        listed = self.store.plans()[0]
        self.assertEqual((listed["quote"], listed["package_title"], listed["analysis_run_id"]), (HINDI, "चुप", run_id))
        self.assertEqual(self.store.plan(plan_id)["package"]["title"], "चुप")


if __name__ == "__main__":
    unittest.main()
