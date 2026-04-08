from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List

import requests


logger = logging.getLogger(__name__)


class YouTubeClient:
    """YouTube Data API v3 client with key rotation and quota-aware fallback."""

    _SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    _VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
    _CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

    def __init__(self, api_keys: List[str], timeout_seconds: int) -> None:
        self._api_keys = api_keys
        self._timeout = timeout_seconds
        self._active_key_index = 0
        self._last_warning: str | None = None
        self._last_reset_date = datetime.now(timezone.utc).date()

    def search_videos(
        self,
        query: str,
        max_results: int = 5,
        raise_on_error: bool = False,
    ) -> List[dict[str, Any]]:
        self._refresh_quota_window()
        self._last_warning = None

        if not self._api_keys:
            logger.warning("YouTube API key not set; returning empty results")
            self._last_warning = "YouTube API key is missing."
            return []

        payload = self._request_json(
            self._SEARCH_URL,
            {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "order": "relevance",
            },
            raise_on_error=raise_on_error,
        )
        if not payload:
            return []

        items = payload.get("items", [])
        results: List[dict[str, Any]] = []
        video_ids: List[str] = []
        channel_ids: List[str] = []

        for item in items:
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId")

            if not video_id:
                continue

            video_ids.append(video_id)
            if channel_id:
                channel_ids.append(channel_id)
            results.append(
                {
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "channel_title": snippet.get("channelTitle"),
                    "published_at": snippet.get("publishedAt"),
                    "thumbnails": snippet.get("thumbnails", {}),
                }
            )

        stats = self._fetch_video_stats(video_ids, raise_on_error=raise_on_error)
        channel_stats = self._fetch_channel_stats(channel_ids, raise_on_error=raise_on_error)
        for entry in results:
            stats_entry = stats.get(entry["video_id"], {})
            channel_entry = channel_stats.get(entry.get("channel_id"), {})
            entry["view_count"] = stats_entry.get("viewCount")
            entry["like_count"] = stats_entry.get("likeCount")
            entry["comment_count"] = stats_entry.get("commentCount")
            entry["duration"] = stats_entry.get("duration")
            entry["subscriber_count"] = channel_entry.get("subscriberCount")
            entry["channel_video_count"] = channel_entry.get("videoCount")

        return results

    def _fetch_video_stats(
        self,
        video_ids: List[str],
        raise_on_error: bool = False,
    ) -> dict[str, dict[str, Any]]:
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
            return {}

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
    ) -> dict[str, dict[str, Any]]:
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
            return {}

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
        last_error: Exception | None = None
        warnings: list[str] = []

        for offset in range(len(self._api_keys)):
            key_index = (self._active_key_index + offset) % len(self._api_keys)
            api_key = self._api_keys[key_index]
            request_params = {**params, "key": api_key}

            try:
                response = requests.get(url, params=request_params, timeout=self._timeout)
                response.raise_for_status()
                self._active_key_index = key_index
                if warnings:
                    self._last_warning = " ".join(warnings)
                return response.json()
            except requests.HTTPError as exc:
                last_error = exc
                reason = self._extract_error_reason(exc.response)
                if self._should_rotate_key(exc.response, reason):
                    warnings.append(
                        f"API key {key_index + 1} hit {reason or 'a quota/access issue'}; switched to next key."
                    )
                    logger.warning("Rotating YouTube API key due to %s", reason or "quota/access issue")
                    continue
                logger.exception("YouTube request failed: %s", exc)
                self._last_warning = f"YouTube API request failed: {reason or str(exc)}"
                if raise_on_error:
                    raise
                return {}
            except requests.RequestException as exc:
                last_error = exc
                logger.exception("YouTube request failed: %s", exc)
                self._last_warning = f"YouTube request error: {exc}"
                if raise_on_error:
                    raise
                return {}

        self._last_warning = " ".join(warnings) if warnings else "All YouTube API keys failed."
        if raise_on_error and last_error is not None:
            raise last_error
        return {}

    def _refresh_quota_window(self) -> None:
        current_date = datetime.now(timezone.utc).date()
        if current_date > self._last_reset_date:
            self._active_key_index = 0
            self._last_warning = "YouTube API quota window rolled over; key rotation state was reset."
            self._last_reset_date = current_date

    def _extract_error_reason(self, response: requests.Response | None) -> str | None:
        if response is None:
            return None
        try:
            payload = response.json()
        except ValueError:
            return response.text or None

        error = payload.get("error", {})
        errors = error.get("errors", [])
        if errors:
            return errors[0].get("reason") or errors[0].get("message")
        return error.get("message")

    def _should_rotate_key(self, response: requests.Response | None, reason: str | None) -> bool:
        if response is None or len(self._api_keys) <= 1:
            return False

        if response.status_code not in {403, 429}:
            return False

        quota_reasons = {
            "quotaExceeded",
            "dailyLimitExceeded",
            "rateLimitExceeded",
            "userRateLimitExceeded",
            "accessNotConfigured",
            "keyInvalid",
            "forbidden",
        }
        return reason in quota_reasons or response.status_code == 429

    def runtime_state(self) -> dict[str, Any]:
        return {
            "active_key_index": self._active_key_index + 1 if self._api_keys else None,
            "available_key_count": len(self._api_keys),
            "warning": self._last_warning,
            "quota_date": self._last_reset_date.isoformat(),
        }
