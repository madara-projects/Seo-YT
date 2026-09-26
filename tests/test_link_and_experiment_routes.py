"""Linking says where a video moved from, and an experiment keeps the count it replaced."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.core.schemas import LinkVideoRequest, RecordExperimentRequest
from win_engine.feedback.audit_experiment_store import AuditExperimentStore
from win_engine.feedback.history_store import HistoryStore

PUBLIC_METADATA = {
    "title": "Public video", "description": "", "tags": [], "published_at": "2026-08-01T00:00:00Z",
    "channel_id": "public-channel", "ownership_verified": False, "metadata_source": "youtube_data_api",
}


class LinkAndExperimentRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.settings = Settings(database_path=str(Path(self.dir.name) / "routes.db"))
        self.store = HistoryStore(self.settings.database_path)

    def run_id(self, query: str) -> int:
        return self.store.record_analysis_run(query, "browse", "emotion", query.title(), 7.0, "LOW", "WORKABLE", 50, {})

    def link_through_the_route(self, run_id: int, video_id: str) -> dict:
        with (
            patch.object(routes, "get_settings", return_value=self.settings),
            patch.object(routes.YouTubeChannelService, "status", return_value={"connected": False}),
            patch.object(routes.YouTubeChannelService, "verify_public_video", return_value={**PUBLIC_METADATA, "video_id": video_id}),
        ):
            return routes.link_published_video(run_id, LinkVideoRequest(youtube_video_id=video_id))

    def test_linking_a_video_of_another_package_says_where_it_moved_from(self):
        first, second = self.run_id("first package"), self.run_id("second package")
        self.assertIsNone(self.link_through_the_route(first, "movedvideo1")["moved_from_run_id"])
        link_id = self.store.published_video_link_by_run(first)["id"]
        self.store.record_performance_snapshot("movedvideo1", 24, views=40, snapshot_window="24h")

        result = self.link_through_the_route(second, "movedvideo1")

        self.assertEqual(result["moved_from_run_id"], first)
        self.assertTrue(result["ownership_message"].startswith(f"This video was linked to saved package #{first}"))
        # The link itself moved, with the evidence collected for it.
        self.assertEqual(result["link_id"], link_id)
        self.assertIsNone(self.store.published_video_link_by_run(first))
        self.assertEqual(len(self.store.performance_snapshots("movedvideo1")), 1)
        # Linking the same package again is not a move.
        self.assertIsNone(self.link_through_the_route(second, "movedvideo1")["moved_from_run_id"])

    def test_an_experiment_keeps_the_current_count_as_its_baseline(self):
        self.store.link_published_video(self.run_id("package"), "baselinevid", "2026-08-01T00:00:00Z")
        self.store.record_performance_snapshot("baselinevid", 900, views=900, snapshot_window="current")
        self.store.record_performance_snapshot("baselinevid", 24, views=100, snapshot_window="24h")

        with patch.object(routes, "get_settings", return_value=self.settings):
            routes.record_experiment(RecordExperimentRequest(youtube_video_id="baselinevid", old_title="Old", new_title="New"))

        before = self.store.get_package_experiments("baselinevid")[0]["performance_before"]
        self.assertEqual((before["snapshot_window"], before["views"]), ("current", 900))

    def test_removing_a_video_from_a_closed_experiment_is_refused_not_an_error(self):
        experiments = AuditExperimentStore(self.store)
        link_id = self.store.link_published_video(
            self.run_id("package"), "closedexp01", "2026-08-01T00:00:00Z", ownership_state="verified",
            ownership_verified=True, verified_channel_id="UC-owner", ownership_verified_at="2026-08-01T00:00:00Z",
        )
        experiment = experiments.create_experiment({"name": "n", "hypothesis": "h", "variable": "title",
                                                    "control_definition": "c", "variant_definition": "v"})
        assignment_id = experiments.assign_video(experiment["id"], link_id, "control")["assignments"][0]["id"]
        for status in ("planned", "active", "completed"):
            experiments.update_experiment(experiment["id"], {"status": status})

        with patch.object(routes, "get_settings", return_value=self.settings):
            with self.assertRaises(HTTPException) as raised:
                routes.remove_structured_experiment_assignment(experiment["id"], assignment_id)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(experiments.experiment(experiment["id"])["assignment_counts"]["control"], 1)


if __name__ == "__main__":
    unittest.main()
