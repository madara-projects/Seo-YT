"""Route contracts: relink consent, honest status, safe resets and strict video IDs."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from win_engine.api import routes
from win_engine.api.app import create_app
from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "routes.db")
        self.settings = Settings(database_path=self.path, allowed_hosts="testserver", app_environment="development")
        self.patches = [
            patch.object(routes, "get_settings", return_value=self.settings),
            patch("win_engine.core.config.get_settings", return_value=self.settings),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(create_app(), raise_server_exceptions=False)
        self.store = HistoryStore(self.path)

    def tearDown(self) -> None:
        for item in self.patches:
            item.stop()
        self.dir.cleanup()

    def run_id(self) -> int:
        with self.store._connect() as connection:
            return int(connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES ('q', ?, 't')",
                (datetime.now(timezone.utc).isoformat(),),
            ).lastrowid)

    def test_relinking_away_from_evidence_needs_confirmation(self):
        run = self.run_id()
        self.store.link_published_video(run, "firstvideo1", "2026-08-01T00:00:00+00:00")
        self.store.record_performance_snapshot("firstvideo1", 24, views=10, snapshot_window="24h")
        public = {"video_id": "secondvide2", "published_at": "2026-08-02T00:00:00Z", "ownership_verified": False}

        with patch.object(routes.YouTubeChannelService, "verify_public_video", return_value=public):
            refused = self.client.post(f"/api/history/runs/{run}/link-video", json={"youtube_video_id": "secondvide2"})
            self.assertEqual(refused.status_code, 409)
            error = refused.json()["error"]
            self.assertEqual(error["code"], "relink_would_delete_evidence")
            self.assertEqual(error["details"]["evidence"]["snapshots"], 1)

            confirmed = self.client.post(
                f"/api/history/runs/{run}/link-video",
                json={"youtube_video_id": "secondvide2", "replace_existing_evidence": True},
            )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["youtube_video_id"], "secondvide2")

    def test_the_relink_question_comes_before_any_youtube_lookup(self):
        run = self.run_id()
        self.store.link_published_video(run, "firstvideo1", "2026-08-01T00:00:00+00:00")
        self.store.record_performance_snapshot("firstvideo1", 24, views=10, snapshot_window="24h")

        with patch.object(routes.YouTubeChannelService, "verify_public_video") as public, \
                patch.object(routes.YouTubeChannelService, "verify_owned_video") as owned:
            refused = self.client.post(f"/api/history/runs/{run}/link-video", json={"youtube_video_id": "secondvide2"})

        self.assertEqual(refused.status_code, 409)
        public.assert_not_called()
        owned.assert_not_called()

    def test_a_published_time_without_a_zone_is_refused(self):
        run = self.run_id()
        response = self.client.post(
            f"/api/history/runs/{run}/link-video",
            json={"youtube_video_id": "abcdefghijk", "published_at": "2026-08-01 10:00"},
        )
        self.assertEqual(response.status_code, 422)

    def test_health_reports_a_broken_database_as_degraded(self):
        with patch.object(routes.HistoryStore, "system_status", side_effect=RuntimeError("cannot open")):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "degraded")
        self.assertFalse(response.json()["database_ok"])

    def test_settings_status_reports_real_database_health(self):
        healthy = self.client.get("/api/settings/status").json()["database"]
        self.assertTrue(healthy["healthy"])
        self.assertEqual(healthy["counts"]["packages"], 0)
        with patch.object(routes.HistoryStore, "system_status", return_value={"database_ok": False, "error": "OperationalError"}):
            broken = self.client.get("/api/settings/status").json()["database"]
        self.assertFalse(broken["healthy"])
        self.assertIsNone(broken["counts"])

    def test_settings_status_reports_a_database_that_cannot_open(self):
        # A file where the data folder should be: preparing the database fails.
        blocker = Path(self.dir.name) / "not-a-folder"
        blocker.write_text("")
        self.settings.database_path = str(blocker / "win_engine.db")

        response = self.client.get("/api/settings/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["database"]["healthy"])
        self.assertTrue(body["database"]["error"])
        self.assertIsNone(body["database"]["counts"])
        # The channel connection is stored in the database, so its state is unknown, not "disconnected".
        self.assertEqual(
            body["youtube_oauth"],
            {"configured": None, "connected": None, "channel_title": None, "last_synced_at": None},
        )

    def test_a_blank_experiment_date_clears_it(self):
        created = self.client.post("/api/experiment-center/experiments", json={
            "name": "Title length", "hypothesis": "Shorter titles win", "variable": "title_length",
            "control_definition": "Long title", "variant_definition": "Short title",
            "start_date": "2026-09-01", "end_date": "2026-09-30",
        })
        self.assertEqual(created.status_code, 201, created.text)
        url = f"/api/experiment-center/experiments/{created.json()['experiment']['id']}"

        for change in ({"start_date": ""}, {"end_date": None}):
            with self.subTest(change=change):
                response = self.client.patch(url, json=change)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIsNone(response.json()["experiment"][next(iter(change))])
        self.assertEqual(
            self.client.patch(url, json={"start_date": "next Monday"}).json()["error"]["message"],
            "start_date: Use an ISO date, for example 2026-09-01.",
        )
        self.assertEqual(
            self.client.patch(url, json={"notes": None}).json()["error"]["message"],
            "Experiment fields cannot be set to null.",
        )

    def test_a_stray_bracket_in_a_video_id_is_refused_not_a_server_error(self):
        run = self.run_id()
        for value in ("[aaaaaaaaaaa", "https://[aaaaaaaaaaaa"):
            with self.subTest(value=value):
                self.assertEqual(self.client.post("/api/watchlist/videos", json={"video_id": value}).status_code, 422)
                linked = self.client.post(f"/api/history/runs/{run}/link-video", json={"youtube_video_id": value})
                self.assertEqual(linked.status_code, 422)

    def test_history_runs_report_the_total(self):
        for _ in range(3):
            self.run_id()
        body = self.client.get("/api/history/runs?limit=2").json()
        self.assertEqual((len(body["runs"]), body["total"]), (2, 3))

    def test_reset_is_refused_while_cloud_sync_would_restore_packages(self):
        self.run_id()
        self.client.app.state.cloud_sync = SimpleNamespace(status=lambda: {"enabled": True})
        response = self.client.post("/api/reset-database")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.store.history_run_count(), 1)

        self.client.app.state.cloud_sync = SimpleNamespace(status=lambda: {"enabled": False})
        self.assertEqual(self.client.post("/api/reset-database").status_code, 200)
        self.assertEqual(self.store.history_run_count(), 0)

    def test_diagnostics_spend_quota_only_on_a_post(self):
        self.assertEqual(self.client.get("/diagnostics").status_code, 405)


class VideoIdTests(unittest.TestCase):
    def test_ids_come_only_from_youtube_urls_and_are_never_truncated(self):
        extract = routes._extract_youtube_video_id
        self.assertEqual(extract("abcdefghijk"), "abcdefghijk")
        self.assertEqual(extract("https://www.youtube.com/watch?v=abcdefghijk&t=10"), "abcdefghijk")
        self.assertEqual(extract("youtu.be/abcdefghijk"), "abcdefghijk")
        self.assertEqual(extract("https://youtube.com/shorts/abcdefghijk?feature=share"), "abcdefghijk")
        self.assertEqual(extract("https://m.youtube.com/embed/abcdefghijk"), "abcdefghijk")
        self.assertIsNone(extract("https://evil.example/watch?v=abcdefghijk"))
        self.assertIsNone(extract("https://www.youtube.com/watch?v=abcdefghijkXYZ"))
        self.assertIsNone(extract("abcdefghijkl"))
        # urlsplit raises on an unbalanced or invalid bracketed host.
        for value in ("[aaaaaaaaaaa", "https://[aaaaaaaaaaaa", "youtube.com]/watch?v=abcdefghijk",
                      "https://[aaaaaaaaaaa]/watch?v=abcdefghijk"):
            self.assertIsNone(extract(value), value)


class AutoLanguageTests(unittest.TestCase):
    def test_auto_gives_research_and_the_brief_the_video_language(self):
        from win_engine.core.schemas import AnalyzeRequest

        payload = AnalyzeRequest(script="Chettinad chicken biryani at home", language="auto", video_language="tamil")
        with patch.object(routes, "ResearchService") as research, \
                patch.object(routes, "generate_seo_suggestions", return_value="package") as generate:
            self.assertEqual(routes.analyze_script(payload), "package")

        gather = research.return_value.gather.call_args.kwargs
        self.assertEqual(gather["primary_language"], "tamil")
        self.assertEqual(gather["creator_brief"]["language"], "tamil")
        # Generation resolves "auto" itself, from both values.
        self.assertEqual(generate.call_args.kwargs["context"]["language"], "auto")
        self.assertEqual(generate.call_args.kwargs["context"]["video_language"], "tamil")


if __name__ == "__main__":
    unittest.main()
