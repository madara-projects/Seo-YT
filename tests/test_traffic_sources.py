"""Traffic sources are kept with each completed window and compared only with enough evidence."""
from __future__ import annotations

import contextlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httplib2
from cryptography.fernet import Fernet
from google.auth.exceptions import RefreshError
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

    def refresh(self, link: dict, *, rows=None, error: Exception | None = None, views: int | None = 100,
                collect_current: bool = False):
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[self.youtube(), MagicMock()]),
            patch.object(self.service, "_query", return_value={"views": views} if views is not None else {}),
            patch.object(self.service, "_query_rows", return_value=rows or [], side_effect=error) as query_rows,
        ):
            result = self.service.refresh_linked_video_performance(link, collect_current=collect_current, windows=["24h"])
        return result, query_rows

    def legacy_window(self, video_id: str, window: str = "24h", views: int = 55, *,
                      source_start_date: str = "2026-07-31", source_end_date: str = "2026-08-01") -> None:
        """A completed window captured before traffic outcomes were recorded: no breakdown, no status.

        Its range starts on the link's Pacific publish date, as a real window's
        does; one that starts elsewhere was measured from another publish time
        and is retired from learning as pre-public history.
        """
        self.store.record_performance_snapshot(
            video_id, 24, views=views, snapshot_window=window,
            source_start_date=source_start_date, source_end_date=source_end_date,
        )

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
        self.assertEqual((stored["traffic_status"], stored["traffic_attempt_count"]), ("ok", 1))
        self.assertIsNone(stored["traffic_last_failure_reason"])
        self.assertIsNotNone(stored["traffic_last_attempted_at"])

    def test_each_breakdown_outcome_is_recorded_and_the_metrics_are_kept(self):
        for video_id, error, outcome in (
            ("trafficvid2", _http_error(403, "insufficientPermissions"), ("refused", "analytics_access_refused", 1)),
            ("trafficvid3", _http_error(400, "badRequest"), ("failed", "analytics_request_failed", 1)),
            # An outage is not the window's fault: noted without spending an attempt.
            ("trafficvid4", TimeoutError("read"), ("failed", "youtube_unavailable", 0)),
            ("trafficvi4b", _http_error(503, "backendError"), ("failed", "youtube_unavailable", 0)),
            # A quota or rate limit answered with HTTP 403 is an outage too, not a
            # refusal that would wait for a reconnect.
            ("trafficvi4c", _http_error(403, "quotaExceeded"), ("failed", "youtube_unavailable", 0)),
        ):
            with self.subTest(error=type(error).__name__, video=video_id):
                result, _ = self.refresh(self.link(video_id), error=error)
                snapshot = self.store.completed_evidence_snapshot(video_id, "24h")
                self.assertEqual((snapshot["snapshot_status"], snapshot["views"]), ("complete", 100))
                self.assertIsNone(snapshot["traffic_sources"])
                self.assertEqual(
                    (snapshot["traffic_status"], snapshot["traffic_last_failure_reason"], snapshot["traffic_attempt_count"]),
                    outcome,
                )
                self.assertEqual(result["captured"][0]["traffic_status"], outcome[0])

    def test_a_bug_in_the_breakdown_request_is_logged_and_recorded_not_swallowed(self):
        with self.assertLogs("win_engine.integrations.youtube_channel", level="ERROR") as logs:
            result, _ = self.refresh(self.link("trafficbug1"), error=KeyError("columnHeaders"))
        self.assertTrue(any("Traceback" in line and "KeyError" in line for line in logs.output))
        snapshot = self.store.completed_evidence_snapshot("trafficbug1", "24h")
        self.assertEqual((snapshot["snapshot_status"], snapshot["views"]), ("complete", 100))
        self.assertEqual((snapshot["traffic_status"], snapshot["traffic_last_failure_reason"]), ("failed", "unexpected_error"))
        self.assertEqual(result["captured"][0]["traffic_last_failure_reason"], "unexpected_error")

    def test_a_breakdown_answer_of_another_shape_is_a_bug_that_never_fails_the_refresh(self):
        # None is what an older version returned; a stale patch or merge that keeps it is caught.
        link = self.link("shapebug001")
        with (
            patch.object(self.service, "_traffic_sources", return_value=None),
            self.assertLogs("win_engine.integrations.youtube_channel", level="ERROR") as logs,
        ):
            result, _ = self.refresh(link, rows=TRAFFIC_ROWS, collect_current=True)
        self.assertTrue(any("TypeError" in line for line in logs.output))
        snapshot = self.store.completed_evidence_snapshot("shapebug001", "24h")
        self.assertEqual((snapshot["snapshot_status"], snapshot["views"]), ("complete", 100))
        self.assertEqual((snapshot["traffic_status"], snapshot["traffic_last_failure_reason"]), ("failed", "unexpected_error"))
        self.assertEqual(result["captured"][0]["traffic_status"], "failed")
        # The refresh went on to its current count.
        with self.store._connect() as connection:
            current = connection.execute(
                "SELECT COUNT(*) FROM video_performance_snapshots WHERE youtube_video_id = 'shapebug001' AND snapshot_window = 'current'"
            ).fetchone()[0]
        self.assertEqual(current, 1)

    def test_rows_without_a_usable_source_are_a_failure_not_a_final_empty_breakdown(self):
        rows = [{"insightTrafficSourceType": "", "views": 5}, {"insightTrafficSourceType": "YT_SEARCH", "views": None}]
        self.refresh(self.link("unusable001"), rows=rows)
        snapshot = self.store.completed_evidence_snapshot("unusable001", "24h")
        self.assertEqual((snapshot["snapshot_status"], snapshot["views"]), ("complete", 100))
        self.assertEqual(
            (snapshot["traffic_status"], snapshot["traffic_last_failure_reason"], snapshot["traffic_attempt_count"]),
            ("failed", "analytics_rows_unusable", 1),
        )
        # The store applies the same rule to sources it is handed.
        self.link("unusable002")
        self.legacy_window("unusable002")
        self.assertEqual(
            self.store.record_traffic_breakdown("unusable002", "24h", status="ok", sources=[{"source": "", "views": 3}]),
            "failed",
        )

    def test_an_expired_grant_mid_request_spends_no_attempt_and_is_not_logged_as_a_bug(self):
        with self.assertNoLogs("win_engine.integrations.youtube_channel", level="ERROR"):
            self.refresh(self.link("grantvid001"), error=RefreshError("invalid_grant"))
        snapshot = self.store.completed_evidence_snapshot("grantvid001", "24h")
        self.assertEqual((snapshot["snapshot_status"], snapshot["views"]), ("complete", 100))
        self.assertEqual(
            (snapshot["traffic_status"], snapshot["traffic_last_failure_reason"], snapshot["traffic_attempt_count"]),
            ("failed", "channel_authorization_failed", 0),
        )

    def test_the_metrics_are_saved_before_the_breakdown_is_asked_for(self):
        seen: list[tuple] = []

        def traffic_query(*_args, **_kwargs):
            stored = self.store.completed_evidence_snapshot("ordervid001", "24h") or {}
            seen.append((stored.get("snapshot_status"), stored.get("views")))
            return TRAFFIC_ROWS

        self.refresh(self.link("ordervid001"), error=traffic_query)
        self.assertEqual(seen, [("complete", 100)])

    def test_a_failing_backfill_plan_never_fails_the_refresh(self):
        link = self.link("planbug0001")
        with (
            patch.object(self.service, "_traffic_backfill_plan", side_effect=sqlite3.OperationalError("database is locked")),
            self.assertLogs("win_engine.integrations.youtube_channel", level="ERROR") as logs,
        ):
            result, _ = self.refresh(link, rows=TRAFFIC_ROWS, collect_current=True)
        self.assertTrue(any("OperationalError" in line for line in logs.output))
        self.assertEqual(result["traffic_backfill"]["unexpected"], 1)
        self.assertEqual(result["captured"][0]["traffic_status"], "ok")
        # The refresh went on to its current count.
        with self.store._connect() as connection:
            current = connection.execute(
                "SELECT COUNT(*) FROM video_performance_snapshots WHERE youtube_video_id = 'planbug0001' AND snapshot_window = 'current'"
            ).fetchone()[0]
        self.assertEqual(current, 1)

    def test_the_collector_pass_skips_a_window_a_manual_refresh_just_resolved(self):
        self.link("racevid0001")
        self.legacy_window("racevid0001")
        real_lock = youtube_channel._refresh_lock

        @contextlib.contextmanager
        def lock_after_a_manual_refresh(video_id):
            # The manual refresh held the lock while the plan was made, and filled the window.
            self.store.record_traffic_breakdown(video_id, "24h", status="ok", sources=_sources("YT_SEARCH"))
            with real_lock(video_id):
                yield

        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, return_value=MagicMock()),
            patch.object(youtube_channel, "_refresh_lock", lock_after_a_manual_refresh),
            patch.object(self.service, "_query_rows", return_value=TRAFFIC_ROWS) as query_rows,
        ):
            counts = self.service.backfill_traffic_sources(limit=5)
        query_rows.assert_not_called()
        self.assertEqual(counts["windows"], 0)

    def test_no_rows_is_a_final_empty_breakdown_and_an_empty_window_asks_for_none(self):
        self.refresh(self.link("trafficvid5"), rows=[])
        snapshot = self.store.completed_evidence_snapshot("trafficvid5", "24h")
        self.assertIsNone(snapshot["traffic_sources"])
        self.assertEqual(snapshot["traffic_status"], "empty")
        # "empty" is final: never asked for again, and never overwritten.
        self.assertEqual(self.store.due_traffic_backfills(reconnected_at=datetime.now(timezone.utc) + timedelta(days=1)), [])
        self.assertIsNone(self.store.record_traffic_breakdown("trafficvid5", "24h", status="ok", sources=_sources("YT_SEARCH")))

        _, query_rows = self.refresh(self.link("trafficvid6"), views=None)
        query_rows.assert_not_called()
        self.assertEqual(self.store.snapshot_window_state("trafficvid6", "24h")["status"], "empty_retryable")

    def test_a_manual_refresh_fills_a_legacy_window_without_touching_its_metrics(self):
        link = self.link("legacyvid01")
        self.legacy_window("legacyvid01")
        self.assertIsNone(self.store.completed_evidence_snapshot("legacyvid01", "24h")["traffic_status"])

        _, query_rows = self.refresh(link, rows=TRAFFIC_ROWS, collect_current=True)

        # The window's stored days, not a new range.
        start, end = query_rows.call_args.args[1:3]
        self.assertEqual((start.isoformat(), end.isoformat()), ("2026-07-31", "2026-08-01"))
        snapshot = self.store.completed_evidence_snapshot("legacyvid01", "24h")
        self.assertEqual((snapshot["views"], snapshot["traffic_status"]), (55, "ok"))
        self.assertEqual(snapshot["traffic_sources"]["dominant_source"], "YT_SEARCH")
        # Final now: the next refresh asks for nothing.
        _, query_rows = self.refresh(link, rows=TRAFFIC_ROWS, collect_current=True)
        query_rows.assert_not_called()

    def test_a_failed_breakdown_is_retried_after_its_backoff_within_its_attempts(self):
        self.link("failedvid01")
        self.legacy_window("failedvid01")
        self.store.record_traffic_breakdown("failedvid01", "24h", status="failed", failure_reason="analytics_request_failed")

        def plan() -> list[dict]:
            return self.store.due_traffic_backfills(retry_cooldown_seconds=3600, retry_max_seconds=86400)

        self.assertEqual(plan(), [])
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE video_performance_snapshots SET traffic_last_attempted_at = ? WHERE youtube_video_id = 'failedvid01'",
                ((datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),),
            )
        self.assertEqual([(item["youtube_video_id"], item["snapshot_window"]) for item in plan()], [("failedvid01", "24h")])
        with self.store._connect() as connection:
            connection.execute("UPDATE video_performance_snapshots SET traffic_attempt_count = 5 WHERE youtube_video_id = 'failedvid01'")
        self.assertEqual(plan(), [])

    def test_a_refused_breakdown_waits_for_the_channel_to_be_connected_again(self):
        self.link("refusevid01")
        self.legacy_window("refusevid01")
        self.store.record_traffic_breakdown("refusevid01", "24h", status="refused", failure_reason="analytics_access_refused")
        record = self.service._connection()
        # Connected before the refusal, and a channel sync is no reconnect.
        self.service._update_connection_channel("UC-owner", "Owner")
        self.assertEqual(self.service._traffic_backfill_plan(self.store, self.service._connection()), [])

        later = datetime.now(timezone.utc) + timedelta(minutes=5)
        with patch("cryptography.fernet.time.time", return_value=later.timestamp()):
            self.service._save_connection("refresh-again", "UC-owner", "Owner")
        self.assertNotEqual(self.service._connection()[0], record[0])
        planned = self.service._traffic_backfill_plan(self.store, self.service._connection())
        self.assertEqual([(item["youtube_video_id"], item["traffic_status"]) for item in planned], [("refusevid01", "refused")])

    def test_the_breakdown_update_touches_only_the_traffic_columns(self):
        self.link("onlytraf01")
        self.legacy_window("onlytraf01", views=55)
        before = self.store.completed_evidence_snapshot("onlytraf01", "24h")
        self.assertEqual(self.store.record_traffic_breakdown("onlytraf01", "24h", status="ok", sources=_sources("SHORTS")), "ok")
        after = self.store.completed_evidence_snapshot("onlytraf01", "24h")
        traffic_fields = {"traffic_sources", "traffic_status", "traffic_attempt_count", "traffic_last_attempted_at",
                          "traffic_last_failure_reason"}
        self.assertEqual({k: v for k, v in before.items() if k not in traffic_fields},
                         {k: v for k, v in after.items() if k not in traffic_fields})
        # A window still collecting has no completed row to fill.
        self.store.record_snapshot_attempt("onlytraf01", "7d", status="failed_retryable", failure_reason="analytics_request_failed")
        self.assertIsNone(self.store.record_traffic_breakdown("onlytraf01", "7d", status="ok", sources=_sources("SHORTS")))
        # A breakdown stored before these columns existed is kept and not asked for again.
        self.link("oldtraffic1")
        self.store.record_performance_snapshot(
            "oldtraffic1", 24, views=9, snapshot_window="24h", source_start_date="2026-07-31",
            source_end_date="2026-08-01", traffic_sources=_sources("EXT_URL"),
        )
        with self.store._connect() as connection:
            connection.execute("UPDATE video_performance_snapshots SET traffic_status = NULL WHERE youtube_video_id = 'oldtraffic1'")
        self.assertNotIn("oldtraffic1", [item["youtube_video_id"] for item in self.store.due_traffic_backfills()])
        self.assertIsNone(self.store.record_traffic_breakdown("oldtraffic1", "24h", status="failed"))

    def test_the_collector_backfills_completed_windows_without_a_breakdown(self):
        self.link("backfill001")
        for window in ("24h", "7d", "28d"):
            self.legacy_window("backfill001", window, views=40)
        youtube = self.youtube()
        with (
            patch.object(YouTubeChannelService, "status", return_value=CONNECTED),
            patch.object(YouTubeChannelService, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=lambda name, *_args, **_kwargs: youtube if name == "youtube" else MagicMock()),
            patch.object(YouTubeChannelService, "_query_rows", return_value=TRAFFIC_ROWS) as query_rows,
        ):
            result = SnapshotCollector(self.settings).run_once()

        self.assertEqual(result["state"], "healthy/idle")
        self.assertEqual((result["counts"]["traffic_backfill"], result["counts"]["traffic_sources"]), (3, 3))
        self.assertEqual(query_rows.call_count, 3)
        for window in ("24h", "7d", "28d"):
            snapshot = self.store.completed_evidence_snapshot("backfill001", window)
            self.assertEqual((snapshot["views"], snapshot["traffic_status"]), (40, "ok"))

    def test_the_collector_backfill_stops_at_an_outage_without_spending_attempts(self):
        self.link("backfill002")
        for window in ("24h", "7d", "28d"):
            self.legacy_window("backfill002", window)
        with (
            patch.object(YouTubeChannelService, "status", return_value=CONNECTED),
            patch.object(YouTubeChannelService, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, return_value=MagicMock()),
            patch.object(YouTubeChannelService, "_query_rows", side_effect=_http_error(503, "backendError")) as query_rows,
        ):
            result = SnapshotCollector(self.settings).run_once()

        self.assertEqual(query_rows.call_count, 1)
        self.assertEqual((result["counts"]["traffic_backfill"], result["counts"]["traffic_failed"]), (1, 1))
        states = [self.store.completed_evidence_snapshot("backfill002", window) for window in ("24h", "7d", "28d")]
        self.assertEqual(sorted(str(state["traffic_status"]) for state in states), ["None", "None", "failed"])
        tried = [state for state in states if state["traffic_status"] == "failed"]
        self.assertEqual([(state["traffic_attempt_count"], state["traffic_last_failure_reason"]) for state in tried],
                         [(0, "youtube_unavailable")])
        self.assertTrue(all(state["views"] == 55 for state in states))

    def test_the_collector_counts_the_windows_a_refresh_backfilled(self):
        published_at = datetime.now(timezone.utc) - timedelta(days=3)
        published = published_at.isoformat()
        self.link("collectback", published_at=published)
        # A completed window of the same link still without a breakdown, its
        # range starting on the link's Pacific publish date.
        first_day = published_at.astimezone(youtube_channel._ANALYTICS_ZONE).date()
        self.legacy_window(
            "collectback", "7d",
            source_start_date=first_day.isoformat(), source_end_date=(first_day + timedelta(days=7)).isoformat(),
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

        self.assertEqual(query_rows.call_count, 2)
        self.assertEqual(result["counts"]["captured"], 1)
        self.assertEqual((result["counts"]["traffic_backfill"], result["counts"]["traffic_sources"]), (1, 2))
        self.assertEqual(self.store.completed_evidence_snapshot("collectback", "7d")["traffic_status"], "ok")

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
        # The window just captured has its breakdown: nothing is asked for again.
        self.assertEqual(result["counts"]["traffic_backfill"], 0)
        self.assertEqual(self.store.completed_evidence_snapshot("collecttraf", "24h")["traffic_sources"]["dominant_source"], "YT_SEARCH")

    def test_the_collector_reports_a_bug_in_a_breakdown_request(self):
        published = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        self.link("collectbug1", published_at=published)
        youtube = self.youtube()
        collector = SnapshotCollector(self.settings)
        with (
            patch.object(YouTubeChannelService, "status", return_value=CONNECTED),
            patch.object(YouTubeChannelService, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=lambda name, *_args, **_kwargs: youtube if name == "youtube" else MagicMock()),
            patch.object(YouTubeChannelService, "_query", return_value={"views": 12}),
            patch.object(YouTubeChannelService, "_query_rows", side_effect=KeyError("columnHeaders")),
            self.assertLogs("win_engine.integrations.youtube_channel", level="ERROR"),
        ):
            result = collector.run_once()
        # The window is evidence as captured; the bug is reported, not passed over.
        self.assertEqual((result["state"], result["counts"]["captured"], result["counts"]["traffic_failed"]), ("healthy/idle", 1, 1))
        self.assertEqual(collector.status()["last_error"], "traffic_sources_unexpected_error")
        snapshot = self.store.completed_evidence_snapshot("collectbug1", "24h")
        self.assertEqual((snapshot["views"], snapshot["traffic_status"]), (12, "failed"))

    def test_an_undated_window_is_named_in_the_log_once_not_on_every_pass(self):
        self.link("undatedvid1")
        self.store.record_performance_snapshot("undatedvid1", 24, views=7, snapshot_window="24h")
        with self.assertLogs("win_engine.feedback.history_store", level="WARNING") as logs:
            self.assertEqual(self.store.due_traffic_backfills(), [])
        self.assertTrue(any("undatedvid1 24h" in line for line in logs.output))
        with self.assertNoLogs("win_engine.feedback.history_store", level="WARNING"):
            self.assertEqual(self.store.due_traffic_backfills(), [])


class _Remote:
    """A cloud database that answers every pull with the given rows (sync_uuid, origin, revision, hash, payload)."""

    def __init__(self, rows):
        self.rows = [(*row, "2026-08-20T10:00:00+00:00", None) for row in rows]

    def cursor(self):
        rows = self.rows

        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, *_args): return None
            def fetchall(self): return rows

        return Cursor()


class CloudSyncTrafficTests(Base):
    def test_a_synced_breakdown_settles_a_window_and_a_synced_window_without_one_is_backfilled(self):
        from win_engine.feedback.cloud_sync import CloudSyncService, _hash

        run_id = self.store.record_analysis_run("obs setup", "search", "tutorial", "Set up OBS", 8.0, "LOW", "WORKABLE", 60,
                                                {"description": "Package"})
        self.store.link_published_video(run_id, "syncedtraf1", "2026-08-01T00:00:00+00:00", format_val="tutorial",
                                        ownership_state="verified", ownership_verified=True, verified_channel_id="UC-owner")
        self.store.record_performance_snapshot(
            "syncedtraf1", 168, views=900, snapshot_window="7d", source_start_date="2026-07-31", source_end_date="2026-08-07",
        )
        self.store.record_traffic_breakdown("syncedtraf1", "7d", status="failed", failure_reason="analytics_request_failed")
        service = CloudSyncService(Settings(
            database_path=self.path, cloud_sync_enabled=True, cloud_sync_device_id="test-device",
            cloud_sync_host="mysql.example", cloud_sync_database="seo_yt_sync", cloud_sync_user="app",
            cloud_sync_password="secret", cloud_sync_ssl_ca_path=__file__,
        ))
        self.assertEqual(service._stage_local_packages(), 1)
        with sqlite3.connect(self.path) as connection:
            sync_uuid, revision, payload_json = connection.execute(
                "SELECT sync_uuid,revision,payload_json FROM cloud_sync_outbox").fetchone()
            connection.execute("DELETE FROM cloud_sync_outbox")
        remote = json.loads(payload_json)
        window = next(item for item in remote["linked_video"]["snapshots"] if item["snapshot_window"] == "7d")
        window["traffic_sources"] = {"sources": [{"source": "YT_SEARCH", "views": 700}, {"source": "SHORTS", "views": 200}]}
        # Windows completed only on the other device: one with its breakdown, one without.
        remote["linked_video"]["snapshots"] += [dict(window, snapshot_window="24h"),
                                                dict(window, snapshot_window="28d", traffic_sources=None)]
        self.assertEqual(service._pull(_Remote([(sync_uuid, "laptop-b", revision + 1, _hash(remote), json.dumps(remote))])), 1)

        settled = self.store.completed_evidence_snapshot("syncedtraf1", "7d")
        # The local metrics stay; the synced breakdown settles the failed request.
        self.assertEqual((settled["views"], settled["traffic_status"], settled["traffic_last_failure_reason"]), (900, "ok", None))
        self.assertEqual(settled["traffic_sources"]["dominant_source"], "YT_SEARCH")
        self.assertEqual(self.store.completed_evidence_snapshot("syncedtraf1", "24h")["traffic_status"], "ok")
        self.assertIsNone(self.store.completed_evidence_snapshot("syncedtraf1", "28d")["traffic_status"])
        self.assertEqual([(item["youtube_video_id"], item["snapshot_window"]) for item in self.store.due_traffic_backfills()],
                         [("syncedtraf1", "28d")])


class CohortTests(Base):
    def setUp(self):
        super().setUp()
        # Learning reads only the connected channel's linked videos.
        with self.store._connect() as connection:
            connection.execute(
                "INSERT INTO youtube_channel_connection (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at) "
                "VALUES (1, 'token', ?, 'Owner', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z')",
                ('UC-owner',),
            )

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
