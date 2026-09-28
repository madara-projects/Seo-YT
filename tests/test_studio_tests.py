"""YouTube Studio title/thumbnail tests: prepared here, run by YouTube, recorded by the creator."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore, RelinkWouldDeleteEvidence
from win_engine.feedback.studio_tests import (
    MAX_VARIANTS,
    SHORTS_NOTE,
    CreateStudioTestRequest,
    StudioTestError,
    StudioTestStore,
    UpdateStudioTestRequest,
)

PACKAGES = [
    {"package_id": "package-a", "title": "How I Fixed My Sleep Schedule in 7 Days", "thumbnail_text": "7 DAYS"},
    {"package_id": "package-b", "title": "How I Fixed My Sleep Schedule in Seven Days", "thumbnail_text": "SLEEP FIXED"},
    {"package_id": "package-c", "title": "The Night Routine That Finally Worked", "thumbnail_text": "IT WORKED"},
    {"package_id": "package-d", "title": "Why Your Alarm Is Not the Problem", "thumbnail_text": "NOT THE ALARM"},
]
LONG_PAYLOAD = {
    "title": PACKAGES[0]["title"],
    "creator_brief": {"video_format": "tutorial", "content": "A twelve minute tutorial on fixing a sleep schedule."},
    "title_thumbnail_packages": PACKAGES,
}
SHORT_PAYLOAD = {
    "title": "Sleep in 30 seconds",
    "creator_brief": {"video_format": "youtube_shorts", "content": "A 30 second Short."},
    "title_thumbnail_packages": PACKAGES[:3],
}


class StudioTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.settings = Settings(database_path=str(Path(self.dir.name) / "studio.db"))
        self.history = HistoryStore(self.settings.database_path)
        self.store = StudioTestStore(self.history)

    def run_id(self, payload: dict = LONG_PAYLOAD) -> int:
        return self.history.record_analysis_run("sleep", "search", "tutorial", payload.get("title", "t"), 7.0, "LOW", "WORKABLE", 50, payload)

    def link(self, run_id: int, video_id: str = "sleepvideo1", format_val: str = "tutorial") -> int:
        return self.history.link_published_video(
            run_id, video_id, "2026-09-01T00:00:00+00:00", format_val=format_val, ownership_state="verified",
            ownership_verified=True, verified_channel_id="UC-owner", ownership_verified_at="2026-09-01T00:00:00+00:00",
        )


class PrepareTests(StudioTestCase):
    def test_the_overview_offers_the_saved_packages_and_flags_near_identical_titles(self):
        overview = self.store.overview(self.run_id())

        self.assertTrue(overview["eligible"])
        self.assertEqual(overview["max_variants"], MAX_VARIANTS)
        self.assertEqual([item["package_id"] for item in overview["candidates"]], ["package-a", "package-b", "package-c", "package-d"])
        self.assertEqual(overview["candidates"][1]["thumbnail_text"], "SLEEP FIXED")
        pairs = {(pair["first"], pair["second"]) for pair in overview["similar_pairs"]}
        self.assertEqual(pairs, {("package-a", "package-b")})
        # The app's own comparisons are not YouTube's test, and it never runs one.
        self.assertIn("not equivalent", overview["note"])
        self.assertIn("never runs", overview["note"])

    def test_a_prepared_test_keeps_the_saved_titles_and_thumbnail_texts(self):
        run_id = self.run_id()
        test = self.store.create(run_id, ["package-c", "package-a", "package-b"], notes="try the promise first")

        self.assertEqual(test["status"], "prepared")
        self.assertEqual([variant["label"] for variant in test["variants"]], ["A", "B", "C"])
        self.assertEqual(test["variants"][0], {
            "label": "A", "package_id": "package-c", "title": PACKAGES[2]["title"], "thumbnail_text": "IT WORKED",
        })
        self.assertEqual(test["notes"], "try the promise first")
        self.assertIsNone(test["linked_video"])
        self.assertEqual([(pair["first"], pair["second"]) for pair in test["similar_pairs"]], [("B", "C")])
        self.assertIn("too similar", test["similar_pairs"][0]["message"])
        self.assertEqual([item["id"] for item in self.store.overview(run_id)["tests"]], [test["id"]])

    def test_two_or_three_distinct_saved_packages_are_required(self):
        run_id = self.run_id()
        for package_ids, message in (
            (["package-a", "package-b", "package-c", "package-d"], "up to three"),
            (["package-a"], "at least two"),
            (["package-a", "package-a"], "twice"),
            (["package-a", "package-z"], "not part of this saved package"),
        ):
            with self.subTest(package_ids=package_ids), self.assertRaisesRegex(StudioTestError, message):
                self.store.create(run_id, package_ids)
        self.assertEqual(self.store.overview(run_id)["tests"], [])

    def test_a_short_cannot_be_prepared(self):
        run_id = self.run_id(SHORT_PAYLOAD)
        overview = self.store.overview(run_id)

        self.assertFalse(overview["eligible"])
        self.assertEqual(overview["reason"], SHORTS_NOTE)
        with self.assertRaisesRegex(StudioTestError, "not available for Shorts"):
            self.store.create(run_id, ["package-a", "package-b"])

    def test_a_missing_run_has_no_overview(self):
        self.assertIsNone(self.store.overview(9999))
        self.assertIsNone(self.store.create(9999, ["package-a", "package-b"]))


class RecordTests(StudioTestCase):
    def prepared(self, run_id: int | None = None) -> dict:
        return self.store.create(run_id or self.run_id(), ["package-a", "package-c"])

    def test_linking_uses_the_packages_existing_published_video(self):
        run_id = self.run_id()
        test = self.prepared(run_id)
        with self.assertRaisesRegex(StudioTestError, "Link the published video"):
            self.store.update(test["id"], {"link_video": True})

        link_id = self.link(run_id)
        linked = self.store.update(test["id"], {"link_video": True})

        self.assertEqual(linked["status"], "linked")
        self.assertEqual(linked["linked_video"], {"link_id": link_id, "youtube_video_id": "sleepvideo1"})

    def test_a_published_short_cannot_hold_a_test(self):
        run_id = self.run_id()
        test = self.prepared(run_id)
        self.link(run_id, format_val="youtube_shorts")
        with self.assertRaisesRegex(StudioTestError, "not available for Shorts"):
            self.store.update(test["id"], {"link_video": True})

    def test_the_result_read_in_studio_is_recorded_as_given(self):
        run_id = self.run_id()
        test = self.prepared(run_id)
        with self.assertRaisesRegex(StudioTestError, "Link the published video"):
            self.store.update(test["id"], {"outcome": "winner", "winner_variant": "A"})
        self.link(run_id)
        self.store.update(test["id"], {"link_video": True})

        done = self.store.update(test["id"], {
            "outcome": "winner", "winner_variant": "B", "watch_time_share": {"A": 41.2, "B": 58.8}, "notes": "B won",
        })

        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["winner_variant"], "B")
        self.assertEqual(done["result"]["outcome"], "winner")
        self.assertEqual(done["result"]["watch_time_share"], {"A": 41.2, "B": 58.8})
        self.assertTrue(done["result"]["recorded_at"])
        self.assertEqual(done["notes"], "B won")

        # A correction replaces it, and "no clear winner" has no winner.
        again = self.store.update(test["id"], {"outcome": "no_clear_winner", "watch_time_share": {"A": 50, "B": 50}})
        self.assertIsNone(again["winner_variant"])
        self.assertEqual(again["result"]["outcome"], "no_clear_winner")

    def test_a_result_that_studio_could_not_show_is_refused(self):
        run_id = self.run_id()
        test = self.prepared(run_id)
        self.link(run_id)
        self.store.update(test["id"], {"link_video": True})
        for changes, message in (
            ({"outcome": "winner"}, "Choose the winning variant"),
            ({"outcome": "winner", "winner_variant": "C"}, "not a variant of this test"),
            ({"outcome": "no_clear_winner", "winner_variant": "A"}, "no winner"),
            ({"outcome": "winner", "winner_variant": "A", "watch_time_share": {"C": 20}}, "not a variant of this test"),
            ({"outcome": "winner", "winner_variant": "A", "watch_time_share": {"A": 120}}, "between 0 and 100"),
            ({"outcome": "winner", "winner_variant": "A", "watch_time_share": {"A": 70, "B": 70}}, "add up to 100"),
            ({"outcome": "winner", "winner_variant": "A", "watch_time_share": {"A": 30, "B": 30}}, "add up to 100"),
            ({"winner_variant": "A"}, "Choose the outcome"),
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(StudioTestError, message):
                self.store.update(test["id"], changes)
        self.assertEqual(self.store.test(test["id"])["status"], "linked")

    def test_notes_can_change_at_any_time_and_a_missing_test_is_none(self):
        test = self.prepared()
        self.assertEqual(self.store.update(test["id"], {"notes": "run it next week"})["notes"], "run it next week")
        self.assertIsNone(self.store.update(9999, {"notes": "x"}))

    def test_deleting_the_package_deletes_its_tests(self):
        run_id = self.run_id()
        test = self.prepared(run_id)
        self.assertTrue(self.history.delete_analysis_run(run_id))
        self.assertIsNone(self.store.test(test["id"]))

    def test_a_video_moved_to_another_package_no_longer_counts_as_this_tests(self):
        run_id = self.run_id()
        test = self.prepared(run_id)
        self.link(run_id)
        self.store.update(test["id"], {"link_video": True})
        # The same video linked to another package moves there.
        self.link(self.run_id(), video_id="sleepvideo1")
        self.assertIsNone(self.store.test(test["id"])["linked_video"])

    def test_a_recorded_result_stays_with_the_video_it_was_read_for(self):
        run_id = self.run_id()
        test = self.prepared(run_id)
        self.link(run_id)
        self.store.update(test["id"], {"link_video": True})
        self.store.update(test["id"], {"outcome": "winner", "winner_variant": "B", "watch_time_share": {"A": 40, "B": 60}})

        # Replacing the video asks first: the result would lose its video.
        with self.assertRaises(RelinkWouldDeleteEvidence) as refused:
            self.history.check_relink(run_id, "sleepvideo2")
        self.assertEqual(refused.exception.evidence["studio test results"], 1)

        self.history.link_published_video(run_id, "sleepvideo2", "2026-09-02T00:00:00+00:00", format_val="tutorial",
                                          replace_existing_evidence=True)
        with self.assertRaisesRegex(StudioTestError, "recorded for a video"):
            self.store.update(test["id"], {"link_video": True})
        kept = self.store.test(test["id"])
        self.assertIsNone(kept["linked_video"])
        self.assertEqual((kept["status"], kept["winner_variant"]), ("completed", "B"))


class RouteTests(StudioTestCase):
    def call(self, function, *args):
        with patch.object(routes, "get_settings", return_value=self.settings):
            return function(*args)

    def test_routes_list_create_and_update(self):
        run_id = self.run_id()
        created = self.call(routes.create_studio_test, run_id, CreateStudioTestRequest(package_ids=["package-a", "package-d"]))
        self.assertEqual(created["status"], "prepared")

        listed = self.call(routes.get_studio_tests, run_id)
        self.assertEqual([item["id"] for item in listed["tests"]], [created["id"]])

        self.link(run_id)
        updated = self.call(routes.update_studio_test, created["id"], UpdateStudioTestRequest(link_video=True))
        self.assertEqual(updated["status"], "linked")

    def test_route_errors_are_clear(self):
        run_id = self.run_id()
        for function, args, status in (
            (routes.get_studio_tests, (9999,), 404),
            (routes.create_studio_test, (9999, CreateStudioTestRequest(package_ids=["package-a", "package-b"])), 404),
            (routes.create_studio_test, (run_id, CreateStudioTestRequest(package_ids=["package-a", "package-b", "package-c", "package-d"])), 422),
            (routes.create_studio_test, (self.run_id(SHORT_PAYLOAD), CreateStudioTestRequest(package_ids=["package-a", "package-b"])), 422),
            (routes.update_studio_test, (9999, UpdateStudioTestRequest(notes="x")), 404),
        ):
            with self.subTest(function=function.__name__, status=status), self.assertRaises(HTTPException) as caught:
                self.call(function, *args)
            self.assertEqual(caught.exception.status_code, status)

    def test_requests_reject_unknown_fields_and_outcomes(self):
        with self.assertRaises(ValidationError):
            CreateStudioTestRequest(package_ids=["package-a", "package-b"], titles=["injected"])
        with self.assertRaises(ValidationError):
            UpdateStudioTestRequest(outcome="preferred")


if __name__ == "__main__":
    unittest.main()
