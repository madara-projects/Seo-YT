"""Read-only OAuth connection and reporting for the creator's YouTube channel."""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from win_engine.core.config import Settings
from win_engine.feedback.channel_learning import learning_summary, save_video_snapshots

_SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]
_PENDING_STATES: dict[str, float] = {}
_OAUTH_STATE_TTL_SECONDS = 600


class YouTubeChannelService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Reuse the existing database initializer before reading connection tables.
        from win_engine.feedback.history_store import HistoryStore
        HistoryStore(settings.database_path)

    def status(self) -> dict[str, Any]:
        record = self._connection()
        configured = self._is_configured()
        latest = self._latest_sync()
        return {
            "configured": configured,
            "connected": bool(record),
            "channel": {"id": record[1], "title": record[2], "connected_at": record[3]} if record else None,
            "latest_sync": latest,
            "setup_message": None if configured else "Add YouTube OAuth client credentials and an encryption key to .env to connect your channel.",
        }

    def authorization_url(self) -> str:
        self._require_configured()
        state = secrets.token_urlsafe(32)
        _PENDING_STATES.clear()
        _PENDING_STATES[state] = time.time() + _OAUTH_STATE_TTL_SECONDS
        flow = self._flow(state=state)
        url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
        return url

    def complete_authorization(self, *, code: str, state: str) -> dict[str, Any]:
        self._require_configured()
        expires_at = _PENDING_STATES.pop(state, None)
        if not expires_at or time.time() > expires_at:
            raise ValueError("The connection request expired. Start the connection again.")
        flow = self._flow(state=state)
        flow.fetch_token(code=code)
        credentials = flow.credentials
        if not credentials.refresh_token:
            raise ValueError("Google did not return a refresh token. Disconnect this app in Google Account permissions and connect again.")
        data = build("youtube", "v3", credentials=credentials, cache_discovery=False).channels().list(
            part="snippet", mine=True, maxResults=1
        ).execute()
        item = (data.get("items") or [{}])[0]
        self._save_connection(credentials.refresh_token, str(item.get("id") or ""), str((item.get("snippet") or {}).get("title") or ""))
        try:
            return self.refresh()
        except HttpError as exc:
            # OAuth is already complete and the encrypted token is safely stored.
            # API enablement can take a few minutes, so do not turn that into a
            # failed connection or force the creator to authorize again.
            return {"connected": True, "sync_pending": True, "sync_error": str(exc)}

    def disconnect(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM youtube_channel_connection WHERE id = 1")

    def refresh(self) -> dict[str, Any]:
        credentials = self._credentials()
        credentials.refresh(Request())
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        analytics = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
        channel_item = (youtube.channels().list(part="snippet,statistics", mine=True, maxResults=1).execute().get("items") or [{}])[0]
        today = date.today()
        start = today - timedelta(days=28)
        previous_start = today - timedelta(days=56)
        metrics = "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,likes,comments"
        current = self._query(analytics, start, today - timedelta(days=1), metrics)
        previous = self._query(analytics, previous_start, start - timedelta(days=1), metrics)
        videos = self._query(analytics, start, today - timedelta(days=1), "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained", dimensions="video", sort="-views", maxResults=10)
        video_rows = self._enrich_videos(youtube, videos.get("rows", []))
        save_video_snapshots(self.settings.database_path, video_rows)
        payload = {
            "channel": {"id": channel_item.get("id"), "title": (channel_item.get("snippet") or {}).get("title"), "subscribers": (channel_item.get("statistics") or {}).get("subscriberCount")},
            "period": {"start": start.isoformat(), "end": (today - timedelta(days=1)).isoformat()},
            "current_28_days": current,
            "previous_28_days": previous,
            "top_videos": {"rows": video_rows},
            "video_learning": learning_summary(self.settings.database_path),
        }
        self._save_sync(payload)
        return payload

    def verify_owned_video(self, youtube_video_id: str) -> dict[str, Any]:
        """Verify that an exact video belongs to the connected channel before linking it."""
        credentials = self._credentials()
        credentials.refresh(Request())
        youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        channel = self._connection()
        if not channel or not channel[1]:
            raise ValueError("Connect a YouTube channel before linking a video.")
        items = youtube.videos().list(part="snippet", id=youtube_video_id, maxResults=1).execute().get("items", [])
        if not items:
            raise ValueError("That video could not be found on YouTube.")
        snippet = items[0].get("snippet") or {}
        if str(snippet.get("channelId") or "") != str(channel[1]):
            raise ValueError("That video does not belong to the connected YouTube channel.")
        return {
            "video_id": youtube_video_id,
            "title": str(snippet.get("title") or ""),
            "published_at": str(snippet.get("publishedAt") or ""),
        }

    def refresh_linked_video_performance(self, link: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
        """Capture only due 24-hour, 7-day, and 28-day analytics snapshots.

        This is intentionally manual: a laptop cannot collect data while it is off.
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
        windows = (("24h", 24.0), ("7d", 24.0 * 7), ("28d", 24.0 * 28))
        due = [(label, hours) for label, hours in windows if age_hours >= hours and (force or not store.has_snapshot_window(video_id, label))]
        if not due:
            return {"video_id": video_id, "age_hours": round(age_hours, 1), "captured": [], "message": "No new scheduled snapshot is due yet."}

        credentials = self._credentials()
        credentials.refresh(Request())
        analytics = build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)
        captured: list[dict[str, Any]] = []
        for label, hours in due:
            end = min(now.date() - timedelta(days=1), (published_at + timedelta(hours=hours)).date())
            start = published_at.date()
            if end < start:
                continue
            metrics = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained"
            data = self._query(analytics, start, end, metrics, filters=f"video=={video_id}")
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
            )
            snapshot = store.latest_performance_snapshot(video_id) or {}
            captured.append(snapshot)
            store.complete_due_experiment_snapshots(video_id, snapshot)
        return {"video_id": video_id, "age_hours": round(age_hours, 1), "captured": captured}

    def _query(self, analytics, start: date, end: date, metrics: str, **kwargs: Any) -> dict[str, Any]:
        response = analytics.reports().query(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(), metrics=metrics, **kwargs).execute()
        headers = [item.get("name") for item in response.get("columnHeaders", [])]
        rows = response.get("rows", [])
        if kwargs.get("dimensions"):
            return {"rows": [dict(zip(headers, row)) for row in rows]}
        return dict(zip(headers, rows[0])) if rows else {}

    def _enrich_videos(self, youtube, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = [str(row.get("video") or "") for row in rows if row.get("video")]
        details = youtube.videos().list(part="snippet", id=",".join(ids), maxResults=50).execute().get("items", []) if ids else []
        metadata = {item.get("id"): item.get("snippet") or {} for item in details}
        return [{**row, "video_id": row.get("video"), "title": metadata.get(row.get("video"), {}).get("title"), "published_at": metadata.get(row.get("video"), {}).get("publishedAt")} for row in rows]

    def _flow(self, state: str) -> Flow:
        return Flow.from_client_config({"web": {"client_id": self.settings.youtube_oauth_client_id, "client_secret": self.settings.youtube_oauth_client_secret, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [self.settings.youtube_oauth_redirect_uri]}}, scopes=_SCOPES, redirect_uri=self.settings.youtube_oauth_redirect_uri, state=state)

    def _credentials(self) -> Credentials:
        record = self._connection()
        if not record:
            raise ValueError("No YouTube channel is connected.")
        try:
            refresh_token = Fernet(self.settings.oauth_token_encryption_key.encode()).decrypt(record[0].encode()).decode()
        except (InvalidToken, AttributeError) as exc:
            raise ValueError("Saved channel token cannot be read. Disconnect and connect again.") from exc
        return Credentials(token=None, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token", client_id=self.settings.youtube_oauth_client_id, client_secret=self.settings.youtube_oauth_client_secret, scopes=_SCOPES)

    def _save_connection(self, refresh_token: str, channel_id: str, title: str) -> None:
        encrypted = Fernet(self.settings.oauth_token_encryption_key.encode()).encrypt(refresh_token.encode()).decode()
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("INSERT INTO youtube_channel_connection (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at) VALUES (1, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET encrypted_refresh_token=excluded.encrypted_refresh_token, channel_id=excluded.channel_id, channel_title=excluded.channel_title, updated_at=excluded.updated_at", (encrypted, channel_id, title, now, now))

    def _save_sync(self, payload: dict[str, Any]) -> None:
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES (?, ?)", (now, json.dumps(payload)))

    def _latest_sync(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT synced_at, payload_json FROM youtube_channel_syncs ORDER BY id DESC LIMIT 1").fetchone()
        return {"synced_at": row[0], "data": json.loads(row[1])} if row else None

    def _connection(self):
        with self._connect() as connection:
            return connection.execute("SELECT encrypted_refresh_token, channel_id, channel_title, connected_at FROM youtube_channel_connection WHERE id = 1").fetchone()

    def _history_store(self):
        from win_engine.feedback.history_store import HistoryStore
        return HistoryStore(self.settings.database_path)

    def _connect(self):
        return sqlite3.connect(self.settings.database_path)

    def _is_configured(self) -> bool:
        if not all((self.settings.youtube_oauth_client_id, self.settings.youtube_oauth_client_secret, self.settings.oauth_token_encryption_key)):
            return False
        try:
            Fernet(self.settings.oauth_token_encryption_key.encode())
            return True
        except Exception:
            return False

    def _require_configured(self) -> None:
        if not self._is_configured():
            raise ValueError("YouTube OAuth is not configured. Check the local .env setup instructions.")


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
