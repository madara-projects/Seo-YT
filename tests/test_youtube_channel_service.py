"""Channel connection, sync and public lookups report gaps honestly and keep secrets out of logs."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import httplib2
from cryptography.fernet import Fernet
from googleapiclient.errors import HttpError

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore
from win_engine.integrations import youtube_channel
from win_engine.integrations.youtube_channel import (
    ChannelConnectError,
    LinkUnavailable,
    YouTubeChannelService,
    YouTubeUnavailable,
    _unavailable,
)

SCOPES = youtube_channel._SCOPES
BUILD = "win_engine.integrations.youtube_channel.build"


def _http_error(status: int, message: str, uri: str = "https://youtube.googleapis.com/youtube/v3/videos") -> HttpError:
    body = json.dumps({"error": {"code": status, "message": message, "errors": [{"reason": message}]}}).encode()
    return HttpError(httplib2.Response({"status": status}), body, uri=uri)


class ChannelServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        self.settings = Settings(
            database_path=self.db_path,
            youtube_api_key="",
            youtube_api_keys="",
            youtube_oauth_client_id="client-id",
            youtube_oauth_client_secret="client-secret",
            oauth_token_encryption_key=Fernet.generate_key().decode(),
        )
        self.service = YouTubeChannelService(self.settings)
        youtube_channel._PENDING_STATES.clear()

    def tearDown(self) -> None:
        youtube_channel._PENDING_STATES.clear()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass

    def save_sync(self, channel_id: str) -> None:
        self.service._save_sync({"channel": {"id": channel_id, "title": "Channel"}, "current_28_days": {}})


class StatusTests(ChannelServiceTestCase):
    def test_a_sync_is_shown_only_for_the_channel_connected_now(self):
        self.service._save_connection("refresh", "UC-now", "Now")
        self.save_sync("UC-now")
        self.save_sync("UC-before")  # newer, but from another channel
        self.assertEqual(self.service.status()["latest_sync"]["data"]["channel"]["id"], "UC-now")

        self.service._save_connection("refresh", "UC-other", "Other")
        self.assertIsNone(self.service.status()["latest_sync"])

    def test_after_a_disconnect_no_sync_is_presented_as_current(self):
        self.service._save_connection("refresh", "UC-now", "Now")
        self.save_sync("UC-now")
        self.service.disconnect()

        status = self.service.status()
        self.assertFalse(status["connected"])
        self.assertIsNone(status["latest_sync"])

    def test_old_syncs_are_pruned(self):
        for _ in range(youtube_channel._SYNCS_KEPT + 5):
            self.save_sync("UC-now")
        with self.service._connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM youtube_channel_syncs").fetchone()[0]
        self.assertEqual(count, youtube_channel._SYNCS_KEPT)


class RefreshTests(ChannelServiceTestCase):
    def _youtube(self, statistics: dict) -> MagicMock:
        youtube = MagicMock()
        youtube.channels.return_value.list.return_value.execute.return_value = {
            "items": [{
                "id": "UC-now",
                "snippet": {"title": "Now"},
                "statistics": statistics,
                "contentDetails": {"relatedPlaylists": {"uploads": "UU-now"}},
            }]
        }
        youtube.playlistItems.return_value.list.return_value.execute.side_effect = TimeoutError("uploads")
        return youtube

    def test_hidden_or_failed_numbers_are_unknown_not_zero(self):
        self.service._save_connection("refresh", "", "")  # token saved before the channel was known
        youtube = self._youtube({"hiddenSubscriberCount": True, "subscriberCount": "0", "viewCount": "10"})
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[youtube, MagicMock()]),
            patch.object(self.service, "_query", side_effect=_http_error(403, "quotaExceeded")),
        ):
            payload = self.service.refresh()

        channel = payload["channel"]
        self.assertIsNone(channel["subscribers"])
        self.assertIsNone(channel["video_count"])
        self.assertEqual(channel["real_total_views"], 10)
        self.assertEqual(payload["partial_failures"], ["uploads", "analytics"])
        self.assertEqual(payload["current_28_days"], {})
        self.assertNotIn("top_videos", payload)
        # The refresh identified the channel, so its sync now shows as current.
        status = self.service.status()
        self.assertEqual(status["channel"]["id"], "UC-now")
        self.assertIsNotNone(status["latest_sync"])

    def test_an_unreachable_youtube_is_an_error_not_an_empty_channel(self):
        self.service._save_connection("refresh", "UC-now", "Now")
        youtube = MagicMock()
        youtube.channels.return_value.list.return_value.execute.side_effect = _http_error(429, "rateLimitExceeded")
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[youtube, MagicMock()]),
        ):
            with self.assertRaises(YouTubeUnavailable) as raised:
                self.service.refresh()
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIsNone(self.service.status()["latest_sync"])


class PublicVideoTests(ChannelServiceTestCase):
    def test_a_video_youtube_does_not_know_is_refused(self):
        self.settings.youtube_api_key = "KEY-ONE"
        youtube = MagicMock()
        youtube.videos.return_value.list.return_value.execute.return_value = {"items": []}
        with patch(BUILD, return_value=youtube):
            with self.assertRaisesRegex(ValueError, "could not be found"):
                self.service.verify_public_video("abcdefghijk")

    def test_a_failing_key_is_logged_without_its_value_and_the_next_one_is_tried(self):
        self.settings.youtube_api_keys = "SECRET-KEY-1,KEY-TWO"
        failing, working = MagicMock(), MagicMock()
        failing.videos.return_value.list.return_value.execute.side_effect = _http_error(
            403, "quotaExceeded", uri="https://youtube.googleapis.com/youtube/v3/videos?key=SECRET-KEY-1"
        )
        working.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"snippet": {"title": "Real title", "publishedAt": "2026-08-01T00:00:00Z"}}]
        }
        with patch(BUILD, side_effect=[failing, working]), self.assertLogs(youtube_channel.logger, "WARNING") as logs:
            metadata = self.service.verify_public_video("abcdefghijk")

        self.assertEqual(metadata["title"], "Real title")
        self.assertNotIn("SECRET-KEY-1", "\n".join(logs.output))
        self.assertIn("key 1", "\n".join(logs.output))

    def test_oembed_not_found_is_refused_rather_than_accepted_unverified(self):
        missing = urllib.error.HTTPError("https://www.youtube.com/oembed", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", side_effect=missing):
            with self.assertRaisesRegex(ValueError, "could not be found"):
                self.service.verify_public_video("abcdefghijk")

    def test_a_private_or_unembeddable_video_stays_linkable_but_unverified(self):
        private = urllib.error.HTTPError("https://www.youtube.com/oembed", 401, "Unauthorized", {}, None)
        with patch("urllib.request.urlopen", side_effect=private):
            metadata = self.service.verify_public_video("abcdefghijk")
        self.assertEqual(metadata["metadata_source"], "unverified_id")
        self.assertIsNone(metadata["title"])

    def test_public_refresh_reports_an_outage_instead_of_a_bad_request(self):
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            with self.assertRaises(YouTubeUnavailable) as raised:
                self.service.refresh_linked_video_public({"id": 1, "youtube_video_id": "abcdefghijk"})
        self.assertEqual(raised.exception.status_code, 503)


class AuthorizationTests(ChannelServiceTestCase):
    def _start(self) -> str:
        url = self.service.authorization_url()
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(query["code_challenge"][0])
        return query["state"][0]

    def _flow(self, scopes: list[str]) -> SimpleNamespace:
        return SimpleNamespace(
            fetch_token=MagicMock(),
            credentials=SimpleNamespace(refresh_token="refresh", granted_scopes=scopes),
            oauth2session=SimpleNamespace(token={}),
        )

    def test_each_attempt_keeps_its_own_state_and_the_table_is_capped(self):
        first = self._start()
        second = self._start()
        self.assertIn(first, youtube_channel._PENDING_STATES)
        self.assertIn(second, youtube_channel._PENDING_STATES)
        for _ in range(youtube_channel._MAX_PENDING_STATES + 5):
            self._start()
        self.assertLessEqual(len(youtube_channel._PENDING_STATES), youtube_channel._MAX_PENDING_STATES)

    def test_the_verifier_from_the_start_is_sent_with_the_code(self):
        state = self._start()
        verifier = youtube_channel._PENDING_STATES[state][1]
        flow = self._flow(SCOPES)
        channel = MagicMock()
        channel.channels.return_value.list.return_value.execute.return_value = {"items": [{"id": "UC-now", "snippet": {"title": "Now"}}]}
        with (
            patch.object(self.service, "_flow", return_value=flow) as make_flow,
            patch(BUILD, return_value=channel),
            patch.object(self.service, "refresh", return_value={"refreshed": True}),
        ):
            self.assertEqual(self.service.complete_authorization(code="code", state=state), {"refreshed": True})

        make_flow.assert_called_once_with(state=state, code_verifier=verifier)
        self.assertEqual(self.service.status()["channel"]["id"], "UC-now")
        # The state is single use.
        with self.assertRaises(ChannelConnectError) as raised:
            self.service.complete_authorization(code="code", state=state)
        self.assertEqual(raised.exception.reason, "expired_state")

    def test_an_unticked_permission_is_named(self):
        state = self._start()
        with patch.object(self.service, "_flow", return_value=self._flow(SCOPES[1:])):
            with self.assertRaises(ChannelConnectError) as raised:
                self.service.complete_authorization(code="code", state=state)
        self.assertEqual(raised.exception.reason, "missing_scopes")
        self.assertFalse(self.service.status()["connected"])

    def test_a_failed_channel_lookup_keeps_the_grant_for_the_next_refresh(self):
        state = self._start()
        channel = MagicMock()
        channel.channels.return_value.list.return_value.execute.side_effect = TimeoutError("lookup")
        with patch.object(self.service, "_flow", return_value=self._flow(SCOPES)), patch(BUILD, return_value=channel):
            result = self.service.complete_authorization(code="code", state=state)

        self.assertTrue(result["sync_pending"])
        status = self.service.status()
        self.assertTrue(status["connected"])
        self.assertEqual(status["channel"]["id"], "")
        # Ownership cannot be checked until the channel is known.
        with self.assertRaisesRegex(ValueError, "Connect the YouTube channel"):
            self.service.verify_owned_video("abcdefghijk")


class _FrozenDatetime(datetime):
    """2026-09-25 20:00 UTC, which is 13:00 in Pacific time."""

    @classmethod
    def now(cls, tz=None):
        moment = datetime(2026, 9, 25, 20, 0, tzinfo=timezone.utc)
        return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)


class LinkedVideoRefreshTests(ChannelServiceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = HistoryStore(self.db_path)
        self.service._save_connection("refresh", "UC-owner", "Owner")

    def link(self, video_id: str, published_at: str, channel: str = "UC-owner") -> dict:
        with self.store._connect() as connection:
            run_id = int(connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES ('q', ?, 't')", (published_at,)
            ).lastrowid)
        link_id = self.store.link_published_video(
            run_id, video_id, published_at, ownership_state="verified", ownership_verified=True,
            verified_channel_id=channel, ownership_verified_at=published_at,
        )
        return self.store.published_video_link(link_id) or {}

    def youtube(self, channel_id: str | None) -> MagicMock:
        youtube = MagicMock()
        items = [{"snippet": {"channelId": channel_id, "publishedAt": "2026-09-23T18:00:00Z"}, "statistics": {}}] if channel_id else []
        youtube.videos.return_value.list.return_value.execute.return_value = {"items": items}
        return youtube

    def test_a_window_waits_until_youtube_has_reported_all_its_days(self):
        # 26 hours old, but its first day after publishing (Pacific) is today: not reported yet.
        link = self.link("windowvid01", "2026-09-24T18:00:00+00:00")
        with patch.object(youtube_channel, "datetime", _FrozenDatetime), patch(BUILD) as build_client:
            result = self.service.refresh_linked_video_performance(link, collect_current=False)
        build_client.assert_not_called()
        self.assertIn("no YouTube API call", result["message"])

    def test_a_reported_window_is_queried_over_pacific_days(self):
        link = self.link("windowvid02", "2026-09-23T18:00:00+00:00")
        with (
            patch.object(youtube_channel, "datetime", _FrozenDatetime),
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[self.youtube("UC-owner"), MagicMock()]),
            patch.object(self.service, "_query", return_value={"views": 12}) as query,
        ):
            self.service.refresh_linked_video_performance(link, collect_current=False)
        start, end = query.call_args.args[1:3]
        self.assertEqual((start.isoformat(), end.isoformat()), ("2026-09-23", "2026-09-24"))

    def test_a_video_gone_from_the_channel_is_no_longer_collected(self):
        link = self.link("windowvid03", "2026-08-01T00:00:00+00:00")
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[self.youtube(None), MagicMock()]),
        ):
            with self.assertRaises(LinkUnavailable):
                self.service.refresh_linked_video_performance(link)
        self.assertEqual(self.store.published_video_link(link["id"])["ownership_state"], "failed")
        self.assertEqual(self.store.due_snapshot_links(), [])

    def test_the_planner_and_the_refresh_agree_on_when_a_window_is_due(self):
        # Old enough for its 24h window, but YouTube has not reported that window's last day yet.
        self.link("windowvid06", "2026-09-24T18:00:00+00:00")
        now = _FrozenDatetime.now(timezone.utc)
        self.assertEqual(self.store.due_snapshot_links(now=now), [])
        # A day earlier, the window is reported and both plan it.
        link = self.link("windowvid07", "2026-09-23T18:00:00+00:00")
        self.assertEqual([item["due_windows"] for item in self.store.due_snapshot_links(now=now)], [["24h"]])
        with (
            patch.object(youtube_channel, "datetime", _FrozenDatetime),
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[self.youtube("UC-owner"), MagicMock()]),
            patch.object(self.service, "_query", return_value={"views": 12}) as query,
        ):
            result = self.service.refresh_linked_video_performance(link, collect_current=False, windows=["24h"])
        self.assertEqual(query.call_count, 1)
        self.assertEqual([item["snapshot_window"] for item in result["captured"]], ["24h"])

    def test_an_analytics_outage_spends_no_attempt_but_a_refused_request_does(self):
        link = self.link("windowvid04", "2026-09-01T00:00:00+00:00")

        def refresh(error: Exception) -> None:
            with (
                patch.object(youtube_channel, "datetime", _FrozenDatetime),
                patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
                patch(BUILD, side_effect=[self.youtube("UC-owner"), MagicMock()]),
                patch.object(self.service, "_query", side_effect=error),
            ):
                self.service.refresh_linked_video_performance(link, collect_current=False)

        for error in (_http_error(503, "backendError"), TimeoutError("read"), _http_error(403, "quotaExceeded")):
            refresh(error)
        states = [self.store.snapshot_window_state("windowvid04", window) for window in ("24h", "7d")]
        self.assertEqual([(state["attempt_count"], state["retry_allowed"]) for state in states], [(0, True), (0, True)])

        refresh(_http_error(400, "badRequest"))
        self.assertEqual(self.store.snapshot_window_state("windowvid04", "24h")["attempt_count"], 1)

    def test_the_current_figure_is_the_current_count_not_a_completed_window(self):
        link = self.link("windowvid05", "2026-09-01T00:00:00+00:00")
        self.store.record_performance_snapshot("windowvid05", 300, views=900, snapshot_window="current")
        self.store.record_performance_snapshot("windowvid05", 24, views=100, snapshot_window="24h")
        self.store.record_performance_snapshot("windowvid05", 168, views=300, snapshot_window="7d")

        with patch.object(youtube_channel, "datetime", _FrozenDatetime), patch(BUILD) as build_client:
            result = self.service.refresh_linked_video_performance(link, collect_current=False)

        build_client.assert_not_called()  # 24h and 7d are complete; 28d is not reported yet
        self.assertEqual((result["current"]["snapshot_window"], result["current"]["views"]), ("current", 900))

    def test_a_video_verified_for_another_channel_is_left_alone(self):
        # Verified on another device, whose connected channel owns it.
        link = self.link("othervideo1", "2026-08-01T00:00:00+00:00", channel="UC-other")
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[self.youtube("UC-other"), MagicMock()]) as build_client,
        ):
            with self.assertRaises(LinkUnavailable):
                self.service.refresh_linked_video_performance(link)

        build_client.assert_not_called()
        stored = self.store.published_video_link(link["id"])
        self.assertEqual((stored["ownership_state"], stored["verified_channel_id"]), ("verified", "UC-other"))
        # The collector plans only the videos of the channel connected here.
        self.assertEqual(self.store.due_snapshot_links(channel_id="UC-owner"), [])
        self.assertEqual(len(self.store.due_snapshot_links(channel_id="UC-other")), 1)


class UpstreamErrorTests(unittest.TestCase):
    def test_quota_and_outages_map_to_meaningful_statuses(self):
        self.assertEqual(_unavailable(_http_error(403, "quotaExceeded")).status_code, 429)
        self.assertEqual(_unavailable(_http_error(403, "dailyLimitExceeded")).status_code, 429)
        self.assertEqual(_unavailable(_http_error(500, "backendError")).status_code, 502)
        self.assertEqual(_unavailable(TimeoutError()).status_code, 503)
        disabled = _unavailable(_http_error(403, "YouTube Analytics API has not been used in project 1 before"))
        self.assertIn("not enabled", str(disabled))

    def test_messages_never_carry_the_request_url(self):
        error = _http_error(500, "backendError", uri="https://youtube.googleapis.com/v3/videos?key=SECRET")
        self.assertNotIn("SECRET", str(_unavailable(error)))


if __name__ == "__main__":
    unittest.main()
