from __future__ import annotations

import html
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

# Creator-facing region names as ISO 3166-1 codes, shared with request validation.
from win_engine.core.regions import REGION_CODES as _REGION_CODES


logger = logging.getLogger(__name__)
_ESCAPED_TEXT_FIELDS = ("title", "description", "channel_title")

try:
    # The daily quota resets at midnight Pacific time, not UTC.
    _QUOTA_ZONE: tzinfo = ZoneInfo("America/Los_Angeles")
except ZoneInfoNotFoundError:  # no tz database: standard time, an hour early in summer
    _QUOTA_ZONE = timezone(timedelta(hours=-8))

# The language of the videos, for relevanceLanguage. Tanglish is Tamil written
# in Latin letters.
_CONTENT_LANGUAGE_CODES = {"english": "en", "tamil": "ta", "tanglish": "ta", "hindi": "hi"}


def youtube_region_code(region: str | None) -> str | None:
    """ISO 3166-1 code for a creator-facing region, or None for no regional bias."""

    return _REGION_CODES.get(str(region or "").strip().casefold())


def youtube_language_code(language: str | None) -> str | None:
    """ISO 639-1 code of the videos' language, or None when it is unknown."""

    return _CONTENT_LANGUAGE_CODES.get(str(language or "").strip().casefold())


def unescape_result(result: dict[str, Any]) -> dict[str, Any]:
    """Decode the HTML entities search.list puts in text fields.

    "Hidden Details &amp; Easter Eggs" reached the writer's prompt as-is, and
    the model copied "&amp;" into a generated title.
    """

    for field in _ESCAPED_TEXT_FIELDS:
        value = result.get(field)
        if isinstance(value, str) and "&" in value:
            result[field] = html.unescape(value)
    return result


def _quota_date() -> date:
    return datetime.now(_QUOTA_ZONE).date()


class _KeyRotation:
    """Which key of a pool to try first, shared by every client of that pool.

    Clients are built per request. While each kept its own index, every request
    spent a failing call on an exhausted key 1 before moving on to key 2.
    Concurrent updates need no lock: a lost one costs at most one failing call.
    """

    def __init__(self) -> None:
        self.active_index = 0
        self.quota_date = _quota_date()


_ROTATIONS: dict[tuple[str, ...], _KeyRotation] = {}
_ROTATIONS_LOCK = threading.Lock()


class YouTubeClient:
    """YouTube Data API v3 client with key rotation and quota-aware fallback."""

    _SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    _VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
    _CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
    _PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
    _REGIONS_URL = "https://www.googleapis.com/youtube/v3/i18nRegions"
    # Short-window limits clear within seconds; the daily quota does not, so
    # only these reasons are retried.
    _BURST_LIMIT_REASONS = {"rateLimitExceeded", "userRateLimitExceeded"}
    # Reasons that condemn the key or its project rather than the request, so
    # another key can succeed. Every "API_KEY_*" detail reason counts too. A bare
    # 403 "forbidden" is about the request and would fail on every key.
    _KEY_REASONS = {
        "quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded",
        "accessNotConfigured", "keyInvalid", "keyExpired", "ipRefererBlocked", "SERVICE_DISABLED",
    }
    _RATE_LIMIT_RETRIES = 2
    _RATE_LIMIT_BACKOFF_SECONDS = 1.0
    _MAX_REASON_LENGTH = 120

    def __init__(self, api_keys: List[str], timeout_seconds: int) -> None:
        self._api_keys = list(api_keys)
        self._timeout = timeout_seconds
        self._last_warning: str | None = None
        self._uploads_playlists: dict[str, str] = {}
        with _ROTATIONS_LOCK:
            self._rotation = _ROTATIONS.setdefault(tuple(self._api_keys), _KeyRotation())

    def search_videos(
        self,
        query: str,
        max_results: int = 5,
        raise_on_error: bool = False,
        *,
        region_code: str | None = None,
        relevance_language: str | None = None,
    ) -> List[dict[str, Any]]:
        """Search results with their video and channel statistics.

        ``captured_at`` on a row says when both lookups returned its statistics.
        A row without it has gaps from a failed lookup, which are not zeros.
        """

        self._last_warning = None

        if not self._api_keys:
            logger.warning("YouTube API key not set; returning empty results")
            self._last_warning = "YouTube API key is missing."
            return []

        params: dict[str, Any] = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "order": "relevance",
        }
        if region_code:
            params["regionCode"] = region_code
        if relevance_language:
            params["relevanceLanguage"] = relevance_language
        payload = self._request_json(self._SEARCH_URL, params, raise_on_error=raise_on_error)
        if not payload:
            return []

        items = payload.get("items", [])
        results: List[dict[str, Any]] = []

        for item in items:
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})

            if not video_id:
                continue

            results.append(unescape_result(
                {
                    "video_id": video_id,
                    "channel_id": snippet.get("channelId"),
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "channel_title": snippet.get("channelTitle"),
                    "published_at": snippet.get("publishedAt"),
                    "thumbnails": snippet.get("thumbnails", {}),
                }
            ))

        return self._attach_statistics(results, raise_on_error=raise_on_error)

    def attach_statistics(self, rows: List[dict[str, Any]]) -> List[dict[str, Any]]:
        """Rows of an earlier search with their statistics looked up again.

        Two 1-unit lookups: a search whose statistics lookup failed no longer
        has to be repeated for 100 units to fill the gaps.
        """

        self._last_warning = None
        results = [dict(row) for row in rows]
        if not self._api_keys:
            self._last_warning = "YouTube API key is missing."
            return results
        return self._attach_statistics(results)

    def _attach_statistics(
        self,
        results: List[dict[str, Any]],
        raise_on_error: bool = False,
    ) -> List[dict[str, Any]]:
        video_ids = [entry["video_id"] for entry in results]
        channel_ids = [entry["channel_id"] for entry in results if entry.get("channel_id")]
        stats = self._fetch_video_stats(video_ids, raise_on_error=raise_on_error)
        # Without video statistics no row can be complete and the next run looks
        # both up again, so a channel lookup now would spend a unit for nothing.
        channel_stats = None if stats is None else self._fetch_channel_stats(channel_ids, raise_on_error=raise_on_error)
        captured_at = datetime.now(timezone.utc).isoformat()
        for entry in results:
            stats_entry = stats.get(entry["video_id"]) if stats is not None else None
            channel_entry = channel_stats.get(entry.get("channel_id")) if channel_stats is not None else None
            entry["view_count"] = (stats_entry or {}).get("viewCount")
            entry["like_count"] = (stats_entry or {}).get("likeCount")
            entry["comment_count"] = (stats_entry or {}).get("commentCount")
            entry["duration"] = (stats_entry or {}).get("duration")
            # A hidden subscriber count is unknown, not zero subscribers.
            hidden = bool((channel_entry or {}).get("hiddenSubscriberCount"))
            entry["subscriber_count"] = None if hidden else (channel_entry or {}).get("subscriberCount")
            entry["channel_video_count"] = (channel_entry or {}).get("videoCount")
            entry["captured_at"] = captured_at if stats_entry is not None and channel_entry is not None else None

        return results

    def get_channel(self, channel_id: str, *, raise_on_error: bool = False) -> dict[str, Any] | None:
        """Resolve one public channel using the read-only Data API key."""
        if not self._api_keys:
            self._last_warning = "YouTube API key is missing."
            return None
        payload = self._request_json(self._CHANNELS_URL, {
            "part": "snippet,statistics,contentDetails", "id": channel_id,
        }, raise_on_error=raise_on_error)
        items = payload.get("items", []) if payload else []
        if not items:
            return None
        item = items[0]
        snippet, stats = item.get("snippet", {}), item.get("statistics", {})
        uploads = ((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
        if uploads:
            self._uploads_playlists[channel_id] = uploads
        return {
            "channel_id": item.get("id"), "title": snippet.get("title"),
            "description": snippet.get("description"), "thumbnail_url": ((snippet.get("thumbnails") or {}).get("high") or (snippet.get("thumbnails") or {}).get("default") or {}).get("url"),
            "subscriber_count": stats.get("subscriberCount"), "video_count": stats.get("videoCount"),
            "view_count": stats.get("viewCount"), "hidden_subscriber_count": stats.get("hiddenSubscriberCount"),
            "uploads_playlist_id": uploads,
        }

    def get_video(self, video_id: str, *, raise_on_error: bool = False) -> dict[str, Any] | None:
        """Resolve one public video and its currently visible public metrics."""
        if not self._api_keys:
            self._last_warning = "YouTube API key is missing."
            return None
        videos = self._get_videos([video_id], raise_on_error=raise_on_error)
        return videos[0] if videos else None

    def _get_videos(self, video_ids: list[str], *, raise_on_error: bool = False) -> list[dict[str, Any]]:
        if not video_ids:
            return []
        payload = self._request_json(self._VIDEOS_URL, {
            "part": "snippet,statistics,contentDetails", "id": ",".join(video_ids),
        }, raise_on_error=raise_on_error)
        items = payload.get("items", []) if payload else []
        results = []
        for item in items:
            snippet, stats, details = item.get("snippet", {}), item.get("statistics", {}), item.get("contentDetails", {})
            results.append({
            "video_id": item.get("id"), "channel_id": snippet.get("channelId"),
            "channel_title": snippet.get("channelTitle"), "title": snippet.get("title"),
            "description": snippet.get("description"), "published_at": snippet.get("publishedAt"),
            "default_language": snippet.get("defaultLanguage") or snippet.get("defaultAudioLanguage"),
            "duration": details.get("duration"), "view_count": stats.get("viewCount"),
            "like_count": stats.get("likeCount"), "comment_count": stats.get("commentCount"),
            "thumbnails": snippet.get("thumbnails", {}),
            })
        return results

    def list_channel_videos(self, channel_id: str, max_results: int = 20, *, raise_on_error: bool = False) -> list[dict[str, Any]]:
        """Return recent public uploads for an observational channel baseline.

        Reads the channel's uploads playlist, newest first, for 1 unit a page.
        search.list by channelId cost 100 units and is known to miss uploads.
        """
        if not self._api_keys:
            self._last_warning = "YouTube API key is missing."
            return []
        playlist_id = self._uploads_playlists.get(channel_id) or self._uploads_playlist(channel_id, raise_on_error=raise_on_error)
        if not playlist_id:
            return []
        payload = self._request_json(self._PLAYLIST_ITEMS_URL, {
            "part": "contentDetails", "playlistId": playlist_id, "maxResults": max(1, min(max_results, 50)),
        }, raise_on_error=raise_on_error)
        items = payload.get("items", []) if payload else []
        ids = [str((item.get("contentDetails") or {}).get("videoId") or "") for item in items]
        return self._get_videos([video_id for video_id in ids if video_id], raise_on_error=raise_on_error)

    def _uploads_playlist(self, channel_id: str, *, raise_on_error: bool = False) -> str | None:
        # get_channel remembers the playlist; this lookup serves callers that skip it.
        payload = self._request_json(self._CHANNELS_URL, {
            "part": "contentDetails", "id": channel_id,
        }, raise_on_error=raise_on_error)
        items = payload.get("items", []) if payload else []
        uploads = ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") if items else None
        if uploads:
            self._uploads_playlists[channel_id] = uploads
        return uploads

    def ping(self) -> None:
        """Prove that a key and the network work, for one quota unit.

        Raises on failure. The health check used to run a search: 102 units.
        """

        self._last_warning = None
        self._request_json(self._REGIONS_URL, {"part": "snippet"}, raise_on_error=True)

    def _fetch_video_stats(
        self,
        video_ids: List[str],
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, Any]] | None:
        """Statistics by video ID, or None when the lookup failed."""

        if not video_ids:
            return {}

        payload = self._request_json(
            self._VIDEOS_URL,
            {
                "part": "statistics,contentDetails",
                "id": ",".join(video_ids),
            },
            raise_on_error=raise_on_error,
        )
        if not payload:
            return None

        stats_map: dict[str, dict[str, Any]] = {}
        for item in payload.get("items", []):
            video_id = item.get("id")
            statistics = item.get("statistics", {})
            content_details = item.get("contentDetails", {})
            if video_id:
                stats_map[video_id] = {
                    **statistics,
                    "duration": content_details.get("duration"),
                }

        return stats_map

    def _fetch_channel_stats(
        self,
        channel_ids: List[str],
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, Any]] | None:
        """Statistics by channel ID, or None when the lookup failed."""

        if not channel_ids:
            return {}

        unique_channel_ids = list(dict.fromkeys(channel_ids))
        payload = self._request_json(
            self._CHANNELS_URL,
            {
                "part": "statistics",
                "id": ",".join(unique_channel_ids),
            },
            raise_on_error=raise_on_error,
        )
        if not payload:
            return None

        stats_map: dict[str, dict[str, Any]] = {}
        for item in payload.get("items", []):
            channel_id = item.get("id")
            statistics = item.get("statistics", {})
            if channel_id:
                stats_map[channel_id] = statistics

        return stats_map

    def _request_json(
        self,
        url: str,
        params: dict[str, Any],
        raise_on_error: bool = False,
    ) -> dict[str, Any]:
        self._refresh_quota_window()
        last_error: Exception | None = None
        warnings: list[str] = []
        start_index = self._rotation.active_index

        for offset in range(len(self._api_keys)):
            key_index = (start_index + offset) % len(self._api_keys)

            try:
                response = self._get_with_backoff(url, params, self._api_keys[key_index])
                self._rotation.active_index = key_index
                if warnings:
                    self._last_warning = " ".join(warnings)
                return response.json()
            except requests.HTTPError as exc:
                last_error = exc
                reason = self._extract_error_reason(exc.response)
                if self._should_rotate_key(exc.response, self._error_reasons(exc.response)):
                    warnings.append(
                        f"API key {key_index + 1} hit {reason or 'a quota/access issue'}; switched to next key."
                    )
                    logger.warning("Rotating YouTube API key due to %s", reason or "quota/access issue")
                    continue
                # A 4xx Response is falsy, so test for None explicitly.
                status = exc.response.status_code if exc.response is not None else "unknown"
                logger.warning("YouTube request failed with HTTP status %s: %s", status, reason or "unknown error")
                self._last_warning = f"YouTube API request failed: {reason or 'unknown error'}"
                if raise_on_error:
                    raise
                return {}
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("YouTube request failed: %s", type(exc).__name__)
                self._last_warning = "YouTube API request failed. Check the network connection."
                if raise_on_error:
                    raise
                return {}

        self._last_warning = " ".join(warnings) if warnings else "All YouTube API keys failed."
        if raise_on_error and last_error is not None:
            raise last_error
        return {}

    def _get_with_backoff(self, url: str, params: dict[str, Any], api_key: str) -> requests.Response:
        """GET once, retrying briefly when YouTube reports a burst rate limit.

        A research run fires several searches back to back; without a retry a
        momentary "rateLimitExceeded" silently dropped that query's evidence.
        The key travels in a header: in the URL, requests copied it into the
        text of every exception.
        """

        headers = {"X-Goog-Api-Key": api_key}
        for attempt in range(self._RATE_LIMIT_RETRIES + 1):
            response = requests.get(url, params=params, headers=headers, timeout=self._timeout)
            if response.status_code in {403, 429} and attempt < self._RATE_LIMIT_RETRIES:
                if response.status_code == 429 or self._BURST_LIMIT_REASONS & set(self._error_reasons(response)):
                    time.sleep(self._RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1))
                    continue
            response.raise_for_status()
            return response
        raise AssertionError("unreachable")  # the final attempt returns or raises

    def _refresh_quota_window(self) -> None:
        current_date = _quota_date()
        if current_date > self._rotation.quota_date:
            self._rotation.active_index = 0
            self._rotation.quota_date = current_date
            # Logged, not warned: a new quota day says nothing about this research.
            logger.info("YouTube quota day rolled over; API key 1 is tried first again.")

    @staticmethod
    def _error_reasons(response: requests.Response | None) -> list[str]:
        """Reason codes in a Google API error body, the most specific first.

        An invalid or expired key is HTTP 400 "badRequest" in the classic
        ``errors`` list; only the ErrorInfo detail ("API_KEY_INVALID") names it.
        """

        try:
            error = response.json().get("error")
        except (AttributeError, ValueError):  # no response, a list, or an HTML error page
            return []
        if not isinstance(error, dict):
            return []
        items = [*(error.get("details") or []), *(error.get("errors") or [])]
        return [str(item["reason"]) for item in items if isinstance(item, dict) and item.get("reason")]

    def _extract_error_reason(self, response: requests.Response | None) -> str | None:
        """A short reason fit for a log line or a user-facing warning."""

        if response is None:
            return None
        reasons = self._error_reasons(response)
        if reasons:
            return reasons[0]
        try:
            message = str((response.json().get("error") or {}).get("message") or "")
        except (AttributeError, ValueError):
            # Proxies and outages answer with an HTML page, which no warning should repeat.
            return f"HTTP {response.status_code}"
        return message[: self._MAX_REASON_LENGTH] or None

    def _should_rotate_key(self, response: requests.Response | None, reasons: list[str]) -> bool:
        if response is None or len(self._api_keys) <= 1:
            return False
        if response.status_code == 429:
            return True
        # An invalid or expired key answers HTTP 400, so a 400 can be the key's fault too.
        return response.status_code in {400, 403} and any(
            reason in self._KEY_REASONS or reason.startswith("API_KEY_") for reason in reasons
        )

    def runtime_state(self) -> dict[str, Any]:
        return {
            "active_key_index": self._rotation.active_index + 1 if self._api_keys else None,
            "available_key_count": len(self._api_keys),
            "warning": self._last_warning,
            "quota_date": self._rotation.quota_date.isoformat(),
        }
