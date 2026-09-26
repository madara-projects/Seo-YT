"""YouTube client: key handling, rotation, quota day, statistics completeness."""

import unittest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import requests
from pydantic import ValidationError

from win_engine.core.config import Settings
from win_engine.ingestion import youtube_client
from win_engine.ingestion.youtube_client import YouTubeClient, youtube_language_code, youtube_region_code

SEARCH = YouTubeClient._SEARCH_URL
VIDEOS = YouTubeClient._VIDEOS_URL
CHANNELS = YouTubeClient._CHANNELS_URL


def _response(status, payload=None, text=""):
    response = MagicMock(status_code=status, text=text)
    if payload is None:
        response.json.side_effect = ValueError("not JSON")
    else:
        response.json.return_value = payload
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


def _key_error(status, *, classic, detail=None):
    error = {"code": status, "message": "error", "errors": [{"reason": classic}]}
    if detail:
        error["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": detail}]
    return _response(status, {"error": error})


SEARCH_OK = {"items": [{"id": {"videoId": "vid1"}, "snippet": {"channelId": "UC1", "title": "A &amp; B",
                                                              "publishedAt": "2026-09-01T00:00:00Z"}}]}
VIDEOS_OK = {"items": [{"id": "vid1", "statistics": {"viewCount": "10"}, "contentDetails": {"duration": "PT1M"}}]}
CHANNELS_OK = {"items": [{"id": "UC1", "statistics": {"subscriberCount": "5"}}]}


class _ClientTestCase(unittest.TestCase):
    def setUp(self):
        # Rotation state is process-wide; each test starts from a clean registry.
        patcher = patch.dict(youtube_client._ROTATIONS, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _get(self, *responses):
        patcher = patch("win_engine.ingestion.youtube_client.requests.get", side_effect=list(responses))
        get = patcher.start()
        self.addCleanup(patcher.stop)
        return get


class KeyTransportTests(_ClientTestCase):
    def test_key_travels_in_a_header_never_the_url(self):
        get = self._get(_response(200, {"items": []}))

        YouTubeClient(["secret-key"], timeout_seconds=5)._request_json(SEARCH, {"q": "x"})

        _, kwargs = get.call_args
        self.assertNotIn("key", kwargs["params"])
        self.assertEqual(kwargs["headers"], {"X-Goog-Api-Key": "secret-key"})
        prepared = requests.Request("GET", SEARCH, params=kwargs["params"], headers=kwargs["headers"]).prepare()
        self.assertNotIn("secret-key", prepared.url)

    def test_html_error_body_is_not_repeated_in_the_warning(self):
        self._get(_response(502, text="<html>" + "x" * 5000 + "</html>"))
        client = YouTubeClient(["key"], timeout_seconds=5)

        self.assertEqual(client._request_json(SEARCH, {}), {})
        self.assertEqual(client.runtime_state()["warning"], "YouTube API request failed: HTTP 502")


class KeyRotationTests(_ClientTestCase):
    def test_invalid_key_rotates_to_the_next_key(self):
        # An invalid key is HTTP 400 "badRequest"; only the detail names the key.
        get = self._get(_key_error(400, classic="badRequest", detail="API_KEY_INVALID"), _response(200, {"items": []}))
        client = YouTubeClient(["bad-key", "good-key"], timeout_seconds=5)

        self.assertEqual(client._request_json(SEARCH, {}), {"items": []})

        self.assertEqual([call.kwargs["headers"]["X-Goog-Api-Key"] for call in get.call_args_list], ["bad-key", "good-key"])
        self.assertIn("API key 1 hit API_KEY_INVALID", client.runtime_state()["warning"])
        self.assertEqual(client.runtime_state()["active_key_index"], 2)

    def test_key_restriction_rotates_but_plain_forbidden_does_not(self):
        get = self._get(_key_error(403, classic="forbidden", detail="API_KEY_HTTP_REFERRER_BLOCKED"),
                        _response(200, {"items": []}))
        self.assertEqual(YouTubeClient(["k1", "k2"], timeout_seconds=5)._request_json(SEARCH, {}), {"items": []})
        self.assertEqual(get.call_count, 2)

        get = self._get(_key_error(403, classic="forbidden"))
        client = YouTubeClient(["k3", "k4"], timeout_seconds=5)
        self.assertEqual(client._request_json(SEARCH, {}), {})
        self.assertEqual(get.call_count, 1)  # the request, not a key, was refused
        self.assertEqual(client.runtime_state()["warning"], "YouTube API request failed: forbidden")

    def test_rotation_is_shared_by_every_client_of_the_pool(self):
        self._get(_key_error(403, classic="quotaExceeded"), _response(200, {"items": []}))
        YouTubeClient(["spent", "fresh"], timeout_seconds=5)._request_json(SEARCH, {})

        get = self._get(_response(200, {"items": []}))
        client = YouTubeClient(["spent", "fresh"], timeout_seconds=5)
        client._request_json(SEARCH, {})

        # A new client (a new request) goes straight to key 2 and warns about nothing.
        self.assertEqual(get.call_args.kwargs["headers"]["X-Goog-Api-Key"], "fresh")
        self.assertIsNone(client.runtime_state()["warning"])


class _Clock(datetime):
    current = datetime(2026, 9, 25, 3, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)


class QuotaDayTests(_ClientTestCase):
    def test_quota_day_follows_pacific_midnight(self):
        with patch.object(youtube_client, "datetime", _Clock):
            _Clock.current = datetime(2026, 9, 25, 3, 0, tzinfo=timezone.utc)  # 20:00 on the 24th in California
            client = YouTubeClient(["k1", "k2"], timeout_seconds=5)
            self.assertEqual(client.runtime_state()["quota_date"], "2026-09-24")
            client._rotation.active_index = 1

            _Clock.current = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)  # a new UTC day, same quota day
            self._get(_response(200, {"items": []}))
            client._request_json(SEARCH, {})
            self.assertEqual(client.runtime_state()["active_key_index"], 2)

            _Clock.current = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)  # 01:00 in California
            get = self._get(_response(200, {"items": []}))
            client._request_json(SEARCH, {})
            self.assertEqual(get.call_args.kwargs["headers"]["X-Goog-Api-Key"], "k1")
            self.assertEqual(client._rotation.quota_date, date(2026, 9, 25))
            self.assertIsNone(client.runtime_state()["warning"])


class SearchTests(_ClientTestCase):
    def test_search_sends_the_region_and_language(self):
        get = self._get(_response(200, {"items": []}))

        YouTubeClient(["key"], timeout_seconds=5).search_videos("q", 25, region_code="IN", relevance_language="ta")

        params = get.call_args.kwargs["params"]
        self.assertEqual((params["regionCode"], params["relevanceLanguage"], params["maxResults"]), ("IN", "ta", 25))

    def test_creator_regions_and_languages_map_to_youtube_codes(self):
        self.assertEqual(youtube_region_code("Tamil Nadu"), "IN")
        self.assertEqual(youtube_region_code("sri lanka"), "LK")
        self.assertEqual(youtube_region_code("uk"), "GB")
        self.assertIsNone(youtube_region_code("gulf"))
        self.assertIsNone(youtube_region_code("global"))
        self.assertEqual(youtube_language_code("tanglish"), "ta")
        self.assertEqual(youtube_language_code("Hindi"), "hi")
        self.assertIsNone(youtube_language_code("klingon"))

    def test_complete_rows_carry_their_capture_time(self):
        self._get(_response(200, SEARCH_OK), _response(200, VIDEOS_OK), _response(200, CHANNELS_OK))

        (row,) = YouTubeClient(["key"], timeout_seconds=5).search_videos("q")

        self.assertEqual((row["view_count"], row["subscriber_count"], row["title"]), ("10", "5", "A & B"))
        self.assertIsNotNone(row["captured_at"])

    def test_failed_statistics_lookup_leaves_rows_uncaptured(self):
        self._get(_response(200, SEARCH_OK), _key_error(403, classic="quotaExceeded"),
                  _key_error(403, classic="quotaExceeded"))
        client = YouTubeClient(["key"], timeout_seconds=5)

        (row,) = client.search_videos("q")

        self.assertIsNone(row["captured_at"])
        self.assertIsNone(row["view_count"])
        self.assertIn("quotaExceeded", client.runtime_state()["warning"])

    def test_statistics_of_an_earlier_search_cost_no_new_search(self):
        get = self._get(_response(200, VIDEOS_OK), _response(200, CHANNELS_OK))
        page = [{"video_id": "vid1", "channel_id": "UC1", "title": "A & B", "view_count": None, "captured_at": None}]

        (row,) = YouTubeClient(["key"], timeout_seconds=5).attach_statistics(page)

        self.assertEqual([call.args[0] for call in get.call_args_list], [VIDEOS, CHANNELS])  # 2 units, not 102
        self.assertEqual((row["view_count"], row["subscriber_count"], row["title"]), ("10", "5", "A & B"))
        self.assertIsNotNone(row["captured_at"])

    def test_hidden_subscriber_count_is_unknown_not_zero(self):
        hidden = {"items": [{"id": "UC1", "statistics": {"subscriberCount": "0", "hiddenSubscriberCount": True}}]}
        self._get(_response(200, SEARCH_OK), _response(200, VIDEOS_OK), _response(200, hidden))

        (row,) = YouTubeClient(["key"], timeout_seconds=5).search_videos("q")

        self.assertIsNone(row["subscriber_count"])
        self.assertIsNotNone(row["captured_at"])  # the lookup worked; the count is private


class CheapCallTests(_ClientTestCase):
    def test_channel_uploads_come_from_the_uploads_playlist(self):
        channel = {"items": [{"id": "UC1", "snippet": {"title": "C"}, "statistics": {},
                              "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        uploads = {"items": [{"contentDetails": {"videoId": "vid1"}}]}
        videos = {"items": [{"id": "vid1", "snippet": {"title": "V"}, "statistics": {}, "contentDetails": {}}]}
        get = self._get(_response(200, channel), _response(200, uploads), _response(200, videos))
        client = YouTubeClient(["key"], timeout_seconds=5)

        self.assertEqual(client.get_channel("UC1")["uploads_playlist_id"], "UU1")
        self.assertEqual([video["video_id"] for video in client.list_channel_videos("UC1", 20)], ["vid1"])

        urls = [call.args[0] for call in get.call_args_list]
        self.assertEqual(urls, [CHANNELS, YouTubeClient._PLAYLIST_ITEMS_URL, VIDEOS])  # 3 units, no search.list
        self.assertEqual(get.call_args_list[1].kwargs["params"]["playlistId"], "UU1")

    def test_ping_is_one_cheap_request_and_raises_on_failure(self):
        get = self._get(_response(200, {"items": []}))
        YouTubeClient(["key"], timeout_seconds=5).ping()
        self.assertEqual([call.args[0] for call in get.call_args_list], [YouTubeClient._REGIONS_URL])

        self._get(_key_error(403, classic="quotaExceeded"))
        with self.assertRaises(requests.HTTPError):
            YouTubeClient(["other-key"], timeout_seconds=5).ping()


class MaxResultsSettingTests(unittest.TestCase):
    def test_page_size_is_bounded_to_what_search_accepts(self):
        self.assertEqual(Settings(youtube_max_results=50).youtube_max_results, 50)
        for invalid in (0, 51):
            with self.assertRaises(ValidationError):
                Settings(youtube_max_results=invalid)


if __name__ == "__main__":
    unittest.main()
