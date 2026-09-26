"""Regression tests for the watchlist outlier baseline, format helpers and list queries."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.intelligence_store import IntelligenceStore, duration_seconds, inferred_format

BASE = datetime(2026, 9, 1, tzinfo=timezone.utc)


class WatchlistFixture(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.path = handle.name
        handle.close()
        self.history = HistoryStore(self.path)
        self.store = IntelligenceStore(self.history)
        self.counter = 0

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.path + suffix)
            except OSError:
                pass

    def video(self, *, published: datetime | None, channel: str | None = "UC-peer", duration: str = "PT8M") -> int:
        """A watched video without snapshots; observations are added at chosen times."""
        self.counter += 1
        item = self.store.upsert_video(
            {"video_id": f"fixfwatch{self.counter:02d}", "title": f"Upload {self.counter}", "channel_id": channel,
             "published_at": published.isoformat() if published else None, "duration": duration},
            snapshot=False,
        )
        return int(item["id"])

    def observe(self, item_id: int, views: int, captured: datetime, *, likes: int | None = 10, comments: int | None = 2) -> None:
        with self.history._connect() as connection:
            connection.execute(
                "INSERT INTO watchlist_video_snapshots(watchlist_video_id,captured_at,view_count,like_count,comment_count,duration_seconds,metadata_json,source) VALUES(?,?,?,?,?,?,'{}','public_observation')",
                (item_id, captured.isoformat(), views, likes, comments, 480),
            )


class OutlierBaselineTests(WatchlistFixture):
    def test_old_uploads_are_not_a_baseline_for_a_new_video(self):
        for _ in range(6):
            peer = self.video(published=datetime(2022, 1, 1, tzinfo=timezone.utc))
            self.observe(peer, 200_000, BASE)
        target = self.video(published=BASE - timedelta(days=2))
        self.observe(target, 60_000, BASE)

        result = self.store.analyze_outlier(target)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["relative_multiplier"])
        self.assertEqual(result["sample_size"], 0)
        self.assertIn("at least 5", result["explanation"])

    def test_peers_are_read_from_the_snapshot_nearest_the_same_age(self):
        published = BASE - timedelta(days=30)
        for index in range(5):
            peer = self.video(published=published + timedelta(days=index))
            self.observe(peer, 1000 + 100 * index, published + timedelta(days=index, hours=48))
            self.observe(peer, 50_000, BASE)  # the same peer a month on
        target = self.video(published=BASE - timedelta(hours=48))
        self.observe(target, 6000, BASE)

        result = self.store.analyze_outlier(target)
        self.assertEqual(result["sample_size"], 5)
        self.assertEqual(result["baseline_median_views"], 1200)
        self.assertEqual(result["relative_multiplier"], 5.0)
        self.assertEqual(result["status"], "possible_outlier")
        self.assertIn("similar age", result["explanation"])

    def test_peer_views_are_scaled_to_the_videos_age(self):
        for index in range(5):
            peer = self.video(published=BASE - timedelta(days=20 + index))
            # Observed at 90 hours; the video is 48 hours old, so 1875 views scale to 1000.
            self.observe(peer, 1875, BASE - timedelta(days=20 + index) + timedelta(hours=90))
        target = self.video(published=BASE - timedelta(hours=48))
        self.observe(target, 1500, BASE)

        result = self.store.analyze_outlier(target)
        self.assertEqual(result["sample_size"], 5)
        self.assertEqual(result["baseline_median_views"], 1000)
        self.assertEqual(result["relative_multiplier"], 1.5)
        self.assertEqual(result["status"], "observed_normal")
        self.assertIn("below the 2.5x", result["explanation"])

    def test_video_without_a_snapshot_is_told_so(self):
        for index in range(7):
            peer = self.video(published=BASE - timedelta(days=3 + index))
            self.observe(peer, 500, BASE)
        target = self.video(published=BASE - timedelta(days=2))

        result = self.store.analyze_outlier(target)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["sample_size"], 0)
        self.assertIn("no public view count", result["explanation"])
        self.assertNotIn("Only 7", result["explanation"])

    def test_videos_without_a_channel_are_not_pooled(self):
        for index in range(6):
            peer = self.video(published=BASE - timedelta(days=2, hours=index), channel=None)
            self.observe(peer, 500, BASE)
        target = self.video(published=BASE - timedelta(days=2), channel=None)
        self.observe(target, 5000, BASE)

        result = self.store.analyze_outlier(target)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["sample_size"], 0)
        self.assertIn("channel is unknown", result["explanation"])

    def test_unknown_publication_time_is_explained(self):
        for index in range(6):
            peer = self.video(published=BASE - timedelta(days=2, hours=index))
            self.observe(peer, 500, BASE)
        target = self.video(published=None)
        self.observe(target, 5000, BASE)

        result = self.store.analyze_outlier(target)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIn("publication time is unavailable", result["explanation"])


class FormatAndEngagementTests(WatchlistFixture):
    def test_duration_decides_the_format_with_a_three_minute_shorts_limit(self):
        cases = {"P0D": "unknown", "": "unknown", "PT59S": "youtube_shorts", "PT2M30S": "youtube_shorts",
                 "PT3M": "youtube_shorts", "PT3M1S": "long_form", "PT1H2M": "long_form"}
        for duration, expected in cases.items():
            self.assertEqual(inferred_format(duration_seconds(duration)), expected, duration)

    def test_live_broadcast_is_saved_with_unknown_length_and_format(self):
        item = self.store.upsert_video(
            {"video_id": "fixflive001", "title": "Live now", "channel_id": "UC-peer", "duration": "P0D", "view_count": 10},
            snapshot=True,
        )
        self.assertIsNone(item["duration_seconds"])
        self.assertEqual(item["format"], "unknown")

    def test_hidden_likes_leave_the_engagement_ratio_unknown(self):
        hidden = self.video(published=BASE - timedelta(days=2))
        self.observe(hidden, 1000, BASE, likes=None, comments=5)
        shown = self.video(published=BASE - timedelta(days=2))
        self.observe(shown, 1000, BASE, likes=10, comments=5)

        self.assertIsNone(self.store.analyze_outlier(hidden)["signals"]["engagement_ratio"])
        self.assertEqual(self.store.analyze_outlier(shown)["signals"]["engagement_ratio"], 0.015)


class WatchlistListQueryTests(WatchlistFixture):
    def test_video_list_items_carry_only_the_latest_snapshot(self):
        item_id = self.video(published=BASE - timedelta(days=5))
        for day, views in ((1, 100), (2, 200), (3, 300)):
            self.observe(item_id, views, BASE - timedelta(days=5 - day))
        analysis = self.store.analyze_outlier(item_id)

        listed = self.store.videos()[0]
        detail = self.store.video(item_id)
        self.assertEqual(len(detail["snapshots"]), 3)
        self.assertEqual(listed["snapshots"], [listed["latest_snapshot"]])
        self.assertEqual(listed["latest_snapshot"], detail["latest_snapshot"])
        self.assertEqual(listed["latest_snapshot"]["view_count"], 300)
        self.assertEqual(listed["outlier"]["id"], analysis["id"])
        self.assertEqual(listed["outlier"], detail["outlier"])

    def test_video_list_filters_still_apply(self):
        kept = self.video(published=BASE)
        archived = self.video(published=BASE)
        self.store.update_video(archived, {"state": "archived"})
        never_observed = self.video(published=BASE)

        self.assertEqual({item["id"] for item in self.store.videos(state="active")}, {kept, never_observed})
        self.assertEqual([item["id"] for item in self.store.videos(state="archived")], [archived])
        self.assertEqual([item["id"] for item in self.store.videos(query="Upload 1")], [kept])
        unobserved = next(item for item in self.store.videos() if item["id"] == never_observed)
        self.assertEqual((unobserved["snapshots"], unobserved["latest_snapshot"], unobserved["outlier"]), ([], None, None))

    def test_channel_list_items_carry_only_the_latest_snapshot(self):
        channel = self.store.create_channel({"channel_id": "UC-peer", "title": "Peer"})
        self.store.snapshot_channel(channel["id"], {"channel_id": "UC-peer", "title": "Peer", "subscriber_count": 10}, [])
        self.store.snapshot_channel(channel["id"], {"channel_id": "UC-peer", "title": "Peer", "subscriber_count": 11}, [])
        self.store.create_channel({"channel_id": "UC-empty", "title": "Empty"})

        listed = {item["channel_id"]: item for item in self.store.channels()}
        self.assertEqual(len(self.store.channel(channel["id"])["snapshots"]), 2)
        self.assertEqual([snapshot["subscriber_count"] for snapshot in listed["UC-peer"]["snapshots"]], [11])
        self.assertEqual(listed["UC-empty"]["snapshots"], [])
        with self.assertRaisesRegex(ValueError, "already"):
            self.store.create_channel({"channel_id": "UC-peer", "title": "Peer"})

    def test_demand_list_returns_the_same_rows_as_single_reads(self):
        saved = [self.store.save_demand({"topic": f"topic {index}", "idea_id": None}, "insufficient_evidence", {"n": index}) for index in range(3)]

        page = self.store.demands(limit=2)
        self.assertEqual(page["total"], 3)
        self.assertEqual((page["limit"], page["offset"]), (2, 0))
        self.assertEqual(page["research"], [self.store.demand(item["id"]) for item in reversed(saved[1:])])
        self.assertEqual(self.store.demands(limit=2, offset=2)["research"], [self.store.demand(saved[0]["id"])])


if __name__ == "__main__":
    unittest.main()
