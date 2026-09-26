"""Read-only OAuth connection and reporting for the creator's YouTube channel."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Collection
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import Error as ApiClientError
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error

from win_engine.core.config import Settings
from win_engine.feedback.channel_learning import learning_summary, save_video_snapshots
from win_engine.feedback.history_store import ANALYTICS_ZONE, SNAPSHOT_WINDOWS, reportable_window
from win_engine.feedback.migrations import connect_managed

# Google's consent screen lets a creator untick one permission. oauthlib would
# then refuse the whole token; with this set, complete_authorization checks
# the granted scopes itself and says which permission is missing.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]
_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_CHANNEL_METRICS = "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,likes,comments"
_VIDEO_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained"
)
# YouTube Analytics reports whole days in Pacific time.
_ANALYTICS_ZONE = ANALYTICS_ZONE
_WINDOWS = SNAPSHOT_WINDOWS
_OAUTH_STATE_TTL_SECONDS = 600
_MAX_PENDING_STATES = 20
# Only the newest sync is read; a few older ones are kept for troubleshooting.
_SYNCS_KEPT = 30
_NOT_FOUND = "That video could not be found on YouTube. Check the link, and that the video is public or unlisted."
# A YouTube call that failed on the way or was refused. A revoked grant
# (RefreshError) is not one of these: the routes ask for a reconnect instead.
_UPSTREAM_ERRORS = (ApiClientError, TransportError, OSError, HttpLib2Error)
# state → (expiry, PKCE code verifier). Several connect attempts may be in
# flight (two tabs, a retry); each keeps its own entry until used or expired.
_PENDING_STATES: dict[str, tuple[float, str]] = {}
_PENDING_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


class YouTubeUnavailable(RuntimeError):
    """YouTube could not be reached or refused the request.

    The message is safe to show: it never carries request URLs, which for the
    Data API include the API key.
    """

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class ChannelConnectError(ValueError):
    """A connect attempt that cannot finish; `reason` is a short code the UI explains."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class LinkUnavailable(ValueError):
    """A linked video is gone, private or on another channel: collecting it again cannot help."""


def _describe(exc: BaseException) -> str:
    """An exception for the log: its type and HTTP status only, never its text."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    return f"{type(exc).__name__} (HTTP {status})" if status else type(exc).__name__


def _unavailable(exc: BaseException) -> YouTubeUnavailable:
    if not isinstance(exc, HttpError):
        return YouTubeUnavailable("YouTube could not be reached. Check the connection and try again.", status_code=503)
    status = int(getattr(exc.resp, "status", 0) or 0)
    text = f"{getattr(exc, 'reason', '')} {getattr(exc, 'error_details', '')}".lower().replace(" ", "")
    # quotaExceeded, dailyLimitExceeded, rateLimitExceeded, userRateLimitExceeded.
    if status == 429 or "quota" in text or "limitexceeded" in text:
        return YouTubeUnavailable("YouTube's API quota or rate limit was reached. Try again later.", status_code=429)
    if "accessnotconfigured" in text or "service_disabled" in text or "hasnotbeenused" in text:
        return YouTubeUnavailable(
            "A YouTube API is not enabled for this Google Cloud project. Enable it, wait a few minutes, then try again."
        )
    return YouTubeUnavailable(f"YouTube returned an error (HTTP {status or 'unknown'}). Try again shortly.")


def _outage(exc: BaseException) -> bool:
    """Whether a failed call is YouTube's or the network's (a 5xx, the quota, no answer), not the request's."""
    status = int(getattr(getattr(exc, "resp", None), "status", 0) or 0)
    return status >= 500 or _unavailable(exc).status_code in {429, 503}


class YouTubeChannelService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Reuse the existing database initializer before reading connection tables.
        from win_engine.feedback.history_store import HistoryStore
        HistoryStore(settings.database_path)

    def status(self) -> dict[str, Any]:
        record = self._connection()
        configured = self._is_configured()
        return {
            "configured": configured,
            "connected": bool(record),
            "channel": {"id": record[1], "title": record[2], "connected_at": record[3]} if record else None,
            "latest_sync": self._history_store().latest_channel_sync(str(record[1] or "")) if record else None,
            "setup_message": None if configured else "Add YouTube OAuth client credentials and an encryption key to .env to connect your channel.",
        }

    def connected_channel_id(self) -> str | None:
        """The connected channel, or None when none is connected or it is not identified yet."""
        record = self._connection()
        return str(record[1]) if record and record[1] else None

    def authorization_url(self) -> str:
        self._require_configured()
        state = secrets.token_urlsafe(32)
        # PKCE: the code Google returns is useless without this verifier.
        verifier = secrets.token_urlsafe(64)
        now = time.time()
        with _PENDING_LOCK:
            for expired in [key for key, (expires, _) in _PENDING_STATES.items() if expires < now]:
                del _PENDING_STATES[expired]
            while len(_PENDING_STATES) >= _MAX_PENDING_STATES:
                del _PENDING_STATES[min(_PENDING_STATES, key=lambda key: _PENDING_STATES[key][0])]
            _PENDING_STATES[state] = (now + _OAUTH_STATE_TTL_SECONDS, verifier)
        url, _ = self._flow(state=state, code_verifier=verifier).authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return url

    def complete_authorization(self, *, code: str, state: str) -> dict[str, Any]:
        if not self._is_configured():
            raise ChannelConnectError("not_configured", "YouTube OAuth is not configured. Check the local .env setup instructions.")
        with _PENDING_LOCK:
            pending = _PENDING_STATES.pop(state, None)
        if not pending or time.time() > pending[0]:
            raise ChannelConnectError("expired_state", "The connection request expired. Start the connection again.")
        flow = self._flow(state=state, code_verifier=pending[1])
        flow.fetch_token(code=code)
        credentials = flow.credentials
        if not credentials.refresh_token:
            raise ChannelConnectError(
                "no_refresh_token",
                "Google did not return a refresh token. Remove Win-Engine in Google Account permissions and connect again.",
            )
        granted = _granted_scopes(credentials, flow)
        if granted is not None and not set(_SCOPES) <= granted:
            raise ChannelConnectError(
                "missing_scopes",
                "Both YouTube permissions are needed. Connect again and allow access to your channel and its analytics.",
            )
        try:
            items = build("youtube", "v3", credentials=credentials, cache_discovery=False).channels().list(
                part="snippet", mine=True, maxResults=1
            ).execute().get("items") or []
        except _UPSTREAM_ERRORS as exc:
            # Authorization itself succeeded, so keep the token rather than make
            # the creator authorize again; the first refresh fills in the channel.
            logger.warning("Channel lookup after authorization failed: %s", _describe(exc))
            self._save_connection(credentials.refresh_token, "", "")
            return {"connected": True, "sync_pending": True, "sync_error": str(_unavailable(exc))}
        if not items:
            raise ChannelConnectError(
                "no_channel", "This Google account has no YouTube channel. Connect with the account that owns your channel."
            )
        item = items[0]
        self._save_connection(credentials.refresh_token, str(item.get("id") or ""), str((item.get("snippet") or {}).get("title") or ""))
        try:
            return self.refresh()
        except YouTubeUnavailable as exc:
            # API enablement can take a few minutes; the connection stands.
            return {"connected": True, "sync_pending": True, "sync_error": str(exc)}

    def disconnect(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM youtube_channel_connection WHERE id = 1")

    def refresh(self) -> dict[str, Any]:
        credentials = self._fresh_credentials()
        try:
            youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
            analytics = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
            channel_items = youtube.channels().list(
                part="snippet,statistics,contentDetails", mine=True, maxResults=1
            ).execute().get("items") or []
        except _UPSTREAM_ERRORS as exc:
            logger.warning("Channel refresh failed: %s", _describe(exc))
            raise _unavailable(exc) from exc
        if not channel_items:
            raise ValueError("The connected Google account no longer has a YouTube channel.")
        channel_item = channel_items[0]
        snippet = channel_item.get("snippet") or {}
        statistics = channel_item.get("statistics") or {}
        content_details = channel_item.get("contentDetails") or {}
        # Parts that fail are named, not hidden, so no view shows a gap as data.
        partial_failures: list[str] = []

        # The newest 50 uploads, read directly (Analytics reports lag by days).
        uploads_playlist_id = (content_details.get("relatedPlaylists") or {}).get("uploads")
        uploaded_video_rows: list[dict[str, Any]] = []
        if uploads_playlist_id:
            try:
                playlist_items = youtube.playlistItems().list(
                    playlistId=uploads_playlist_id, part="snippet,contentDetails", maxResults=50
                ).execute().get("items", [])
                video_ids = [
                    video_id
                    for item in playlist_items
                    if (video_id := (item.get("snippet", {}).get("resourceId") or {}).get("videoId"))
                ]
                if video_ids:
                    details = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids[:50])).execute().get("items", [])
                    uploaded_video_rows = _ordered_upload_rows(playlist_items, details)
            except _UPSTREAM_ERRORS as exc:
                logger.warning("Channel uploads could not be read: %s", _describe(exc))
                partial_failures.append("uploads")

        today = datetime.now(_ANALYTICS_ZONE).date()
        start = today - timedelta(days=28)
        previous_start = today - timedelta(days=56)
        current: dict[str, Any] = {}
        previous: dict[str, Any] = {}
        try:
            current = self._query(analytics, start, today - timedelta(days=1), _CHANNEL_METRICS)
            previous = self._query(analytics, previous_start, start - timedelta(days=1), _CHANNEL_METRICS)
        except _UPSTREAM_ERRORS as exc:
            logger.warning("Channel analytics could not be read: %s", _describe(exc))
            partial_failures.append("analytics")

        channel_id = str(channel_item.get("id") or "")
        if uploaded_video_rows:
            save_video_snapshots(self.settings.database_path, uploaded_video_rows, channel_id=channel_id)

        self._update_connection_channel(channel_id, str(snippet.get("title") or ""))
        payload = {
            "channel": {
                "id": channel_id,
                "title": snippet.get("title"),
                # A channel can hide its subscriber count: unknown, not zero.
                "subscribers": None if statistics.get("hiddenSubscriberCount") else _optional_int(statistics.get("subscriberCount")),
                "video_count": _optional_int(statistics.get("videoCount")),
                "real_total_views": _optional_int(statistics.get("viewCount")),
            },
            "period": {"start": start.isoformat(), "end": (today - timedelta(days=1)).isoformat()},
            "current_28_days": current,
            "previous_28_days": previous,
            "recent_videos": {"sort": "published_at_desc", "rows": uploaded_video_rows},
            "video_learning": learning_summary(self.settings.database_path),
            "partial_failures": partial_failures,
        }
        self._save_sync(payload)
        return payload

    def verify_owned_video(self, youtube_video_id: str) -> dict[str, Any]:
        """Fail closed unless OAuth proves the video belongs to the connected channel."""
        channel = self._connection()
        if not channel or not channel[1]:
            raise ValueError("Connect the YouTube channel that owns this video before linking it.")
        credentials = self._fresh_credentials()
        try:
            items = build("youtube", "v3", credentials=credentials, cache_discovery=False).videos().list(
                part="snippet,statistics,contentDetails,status",
                id=youtube_video_id,
                maxResults=1,
            ).execute().get("items", [])
        except _UPSTREAM_ERRORS as exc:
            logger.warning("OAuth ownership verification failed: %s", _describe(exc))
            raise YouTubeUnavailable(
                "YouTube ownership could not be verified, so nothing was linked. Try again when YouTube is reachable.",
                status_code=_unavailable(exc).status_code,
            ) from exc

        if not items:
            raise ValueError("That video was not found for the connected YouTube channel.")
        metadata = _video_metadata(items[0], youtube_video_id, ownership_verified=True)
        actual_channel_id = str(metadata.get("channel_id") or "")
        if not actual_channel_id or actual_channel_id != str(channel[1]):
            raise ValueError("This video does not belong to the connected YouTube channel.")
        return metadata

    def verify_public_video(self, youtube_video_id: str) -> dict[str, Any]:
        """Look a public video up with an API key, falling back to oEmbed.

        A lookup that answers "no such video" is refused. Only when YouTube
        cannot confirm it either way is the bare id accepted, marked unverified
        and without any made-up title or date.
        """
        for index, api_key in enumerate(self.settings.youtube_api_key_pool, start=1):
            try:
                items = build("youtube", "v3", developerKey=api_key, cache_discovery=False).videos().list(
                    part="snippet,statistics,contentDetails,status",
                    id=youtube_video_id,
                    maxResults=1,
                ).execute().get("items", [])
            except _UPSTREAM_ERRORS as exc:
                # The exception text holds the request URL, and with it the key.
                logger.warning("YouTube Data API lookup with key %d failed: %s", index, _describe(exc))
                continue
            if items:
                return _video_metadata(items[0], youtube_video_id, ownership_verified=False)
            raise ValueError(_NOT_FOUND)

        url = "https://www.youtube.com/oembed?" + urlencode(
            {"url": f"https://www.youtube.com/watch?v={youtube_video_id}", "format": "json"}
        )
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            return {
                "video_id": youtube_video_id,
                "title": str(data.get("title") or "") or None,
                "channel_title": str(data.get("author_name") or "") or None,
                # oEmbed carries no description, tags or date: unknown, not empty.
                "description": None,
                "tags": None,
                "published_at": None,
                "ownership_verified": False,
                "metadata_source": "oembed",
            }
        except urllib.error.HTTPError as exc:
            if exc.code in {400, 404}:
                raise ValueError(_NOT_FOUND) from exc
            # 401/403 mean private or not embeddable: the id may still be real.
            logger.warning("oEmbed lookup failed: HTTP %s", exc.code)
        except (OSError, ValueError) as exc:
            logger.warning("oEmbed lookup failed: %s", _describe(exc))

        if re.fullmatch(r"[A-Za-z0-9_-]{11}", youtube_video_id):
            return {
                "video_id": youtube_video_id,
                "title": None,
                "description": None,
                "tags": None,
                "published_at": None,
                "ownership_verified": False,
                "metadata_source": "unverified_id",
            }
        raise ValueError(_NOT_FOUND)

    def refresh_linked_video_performance(
        self,
        link: dict[str, Any],
        *,
        force: bool = False,
        collect_current: bool = True,
        windows: Collection[str] | None = None,
    ) -> dict[str, Any]:
        """Capture due 24-hour, 7-day and 28-day analytics snapshots, and current counts.

        Runs on request and from the snapshot collector: a laptop cannot collect
        data while it is off, so each run catches up on whatever is due. The
        collector passes the `windows` it planned, so a window still cooling
        down after a failure is not retried early.
        """
        video_id = str(link.get("youtube_video_id") or "")
        if not video_id:
            raise ValueError("Published-video link is missing its YouTube video ID.")
        published_at = _parse_timestamp(str(link.get("published_at") or ""))
        if not published_at:
            raise ValueError("Published-video link has an invalid publication time.")

        store = self._history_store()
        now = datetime.now(timezone.utc)
        age_hours = max(0.0, (now - published_at).total_seconds() / 3600)
        # Analytics reports whole Pacific days, up to yesterday. A window is
        # due only once YouTube has reported every day in it (reportable_window,
        # which the collector plans with too).
        first_day = published_at.astimezone(_ANALYTICS_ZONE).date()
        analytics_end = now.astimezone(_ANALYTICS_ZONE).date() - timedelta(days=1)
        due = [
            (label, hours, days)
            for label, hours in _WINDOWS
            if (windows is None or label in windows)
            and (days := reportable_window(published_at, hours, now))
            and not store.has_snapshot_window(video_id, label)
            and (force or store.snapshot_retry_allowed(video_id, label))
        ]

        if not due and not collect_current:
            return {
                "video_id": video_id,
                "age_hours": round(age_hours, 1),
                "captured": [],
                "window_states": [store.snapshot_window_state(video_id, label) for label, _ in _WINDOWS],
                "current": store.current_performance_snapshot(video_id),
                "youtube": None,
                "message": "No scheduled snapshot window is due; no YouTube API call was made.",
            }

        connected = self._connection()
        if not connected or not connected[1]:
            # Without the channel id, ownership cannot be checked, so nothing is verified.
            raise ValueError("The connected channel is not identified yet. Refresh the channel, then try again.")
        verified_for = str(link.get("verified_channel_id") or "")
        if verified_for and verified_for != str(connected[1]):
            # Verified for another channel, for example on another device: it
            # is neither gone nor foreign, so its ownership stays as it is.
            raise LinkUnavailable(
                "This video is verified for another YouTube channel. Connect that channel to refresh its analytics."
            )
        credentials = self._fresh_credentials()
        try:
            youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
            analytics = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
            items = youtube.videos().list(
                part="snippet,statistics,contentDetails,status",
                id=video_id,
                maxResults=1,
            ).execute().get("items", [])
        except _UPSTREAM_ERRORS as exc:
            logger.warning("Linked-video refresh failed: %s", _describe(exc))
            raise _unavailable(exc) from exc
        link_id = int(link.get("id") or 0)
        if not items:
            # Deleted or private: stop collecting it instead of retrying it on every run.
            store.mark_link_ownership_failed(link_id)
            raise LinkUnavailable("The linked video is no longer available to the connected YouTube account.")
        metadata = _video_metadata(items[0], video_id, ownership_verified=True)
        if metadata.get("channel_id") != str(connected[1]):
            store.mark_link_ownership_failed(link_id)
            raise LinkUnavailable("This video does not belong to the connected YouTube channel.")
        store.update_linked_video_metadata(link_id, metadata)
        store.mark_link_ownership_verified(link_id, str(metadata.get("channel_id") or ""))

        analytics_current: dict[str, Any] = {}
        if collect_current and analytics_end >= first_day:
            try:
                analytics_current = self._query(
                    analytics, first_day, analytics_end, _VIDEO_METRICS, filters=f"video=={video_id}"
                )
            except _UPSTREAM_ERRORS as exc:
                logger.warning("Linked-video analytics are not ready yet: %s", _describe(exc))

        captured: list[dict[str, Any]] = []
        for label, hours, (start, end) in due:
            try:
                data = self._query(analytics, start, end, _VIDEO_METRICS, filters=f"video=={video_id}")
            except _UPSTREAM_ERRORS as exc:
                logger.warning("Linked-video %s snapshot remains retryable: %s", label, _describe(exc))
                if _outage(exc):
                    # YouTube or the network failed, not this request: trying
                    # again later must not use up the window's attempts.
                    store.postpone_snapshot_window(
                        video_id, label, failure_reason="analytics_request_failed", age_hours=age_hours
                    )
                    continue
                store.record_snapshot_attempt(
                    video_id,
                    label,
                    status="failed_retryable",
                    failure_reason="analytics_request_failed",
                    age_hours=age_hours,
                    source_start_date=start.isoformat(),
                    source_end_date=end.isoformat(),
                )
                continue
            if not data or data.get("views") is None:
                store.record_snapshot_attempt(
                    video_id,
                    label,
                    status="empty_retryable",
                    failure_reason="analytics_returned_no_rows",
                    age_hours=age_hours,
                    source_start_date=start.isoformat(),
                    source_end_date=end.isoformat(),
                )
                continue
            store.record_performance_snapshot(
                youtube_video_id=video_id,
                age_hours=hours,
                views=_optional_int(data.get("views")),
                watch_time_minutes=_optional_float(data.get("estimatedMinutesWatched")),
                avg_view_duration_seconds=_optional_float(data.get("averageViewDuration")),
                avg_view_percentage=_optional_float(data.get("averageViewPercentage")),
                likes=_optional_int(data.get("likes")),
                comments=_optional_int(data.get("comments")),
                shares=_optional_int(data.get("shares")),
                subscribers_gained=_optional_int(data.get("subscribersGained")),
                snapshot_window=label,
                snapshot_status="complete",
                source_start_date=start.isoformat(),
                source_end_date=end.isoformat(),
            )
            snapshot = store.completed_evidence_snapshot(video_id, label) or {}
            captured.append(snapshot)
            store.complete_due_experiment_snapshots(video_id, snapshot)
        if collect_current:
            store.record_performance_snapshot(
                youtube_video_id=video_id,
                age_hours=age_hours,
                views=_optional_int(metadata.get("view_count")),
                watch_time_minutes=_optional_float(analytics_current.get("estimatedMinutesWatched")),
                avg_view_duration_seconds=_optional_float(analytics_current.get("averageViewDuration")),
                avg_view_percentage=_optional_float(analytics_current.get("averageViewPercentage")),
                likes=_optional_int(metadata.get("like_count")),
                comments=_optional_int(metadata.get("comment_count")),
                shares=_optional_int(analytics_current.get("shares")),
                subscribers_gained=_optional_int(analytics_current.get("subscribersGained")),
                snapshot_window="current",
                replace_window=True,
            )
        return {
            "video_id": video_id,
            "age_hours": round(age_hours, 1),
            "captured": captured,
            "window_states": [store.snapshot_window_state(video_id, label) for label, _ in _WINDOWS],
            "current": store.current_performance_snapshot(video_id) or {},
            "youtube": metadata,
            "message": "Current YouTube metadata and available analytics were refreshed.",
        }

    def refresh_linked_video_public(self, link: dict[str, Any]) -> dict[str, Any]:
        """Refresh public metadata/counts without treating them as owner analytics."""

        video_id = str(link.get("youtube_video_id") or "")
        if not video_id:
            raise ValueError("Published-video link is missing its YouTube video ID.")
        metadata = self.verify_public_video(video_id)
        if metadata.get("metadata_source") == "unverified_id":
            raise YouTubeUnavailable(
                "Public YouTube metadata is temporarily unavailable. The saved link is unchanged.", status_code=503
            )
        store = self._history_store()
        store.update_linked_video_metadata(int(link.get("id") or 0), metadata)
        published_at = _parse_timestamp(str(link.get("published_at") or metadata.get("published_at") or ""))
        age_hours = max(0.0, (datetime.now(timezone.utc) - published_at).total_seconds() / 3600) if published_at else 0.0
        if any(metadata.get(field) is not None for field in ("view_count", "like_count", "comment_count")):
            store.record_performance_snapshot(
                youtube_video_id=video_id, age_hours=age_hours,
                views=_optional_int(metadata.get("view_count")), likes=_optional_int(metadata.get("like_count")),
                comments=_optional_int(metadata.get("comment_count")), snapshot_window="current",
                snapshot_status="display_only", replace_window=True,
            )
        return {
            "video_id": video_id, "age_hours": round(age_hours, 1), "captured": [],
            "current": store.current_performance_snapshot(video_id), "youtube": metadata,
            "data_scope": "public_metadata", "ownership_verified": bool(link.get("ownership_verified")),
            "private_analytics_available": False,
            "message": (
                "Public metadata and cumulative views, likes, and comments were refreshed. "
                "Reconnect the owning channel for impressions, CTR, watch time, retention, shares, and subscriber impact."
            ),
        }

    def _query(self, analytics, start: date, end: date, metrics: str, **kwargs: Any) -> dict[str, Any]:
        response = analytics.reports().query(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(), metrics=metrics, **kwargs).execute()
        headers = [item.get("name") for item in response.get("columnHeaders", [])]
        rows = response.get("rows", [])
        return dict(zip(headers, rows[0], strict=False)) if rows else {}

    def _flow(self, *, state: str, code_verifier: str) -> Flow:
        client_config = {
            "web": {
                "client_id": self.settings.youtube_oauth_client_id,
                "client_secret": self.settings.youtube_oauth_client_secret,
                "auth_uri": _AUTH_URI,
                "token_uri": _TOKEN_URI,
                "redirect_uris": [self.settings.youtube_oauth_redirect_uri],
            }
        }
        return Flow.from_client_config(
            client_config,
            scopes=_SCOPES,
            redirect_uri=self.settings.youtube_oauth_redirect_uri,
            state=state,
            code_verifier=code_verifier,
        )

    def _decrypt(self, encrypted: str) -> str:
        try:
            return Fernet(self.settings.oauth_token_encryption_key.encode()).decrypt(encrypted.encode()).decode()
        except (InvalidToken, AttributeError) as exc:
            raise ValueError("Saved channel token cannot be read. Disconnect and connect again.") from exc

    def _credentials(self) -> Credentials:
        record = self._connection()
        if not record:
            raise ValueError("No YouTube channel is connected.")
        return Credentials(token=None, refresh_token=self._decrypt(record[0]), token_uri=_TOKEN_URI, client_id=self.settings.youtube_oauth_client_id, client_secret=self.settings.youtube_oauth_client_secret, scopes=_SCOPES)

    def _fresh_credentials(self) -> Credentials:
        """Credentials with a new access token. A revoked grant raises RefreshError."""
        credentials = self._credentials()
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            if not getattr(exc, "retryable", False):
                raise
            logger.warning("Google's token service failed: %s", _describe(exc))
            raise YouTubeUnavailable("Google's sign-in service is not responding. Try again shortly.", status_code=503) from exc
        except TransportError as exc:
            logger.warning("Google's token service could not be reached: %s", _describe(exc))
            raise _unavailable(exc) from exc
        return credentials

    def _save_connection(self, refresh_token: str, channel_id: str, title: str) -> None:
        encrypted = Fernet(self.settings.oauth_token_encryption_key.encode()).encrypt(refresh_token.encode()).decode()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("INSERT INTO youtube_channel_connection (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at) VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET encrypted_refresh_token=excluded.encrypted_refresh_token, channel_id=excluded.channel_id, channel_title=excluded.channel_title, updated_at=excluded.updated_at", (encrypted, channel_id, title, now, now))

    def _update_connection_channel(self, channel_id: str, title: str) -> None:
        """Fill in the channel of a token-only connection, and keep its title current."""
        if not channel_id:
            return
        with self._connect() as connection:
            connection.execute(
                "UPDATE youtube_channel_connection SET channel_id = ?, channel_title = ?, updated_at = ? "
                "WHERE id = 1 AND (channel_id = '' OR channel_id = ?)",
                (channel_id, title, datetime.now(timezone.utc).isoformat(), channel_id),
            )

    def _save_sync(self, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES (?, ?)", (now, json.dumps(payload)))
            connection.execute(
                "DELETE FROM youtube_channel_syncs WHERE id NOT IN (SELECT id FROM youtube_channel_syncs ORDER BY id DESC LIMIT ?)",
                (_SYNCS_KEPT,),
            )

    def _connection(self):
        with self._connect() as connection:
            return connection.execute("SELECT encrypted_refresh_token, channel_id, channel_title, connected_at FROM youtube_channel_connection WHERE id = 1").fetchone()

    def _history_store(self):
        from win_engine.feedback.history_store import HistoryStore
        return HistoryStore(self.settings.database_path)

    def _connect(self):
        return connect_managed(self.settings.database_path, timeout=10)

    def _is_configured(self) -> bool:
        if not all((self.settings.youtube_oauth_client_id, self.settings.youtube_oauth_client_secret, self.settings.oauth_token_encryption_key)):
            return False
        try:
            Fernet(self.settings.oauth_token_encryption_key.encode())
            return True
        except (ValueError, TypeError):
            return False

    def _require_configured(self) -> None:
        if not self._is_configured():
            raise ValueError("YouTube OAuth is not configured. Check the local .env setup instructions.")


def _granted_scopes(credentials: Credentials, flow: Flow) -> set[str] | None:
    """The scopes Google actually granted, or None when the response doesn't say."""
    granted = getattr(credentials, "granted_scopes", None) or (flow.oauth2session.token or {}).get("scope")
    if not granted:
        return None
    return set(granted.split() if isinstance(granted, str) else granted)


def _ordered_upload_rows(
    playlist_items: list[dict[str, Any]],
    video_details: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join unordered videos.list results to uploads and return newest first."""
    details_by_id = {str(item.get("id") or ""): item for item in video_details if item.get("id")}
    rows: list[dict[str, Any]] = []
    for playlist_item in playlist_items:
        playlist_snippet = playlist_item.get("snippet") or {}
        content_details = playlist_item.get("contentDetails") or {}
        video_id = str(
            content_details.get("videoId")
            or (playlist_snippet.get("resourceId") or {}).get("videoId")
            or ""
        )
        if not video_id:
            continue
        detail = details_by_id.get(video_id) or {}
        snippet = detail.get("snippet") or playlist_snippet
        statistics = detail.get("statistics") or {}
        published_at = str(
            snippet.get("publishedAt")
            or content_details.get("videoPublishedAt")
            or playlist_snippet.get("publishedAt")
            or ""
        )
        rows.append({
            "video_id": video_id,
            "title": str(snippet.get("title") or playlist_snippet.get("title") or ""),
            "published_at": published_at,
            # Missing statistics (hidden likes, a failed details call) stay unknown.
            "views": _optional_int(statistics.get("viewCount")),
            "likes": _optional_int(statistics.get("likeCount")),
            "comments": _optional_int(statistics.get("commentCount")),
            # The uploads API carries no retention; only Analytics reports it.
            "averageViewPercentage": None,
        })
    rows.sort(key=lambda row: (str(row.get("published_at") or ""), str(row.get("video_id") or "")), reverse=True)
    return rows


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _video_metadata(item: dict[str, Any], video_id: str, *, ownership_verified: bool) -> dict[str, Any]:
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    content_details = item.get("contentDetails") or {}
    status = item.get("status") or {}
    thumbnails = snippet.get("thumbnails") or {}
    thumbnail = next(
        (str((thumbnails.get(size) or {}).get("url") or "") for size in ("maxres", "standard", "high", "medium", "default") if (thumbnails.get(size) or {}).get("url")),
        "",
    )
    return {
        "video_id": video_id,
        "channel_id": str(snippet.get("channelId") or ""),
        "channel_title": str(snippet.get("channelTitle") or ""),
        "title": str(snippet.get("title") or ""),
        "description": str(snippet.get("description") or ""),
        "tags": [str(tag) for tag in (snippet.get("tags") or [])],
        "category_id": str(snippet.get("categoryId") or ""),
        # Unknown stays unknown: "now" would shift every 24h/7d/28d window.
        "published_at": str(snippet.get("publishedAt") or "") or None,
        "duration": str(content_details.get("duration") or ""),
        "privacy_status": str(status.get("privacyStatus") or ""),
        "thumbnail_url": thumbnail,
        "view_count": _optional_int(statistics.get("viewCount")),
        "like_count": _optional_int(statistics.get("likeCount")),
        "comment_count": _optional_int(statistics.get("commentCount")),
        "ownership_verified": ownership_verified,
        "metadata_source": "youtube_data_api",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
