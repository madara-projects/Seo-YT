"""The explicit "Retry failed windows" refresh asks once more for a breakdown whose attempts are used up."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet

from win_engine.core.config import Settings
from win_engine.feedback.history_store import _MAX_TRAFFIC_ATTEMPTS, HistoryStore
from win_engine.feedback.snapshot_collector import SnapshotCollector
from win_engine.integrations import youtube_channel
from win_engine.integrations.youtube_channel import YouTubeChannelService

BUILD = "win_engine.integrations.youtube_channel.build"
CONNECTED = {"configured": True, "connected": True, "channel": {"id": "UC-owner", "title": "Owner"}}
TRAFFIC_ROWS = [
    {"insightTrafficSourceType": "RELATED_VIDEO", "views": 30, "estimatedMinutesWatched": 90.5},
    {"insightTrafficSourceType": "YT_SEARCH", "views": 70, "estimatedMinutesWatched": 210.0},
]
UNUSABLE = [{"source": "", "views": 3}]


class TrafficBackfillRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = str(Path(self.dir.name) / "traffic-retry.db")
        self.settings = Settings(
            database_path=self.path, youtube_api_key="", youtube_api_keys="",
            youtube_oauth_client_id="client-id", youtube_oauth_client_secret="client-secret",
            oauth_token_encryption_key=Fernet.generate_key().decode(),
            snapshot_collector_enabled=True, snapshot_collector_dry_run=False,
        )
        self.store = HistoryStore(self.path)
        self.service = YouTubeChannelService(self.settings)
        self.service._save_connection("refresh", "UC-owner", "Owner")

    def link(self, video_id: str, published_at: datetime) -> dict:
        published = published_at.isoformat()
        run_id = self.store.record_analysis_run(video_id, "search", "tutorial", video_id, 7.0, "LOW", "WORKABLE", 50, {})
        link_id = self.store.link_published_video(
            run_id, video_id, published, format_val="tutorial", language="english",
            ownership_state="verified", ownership_verified=True,
            verified_channel_id="UC-owner", ownership_verified_at=published,
        )
        return self.store.published_video_link(link_id) or {}

    def exhausted_window(self, video_id: str, published_at: datetime, views: int = 55) -> dict:
        """A completed 24h window, dated from the link's Pacific publish day, whose breakdown failed five counted times."""
        link = self.link(video_id, published_at)
        first_day = published_at.astimezone(youtube_channel._ANALYTICS_ZONE).date()
        self.store.record_performance_snapshot(
            video_id, 24, views=views, snapshot_window="24h",
            source_start_date=first_day.isoformat(), source_end_date=(first_day + timedelta(days=1)).isoformat(),
        )
        for _ in range(_MAX_TRAFFIC_ATTEMPTS):
            # Rows without a usable source are a counted failure, not an empty breakdown.
            self.assertEqual(self.store.record_traffic_breakdown(video_id, "24h", status="ok", sources=UNUSABLE), "failed")
        snapshot = self.store.completed_evidence_snapshot(video_id, "24h")
        self.assertEqual(
            (snapshot["traffic_status"], snapshot["traffic_last_failure_reason"], snapshot["traffic_attempt_count"]),
            ("failed", "analytics_rows_unusable", _MAX_TRAFFIC_ATTEMPTS),
        )
        return link

    def youtube(self) -> MagicMock:
        youtube = MagicMock()
        youtube.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"snippet": {"channelId": "UC-owner", "publishedAt": "2026-08-01T00:00:00Z"}, "statistics": {}}]
        }
        return youtube

    def refresh(self, link: dict, *, force: bool, rows=None):
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=lambda name, *_args, **_kwargs: self.youtube() if name == "youtube" else MagicMock()),
            patch.object(self.service, "_query", return_value={"views": 100}),
            patch.object(self.service, "_query_rows", return_value=rows or []) as query_rows,
        ):
            # Collecting current counts is the manual refresh's default (the route's
            # path), and it reaches the backfill even when no window is due.
            result = self.service.refresh_linked_video_performance(link, force=force, windows=["24h"])
        return result, query_rows

    def test_an_ordinary_refresh_asks_nothing_after_five_counted_failures(self):
        link = self.exhausted_window("exhaust0001", datetime(2026, 8, 1, tzinfo=timezone.utc))

        result, query_rows = self.refresh(link, force=False, rows=TRAFFIC_ROWS)

        query_rows.assert_not_called()
        self.assertEqual(result["captured"], [])
        snapshot = self.store.completed_evidence_snapshot("exhaust0001", "24h")
        self.assertIsNone(snapshot["traffic_sources"])
        self.assertEqual((snapshot["traffic_status"], snapshot["traffic_attempt_count"]), ("failed", _MAX_TRAFFIC_ATTEMPTS))

    def test_the_retry_flag_asks_once_and_keeps_the_breakdown_without_touching_the_metrics(self):
        link = self.exhausted_window("exhaust0002", datetime(2026, 8, 1, tzinfo=timezone.utc), views=55)

        _, query_rows = self.refresh(link, force=True, rows=TRAFFIC_ROWS)

        self.assertEqual(query_rows.call_count, 1)
        self.assertEqual(query_rows.call_args.kwargs["filters"], "video==exhaust0002")
        # The same Pacific days as the window's own metrics.
        start, end = query_rows.call_args.args[1:3]
        self.assertEqual((start.isoformat(), end.isoformat()), ("2026-07-31", "2026-08-01"))
        snapshot = self.store.completed_evidence_snapshot("exhaust0002", "24h")
        self.assertEqual(snapshot["traffic_status"], "ok")
        self.assertIsNone(snapshot["traffic_last_failure_reason"])
        self.assertEqual(snapshot["traffic_sources"]["dominant_source"], "YT_SEARCH")
        self.assertEqual(snapshot["traffic_attempt_count"], _MAX_TRAFFIC_ATTEMPTS + 1)
        # Primary metrics are never touched by the retry.
        self.assertEqual((snapshot["snapshot_status"], snapshot["views"]), ("complete", 55))

        # Final now: a later forced refresh asks for nothing.
        _, query_rows = self.refresh(link, force=True, rows=TRAFFIC_ROWS)
        query_rows.assert_not_called()

    def test_a_forced_retry_that_fails_again_stays_capped_for_ordinary_refreshes(self):
        link = self.exhausted_window("exhaust0003", datetime(2026, 8, 1, tzinfo=timezone.utc))

        _, query_rows = self.refresh(link, force=True, rows=[{"insightTrafficSourceType": "", "views": 2}])
        self.assertEqual(query_rows.call_count, 1)
        snapshot = self.store.completed_evidence_snapshot("exhaust0003", "24h")
        self.assertEqual((snapshot["traffic_status"], snapshot["traffic_attempt_count"]), ("failed", _MAX_TRAFFIC_ATTEMPTS + 1))

        _, query_rows = self.refresh(link, force=False, rows=TRAFFIC_ROWS)
        query_rows.assert_not_called()

    def test_the_retry_keeps_empty_final_and_a_refusal_waiting_for_a_reconnect(self):
        published = datetime(2026, 8, 1, tzinfo=timezone.utc)
        self.exhausted_window("exhaust0004", published)
        self.exhausted_window("exhaust0005", published)
        self.exhausted_window("exhaust0006", published)
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE video_performance_snapshots SET traffic_status = 'empty', traffic_last_failure_reason = NULL "
                "WHERE youtube_video_id = 'exhaust0004'"
            )
            connection.execute(
                "UPDATE video_performance_snapshots SET traffic_status = 'refused', "
                "traffic_last_failure_reason = 'analytics_access_refused' WHERE youtube_video_id = 'exhaust0005'"
            )
        planned = self.service._traffic_backfill_plan(self.store, self.service._connection(), force=True)
        self.assertEqual([item["youtube_video_id"] for item in planned], ["exhaust0006"])
        self.assertEqual(self.service._traffic_backfill_plan(self.store, self.service._connection()), [])
        # Not exhausted, recently failed: the retry flag keeps that window's backoff.
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE video_performance_snapshots SET traffic_attempt_count = 2 WHERE youtube_video_id = 'exhaust0006'"
            )
        self.assertEqual(
            self.store.due_traffic_backfills(retry_cooldown_seconds=3600, retry_max_seconds=86400, include_exhausted=True), []
        )

    def test_the_collector_still_respects_the_cap(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=3)
        self.exhausted_window("exhaust0007", published_at)
        # Only the cap keeps it out: the explicit retry would plan it.
        self.assertEqual(
            [item["youtube_video_id"] for item in self.store.due_traffic_backfills(include_exhausted=True)], ["exhaust0007"]
        )
        youtube = self.youtube()
        with (
            patch.object(YouTubeChannelService, "status", return_value=CONNECTED),
            patch.object(YouTubeChannelService, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=lambda name, *_args, **_kwargs: youtube if name == "youtube" else MagicMock()),
            patch.object(YouTubeChannelService, "_query", return_value={"views": 12}),
            patch.object(YouTubeChannelService, "_query_rows", return_value=TRAFFIC_ROWS) as query_rows,
        ):
            result = SnapshotCollector(self.settings).run_once()

        query_rows.assert_not_called()
        self.assertEqual(result["counts"]["traffic_backfill"], 0)
        snapshot = self.store.completed_evidence_snapshot("exhaust0007", "24h")
        self.assertEqual((snapshot["traffic_status"], snapshot["traffic_attempt_count"]), ("failed", _MAX_TRAFFIC_ATTEMPTS))
        self.assertEqual(snapshot["views"], 55)


if __name__ == "__main__":
    unittest.main()
