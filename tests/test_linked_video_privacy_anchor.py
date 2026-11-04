"""A video's named windows measure its public life: nothing is collected while it is
private, and evidence measured from before it went public leaves learning."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore, window_covered_hours
from win_engine.integrations import youtube_channel
from win_engine.integrations.youtube_channel import YouTubeChannelService

PACIFIC = ZoneInfo("America/Los_Angeles")
UPLOADED = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
WENT_PUBLIC = datetime(2026, 8, 5, 10, 0, tzinfo=timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _clock(instant: datetime):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant if tz is None else instant.astimezone(tz)

    return Frozen


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _YouTube:
    """videos().list() answers from `state`, which a test changes as the video goes public."""

    def __init__(self, state: dict):
        self.state = state

    def videos(self):
        return self

    def list(self, **_kwargs):
        return _Request({"items": [{
            "snippet": {"channelId": "UC-owner", "title": "A title", "publishedAt": self.state["publishedAt"]},
            "statistics": {"viewCount": "0"},
            "status": {"privacyStatus": self.state["privacy"]},
        }]})


class _Analytics:
    """100 views for each public hour inside the requested Pacific days.

    Before the video is public, real Analytics may answer with a row of zeros or
    with no rows at all; `zero_rows` picks which.
    """

    def __init__(self):
        self.window_queries: list[dict] = []
        self.zero_rows = True

    def reports(self):
        return self

    def query(self, **kwargs):
        if kwargs.get("dimensions"):
            return _Request({"columnHeaders": [], "rows": []})
        self.window_queries.append(kwargs)
        start, end = date.fromisoformat(kwargs["startDate"]), date.fromisoformat(kwargs["endDate"])
        low = datetime(start.year, start.month, start.day, tzinfo=PACIFIC).astimezone(timezone.utc)
        high = (datetime(end.year, end.month, end.day, tzinfo=PACIFIC) + timedelta(days=1)).astimezone(timezone.utc)
        views = int(max(0.0, (high - max(low, WENT_PUBLIC)).total_seconds() / 3600) * 100)
        metrics = kwargs["metrics"].split(",")
        if not views and not self.zero_rows:
            return _Request({"columnHeaders": [{"name": name} for name in metrics], "rows": []})
        return _Request({"columnHeaders": [{"name": name} for name in metrics],
                         "rows": [[views if name == "views" else 0 for name in metrics]]})


class PrivateToPublicAnchorTests(unittest.TestCase):
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
        self.youtube = _YouTube({"publishedAt": _iso(UPLOADED), "privacy": "private"})
        self.analytics = _Analytics()
        run_id = self.store.record_analysis_run("query", "browse", "emotion", "Title", 7.0, "LOW", "WORKABLE", 50, {})
        # Linked while private: the owner's record dates it from the upload.
        self.link_id = self.store.link_published_video(
            run_id, "privatevid1", _iso(UPLOADED), ownership_state="verified", ownership_verified=True,
            verified_channel_id="UC-owner", ownership_verified_at=_iso(UPLOADED),
        )
        self.store.update_linked_video_metadata(self.link_id, self._owner_metadata())

    def _remove_database(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except FileNotFoundError:
                pass

    def _owner_metadata(self) -> dict:
        return {
            "title": "A title", "description": "", "tags": [], "channel_id": "UC-owner",
            "published_at": self.youtube.state["publishedAt"], "privacy_status": self.youtube.state["privacy"],
            "ownership_verified": True, "metadata_source": "youtube_data_api",
        }

    def _refresh(self, now: datetime, windows: list[str] | None = None) -> dict:
        link = self.store.published_video_link(self.link_id)
        with (
            patch.object(youtube_channel, "datetime", _clock(now)),
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch.object(youtube_channel, "build",
                         side_effect=lambda name, *_a, **_k: self.youtube if name == "youtube" else self.analytics),
        ):
            return self.service.refresh_linked_video_performance(link, collect_current=False, windows=windows)

    def _go_public(self) -> None:
        self.youtube.state.update(publishedAt=_iso(WENT_PUBLIC), privacy="public")

    def _windows(self) -> dict[str, list[dict]]:
        rows: dict[str, list[dict]] = {}
        for snapshot in self.store.performance_snapshots("privatevid1"):
            rows.setdefault(snapshot["snapshot_window"], []).append(snapshot)
        return rows

    def test_a_private_video_records_nothing_and_spends_no_attempt(self):
        # Four days after upload the 24-hour window from the upload is reportable.
        result = self._refresh(datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc))

        self.assertEqual(result["captured"], [])
        self.assertEqual(self.analytics.window_queries, [])
        self.assertEqual(self._windows(), {})
        self.assertEqual(self.store.snapshot_window_state("privatevid1", "24h")["attempt_count"], 0)

    def test_a_video_that_goes_public_is_measured_from_its_public_time(self):
        self._refresh(datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc))
        self._go_public()

        result = self._refresh(datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))

        self.assertEqual(self.store.published_video_link(self.link_id)["published_at"], WENT_PUBLIC.isoformat())
        self.assertEqual([item["snapshot_window"] for item in result["captured"]], ["24h", "7d"])
        day_one = self.store.completed_evidence_snapshot("privatevid1", "24h")
        self.assertEqual(day_one["source_start_date"], "2026-08-05")
        self.assertGreater(day_one["views"], 0)

    def test_empty_reports_while_private_cannot_use_up_the_public_window(self):
        # Analytics may answer a private video with no rows at all. An earlier
        # version spent one of the 24h window's five attempts on each answer.
        self.analytics.zero_rows = False
        for day in range(4, 10):
            self._refresh(datetime(2026, 8, day, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(self.store.snapshot_window_state("privatevid1", "24h")["attempt_count"], 0)
        self._go_public()

        result = self._refresh(datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))

        self.assertEqual([item["snapshot_window"] for item in result["captured"]], ["24h", "7d"])
        self.assertEqual(self.store.completed_evidence_snapshot("privatevid1", "24h")["source_start_date"], "2026-08-05")

    def test_a_window_retired_by_the_refresh_is_collected_again_in_the_same_call(self):
        # The sync brought the public time, so the collector planned only 7d:
        # this device's 0-view 24h window from the upload looked complete.
        self.store.record_performance_snapshot(
            "privatevid1", 24, views=0, snapshot_window="24h", snapshot_status="complete",
            source_start_date="2026-08-01", source_end_date="2026-08-02",
        )
        self._go_public()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE published_video_links SET published_at = ?, youtube_metadata_json = ? WHERE id = ?",
                (WENT_PUBLIC.isoformat(), json.dumps(self._owner_metadata()), self.link_id),
            )
        now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        planned = self.store.due_snapshot_links(now=now)
        self.assertEqual([item["due_windows"] for item in planned], [["7d"]])

        result = self._refresh(now, windows=planned[0]["due_windows"])

        self.assertEqual([item["snapshot_window"] for item in result["captured"]], ["24h", "7d"])
        self.assertEqual(self.store.completed_evidence_snapshot("privatevid1", "24h")["source_start_date"], "2026-08-05")
        self.assertEqual([row["views"] for row in self._windows()["pre_public_24h"]], [0])

    def test_a_window_measured_while_private_leaves_learning_and_is_collected_again(self):
        # What an earlier version stored: a 0-view 24h window from the upload.
        self.store.record_performance_snapshot(
            "privatevid1", 24, views=0, snapshot_window="24h", snapshot_status="complete",
            source_start_date="2026-08-01", source_end_date="2026-08-02",
        )
        self._go_public()

        self._refresh(datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))

        windows = self._windows()
        self.assertEqual(self.store.published_video_link(self.link_id)["published_at"], WENT_PUBLIC.isoformat())
        # Kept as history under a label no evidence reader asks for.
        self.assertEqual([(row["views"], row["source_start_date"]) for row in windows["pre_public_24h"]],
                         [(0, "2026-08-01")])
        self.assertFalse(windows["pre_public_24h"][0]["retry_allowed"])
        # The window itself is measured again from the public time.
        self.assertEqual(len(windows["24h"]), 1)
        self.assertEqual(windows["24h"][0]["snapshot_status"], "complete")
        self.assertEqual(windows["24h"][0]["source_start_date"], "2026-08-05")
        self.assertGreater(windows["24h"][0]["views"], 0)

    def test_a_window_from_before_a_synced_public_time_leaves_learning(self):
        # Another device moved the anchor and the sync brought the new time here,
        # while this device still holds its 0-view 24h window from the upload.
        self.store.record_performance_snapshot(
            "privatevid1", 24, views=0, snapshot_window="24h", snapshot_status="complete",
            source_start_date="2026-08-01", source_end_date="2026-08-02",
        )
        self._go_public()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE published_video_links SET published_at = ?, youtube_metadata_json = ? WHERE id = ?",
                (WENT_PUBLIC.isoformat(), json.dumps(self._owner_metadata()), self.link_id),
            )

        # Times already agree, so nothing moves; the stored range still says pre-public.
        self.store.update_linked_video_metadata(self.link_id, self._owner_metadata())
        self.assertEqual([(row["views"], row["source_start_date"]) for row in self._windows()["pre_public_24h"]],
                         [(0, "2026-08-01")])
        self.assertIsNone(self.store.completed_evidence_snapshot("privatevid1", "24h"))

        self._refresh(datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))
        day_one = self.store.completed_evidence_snapshot("privatevid1", "24h")
        self.assertEqual(day_one["source_start_date"], "2026-08-05")
        self.assertGreater(day_one["views"], 0)

    def test_a_move_within_the_same_pacific_day_keeps_the_windows_it_covers(self):
        self._go_public()
        self.store.update_linked_video_metadata(self.link_id, self._owner_metadata())
        self.store.record_performance_snapshot(
            "privatevid1", 24, views=2400, snapshot_window="24h", snapshot_status="complete",
            source_start_date="2026-08-05", source_end_date="2026-08-06",
        )
        self.store.record_performance_snapshot(
            "privatevid1", 168, views=9000, snapshot_window="7d", snapshot_status="complete",
            source_start_date="2026-08-05", source_end_date="2026-08-12",
        )
        with sqlite3.connect(self.db_path) as connection:
            # Hours stored from the old time on 24h; 7d has none, as legacy rows.
            connection.execute(
                "UPDATE video_performance_snapshots SET covered_hours = 99 WHERE snapshot_window = '24h'"
            )
        minutes_later = WENT_PUBLIC + timedelta(minutes=4)

        self.store.update_linked_video_metadata(
            self.link_id, {**self._owner_metadata(), "published_at": _iso(minutes_later)},
        )

        # The days are the same, so a new query would return the same numbers.
        self.assertEqual(self.store.published_video_link(self.link_id)["published_at"], minutes_later.isoformat())
        self.assertEqual(set(self._windows()), {"24h", "7d"})
        self.assertEqual(self.store.completed_evidence_snapshot("privatevid1", "24h")["views"], 2400)
        # Only the hours they cover follow the new time, where any were stored.
        with sqlite3.connect(self.db_path) as connection:
            stored_hours = dict(connection.execute(
                "SELECT snapshot_window, covered_hours FROM video_performance_snapshots"
            ).fetchall())
        self.assertEqual(stored_hours, {
            "24h": window_covered_hours(minutes_later.isoformat(), "2026-08-06"),
            "7d": None,
        })

    def test_a_move_that_changes_a_windows_last_day_retires_it(self):
        # Across the spring daylight-saving change, 24 hours after 22:00 PST on
        # 13 March is 23:00 on the 14th, but 24 hours after 23:30 PST is 00:30 on
        # the 15th: the move keeps the first Pacific day and changes the last.
        before = datetime(2027, 3, 14, 6, 0, tzinfo=timezone.utc)
        self._go_public()
        self.store.update_linked_video_metadata(self.link_id, {**self._owner_metadata(), "published_at": _iso(before)})
        self.store.record_performance_snapshot(
            "privatevid1", 24, views=2400, snapshot_window="24h", snapshot_status="complete",
            source_start_date="2027-03-13", source_end_date="2027-03-14",
        )

        self.store.update_linked_video_metadata(
            self.link_id, {**self._owner_metadata(), "published_at": _iso(before + timedelta(minutes=90))},
        )

        self.assertEqual(set(self._windows()), {"pre_public_24h"})

    def test_attempts_spent_while_private_are_returned_when_it_goes_public(self):
        # An earlier version spent all five attempts on empty reports while private.
        for _ in range(5):
            self.store.record_snapshot_attempt(
                "privatevid1", "24h", status="empty_retryable", failure_reason="analytics_returned_no_rows",
                source_start_date="2026-08-01", source_end_date="2026-08-02",
            )
        self.assertFalse(self.store.snapshot_retry_allowed("privatevid1", "24h"))
        self._go_public()

        self._refresh(datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc))

        day_one = self.store.completed_evidence_snapshot("privatevid1", "24h")
        self.assertIsNotNone(day_one)
        self.assertEqual(day_one["source_start_date"], "2026-08-05")
        self.assertNotIn("pre_public_24h", self._windows())

    def test_a_video_public_before_its_first_window_is_due_is_collected_normally(self):
        self._go_public()

        result = self._refresh(datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc))

        self.assertEqual(self.store.published_video_link(self.link_id)["published_at"], WENT_PUBLIC.isoformat())
        self.assertEqual([item["snapshot_window"] for item in result["captured"]], ["24h"])
        self.assertEqual(result["captured"][0]["source_start_date"], "2026-08-05")
        self.assertEqual(set(self._windows()), {"24h"})

    def test_measured_windows_move_only_for_the_owners_record_of_a_public_video(self):
        self.store.record_performance_snapshot("privatevid1", 24, views=10, snapshot_window="24h")
        later = {**self._owner_metadata(), "published_at": _iso(WENT_PUBLIC)}

        def anchor() -> datetime:
            return datetime.fromisoformat(self.store.published_video_link(self.link_id)["published_at"].replace("Z", "+00:00"))

        # Still private, then a public lookup that cannot see the owner's record.
        self.store.update_linked_video_metadata(self.link_id, later)
        self.store.update_linked_video_metadata(
            self.link_id, {**later, "privacy_status": "public", "ownership_verified": False},
        )
        self.assertEqual(anchor(), UPLOADED)
        self.assertEqual(set(self._windows()), {"24h"})

        # Those lookups already stored the later time; the owner's public record still moves it.
        self.store.update_linked_video_metadata(self.link_id, {**later, "privacy_status": "public"})
        self.assertEqual(anchor(), WENT_PUBLIC)
        self.assertEqual(set(self._windows()), {"pre_public_24h"})

    def test_a_private_video_waits_its_turn_in_the_collector(self):
        now = datetime.now(timezone.utc)
        self.store.update_linked_video_metadata(self.link_id, self._owner_metadata())

        # Just checked and still private: it cools down like a failed attempt.
        self.assertEqual(self.store.due_snapshot_links(now=now, retry_cooldown_seconds=3600), [])
        due = self.store.due_snapshot_links(now=now + timedelta(hours=2), retry_cooldown_seconds=3600)
        self.assertEqual([item["youtube_video_id"] for item in due], ["privatevid1"])


class MetadataObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.store = HistoryStore(os.path.join(self.dir.name, "observations.db"))
        run_id = self.store.record_analysis_run("query", "browse", "emotion", "Title", 7.0, "LOW", "WORKABLE", 50, {})
        self.link_id = self.store.link_published_video(run_id, "observedvid", "2026-08-01T00:00:00Z")

    def _update(self, **fields) -> None:
        metadata = {"title": "First", "tags": ["a"], "description": "d", "published_at": "2026-08-01T00:00:00Z",
                    "metadata_source": "youtube_data_api", **fields}
        self.store.update_linked_video_metadata(self.link_id, metadata)

    def _observations(self) -> list[dict]:
        return self.store.published_video_link(self.link_id)["youtube_metadata"]["observations"]

    def test_an_observation_is_added_on_the_first_write_and_on_each_change(self):
        self._update(fetched_at="2026-08-01T01:00:00+00:00")
        self._update(fetched_at="2026-08-02T01:00:00+00:00")
        self._update(title="Second", fetched_at="2026-08-03T01:00:00+00:00")
        # A partial lookup keeps the fields it cannot see, so nothing changed.
        self.store.update_linked_video_metadata(
            self.link_id, {"title": "Second", "tags": None, "description": None, "metadata_source": "oembed"},
        )

        self.assertEqual(self._observations(), [
            {"observed_at": "2026-08-01T01:00:00+00:00", "title": "First", "tags": ["a"], "description": "d"},
            {"observed_at": "2026-08-03T01:00:00+00:00", "title": "Second", "tags": ["a"], "description": "d"},
        ])

    def test_only_the_latest_twenty_observations_are_kept(self):
        for number in range(25):
            self._update(description=f"edit {number}")

        observations = self._observations()
        self.assertEqual(len(observations), 20)
        self.assertEqual(observations[0]["description"], "edit 5")
        self.assertEqual(observations[-1]["description"], "edit 24")


if __name__ == "__main__":
    unittest.main()
