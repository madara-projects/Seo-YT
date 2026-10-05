"""One YouTube Analytics request asks for a video's retention curve and says plainly why it is missing."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httplib2
from cryptography.fernet import Fernet
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.retention_probe import HOOK_RATIO, curve_observations
from win_engine.integrations import youtube_channel
from win_engine.integrations.youtube_channel import YouTubeChannelService

BUILD = "win_engine.integrations.youtube_channel.build"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
DATA_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
CHAPTERS = [
    {"timestamp": "0:00", "title": "Intro"},
    {"timestamp": "2:00", "title": "Setup"},
    {"timestamp": "6:00", "title": "Results"},
]


def _http_error(status: int, reason: str) -> HttpError:
    body = json.dumps({"error": {"code": status, "message": reason, "errors": [{"reason": reason}]}}).encode()
    return HttpError(httplib2.Response({"status": status}), body, uri="https://youtubeanalytics.googleapis.com/v2/reports")


def curve(drop_at: float, drop: float = 0.2) -> list[dict]:
    """A slow decline with one sharp drop landing at `drop_at` of the video."""
    rows, watch = [], 1.0
    for step in range(1, 101):
        ratio = step / 100
        if abs(ratio - drop_at) < 1e-9:
            watch -= drop
        rows.append({
            "elapsedVideoTimeRatio": ratio,
            "audienceWatchRatio": round(watch, 4),
            "relativeRetentionPerformance": 0.62 if ratio <= HOOK_RATIO else 0.45,
        })
        watch -= 0.004
    return rows


def points(rows: list[dict]) -> list[dict]:
    return [
        {"elapsed_ratio": row["elapsedVideoTimeRatio"], "audience_watch_ratio": row["audienceWatchRatio"],
         "relative_retention_performance": row["relativeRetentionPerformance"]}
        for row in rows
    ]


class ProbeBase(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.settings = Settings(
            database_path=str(Path(self.dir.name) / "probe.db"), youtube_api_key="", youtube_api_keys="",
            youtube_oauth_client_id="client-id", youtube_oauth_client_secret="client-secret",
            oauth_token_encryption_key=Fernet.generate_key().decode(),
        )
        self.store = HistoryStore(self.settings.database_path)
        self.service = YouTubeChannelService(self.settings)
        self.service._save_connection("refresh", "UC-owner", "Owner")

    def link(self, video_id: str, *, verified: bool = True, channel: str = "UC-owner",
             published_at: str = "2026-08-01T00:00:00+00:00") -> dict:
        run_id = self.store.record_analysis_run(video_id, "search", "tutorial", video_id, 7.0, "LOW", "WORKABLE", 50, {})
        link_id = self.store.link_published_video(
            run_id, video_id, published_at, ownership_state="verified" if verified else "unverified",
            ownership_verified=verified, verified_channel_id=channel if verified else None,
            ownership_verified_at=published_at if verified else None,
        )
        return self.store.published_video_link(link_id) or {}

    def probe(self, link: dict, *, rows=None, error: Exception | None = None, scopes=None):
        credentials = MagicMock()
        credentials.granted_scopes = scopes if scopes is not None else [ANALYTICS_SCOPE, DATA_SCOPE]
        with (
            patch.object(self.service, "_fresh_credentials", return_value=credentials),
            patch(BUILD, return_value=MagicMock()) as build_client,
            patch.object(self.service, "_query_rows", return_value=rows or [], side_effect=error) as query_rows,
        ):
            result = self.service.probe_retention_curve(link)
        return result, build_client, query_rows


class ProbeTests(ProbeBase):
    def test_an_available_curve_costs_one_analytics_request(self):
        result, build_client, query_rows = self.probe(self.link("curvevideo1"), rows=list(reversed(curve(0.05))))

        self.assertEqual((result["status"], result["reason"], result["requests"]), ("available", None, 1))
        self.assertEqual(len(result["points"]), 100)
        self.assertEqual(result["points"][0]["elapsed_ratio"], 0.01)  # sorted from the start
        self.assertEqual(result["points"][0]["relative_retention_performance"], 0.62)
        # Only the Analytics API: no Data API lookup, so no Data API quota.
        self.assertEqual([call.args[0] for call in build_client.call_args_list], ["youtubeAnalytics"])
        self.assertEqual(query_rows.call_count, 1)
        kwargs = query_rows.call_args.kwargs
        self.assertEqual(query_rows.call_args.args[3], "audienceWatchRatio,relativeRetentionPerformance")
        self.assertEqual(
            (kwargs["dimensions"], kwargs["filters"], kwargs["sort"]),
            ("elapsedVideoTimeRatio", "video==curvevideo1", "elapsedVideoTimeRatio"),
        )

    def test_each_reason_is_named(self):
        cases = (
            ("missing_scope", {"error": _http_error(403, "insufficientPermissions")}, 1),
            ("not_channel_video", {"error": _http_error(403, "forbidden")}, 1),
            ("no_data_yet", {"rows": []}, 1),
            ("api_error", {"error": _http_error(500, "backendError")}, 1),
            ("api_error", {"error": _http_error(403, "quotaExceeded")}, 1),
            ("api_error", {"error": TimeoutError("read")}, 1),
            ("missing_scope", {"scopes": [DATA_SCOPE]}, 0),
        )
        for index, (reason, kwargs, requests) in enumerate(cases):
            with self.subTest(reason=reason, case=index):
                result, _, query_rows = self.probe(self.link(f"reasonvid{index:02d}"), **kwargs)
                self.assertEqual((result["status"], result["reason"], result["requests"]), ("unavailable", reason, requests))
                self.assertTrue(result["message"])
                self.assertEqual(query_rows.call_count, requests)

    def test_videos_that_cannot_be_asked_about_make_no_request(self):
        today = datetime.now(timezone.utc).isoformat()
        for reason, link in (
            ("not_channel_video", self.link("unverified1", verified=False)),
            ("not_channel_video", self.link("otherchann1", channel="UC-other")),
            ("no_data_yet", self.link("brandnewvid", published_at=today)),
        ):
            with self.subTest(video=link["youtube_video_id"]):
                result, build_client, query_rows = self.probe(link)
                self.assertEqual((result["reason"], result["requests"]), (reason, 0))
                build_client.assert_not_called()
                query_rows.assert_not_called()

        self.service.disconnect()
        result, build_client, _ = self.probe(self.link("noconnect01"))
        self.assertEqual((result["reason"], result["requests"]), ("not_connected", 0))
        build_client.assert_not_called()

    def test_a_grant_without_the_analytics_scope_is_missing_scope_and_a_revoked_one_asks_to_reconnect(self):
        link = self.link("grantvideo1")
        with patch.object(self.service, "_fresh_credentials", side_effect=RefreshError("invalid_scope: Bad Request")):
            result = self.service.probe_retention_curve(link)
        self.assertEqual((result["reason"], result["requests"]), ("missing_scope", 0))
        with patch.object(self.service, "_fresh_credentials", side_effect=RefreshError("invalid_grant")):
            with self.assertRaises(RefreshError):
                self.service.probe_retention_curve(link)

    def test_an_unreadable_saved_token_is_reported_not_raised(self):
        # The encryption key changed since the channel was connected: every
        # other route says so with a 400; the probe used to raise it as a 500.
        link = self.link("tokenvideo1")
        with (
            patch.object(youtube_channel.Fernet, "decrypt", side_effect=youtube_channel.InvalidToken()),
            patch(BUILD) as build_client,
        ):
            result = self.service.probe_retention_curve(link)
        self.assertEqual((result["status"], result["reason"], result["requests"]), ("unavailable", "api_error", 0))
        self.assertIn("Disconnect and connect again", result["message"])
        build_client.assert_not_called()


class ObservationTests(unittest.TestCase):
    def test_a_drop_inside_the_hook_is_placed_there(self):
        result = curve_observations(points(curve(0.05)), duration_seconds=600, chapters=[], short=False)

        drop = result["biggest_drop"]
        self.assertEqual((drop["from_ratio"], drop["at_ratio"]), (0.04, 0.05))
        self.assertTrue(drop["in_hook"])
        self.assertEqual(drop["at_seconds"], 30)
        self.assertAlmostEqual(drop["drop_points"], 20.4, places=1)
        self.assertIn("within the hook", result["observations"][0])
        self.assertIn("0:30", result["observations"][0])
        self.assertEqual(result["hook"]["relative_retention_performance"], 0.62)
        self.assertTrue(any("above" in item and "similar length" in item for item in result["observations"]))
        self.assertIn("not", result["note"])  # observations, not causes

    def test_a_later_drop_is_related_to_the_chapter_it_falls_in(self):
        result = curve_observations(points(curve(0.5)), duration_seconds=600, chapters=CHAPTERS, short=False)

        self.assertFalse(result["biggest_drop"]["in_hook"])
        self.assertIn("after the hook", result["observations"][0])
        self.assertEqual(result["biggest_drop"]["chapter"], "Setup")
        self.assertEqual([item["title"] for item in result["chapters"]], ["Intro", "Setup", "Results"])
        self.assertEqual(result["chapters"][1]["start_seconds"], 120)
        self.assertEqual(max(result["chapters"], key=lambda item: item["viewers_lost_points"])["title"], "Setup")
        self.assertTrue(any('"Setup" (2:00' in item for item in result["observations"]))

    def test_without_a_length_or_for_a_short_no_chapter_is_named(self):
        without_length = curve_observations(points(curve(0.5)), duration_seconds=None, chapters=CHAPTERS, short=False)
        self.assertEqual(without_length["chapters"], [])
        self.assertIsNone(without_length["biggest_drop"]["at_seconds"])
        short = curve_observations(points(curve(0.5)), duration_seconds=40, chapters=CHAPTERS, short=True)
        self.assertEqual(short["chapters"], [])
        self.assertIsNone(short["biggest_drop"]["chapter"])

    def test_too_few_points_make_no_observation(self):
        result = curve_observations(points(curve(0.5))[:1], duration_seconds=600, chapters=[], short=False)
        self.assertIsNone(result["biggest_drop"])
        self.assertEqual(result["observations"], [])


class RouteTests(ProbeBase):
    def test_the_route_adds_observations_from_the_package_and_video(self):
        run_id = self.store.record_analysis_run(
            "q", "search", "tutorial", "t", 7.0, "LOW", "WORKABLE", 50,
            {"chapters": CHAPTERS, "creator_brief": {"video_format": "tutorial"}},
        )
        link_id = self.store.link_published_video(
            run_id, "routecurve1", "2026-08-01T00:00:00+00:00", ownership_state="verified", ownership_verified=True,
            verified_channel_id="UC-owner", ownership_verified_at="2026-08-01T00:00:00+00:00",
        )
        self.store.update_linked_video_metadata(link_id, {"duration": "PT10M"})
        available = {"status": "available", "reason": None, "requests": 1, "points": points(curve(0.5)), "message": "ok"}
        with (
            patch.object(routes, "get_settings", return_value=self.settings),
            patch.object(routes.YouTubeChannelService, "probe_retention_curve", return_value=available),
        ):
            result = routes.probe_published_video_retention(link_id)
            with self.assertRaises(HTTPException) as caught:
                routes.probe_published_video_retention(9999)

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(result["duration_seconds"], 600)
        self.assertEqual(result["observations"]["biggest_drop"]["chapter"], "Setup")

    def test_an_unavailable_probe_has_no_observations(self):
        link = self.link("routecurve2")
        unavailable = {"status": "unavailable", "reason": "no_data_yet", "requests": 1, "points": [], "message": "none"}
        with (
            patch.object(routes, "get_settings", return_value=self.settings),
            patch.object(routes.YouTubeChannelService, "probe_retention_curve", return_value=unavailable),
        ):
            result = routes.probe_published_video_retention(link["id"])
        self.assertEqual(result["reason"], "no_data_yet")
        self.assertIsNone(result["observations"])


if __name__ == "__main__":
    unittest.main()
