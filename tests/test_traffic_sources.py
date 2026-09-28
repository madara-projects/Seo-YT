"""Traffic sources are kept with each completed window and compared only with enough evidence."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httplib2
from cryptography.fernet import Fernet
from googleapiclient.errors import HttpError

from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.feedback.evidence_policy import EARLY_SIGNAL_MIN_SAMPLES
from win_engine.feedback.history_store import HistoryStore, traffic_source_summary
from win_engine.feedback.snapshot_collector import SnapshotCollector
from win_engine.integrations import youtube_channel
from win_engine.integrations.youtube_channel import YouTubeChannelService

BUILD = "win_engine.integrations.youtube_channel.build"
CONNECTED = {"configured": True, "connected": True, "channel": {"id": "UC-owner", "title": "Owner"}}
TRAFFIC_ROWS = [
    {"insightTrafficSourceType": "RELATED_VIDEO", "views": 30, "estimatedMinutesWatched": 90.5},
    {"insightTrafficSourceType": "YT_SEARCH", "views": 70, "estimatedMinutesWatched": 210.0},
    {"insightTrafficSourceType": "", "views": 5, "estimatedMinutesWatched": 1.0},
]


def _http_error(status: int, reason: str) -> HttpError:
    body = json.dumps({"error": {"code": status, "message": reason, "errors": [{"reason": reason}]}}).encode()
    return HttpError(httplib2.Response({"status": status}), body, uri="https://youtubeanalytics.googleapis.com/v2/reports")


def _sources(dominant: str, views: int = 100) -> list[dict]:
    other = "BROWSE_OTHER" if dominant != "BROWSE_OTHER" else "EXT_URL"
    return [{"source": dominant, "views": int(views * 0.8), "watch_time_minutes": 50.0},
            {"source": other, "views": int(views * 0.2), "watch_time_minutes": 5.0}]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = str(Path(self.dir.name) / "traffic.db")
        self.settings = Settings(
            database_path=self.path, youtube_api_key="", youtube_api_keys="",
            youtube_oauth_client_id="client-id", youtube_oauth_client_secret="client-secret",
            oauth_token_encryption_key=Fernet.generate_key().decode(),
            snapshot_collector_enabled=True, snapshot_collector_dry_run=False,
        )
        self.store = HistoryStore(self.path)

    def link(self, video_id: str, published_at: str = "2026-08-01T00:00:00+00:00", **values) -> dict:
        run_id = self.store.record_analysis_run(video_id, "search", "tutorial", video_id, 7.0, "LOW", "WORKABLE", 50, {})
        link_id = self.store.link_published_video(
            run_id, video_id, published_at, format_val=values.get("format_val", "tutorial"),
            language=values.get("language", "english"), ownership_state="verified", ownership_verified=True,
            verified_channel_id="UC-owner", ownership_verified_at=published_at,
        )
        return self.store.published_video_link(link_id) or {}


class SummaryTests(unittest.TestCase):
    def test_the_breakdown_is_sorted_with_shares_and_a_dominant_source(self):
        summary = traffic_source_summary([
            {"source": "RELATED_VIDEO", "views": 30, "watch_time_minutes": 90.5},
            {"source": "YT_SEARCH", "views": 70, "watch_time_minutes": 210.0},
        ])
        self.assertEqual(summary["dominant_source"], "YT_SEARCH")
        self.assertEqual(summary["dominant_share_percent"], 70.0)
        self.assertEqual(summary["total_views"], 100)
        self.assertEqual([item["source"] for item in summary["sources"]], ["YT_SEARCH", "RELATED_VIDEO"])
        self.assertEqual(summary["sources"][1]["share_percent"], 30.0)

    def test_nothing_usable_is_no_breakdown(self):
        self.assertIsNone(traffic_source_summary(None))
        self.assertIsNone(traffic_source_summary([]))
        self.assertIsNone(traffic_source_summary([{"source": "", "views": 3}, {"source": "YT_SEARCH", "views": None}]))
        # Malformed rows from a synced package are skipped, never an error.
        self.assertIsNone(traffic_source_summary([None, "YT_SEARCH", 3]))
        self.assertIsNone(traffic_source_summary({"source": "YT_SEARCH", "views": 3}))
        self.assertEqual(traffic_source_summary([None, {"source": "YT_SEARCH", "views": 3}])["dominant_source"], "YT_SEARCH")
        # Rows without a single view have no dominant source.
        self.assertIsNone(traffic_source_summary([{"source": "YT_SEARCH", "views": 0}])["dominant_source"])


class RefreshTests(Base):
    def setUp(self) -> None:
        super().setUp()
        self.service = YouTubeChannelService(self.settings)
        self.service._save_connection("refresh", "UC-owner", "Owner")

    def youtube(self) -> MagicMock:
        youtube = MagicMock()
        youtube.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"snippet": {"channelId": "UC-owner", "publishedAt": "2026-08-01T00:00:00Z"}, "statistics": {}}]
        }
        return youtube

    def refresh(self, link: dict, *, rows=None, error: Exception | None = None, views: int | None = 100):
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[self.youtube(), MagicMock()]),
            patch.object(self.service, "_query", return_value={"views": views} if views is not None else {}),
            patch.object(self.service, "_query_rows", return_value=rows or [], side_effect=error) as query_rows,
        ):
            result = self.service.refresh_linked_video_performance(link, collect_current=False, windows=["24h"])
        return result, query_rows

    def test_a_completed_window_keeps_its_traffic_sources(self):
        link = self.link("trafficvid1")
        result, query_rows = self.refresh(link, rows=TRAFFIC_ROWS)

        kwargs = query_rows.call_args.kwargs
        self.assertEqual(query_rows.call_args.args[3], "views,estimatedMinutesWatched")
        self.assertEqual((kwargs["dimensions"], kwargs["filters"]), ("insightTrafficSourceType", "video==trafficvid1"))
        # The same Pacific days as the window's own metrics (published 17:00 on 31 July, Pacific).
        start, end = query_rows.call_args.args[1:3]
        self.assertEqual((start.isoformat(), end.isoformat()), ("2026-07-31", "2026-08-01"))

        traffic = result["captured"][0]["traffic_sources"]
        self.assertEqual(traffic["dominant_source"], "YT_SEARCH")
        self.assertEqual([item["source"] for item in traffic["sources"]], ["YT_SEARCH", "RELATED_VIDEO"])
        stored = self.store.completed_evidence_snapshot("trafficvid1", "24h")
        self.assertEqual(stored["traffic_sources"], traffic)

    def test_a_refused_or_failed_breakdown_is_null_and_the_snapshot_is_kept(self):
        for video_id, error in (
            ("trafficvid2", _http_error(403, "insufficientPermissions")),
            ("trafficvid3", _http_error(400, "badRequest")),
            ("trafficvid4", TimeoutError("read")),
        ):
            with self.subTest(error=type(error).__name__):
                result, _ = self.refresh(self.link(video_id), error=error)
                snapshot = self.store.completed_evidence_snapshot(video_id, "24h")
                self.assertEqual((snapshot["snapshot_status"], snapshot["views"]), ("complete", 100))
                self.assertIsNone(snapshot["traffic_sources"])
                self.assertIsNone(result["captured"][0]["traffic_sources"])

    def test_no_rows_is_null_and_an_empty_window_asks_for_no_breakdown(self):
        self.refresh(self.link("trafficvid5"), rows=[])
        self.assertIsNone(self.store.completed_evidence_snapshot("trafficvid5", "24h")["traffic_sources"])

        _, query_rows = self.refresh(self.link("trafficvid6"), views=None)
        query_rows.assert_not_called()
        self.assertEqual(self.store.snapshot_window_state("trafficvid6", "24h")["status"], "empty_retryable")

    def test_the_collector_counts_the_windows_with_traffic_sources(self):
        published = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        self.link("collecttraf", published_at=published)
        youtube = self.youtube()
        with (
            patch.object(YouTubeChannelService, "status", return_value=CONNECTED),
            patch.object(YouTubeChannelService, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=lambda name, *_args, **_kwargs: youtube if name == "youtube" else MagicMock()),
            patch.object(YouTubeChannelService, "_query", return_value={"views": 12}),
            patch.object(YouTubeChannelService, "_query_rows", return_value=TRAFFIC_ROWS),
        ):
            result = SnapshotCollector(self.settings).run_once()

        self.assertEqual(result["counts"]["captured"], 1)
        self.assertEqual(result["counts"]["traffic_sources"], 1)
        self.assertEqual(self.store.completed_evidence_snapshot("collecttraf", "24h")["traffic_sources"]["dominant_source"], "YT_SEARCH")


class CohortTests(Base):
    def add(self, video_id: str, dominant: str | None, *, views: int = 100, retention: float = 40.0, window: str = "7d",
            **link_values) -> None:
        self.link(video_id, **link_values)
        self.store.record_performance_snapshot(
            video_id, 168, views=views, avg_view_percentage=retention, snapshot_window=window,
            traffic_sources=_sources(dominant, views) if dominant else None,
        )

    def test_a_traffic_source_cohort_waits_for_the_evidence_minimum(self):
        for index in range(EARLY_SIGNAL_MIN_SAMPLES - 1):
            self.add(f"searchvid{index:02d}", "YT_SEARCH")
        self.add("suggestvid0", "RELATED_VIDEO")

        cohort = self.store.cohort_analytics(snapshot_window="7d", traffic_source_filter="YT_SEARCH")

        self.assertEqual(cohort["traffic_source"], "YT_SEARCH")
        self.assertEqual(cohort["sample_size"], EARLY_SIGNAL_MIN_SAMPLES - 1)
        self.assertFalse(cohort["learning_allowed"])
        self.assertEqual(cohort["more_needed"], 1)
        self.assertIn("1 more", cohort["recommendation"])
        # Counted from links with the same dominant source, not every link.
        self.assertEqual(cohort["total_links_considered"], EARLY_SIGNAL_MIN_SAMPLES - 1)

        self.add("searchvid99", "YT_SEARCH")
        cohort = self.store.cohort_analytics(snapshot_window="7d", traffic_source_filter="YT_SEARCH")
        self.assertTrue(cohort["learning_allowed"])
        self.assertEqual(cohort["more_needed"], 0)

    def test_groups_compare_dominant_sources_only_past_the_minimum(self):
        for index in range(EARLY_SIGNAL_MIN_SAMPLES):
            self.add(f"suggest{index:04d}", "RELATED_VIDEO", views=200 + index)
        for index in range(2):
            self.add(f"search{index:05d}", "YT_SEARCH")
        self.add("notraffic01", None)

        groups = {item["traffic_source"]: item for item in self.store.cohort_analytics(snapshot_window="7d")["traffic_source_groups"]}

        self.assertEqual(set(groups), {"RELATED_VIDEO", "YT_SEARCH"})
        suggested, search = groups["RELATED_VIDEO"], groups["YT_SEARCH"]
        self.assertTrue(suggested["learning_allowed"])
        self.assertEqual(suggested["median_views"], 202)
        self.assertEqual(suggested["median_retention_percentage"], 40.0)
        self.assertFalse(search["learning_allowed"])
        self.assertEqual(search["more_needed"], EARLY_SIGNAL_MIN_SAMPLES - 2)
        self.assertIsNone(search["median_views"])
        self.assertIsNone(search["median_retention_percentage"])
        self.assertIn("3 more", search["message"])
        self.assertEqual(self.store.cohort_analytics(snapshot_window="7d")["without_traffic_sources"], 1)

    def test_a_group_holds_one_format_and_language(self):
        for index in range(3):
            self.add(f"shorten{index:04d}", "RELATED_VIDEO", format_val="youtube_shorts", language="english")
        for index in range(2):
            self.add(f"longtam{index:04d}", "RELATED_VIDEO", format_val="tutorial", language="tamil")

        groups = self.store.cohort_analytics(snapshot_window="7d")["traffic_source_groups"]

        self.assertEqual(
            [(group["format"], group["language"], group["traffic_source"], group["sample_size"]) for group in groups],
            [("youtube_shorts", "english", "RELATED_VIDEO", 3), ("tutorial", "tamil", "RELATED_VIDEO", 2)],
        )
        self.assertFalse(any(group["learning_allowed"] for group in groups))

    def test_everyday_names_are_accepted_and_unknown_ones_refused(self):
        self.add("browsevid01", "SUBSCRIBER")
        self.assertEqual(self.store.cohort_analytics(snapshot_window="7d", traffic_source_filter="browse")["traffic_source"], "SUBSCRIBER")
        self.assertEqual(self.store.cohort_analytics(snapshot_window="7d", traffic_source_filter="Suggested")["traffic_source"], "RELATED_VIDEO")
        self.assertEqual(self.store.cohort_analytics(snapshot_window="7d")["traffic_source"], "all")
        with self.assertRaisesRegex(ValueError, "traffic source"):
            self.store.cohort_analytics(snapshot_window="7d", traffic_source_filter="drop table;")

    def test_the_route_passes_the_traffic_source(self):
        self.add("routevid001", "SHORTS")
        with patch.object(routes, "get_settings", return_value=self.settings):
            cohort = routes.get_cohort_analytics(window="7d", traffic_source="SHORTS")
            self.assertEqual((cohort["traffic_source"], cohort["sample_size"]), ("SHORTS", 1))
            with self.assertRaises(routes.HTTPException) as caught:
                routes.get_cohort_analytics(window="7d", traffic_source="not a source!")
        self.assertEqual(caught.exception.status_code, 422)

    def test_the_linked_report_shows_the_breakdown_and_its_cohort(self):
        self.add("reportvid01", "YT_SEARCH")
        self.add("peervideo01", "YT_SEARCH")
        run_id = int(self.store.published_video_link(self.store.published_video_links_list()[-1]["id"])["analysis_run_id"])
        report = self.store.linked_package_report(run_id)

        self.assertEqual(report["video_id"], "reportvid01")
        self.assertEqual(report["traffic_sources"]["dominant_source"], "YT_SEARCH")
        self.assertEqual(report["traffic_sources"]["window"], "7d")
        cohort = report["traffic_source_cohort"]
        # The video itself is left out: one peer so far.
        self.assertEqual((cohort["traffic_source"], cohort["sample_size"]), ("YT_SEARCH", 1))
        self.assertEqual(cohort["more_needed"], EARLY_SIGNAL_MIN_SAMPLES - 1)
        self.assertIsNone(cohort["median_views"])

    def test_a_report_without_a_breakdown_says_so(self):
        self.add("plainvideo1", None)
        run_id = int(self.store.published_video_links_list()[0]["analysis_run_id"])
        report = self.store.linked_package_report(run_id)
        self.assertIsNone(report["traffic_sources"])
        self.assertIsNone(report["traffic_source_cohort"])


if __name__ == "__main__":
    unittest.main()
