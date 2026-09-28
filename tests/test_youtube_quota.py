"""YouTube quota ledger: what is counted, in which bucket, on which Pacific day, and how it is reported."""

import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import httplib2
import requests
from fastapi.testclient import TestClient
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from pydantic import ValidationError

from win_engine.api import routes
from win_engine.api.app import create_app
from win_engine.core.config import Settings
from win_engine.feedback import quota_ledger
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.quota_ledger import (
    QuotaLedger,
    charge,
    next_reset,
    quota_date,
    quota_status,
    quota_warnings,
    recording_request_builder,
)
from win_engine.ingestion import cache as cache_module
from win_engine.ingestion import research_service, youtube_client
from win_engine.ingestion.research_service import ResearchService
from win_engine.ingestion.youtube_client import YouTubeClient
from win_engine.integrations import youtube_channel
from win_engine.integrations.youtube_channel import YouTubeChannelService

LATE_EVENING = datetime(2026, 9, 25, 6, 59, tzinfo=timezone.utc)  # 23:59 on the 24th in California
MIDNIGHT = datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc)  # 00:00 on the 25th in California
QUOTA_EXCEEDED = {"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}}


def _response(status, payload):
    response = MagicMock(status_code=status)
    response.json.return_value = payload
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


class _Http:
    """httplib2.Http stand-in: answers by URL fragment; a fragment's last answer repeats."""

    def __init__(self, answers):
        self.answers = {fragment: list(queue) for fragment, queue in answers.items()}
        self.uris = []

    def request(self, uri, method="GET", body=None, headers=None, **_kwargs):
        self.uris.append(uri)
        queue = next(queue for fragment, queue in self.answers.items() if fragment in uri)
        status, payload = queue.pop(0) if len(queue) > 1 else queue[0]
        return httplib2.Response({"status": str(status)}), json.dumps(payload).encode()

    def count(self, fragment):
        return sum(fragment in uri for uri in self.uris)


class _DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)
        self.path = str(self.dir / "quota.db")
        HistoryStore(self.path)  # a new database already has youtube_quota_usage
        self.ledger = QuotaLedger(self.path)

    def rows(self):
        self.assertTrue(quota_ledger.flush())  # counts are written in the background
        with closing(sqlite3.connect(self.path)) as connection:
            return connection.execute(
                "SELECT quota_date, source, bucket, calls, units FROM youtube_quota_usage "
                "ORDER BY quota_date, source, bucket"
            ).fetchall()


class BucketTests(unittest.TestCase):
    def test_search_list_draws_on_its_own_bucket_of_calls(self):
        self.assertEqual(charge("youtube.search.list"), ("search", 0))
        self.assertEqual(charge("search.list"), ("search", 0))

    def test_every_other_data_api_read_costs_one_unit_of_the_shared_bucket(self):
        for method in ("youtube.videos.list", "channels.list", "playlistItems.list", "i18nRegions.list"):
            with self.subTest(method=method):
                self.assertEqual(charge(method), ("default", 1))

    def test_analytics_requests_are_counted_apart_from_the_data_api(self):
        self.assertEqual(charge("youtubeAnalytics.reports.query"), ("analytics", 0))


class RecordingTests(_DatabaseTestCase):
    def test_each_request_adds_a_call_and_its_units_to_its_bucket(self):
        for method in ("search.list", "search.list", "videos.list", "channels.list"):
            self.ledger.record("key1", method, now=MIDNIGHT)
        self.ledger.record("oauth", "youtubeAnalytics.reports.query", now=MIDNIGHT)

        self.assertEqual(self.rows(), [
            ("2026-09-25", "key1", "default", 2, 2),
            ("2026-09-25", "key1", "search", 2, 0),
            ("2026-09-25", "oauth", "analytics", 1, 0),
        ])

    def test_the_quota_day_turns_at_midnight_pacific_time(self):
        self.ledger.record("key1", "search.list", now=LATE_EVENING)
        self.ledger.record("key1", "search.list", now=MIDNIGHT)

        self.assertEqual([row[0] for row in self.rows()], ["2026-09-24", "2026-09-25"])
        self.assertEqual(quota_date(LATE_EVENING), date(2026, 9, 24))
        self.assertEqual(next_reset(LATE_EVENING), MIDNIGHT)
        # Pacific standard time in winter: midnight is 08:00 UTC.
        self.assertEqual(next_reset(datetime(2026, 12, 1, 12, tzinfo=timezone.utc)),
                         datetime(2026, 12, 2, 8, tzinfo=timezone.utc))

    def test_a_database_error_is_logged_and_never_raised(self):
        missing = self.dir / "missing.db"
        with self.assertLogs(quota_ledger.logger, "WARNING"):
            QuotaLedger(str(missing)).record("key1", "search.list")
            quota_ledger.flush()
        self.assertFalse(missing.exists())  # counting never creates a database

        bare = self.dir / "bare.db"
        sqlite3.connect(bare).close()  # a database without the table
        with self.assertLogs(quota_ledger.logger, "WARNING"):
            QuotaLedger(str(bare)).record("key1", "search.list")
            quota_ledger.flush()

        # The writer carries on: the next count reaches a healthy database.
        self.ledger.record("key1", "search.list", now=MIDNIGHT)
        self.assertEqual(self.rows(), [("2026-09-25", "key1", "search", 1, 0)])

    def test_a_busy_database_gets_the_counts_later(self):
        real, attempts = quota_ledger._connect, []

        def busy_once(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise sqlite3.OperationalError("database is locked")
            return real(*args, **kwargs)

        with patch.object(quota_ledger, "_connect", side_effect=busy_once), \
                patch.object(quota_ledger, "_RETRY_DELAY_SECONDS", 0.01):
            self.ledger.record("key1", "search.list", now=MIDNIGHT)
            self.assertTrue(quota_ledger.flush())
        self.assertEqual(self.rows(), [("2026-09-25", "key1", "search", 1, 0)])

    def test_a_database_that_stays_busy_is_given_up_on_with_a_warning(self):
        with patch.object(quota_ledger, "_connect", side_effect=sqlite3.OperationalError("database is locked")), \
                patch.object(quota_ledger, "_RETRY_DELAY_SECONDS", 0.01), \
                self.assertLogs(quota_ledger.logger, "WARNING") as logged:
            self.ledger.record("key1", "search.list")
            self.assertTrue(quota_ledger.flush())
        self.assertIn("stayed busy", " ".join(logged.output))
        self.assertEqual(self.rows(), [])

    def test_recording_returns_without_waiting_for_the_database(self):
        with patch.object(quota_ledger, "_write", side_effect=lambda counts: threading.Event().wait(0.5)):
            started = datetime.now(timezone.utc)
            for _ in range(20):
                self.ledger.record("key1", "search.list")
            elapsed = datetime.now(timezone.utc) - started
            quota_ledger.flush()
        self.assertLess(elapsed, timedelta(milliseconds=200))

    def test_concurrent_requests_are_all_counted(self):
        def spend():
            for _ in range(25):
                self.ledger.record("key1", "search.list")

        threads = [threading.Thread(target=spend) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual([row[1:] for row in self.rows()], [("key1", "search", 200, 0)])


class YouTubeClientRecordingTests(_DatabaseTestCase):
    SEARCH_OK = {"items": [{"id": {"videoId": "vid1"}, "snippet": {"channelId": "UC1", "title": "A"}}]}
    VIDEOS_OK = {"items": [{"id": "vid1", "statistics": {"viewCount": "10"}, "contentDetails": {"duration": "PT1M"}}]}
    CHANNELS_OK = {"items": [{"id": "UC1", "statistics": {"subscriberCount": "5"}}]}

    def setUp(self):
        super().setUp()
        patcher = patch.dict(youtube_client._ROTATIONS, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.today = quota_date().isoformat()

    def _get(self, *answers):
        patcher = patch("win_engine.ingestion.youtube_client.requests.get", side_effect=list(answers))
        self.addCleanup(patcher.stop)
        return patcher.start()

    def client(self, *keys):
        return YouTubeClient(list(keys) or ["secret-key"], timeout_seconds=5, database_path=self.path)

    def test_a_search_counts_one_search_and_its_lookups_one_unit_each(self):
        self._get(_response(200, self.SEARCH_OK), _response(200, self.VIDEOS_OK), _response(200, self.CHANNELS_OK))

        self.client().search_videos("q")

        self.assertEqual(self.rows(), [(self.today, "key1", "default", 2, 2), (self.today, "key1", "search", 1, 0)])

    def test_statistics_looked_up_again_spend_no_search(self):
        self._get(_response(200, self.VIDEOS_OK), _response(200, self.CHANNELS_OK))

        self.client().attach_statistics([{"video_id": "vid1", "channel_id": "UC1"}])

        self.assertEqual(self.rows(), [(self.today, "key1", "default", 2, 2)])

    def test_a_refused_request_counts_against_the_key_that_sent_it_named_by_its_slot(self):
        self._get(_response(403, QUOTA_EXCEEDED), _response(200, {"items": []}))

        self.client("secret-a", "secret-b")._request_json(YouTubeClient._SEARCH_URL, {})

        rows = self.rows()
        self.assertEqual(rows, [(self.today, "key1", "search", 1, 0), (self.today, "key2", "search", 1, 0)])
        self.assertNotIn("secret", repr(rows))

    def test_a_burst_retry_is_another_request(self):
        limited = _response(403, {"error": {"errors": [{"reason": "rateLimitExceeded"}]}})
        self._get(limited, _response(200, {"items": []}))
        with patch("win_engine.ingestion.youtube_client.time.sleep"):
            self.client()._request_json(YouTubeClient._SEARCH_URL, {})

        self.assertEqual(self.rows(), [(self.today, "key1", "search", 2, 0)])

    def test_only_requests_that_reached_youtube_are_counted(self):
        self._get(requests.ConnectionError("offline"))
        self.client()._request_json(YouTubeClient._SEARCH_URL, {})
        self.assertEqual(self.rows(), [])

        # A read timeout means the request was sent; YouTube may well have counted it.
        self._get(requests.ReadTimeout("slow"))
        self.client()._request_json(YouTubeClient._SEARCH_URL, {})
        self.assertEqual(self.rows(), [(self.today, "key1", "search", 1, 0)])

    def test_the_configured_database_is_used_by_default(self):
        self._get(_response(200, {"items": []}))
        with patch.object(youtube_client, "get_settings", return_value=Settings(database_path=self.path)):
            YouTubeClient(["secret-key"], timeout_seconds=5).ping()

        self.assertEqual(self.rows(), [(self.today, "key1", "default", 1, 1)])


class GoogleApiClientRecordingTests(_DatabaseTestCase):
    CHANNEL = {"items": [{"id": "UC1", "snippet": {"title": "Mine"}, "statistics": {},
                          "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
    UPLOADS = {"items": [{"snippet": {"resourceId": {"videoId": "vid1"}}, "contentDetails": {"videoId": "vid1"}}]}
    VIDEO = {"items": [{"id": "vid1", "snippet": {"channelId": "UC1", "title": "V"}, "statistics": {}}]}
    NO_ROWS = {"columnHeaders": [], "rows": []}

    def setUp(self):
        super().setUp()
        self.today = quota_date().isoformat()

    def _fake_build(self, http):
        def build(name, version, **kwargs):
            # The real client, offline: bundled discovery documents and a stand-in transport.
            return discovery.build(name, version, http=http, requestBuilder=kwargs["requestBuilder"],
                                   cache_discovery=False)
        return build

    def test_requests_built_with_the_recorder_are_counted_even_when_refused(self):
        http = _Http({"/search": [(200, {"items": []})], "/videos": [(403, QUOTA_EXCEEDED)],
                      "/reports": [(200, self.NO_ROWS)]})
        youtube = discovery.build("youtube", "v3", http=http, cache_discovery=False,
                                  requestBuilder=recording_request_builder(self.path, "oauth"))
        analytics = discovery.build("youtubeAnalytics", "v2", http=http, cache_discovery=False,
                                    requestBuilder=recording_request_builder(self.path, "oauth"))

        youtube.search().list(part="snippet", q="x").execute()
        with self.assertRaises(HttpError):
            youtube.videos().list(part="snippet", id="vid1").execute()
        analytics.reports().query(ids="channel==MINE", startDate="2026-09-01", endDate="2026-09-02",
                                  metrics="views").execute()

        self.assertEqual(self.rows(), [
            (self.today, "oauth", "analytics", 1, 0),
            (self.today, "oauth", "default", 1, 1),
            (self.today, "oauth", "search", 1, 0),
        ])

    def test_a_request_left_unanswered_is_counted_and_one_never_sent_is_not(self):
        # As youtube_client counts a read timeout but not a refused connection.
        class Failing:
            def __init__(self, error):
                self.error = error

            def request(self, *_args, **_kwargs):
                raise self.error

        for error in (ConnectionRefusedError("refused"), TimeoutError("timed out")):
            youtube = discovery.build("youtube", "v3", http=Failing(error), cache_discovery=False,
                                      requestBuilder=recording_request_builder(self.path, "oauth"))
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                youtube.videos().list(part="snippet", id="vid1").execute()

        self.assertEqual(self.rows(), [(self.today, "oauth", "default", 1, 1)])

    def test_a_channel_refresh_counts_every_data_and_analytics_request_as_oauth(self):
        http = _Http({"/youtube/v3/channels": [(200, self.CHANNEL)], "/playlistItems": [(200, self.UPLOADS)],
                      "/youtube/v3/videos": [(200, self.VIDEO)], "youtubeanalytics": [(200, self.NO_ROWS)]})
        service = YouTubeChannelService(Settings(database_path=self.path))
        with patch.object(service, "_fresh_credentials", return_value=MagicMock()), \
                patch.object(youtube_channel, "build", side_effect=self._fake_build(http)):
            service.refresh()

        data_requests, analytics_requests = http.count("/youtube/v3/"), http.count("youtubeanalytics")
        self.assertEqual(data_requests, 3)
        self.assertGreaterEqual(analytics_requests, 2)
        self.assertEqual(self.rows(), [
            (self.today, "oauth", "analytics", analytics_requests, 0),
            (self.today, "oauth", "default", data_requests, data_requests),
        ])

    def test_a_public_lookup_counts_against_each_key_slot_it_tried(self):
        http = _Http({"/youtube/v3/videos": [(403, QUOTA_EXCEEDED), (200, self.VIDEO)]})
        service = YouTubeChannelService(Settings(database_path=self.path, youtube_api_keys="secret-a,secret-b"))
        with patch.object(youtube_channel, "build", side_effect=self._fake_build(http)):
            service.verify_public_video("vid1")

        rows = self.rows()
        self.assertEqual(rows, [(self.today, "key1", "default", 1, 1), (self.today, "key2", "default", 1, 1)])
        self.assertNotIn("secret", repr(rows))


class QuotaStatusTests(_DatabaseTestCase):
    def settings(self, **overrides):
        return Settings(database_path=self.path, youtube_api_keys="secret-a,secret-b", **overrides)

    def test_used_and_remaining_per_source_against_the_configured_limits(self):
        self.ledger.record("key1", "search.list", now=LATE_EVENING)  # yesterday's quota day
        for method in ("search.list", "search.list", "search.list", "videos.list", "channels.list"):
            self.ledger.record("key1", method, now=MIDNIGHT)
        self.ledger.record("oauth", "youtubeAnalytics.reports.query", now=MIDNIGHT)

        status = quota_status(self.settings(), oauth_connected=True, now=MIDNIGHT + timedelta(hours=1))

        self.assertTrue(status["available"])
        self.assertEqual((status["quota_date"], status["resets_at"]), ("2026-09-25", "2026-09-26T07:00:00+00:00"))
        self.assertEqual(status["limits"], {"search_calls_per_day": 100, "units_per_day": 10000})
        self.assertEqual([item["source"] for item in status["sources"]], ["key1", "key2", "oauth"])
        key1, key2, oauth = status["sources"]
        self.assertEqual(key1["label"], "API key 1")
        self.assertEqual(key1["search"], {"used": 3, "limit": 100, "remaining": 97})
        self.assertEqual(key1["default"], {"calls": 2, "used": 2, "limit": 10000, "remaining": 9998})
        self.assertEqual(key1["analytics"], {"calls": 0})
        self.assertEqual(key2["search"]["used"], 0)  # counted, so a real zero
        self.assertEqual(oauth["analytics"], {"calls": 1})
        self.assertEqual(status["warnings"], [])
        self.assertNotIn("secret", json.dumps(status))

    def test_usage_that_cannot_be_read_is_unavailable_not_zero(self):
        with self.assertLogs(quota_ledger.logger, "WARNING"):
            status = quota_status(Settings(database_path=str(self.dir / "missing.db"), youtube_api_key="secret"))

        self.assertFalse(status["available"])
        self.assertEqual(status["sources"], [])
        self.assertIsNotNone(status["resets_at"])

    def test_limits_are_settings_copied_from_cloud_console(self):
        self.assertEqual((Settings().youtube_search_calls_per_day, Settings().youtube_units_per_day), (100, 10000))
        with patch.dict("os.environ", {"WIN_ENGINE_YOUTUBE_SEARCH_CALLS_PER_DAY": "250",
                                       "WIN_ENGINE_YOUTUBE_UNITS_PER_DAY": "50000"}):
            self.assertEqual((Settings().youtube_search_calls_per_day, Settings().youtube_units_per_day), (250, 50000))
        for invalid in ({"youtube_search_calls_per_day": 0}, {"youtube_units_per_day": 0}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                Settings(**invalid)


class QuotaWarningTests(_DatabaseTestCase):
    def settings(self):
        return Settings(database_path=self.path, youtube_api_key="secret",
                        youtube_search_calls_per_day=10, youtube_units_per_day=20)

    def test_a_bucket_warns_from_ninety_percent_of_its_limit(self):
        for _ in range(8):
            self.ledger.record("key1", "search.list")
        self.assertEqual(quota_warnings(self.settings()), [])

        self.ledger.record("key1", "search.list")
        (warning,) = quota_warnings(self.settings())
        self.assertIn("API key 1 has used 9 of 10 searches", warning)
        self.assertIn("midnight Pacific time", warning)

        for _ in range(18):
            self.ledger.record("key1", "videos.list")
        self.assertIn("18 of 20 units", quota_warnings(self.settings())[1])

    def test_research_responses_carry_the_warning_without_blocking_the_search(self):
        for _ in range(9):
            self.ledger.record("key1", "search.list")
        patcher = patch.dict(cache_module._SHARED_CACHES, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        service = ResearchService(self.settings())
        service._youtube = MagicMock()
        service._youtube.search_videos.return_value = []
        service._youtube.runtime_state.return_value = {"warning": None}
        service._history = MagicMock()

        with patch.object(research_service, "plan_research_queries",
                          return_value=[{"type": "primary", "query": "grief quotes"}]):
            research = service.gather("grief quotes", results_only=True)

        service._youtube.search_videos.assert_called_once()
        self.assertTrue(any("9 of 10 searches" in item for item in research["research_warnings"]))


class SettingsStatusRouteTests(_DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.settings = Settings(database_path=self.path, allowed_hosts="testserver", app_environment="development",
                                 youtube_api_keys="secret-a,secret-b")
        for target in (patch.object(routes, "get_settings", return_value=self.settings),
                       patch("win_engine.core.config.get_settings", return_value=self.settings)):
            target.start()
            self.addCleanup(target.stop)
        self.client = TestClient(create_app(), raise_server_exceptions=False)

    def test_settings_status_reports_todays_quota_per_source(self):
        for _ in range(3):
            self.ledger.record("key2", "search.list")

        response = self.client.get("/api/settings/status")

        self.assertEqual(response.status_code, 200)
        quota = response.json()["youtube_quota"]
        self.assertTrue(quota["available"])
        self.assertEqual(quota["quota_date"], quota_date().isoformat())
        self.assertEqual(quota["resets_at"], next_reset().isoformat())
        self.assertEqual([item["source"] for item in quota["sources"]], ["key1", "key2"])
        self.assertEqual(quota["sources"][1]["search"], {"used": 3, "limit": 100, "remaining": 97})
        self.assertNotIn("secret", response.text)

    def test_a_database_that_cannot_open_leaves_the_quota_unavailable(self):
        blocker = self.dir / "not-a-folder"
        blocker.write_text("")
        self.settings.database_path = str(blocker / "win_engine.db")

        quota = self.client.get("/api/settings/status").json()["youtube_quota"]

        self.assertFalse(quota["available"])
        self.assertEqual(quota["sources"], [])


if __name__ == "__main__":
    unittest.main()
