"""Quick refreshes cannot use up a linked video's named windows, and the creator can
retry the windows whose attempts are spent without touching completed ones."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httplib2
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError

from win_engine.api import routes
from win_engine.api.app import create_app
from win_engine.core.config import Settings
from win_engine.core.schemas import RefreshPublishedVideoRequest
from win_engine.feedback.history_store import HistoryStore
from win_engine.integrations import youtube_channel
from win_engine.integrations.youtube_channel import YouTubeChannelService

PUBLISHED = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
# Every named window of PUBLISHED is fully reported by then.
NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
# The Pacific days each window of PUBLISHED covers, as the refresh queries them.
RANGES = {"24h": ("2026-08-01", "2026-08-02"), "7d": ("2026-08-01", "2026-08-08"), "28d": ("2026-08-01", "2026-08-29")}
WINDOWS = ("24h", "7d", "28d")


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _clock(instant: datetime):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant if tz is None else instant.astimezone(tz)

    return Frozen


class _Request:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error

    def execute(self):
        if self.error:
            raise self.error
        return self.payload


class _YouTube:
    def videos(self):
        return self

    def list(self, **_kwargs):
        return _Request({"items": [{
            "snippet": {"channelId": "UC-owner", "title": "A title", "publishedAt": _iso(PUBLISHED)},
            "statistics": {"viewCount": "500"},
            "status": {"privacyStatus": "public"},
        }]})


class _Analytics:
    """Window reports answer `views` (None: no rows), or raise `error`."""

    def __init__(self):
        self.views: int | None = None
        self.error: Exception | None = None
        self.window_queries: list[tuple[str, str]] = []

    def reports(self):
        return self

    def query(self, **kwargs):
        if kwargs.get("dimensions"):
            return _Request({"columnHeaders": [], "rows": []})
        self.window_queries.append((kwargs["startDate"], kwargs["endDate"]))
        if self.error:
            return _Request(error=self.error)
        metrics = kwargs["metrics"].split(",")
        rows = [] if self.views is None else [[self.views if name == "views" else 0 for name in metrics]]
        return _Request({"columnHeaders": [{"name": name} for name in metrics], "rows": rows})

    def windows_queried(self) -> set[str]:
        return {label for label, span in RANGES.items() if span in self.window_queries}


class LinkedVideoRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        self.addCleanup(self._remove_database)
        self.settings = Settings(
            database_path=self.db_path, youtube_api_key="", youtube_api_keys="",
            youtube_oauth_client_id="client-id", youtube_oauth_client_secret="client-secret",
            oauth_token_encryption_key=Fernet.generate_key().decode(),
        )
        self.service = YouTubeChannelService(self.settings)
        self.service._save_connection("refresh", "UC-owner", "Owner")
        self.store = HistoryStore(self.db_path)
        self.analytics = _Analytics()
        self.run_id = self.store.record_analysis_run("query", "browse", "emotion", "Title", 7.0, "LOW", "WORKABLE", 50, {})
        self.link_id = self.store.link_published_video(
            self.run_id, "retryvideo1", _iso(PUBLISHED), ownership_state="verified", ownership_verified=True,
            verified_channel_id="UC-owner", ownership_verified_at=_iso(PUBLISHED),
        )

    def _remove_database(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except FileNotFoundError:
                pass

    def _youtube(self):
        return (
            patch.object(youtube_channel, "datetime", _clock(NOW)),
            patch.object(YouTubeChannelService, "_fresh_credentials", return_value=MagicMock()),
            patch.object(youtube_channel, "build",
                         side_effect=lambda name, *_a, **_k: _YouTube() if name == "youtube" else self.analytics),
        )

    def _refresh(self, *, force: bool = False) -> dict:
        clock, credentials, build = self._youtube()
        with clock, credentials, build:
            return self.service.refresh_linked_video_performance(
                self.store.published_video_link(self.link_id), force=force, collect_current=False,
            )

    def _state(self, window: str) -> dict:
        return self.store.snapshot_window_state("retryvideo1", window)

    def _exhaust(self, window: str) -> None:
        # Attempts spent a cooldown apart, as the collector spends them.
        for _ in range(5):
            self.store.record_snapshot_attempt(
                "retryvideo1", window, status="empty_retryable", failure_reason="analytics_returned_no_rows",
                source_start_date=RANGES[window][0], source_end_date=RANGES[window][1],
            )
        self.assertTrue(self._state(window)["retry_exhausted"])

    def _age_last_attempt(self, seconds: int) -> None:
        moment = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE video_performance_snapshots SET last_attempted_at = ? WHERE youtube_video_id = ?",
                (moment, "retryvideo1"),
            )

    def test_quick_refreshes_cannot_use_up_the_windows(self):
        for _ in range(6):
            self._refresh()

        # Each click still asked YouTube, but only the first try counted.
        self.assertEqual(len(self.analytics.window_queries), 18)
        for window in WINDOWS:
            state = self._state(window)
            self.assertEqual(state["attempt_count"], 1, window)
            self.assertTrue(state["retry_allowed"], window)
            self.assertFalse(state["retry_exhausted"], window)
            self.assertEqual(state["status"], "empty_retryable", window)

    def test_a_try_after_the_cooldown_counts(self):
        self._refresh()
        self._age_last_attempt(self.settings.snapshot_collector_retry_base_seconds + 60)

        self._refresh()

        self.assertEqual({self._state(window)["attempt_count"] for window in WINDOWS}, {2})

    def test_a_ceiling_below_the_base_delay_shortens_the_interval(self):
        # The collector's shortest cooldown is the lower of the two settings,
        # so a try that late must count even though the base delay is longer.
        self.service.settings = self.settings.model_copy(update={"snapshot_collector_retry_max_seconds": 600})
        self._refresh()
        self._age_last_attempt(700)

        self._refresh()

        self.assertEqual({self._state(window)["attempt_count"] for window in WINDOWS}, {2})

    def test_an_outage_still_spends_no_attempt(self):
        self.analytics.error = HttpError(httplib2.Response({"status": 503}), b"{}", uri="https://youtube")

        self._refresh()

        for window in WINDOWS:
            state = self._state(window)
            self.assertEqual(state["attempt_count"], 0, window)
            self.assertTrue(state["retry_allowed"], window)

    def test_the_first_empty_try_after_an_outage_counts(self):
        # The outage's postponement sets last_attempted_at but spends nothing;
        # the empty try right after it is the window's first attempt and counts.
        self.analytics.error = HttpError(httplib2.Response({"status": 503}), b"{}", uri="https://youtube")
        self._refresh()
        self.analytics.error = None

        self._refresh()

        for window in WINDOWS:
            state = self._state(window)
            self.assertEqual(state["attempt_count"], 1, window)
            self.assertEqual(state["status"], "empty_retryable", window)

    def test_quick_refreshes_that_fail_cannot_use_up_the_windows(self):
        # A failure of the request itself (not an outage) spends attempts too,
        # so a burst of clicks must count it once, like an empty report.
        self.analytics.error = HttpError(httplib2.Response({"status": 400}), b"{}", uri="https://youtube")

        for _ in range(6):
            self._refresh()

        for window in WINDOWS:
            state = self._state(window)
            self.assertEqual(state["attempt_count"], 1, window)
            self.assertEqual(state["status"], "failed_retryable", window)
            self.assertFalse(state["retry_exhausted"], window)

    def test_an_exhausted_window_is_skipped_until_the_retry_flag(self):
        self._exhaust("24h")
        self.analytics.views = 700

        self._refresh()

        self.assertNotIn("24h", self.analytics.windows_queried())
        self.assertTrue(self._state("24h")["retry_exhausted"])
        self.assertIsNone(self.store.completed_evidence_snapshot("retryvideo1", "24h"))

        self._refresh(force=True)

        day_one = self.store.completed_evidence_snapshot("retryvideo1", "24h")
        self.assertIsNotNone(day_one)
        self.assertEqual(day_one["views"], 700)
        self.assertFalse(self._state("24h")["retry_exhausted"])

    def test_a_retry_that_finds_nothing_stays_exhausted_and_is_tried_once(self):
        self._exhaust("24h")

        self._refresh(force=True)

        self.assertEqual([span for span in self.analytics.window_queries if span == RANGES["24h"]], [RANGES["24h"]])
        state = self._state("24h")
        self.assertEqual(state["attempt_count"], 5)
        self.assertTrue(state["retry_exhausted"])

    def test_a_later_retry_that_finds_nothing_stops_at_the_maximum(self):
        # Outside the interval the retry is a counted attempt, and the count
        # still stops at the maximum rather than going past it.
        self._exhaust("24h")
        self._age_last_attempt(self.settings.snapshot_collector_retry_base_seconds + 60)

        self._refresh(force=True)

        self.assertEqual([span for span in self.analytics.window_queries if span == RANGES["24h"]], [RANGES["24h"]])
        state = self._state("24h")
        self.assertEqual(state["attempt_count"], 5)
        self.assertTrue(state["retry_exhausted"])
        self.assertFalse(state["retry_allowed"])

    def test_the_retry_flag_leaves_completed_windows_untouched(self):
        self.analytics.views = 900
        self._refresh()
        before = {window: self.store.completed_evidence_snapshot("retryvideo1", window) for window in WINDOWS}
        self.analytics.window_queries.clear()
        self.analytics.views = 5

        result = self._refresh(force=True)

        self.assertEqual(self.analytics.window_queries, [])
        self.assertEqual(result["captured"], [])
        for window in WINDOWS:
            after = self.store.completed_evidence_snapshot("retryvideo1", window)
            self.assertEqual(after["captured_at"], before[window]["captured_at"])
            self.assertEqual(after["views"], 900)
            self.assertEqual(after["completed_at"], before[window]["completed_at"])

    def test_snapshot_rows_say_when_a_window_is_exhausted(self):
        self._exhaust("24h")
        self.store.record_snapshot_attempt(
            "retryvideo1", "7d", status="empty_retryable", failure_reason="analytics_returned_no_rows",
        )

        rows = {row["snapshot_window"]: row for row in self.store.performance_snapshots("retryvideo1")}

        self.assertTrue(rows["24h"]["retry_exhausted"])
        self.assertFalse(rows["24h"]["retry_allowed"])
        self.assertFalse(rows["7d"]["retry_exhausted"])
        self.assertTrue(rows["7d"]["retry_allowed"])
        self.assertFalse(self._state("28d")["retry_exhausted"])

    def test_attempts_spent_for_another_time_are_returned_when_a_sync_moves_it(self):
        self._exhaust("24h")
        later = PUBLISHED + timedelta(days=3)
        # A sync or a relink sets the time directly, so the metadata write sees no move.
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE published_video_links SET published_at = ? WHERE id = ?", (_iso(later), self.link_id)
            )

        self.store.update_linked_video_metadata(self.link_id, {
            "title": "A title", "description": "", "tags": [], "channel_id": "UC-owner",
            "published_at": _iso(later), "privacy_status": "public",
            "ownership_verified": True, "metadata_source": "youtube_data_api",
        })

        state = self._state("24h")
        self.assertEqual(state["attempt_count"], 0)
        self.assertTrue(state["retry_allowed"])

    def test_attempts_on_the_current_time_stay_after_a_metadata_write(self):
        self._exhaust("24h")

        self.store.update_linked_video_metadata(self.link_id, {
            "title": "A new title", "description": "", "tags": [], "channel_id": "UC-owner",
            "published_at": _iso(PUBLISHED), "privacy_status": "public",
            "ownership_verified": True, "metadata_source": "youtube_data_api",
        })

        self.assertTrue(self._state("24h")["retry_exhausted"])


class RefreshRouteBodyTests(unittest.TestCase):
    """The refresh routes keep working without a body; the flag reaches the service."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.settings = Settings(database_path=os.path.join(directory.name, "routes.db"))
        store = HistoryStore(self.settings.database_path)
        run_id = store.record_analysis_run("query", "browse", "emotion", "Title", 7.0, "LOW", "WORKABLE", 50, {})
        self.link_id = store.link_published_video(run_id, "routevideo1", _iso(PUBLISHED))
        self.refresh = MagicMock(return_value={"captured": []})
        for item in (
            patch.object(routes, "get_settings", return_value=self.settings),
            patch.object(routes.YouTubeChannelService, "status", return_value={"connected": True}),
            patch.object(routes.YouTubeChannelService, "refresh_linked_video_performance", self.refresh),
        ):
            item.start()
            self.addCleanup(item.stop)
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def test_a_refresh_without_a_body_does_not_retry_exhausted_windows(self):
        response = self.client.post(f"/api/published-videos/{self.link_id}/refresh")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIs(self.refresh.call_args.kwargs["force"], False)

    def test_an_empty_body_does_not_retry_exhausted_windows(self):
        response = self.client.post(f"/api/published-videos/{self.link_id}/refresh", json={})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIs(self.refresh.call_args.kwargs["force"], False)

    def test_the_retry_flag_reaches_the_service(self):
        response = self.client.post(
            f"/api/published-videos/{self.link_id}/refresh", json={"retry_failed_windows": True}
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIs(self.refresh.call_args.kwargs["force"], True)

    def test_the_audit_refresh_takes_the_same_body(self):
        audit = MagicMock(return_value={"id": 1})
        with (
            patch.object(routes.AuditExperimentStore, "refresh_audit", audit),
            patch.object(routes.AuditExperimentStore, "audit_versions", return_value=[]),
        ):
            plain = self.client.post(f"/api/audits/{self.link_id}/refresh")
            self.assertEqual(plain.status_code, 201, plain.text)
            self.assertIs(self.refresh.call_args.kwargs["force"], False)
            retried = self.client.post(f"/api/audits/{self.link_id}/refresh", json={"retry_failed_windows": True})
            self.assertEqual(retried.status_code, 201, retried.text)
            self.assertIs(self.refresh.call_args.kwargs["force"], True)

    def test_the_route_function_accepts_no_payload(self):
        with patch.object(routes.HistoryStore, "linked_package_report", return_value={}):
            routes.refresh_published_video(self.link_id)
            self.assertIs(self.refresh.call_args.kwargs["force"], False)
            routes.refresh_published_video(self.link_id, RefreshPublishedVideoRequest(retry_failed_windows=True))
            self.assertIs(self.refresh.call_args.kwargs["force"], True)


if __name__ == "__main__":
    unittest.main()
