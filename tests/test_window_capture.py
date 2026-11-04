"""A completed window keeps the hours it covers and the uploaded metadata seen when it was captured."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import httplib2
from cryptography.fernet import Fernet
from googleapiclient.errors import HttpError

from win_engine.core.config import Settings
from win_engine.feedback.history_store import HistoryStore, window_covered_hours
from win_engine.integrations.youtube_channel import YouTubeChannelService

BUILD = "win_engine.integrations.youtube_channel.build"
PUBLISHED = "2026-08-01T00:00:00+00:00"  # 17:00 on 31 July, Pacific
SNIPPET = {
    "channelId": "UC-owner", "publishedAt": "2026-08-01T00:00:00Z", "title": "Uploaded title",
    "tags": ["first tag", "second tag"], "description": "Uploaded description",
}


def _http_error(status: int, reason: str) -> HttpError:
    body = json.dumps({"error": {"code": status, "message": reason, "errors": [{"reason": reason}]}}).encode()
    return HttpError(httplib2.Response({"status": status}), body, uri="https://youtubeanalytics.googleapis.com/v2/reports")


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = str(Path(self.dir.name) / "capture.db")
        self.settings = Settings(
            database_path=self.path, youtube_api_key="", youtube_api_keys="",
            youtube_oauth_client_id="client-id", youtube_oauth_client_secret="client-secret",
            oauth_token_encryption_key=Fernet.generate_key().decode(),
            snapshot_collector_enabled=True, snapshot_collector_dry_run=False,
        )
        self.store = HistoryStore(self.path)

    def link(self, video_id: str, published_at: str = PUBLISHED) -> dict:
        run_id = self.store.record_analysis_run(video_id, "search", "tutorial", video_id, 7.0, "LOW", "WORKABLE", 50, {})
        link_id = self.store.link_published_video(
            run_id, video_id, published_at, format_val="tutorial", language="english", ownership_state="verified",
            ownership_verified=True, verified_channel_id="UC-owner", ownership_verified_at=published_at,
        )
        return self.store.published_video_link(link_id) or {}

    def window(self, video_id: str, window: str = "24h") -> dict:
        rows = [item for item in self.store.performance_snapshots(video_id) if item["snapshot_window"] == window]
        self.assertEqual(len(rows), 1)
        return rows[0]


class RefreshCaptureTests(Base):
    def setUp(self) -> None:
        super().setUp()
        self.service = YouTubeChannelService(self.settings)
        self.service._save_connection("refresh", "UC-owner", "Owner")

    def refresh(self, link: dict, *, snippet: dict | None = None, query=None):
        youtube = MagicMock()
        youtube.videos.return_value.list.return_value.execute.return_value = {"items": [{
            "snippet": snippet or SNIPPET, "statistics": {}, "status": {"privacyStatus": "public"},
        }]}
        query = query or {"return_value": {"views": 100}}
        with (
            patch.object(self.service, "_fresh_credentials", return_value=MagicMock()),
            patch(BUILD, side_effect=[youtube, MagicMock()]),
            patch.object(self.service, "_query", **query),
            patch.object(self.service, "_query_rows", return_value=[]),
        ):
            return self.service.refresh_linked_video_performance(link, collect_current=False, windows=["24h"])

    def test_a_completed_window_stores_its_coverage_and_the_metadata_it_was_captured_with(self):
        link = self.link("capturevid1")
        result = self.refresh(link)

        stored = self.store.completed_evidence_snapshot("capturevid1", "24h")
        self.assertEqual((stored["source_start_date"], stored["source_end_date"]), ("2026-07-31", "2026-08-01"))
        # Published at 17:00 Pacific; the range ends at the Pacific midnight after 1 August: 31 hours.
        self.assertEqual(stored["covered_hours"], 31.0)
        self.assertEqual(stored["covered_hours"], window_covered_hours(link["published_at"], stored["source_end_date"]))
        metadata = stored["uploaded_metadata"]
        self.assertEqual(
            {key: metadata[key] for key in ("title", "tags", "description", "published_at", "privacy_status")},
            {"title": "Uploaded title", "tags": ["first tag", "second tag"], "description": "Uploaded description",
             "published_at": "2026-08-01T00:00:00Z", "privacy_status": "public"},
        )
        # When it was fetched, as an ISO-8601 time with its zone.
        self.assertIsNotNone(datetime.fromisoformat(metadata["observed_at"]).tzinfo)
        # The refresh answers with the same stored window.
        self.assertEqual(result["captured"][0]["covered_hours"], 31.0)
        self.assertEqual(result["captured"][0]["uploaded_metadata"], metadata)

    def test_a_video_without_tags_or_description_is_stored_as_known_empty_not_unknown(self):
        self.refresh(self.link("capturevid2"), snippet={"channelId": "UC-owner", "publishedAt": "2026-08-01T00:00:00Z",
                                                         "title": "Only a title"})
        metadata = self.store.completed_evidence_snapshot("capturevid2", "24h")["uploaded_metadata"]
        self.assertEqual((metadata["title"], metadata["tags"], metadata["description"]), ("Only a title", [], ""))

    def test_failed_and_empty_attempts_claim_no_coverage_or_metadata(self):
        for video_id, query, status in (
            ("capturevid3", {"return_value": {}}, "empty_retryable"),
            ("capturevid4", {"side_effect": _http_error(400, "badRequest")}, "failed_retryable"),
        ):
            with self.subTest(status=status):
                self.refresh(self.link(video_id), query=query)
                row = self.window(video_id)
                self.assertEqual(row["snapshot_status"], status)
                self.assertIsNone(row["covered_hours"])
                self.assertIsNone(row["uploaded_metadata"])
                self.assertIsNone(self.store.completed_evidence_snapshot(video_id, "24h"))

    def test_a_window_completed_after_a_failed_attempt_gains_its_coverage(self):
        link = self.link("capturevid5")
        self.refresh(link, query={"side_effect": _http_error(400, "badRequest")})
        self.refresh(link)
        row = self.window("capturevid5")
        self.assertEqual((row["snapshot_status"], row["covered_hours"]), ("complete", 31.0))
        self.assertEqual(row["uploaded_metadata"]["title"], "Uploaded title")

    def test_coverage_is_counted_from_the_publish_time_the_refresh_moved_the_link_to(self):
        # Linked at the upload, two days before the video went public: the
        # refresh takes YouTube's publish time and measures the window from it.
        link = self.link("capturevid6", "2026-07-30T00:00:00+00:00")
        self.store.update_linked_video_metadata(int(link["id"]), {
            "title": "Uploaded title", "channel_id": "UC-owner", "published_at": "2026-07-30T00:00:00+00:00",
            "metadata_source": "youtube_data_api",
        })
        self.refresh(self.store.published_video_link(int(link["id"])) or {})

        self.assertEqual(self.store.published_video_link(int(link["id"]))["published_at"], PUBLISHED)
        stored = self.store.completed_evidence_snapshot("capturevid6", "24h")
        self.assertEqual((stored["source_start_date"], stored["source_end_date"]), ("2026-07-31", "2026-08-01"))
        # 31 hours from the publish time, not the 79 from the upload.
        self.assertEqual(stored["covered_hours"], 31.0)


class StoreTests(Base):
    METADATA = {"title": "T", "tags": None, "description": None, "published_at": None, "privacy_status": None,
                "observed_at": "2026-08-03T10:00:00+00:00"}

    def test_coverage_is_counted_from_the_time_the_window_was_measured_from(self):
        self.link("storevid1")
        self.store.record_performance_snapshot(
            "storevid1", 24, views=10, snapshot_window="24h", source_start_date="2026-08-01",
            source_end_date="2026-08-02", measured_from="2026-08-01T19:00:00+00:00", uploaded_metadata=self.METADATA,
        )
        row = self.window("storevid1")
        # 12:00 Pacific on 1 August to the Pacific midnight after 2 August: 36 hours, not the link's 55.
        self.assertEqual(row["covered_hours"], 36.0)
        # Unknown values stay null, as given.
        self.assertEqual(row["uploaded_metadata"], self.METADATA)

    def test_only_a_completed_named_window_claims_coverage(self):
        self.link("storevid2")
        for window, views, status in (("24h", None, None), ("7d", None, "empty_retryable"), ("current", 40, None)):
            with self.subTest(window=window):
                self.store.record_performance_snapshot(
                    "storevid2", 24, views=views, snapshot_window=window, snapshot_status=status,
                    source_start_date="2026-07-31", source_end_date="2026-08-01",
                    measured_from=PUBLISHED, uploaded_metadata=self.METADATA,
                )
                row = self.window("storevid2", window)
                self.assertNotEqual(row["snapshot_status"], "complete")
                self.assertIsNone(row["covered_hours"])
                self.assertIsNone(row["uploaded_metadata"])

    def test_a_completed_window_is_not_rewritten_by_a_later_capture(self):
        self.link("storevid3")
        for title in ("First", "Second"):
            self.store.record_performance_snapshot(
                "storevid3", 24, views=10, snapshot_window="24h", source_start_date="2026-07-31",
                source_end_date="2026-08-01", measured_from=PUBLISHED, uploaded_metadata={**self.METADATA, "title": title},
            )
        self.assertEqual(self.window("storevid3")["uploaded_metadata"]["title"], "First")

    def test_metadata_that_cannot_be_encoded_raw_does_not_lose_the_window(self):
        self.link("storevid5")
        # A lone surrogate (a JSON escape can decode to one) is not valid UTF-8.
        description = "Broken \ud800 text"
        self.store.record_performance_snapshot(
            "storevid5", 24, views=10, snapshot_window="24h", source_start_date="2026-07-31",
            source_end_date="2026-08-01", measured_from=PUBLISHED,
            uploaded_metadata={**self.METADATA, "description": description},
        )
        row = self.window("storevid5")
        self.assertEqual((row["snapshot_status"], row["views"]), ("complete", 10))
        self.assertEqual(row["uploaded_metadata"]["description"], description)

    def test_legacy_rows_still_read_with_unknown_coverage_and_metadata(self):
        self.link("storevid4")
        # Written as before version 13: neither value given.
        self.store.record_performance_snapshot(
            "storevid4", 24, views=55, snapshot_window="24h", source_start_date="2026-07-31", source_end_date="2026-08-01",
        )
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """INSERT INTO video_performance_snapshots(youtube_video_id, age_hours, views, snapshot_window,
                       snapshot_status, captured_at, metadata_json, covered_hours)
                   VALUES ('storevid4', 168, 90, '7d', 'complete', '2026-08-09T00:00:00+00:00', NULL, NULL)"""
            )
        for window, views in (("24h", 55), ("7d", 90)):
            with self.subTest(window=window):
                row = self.store.completed_evidence_snapshot("storevid4", window)
                self.assertEqual((row["views"], row["covered_hours"], row["uploaded_metadata"]), (views, None, None))


if __name__ == "__main__":
    unittest.main()
