from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.integrations.youtube_channel import YouTubeChannelService


class Phase1YouTubeSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        self.store = HistoryStore(self.db_path)
        with self.store._connect() as connection:
            run_id = connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES (?, ?, ?)",
                ("snapshot test", datetime.now(timezone.utc).isoformat(), "Snapshot package"),
            ).lastrowid
        self.video_id = "phase1vid01"
        self.link_id = self.store.link_published_video(
            int(run_id),
            self.video_id,
            (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
            ownership_state="verified",
            ownership_verified=True,
            verified_channel_id="owner-channel",
            ownership_verified_at=datetime.now(timezone.utc).isoformat(),
        )
        self.settings = Settings(database_path=self.db_path)
        self.service = YouTubeChannelService(self.settings)

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            try:
                if os.path.exists(self.db_path + suffix):
                    os.remove(self.db_path + suffix)
            except OSError:
                pass

    def _youtube_api(self) -> MagicMock:
        youtube = MagicMock()
        youtube.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": self.video_id,
                    "snippet": {
                        "channelId": "owner-channel",
                        "title": "Owned video",
                        "description": "Description",
                        "publishedAt": "2026-08-01T00:00:00Z",
                        "tags": ["owned"],
                        "thumbnails": {},
                    },
                    "statistics": {"viewCount": "100", "likeCount": "5", "commentCount": "1"},
                    "contentDetails": {"duration": "PT10S"},
                    "status": {"privacyStatus": "public"},
                }
            ]
        }
        return youtube

    def _refresh_with_query_results(self, query_side_effect: list[object]) -> dict:
        credentials = MagicMock()
        analytics = MagicMock()
        with (
            patch.object(self.service, "_credentials", return_value=credentials),
            patch.object(
                self.service,
                "_connection",
                return_value=("token", "owner-channel", "Owner", "now"),
            ),
            patch(
                "win_engine.integrations.youtube_channel.build",
                side_effect=[self._youtube_api(), analytics],
            ),
            patch.object(self.service, "_query", side_effect=query_side_effect),
        ):
            link = self.store.published_video_link(self.link_id)
            return self.service.refresh_linked_video_performance(link or {})

    def test_empty_analytics_window_is_retryable_then_completes(self):
        first = self._refresh_with_query_results([{"views": 100}, {}])
        state = self.store.snapshot_window_state(self.video_id, "24h")
        self.assertEqual(first["captured"], [])
        self.assertEqual(state["status"], "empty_retryable")
        self.assertTrue(state["retry_allowed"])
        self.assertFalse(self.store.has_snapshot_window(self.video_id, "24h"))

        second = self._refresh_with_query_results(
            [
                {"views": 110},
                {
                    "views": 100,
                    "estimatedMinutesWatched": 20,
                    "averageViewDuration": 8,
                    "averageViewPercentage": 80,
                    "likes": 5,
                    "comments": 1,
                    "shares": 0,
                    "subscribersGained": 0,
                },
            ]
        )
        self.assertEqual(len(second["captured"]), 1)
        self.assertTrue(self.store.has_snapshot_window(self.video_id, "24h"))
        self.assertEqual(self.store.snapshot_window_state(self.video_id, "24h")["status"], "complete")

    def test_failed_analytics_window_is_retryable_without_aborting_current_refresh(self):
        result = self._refresh_with_query_results(
            [{"views": 100}, RuntimeError("temporary analytics failure")]
        )
        state = self.store.snapshot_window_state(self.video_id, "24h")
        self.assertEqual(result["captured"], [])
        self.assertEqual(state["status"], "failed_retryable")
        self.assertEqual(state["last_failure_reason"], "analytics_request_failed")
        self.assertTrue(state["retry_allowed"])
        self.assertIsNotNone(self.store.current_performance_snapshot(self.video_id))

    def test_retry_attempts_are_bounded_and_observable(self):
        for _ in range(5):
            self.store.record_snapshot_attempt(
                self.video_id,
                "24h",
                status="failed_retryable",
                failure_reason="analytics_request_failed",
                age_hours=48,
            )
        state = self.store.snapshot_window_state(self.video_id, "24h")
        self.assertEqual(state["attempt_count"], 5)
        self.assertFalse(state["retry_allowed"])


if __name__ == "__main__":
    unittest.main()
