"""The snapshot collector keeps going past dead links and stops on problems every link shares."""
from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from google.auth.exceptions import RefreshError

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.snapshot_collector import SnapshotCollector
from win_engine.integrations.youtube_channel import LinkUnavailable, YouTubeChannelService, YouTubeUnavailable

CONNECTED = {"configured": True, "connected": True, "channel": {"id": "UC-owner", "title": "Owner"}}


class SnapshotCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "collector.db")
        self.store = HistoryStore(self.path)
        published = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        for video_id in ("collectvid1", "collectvid2", "collectvid3"):
            with self.store._connect() as connection:
                run_id = int(connection.execute(
                    "INSERT INTO analysis_runs (query, created_at, title) VALUES (?, ?, ?)",
                    (video_id, published, video_id),
                ).lastrowid)
            self.store.link_published_video(
                run_id, video_id, published, ownership_state="verified", ownership_verified=True,
                verified_channel_id="UC-owner", ownership_verified_at=published,
            )
        self.collector = SnapshotCollector(Settings(
            database_path=self.path, snapshot_collector_enabled=True, snapshot_collector_dry_run=False,
            snapshot_collector_max_links_per_run=3,
        ))
        self.calls: list[tuple[str, list[str]]] = []

    def tearDown(self) -> None:
        self.dir.cleanup()

    def run_with(self, outcomes: dict[str, Exception | None], status: dict = CONNECTED) -> dict:
        def refresh(_service, item, *, force, collect_current, windows):
            self.calls.append((item["youtube_video_id"], list(windows)))
            outcome = outcomes.get(item["youtube_video_id"])
            if outcome:
                raise outcome
            return {"captured": []}

        with (
            patch.object(YouTubeChannelService, "status", return_value=status),
            patch.object(YouTubeChannelService, "refresh_linked_video_performance", autospec=True, side_effect=refresh),
        ):
            return self.collector.run_once()

    def test_a_dead_link_does_not_stop_the_others(self):
        result = self.run_with({"collectvid1": LinkUnavailable("gone")})
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(result["counts"]["failed"], 1)
        # The planned windows are what the refresh may collect.
        self.assertEqual(self.calls[0][1], ["24h", "7d", "28d"])

    def test_running_out_of_quota_stops_the_run_and_backs_off(self):
        quota = YouTubeUnavailable("quota", status_code=429)
        result = self.run_with({video: quota for video in ("collectvid1", "collectvid2", "collectvid3")})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["state"], "cooldown")
        failed_video = self.calls[0][0]
        state = self.store.snapshot_window_state(failed_video, "24h")
        self.assertEqual((state["status"], state["attempt_count"]), ("failed_retryable", 0))

    def test_an_outage_that_lasts_several_runs_spends_no_attempts(self):
        outage = YouTubeUnavailable("unreachable", status_code=503)
        for _ in range(6):
            with self.store._connect() as connection:  # as if every cooldown had passed
                connection.execute("UPDATE video_performance_snapshots SET last_attempted_at = '2000-01-01T00:00:00+00:00'")
            self.calls.clear()
            result = self.run_with({video: outage for video in ("collectvid1", "collectvid2", "collectvid3")})
            # Every later link would fail the same way, so the run stops at the first.
            self.assertEqual((len(self.calls), result["state"]), (1, "cooldown"))

        for video in ("collectvid1", "collectvid2", "collectvid3"):
            state = self.store.snapshot_window_state(video, "28d")
            self.assertEqual((state["attempt_count"], state["retry_allowed"]), (0, True), video)
        self.assertEqual(len(self.store.due_snapshot_links()), 3)

    def test_an_unexpected_error_spends_no_attempt_and_the_link_goes_last(self):
        result = self.run_with({"collectvid1": RuntimeError("bug")})

        self.assertEqual([video for video, _windows in self.calls], ["collectvid1"])
        self.assertEqual(result["counts"]["failed"], 1)
        self.assertEqual(self.store.snapshot_window_state("collectvid1", "24h")["attempt_count"], 0)
        self.assertEqual(self.store.due_snapshot_links()[-1]["youtube_video_id"], "collectvid1")

    def test_videos_verified_for_another_channel_are_not_planned(self):
        # Verified on another device for its channel, and the oldest, so it would be planned first.
        published = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        with self.store._connect() as connection:
            run_id = int(connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES ('other', ?, 'other')", (published,)
            ).lastrowid)
        self.store.link_published_video(
            run_id, "othervideo1", published, ownership_state="verified", ownership_verified=True,
            verified_channel_id="UC-other", ownership_verified_at=published,
        )

        result = self.run_with({})

        self.assertEqual(sorted(video for video, _windows in self.calls), ["collectvid1", "collectvid2", "collectvid3"])
        self.assertNotIn("othervideo1", [item["video_id"] for item in result["planned"]])

    def test_a_restart_during_a_run_leaves_a_running_loop(self):
        collector = SnapshotCollector(Settings(
            database_path=self.path, snapshot_collector_enabled=True, snapshot_collector_initial_delay_seconds=0,
        ))
        self.addCleanup(collector.stop)
        running, release = threading.Event(), threading.Event()

        def slow_run():
            running.set()
            release.wait(5)
            return {}

        collector.run_once = slow_run
        collector.start()
        self.assertTrue(running.wait(5))
        old_loop = collector._thread
        collector._stop.set()  # what stop() leaves behind when its join times out during a run

        collector.start()
        release.set()

        old_loop.join(5)  # the old loop finishes its run, sees its stop signal and ends
        self.assertFalse(old_loop.is_alive())
        self.assertTrue(collector._thread.is_alive())

    def test_a_revoked_grant_stops_the_run(self):
        self.run_with({video: RefreshError("invalid_grant") for video in ("collectvid1", "collectvid2", "collectvid3")})
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.collector.status()["last_error"], "RefreshError")

    def test_nothing_is_collected_until_the_channel_is_identified(self):
        pending = {**CONNECTED, "channel": {"id": "", "title": ""}}
        result = self.run_with({}, status=pending)
        self.assertEqual(result["state"], "unconfigured")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
