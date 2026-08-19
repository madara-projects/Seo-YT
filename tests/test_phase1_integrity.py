from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from win_engine.api import routes
from win_engine.core.config import Settings
from win_engine.core.schemas import LinkVideoRequest
from win_engine.feedback.channel_learning import learning_summary as channel_learning_summary
from win_engine.feedback.history_store import HistoryStore
from win_engine.integrations.youtube_channel import YouTubeChannelService


class Phase1IntegrityRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        self.store = HistoryStore(self.db_path)

    def tearDown(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    def _analysis_run(self, title: str = "Package title") -> int:
        with self.store._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title, payload_json) VALUES (?, ?, ?, ?)",
                (
                    "phase one regression",
                    datetime.now(timezone.utc).isoformat(),
                    title,
                    json.dumps({"title": title, "tags": ["phase one"]}),
                ),
            )
            return int(cursor.lastrowid)

    def _link(self, *, age_hours: float = 48.0, video_id: str = "phase1vid01") -> tuple[int, int]:
        run_id = self._analysis_run()
        link_id = self.store.link_published_video(
            run_id,
            video_id,
            (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat(),
            selected_title="Package title",
            format_val="youtube_shorts",
            language="english",
        )
        # The Phase 1 schema adds explicit ownership. Keep this regression test
        # runnable against both the pre-migration and migrated databases.
        with self.store._connect() as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(published_video_links)")}
            if "ownership_state" in columns:
                connection.execute(
                    """UPDATE published_video_links
                       SET ownership_state = 'verified', ownership_verified = 1,
                           verified_channel_id = 'owner-channel', ownership_verified_at = ?
                       WHERE id = ?""",
                    (datetime.now(timezone.utc).isoformat(), link_id),
                )
        return run_id, link_id

    def test_one_linked_video_is_one_cohort_sample_even_with_repeated_owned_snapshots(self):
        self._link(video_id="phase1vid01")
        now = datetime.now(timezone.utc).isoformat()
        with self.store._connect() as connection:
            connection.executemany(
                """INSERT INTO owned_video_snapshots
                   (video_id, captured_at, title, views, likes)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    ("phase1vid01", now, "Package title", 100, 4),
                    ("phase1vid01", now + "1", "Package title", 120, 5),
                    ("phase1vid01", now + "2", "Package title", 140, 6),
                ],
            )
        self.store.record_performance_snapshot(
            "phase1vid01", 24, views=100, likes=4,
            avg_view_percentage=70, snapshot_window="24h",
        )

        cohort = self.store.cohort_analytics(format_filter="youtube_shorts", language_filter="english")

        self.assertEqual(cohort["sample_size"], 1)
        self.assertEqual(cohort["total_linked"], 1)

    def test_foreign_video_ownership_fails_closed_without_public_fallback(self):
        settings = Settings(
            database_path=self.db_path,
            youtube_oauth_client_id="client",
            youtube_oauth_client_secret="secret",
            oauth_token_encryption_key="unused-in-mocked-test",
        )
        service = YouTubeChannelService(settings)
        youtube = MagicMock()
        youtube.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "foreignvid1",
                    "snippet": {
                        "channelId": "foreign-channel",
                        "title": "Foreign video",
                        "publishedAt": "2026-08-01T00:00:00Z",
                    },
                    "statistics": {"viewCount": "1"},
                    "contentDetails": {"duration": "PT10S"},
                }
            ]
        }
        credentials = MagicMock()

        with (
            patch.object(service, "_connection", return_value=("token", "owner-channel", "Owner", "now")),
            patch.object(service, "_credentials", return_value=credentials),
            patch("win_engine.integrations.youtube_channel.build", return_value=youtube),
            patch.object(
                service,
                "verify_public_video",
                return_value={
                    "video_id": "foreignvid1",
                    "published_at": "2026-08-01T00:00:00Z",
                    "ownership_verified": False,
                },
            ) as public_fallback,
        ):
            with self.assertRaisesRegex(ValueError, "belong|own|channel"):
                service.verify_owned_video("foreignvid1")

        public_fallback.assert_not_called()

    def test_public_video_helper_valid_id_fallback_is_non_ownership_evidence(self):
        service = YouTubeChannelService(
            Settings(
                database_path=self.db_path,
                youtube_api_key="",
                youtube_api_keys="",
            )
        )
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            metadata = service.verify_public_video("abcdefghijk")

        self.assertFalse(metadata["ownership_verified"])
        self.assertEqual(metadata["metadata_source"], "unverified_id")

    def test_link_route_does_not_write_when_ownership_verification_fails(self):
        run_id = self._analysis_run()
        settings = Settings(database_path=self.db_path)
        with (
            patch.object(routes, "get_settings", return_value=settings),
            patch.object(
                routes.YouTubeChannelService,
                "verify_owned_video",
                side_effect=ValueError("This video does not belong to the connected YouTube channel."),
            ),
        ):
            with self.assertRaises(HTTPException):
                routes.link_published_video(run_id, LinkVideoRequest(youtube_video_id="foreignvid1"))

        self.assertEqual(self.store.published_video_links_list(), [])

    def test_verified_link_persists_explicit_ownership_provenance(self):
        run_id = self._analysis_run()
        verified_at = datetime.now(timezone.utc).isoformat()
        self.store.link_published_video(
            run_id,
            "phase1vid01",
            "2026-08-01T00:00:00Z",
            ownership_state="verified",
            ownership_verified=True,
            verified_channel_id="owner-channel",
            ownership_verified_at=verified_at,
        )

        link = self.store.published_video_links_list()[0]
        self.assertEqual(link["ownership_state"], "verified")
        self.assertTrue(link["ownership_verified"])
        self.assertEqual(link["verified_channel_id"], "owner-channel")
        self.assertEqual(link["ownership_verified_at"], verified_at)

    def test_empty_scheduled_snapshot_does_not_consume_window(self):
        self.store.record_performance_snapshot(
            "phase1vid01",
            24,
            views=None,
            watch_time_minutes=None,
            avg_view_duration_seconds=None,
            avg_view_percentage=None,
            snapshot_window="24h",
        )

        self.assertFalse(self.store.has_snapshot_window("phase1vid01", "24h"))

    def test_failed_snapshot_attempt_is_observable_and_retryable(self):
        self.assertTrue(
            hasattr(self.store, "record_snapshot_attempt"),
            "Phase 1 requires observable retryable snapshot-attempt state.",
        )
        self.store.record_snapshot_attempt(
            "phase1vid01",
            "24h",
            status="failed_retryable",
            failure_reason="analytics_unavailable",
        )

        state = self.store.snapshot_window_state("phase1vid01", "24h")
        self.assertEqual(state["status"], "failed_retryable")
        self.assertGreaterEqual(state["attempt_count"], 1)
        self.assertFalse(self.store.has_snapshot_window("phase1vid01", "24h"))

    def test_current_only_snapshot_never_becomes_mature_learning_evidence(self):
        self._link(age_hours=72, video_id="phase1vid01")
        self.store.record_performance_snapshot(
            "phase1vid01",
            72,
            views=500,
            likes=20,
            avg_view_percentage=85,
            snapshot_window="current",
            replace_window=True,
        )

        learning = channel_learning_summary(self.db_path)

        self.assertEqual(learning["sample_size"], 0)
        self.assertEqual(learning["confidence"], "collecting")

    def test_unverified_video_never_becomes_learning_evidence(self):
        run_id = self._analysis_run()
        self.store.link_published_video(
            run_id,
            "unverified01",
            (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
            format_val="youtube_shorts",
            language="english",
        )
        self.store.record_performance_snapshot(
            "unverified01",
            24,
            views=5000,
            avg_view_percentage=95,
            snapshot_window="24h",
        )

        learning = channel_learning_summary(
            self.db_path,
            format_filter="youtube_shorts",
            language_filter="english",
        )
        cohort = self.store.cohort_analytics(
            format_filter="youtube_shorts",
            language_filter="english",
        )

        self.assertEqual(learning["sample_size"], 0)
        self.assertEqual(cohort["sample_size"], 0)
        self.assertEqual(cohort["excluded_count"], 1)

    def test_shared_evidence_policy_is_the_only_threshold_source(self):
        try:
            from win_engine.feedback.evidence_policy import evidence_level
        except ImportError as exc:  # Expected to fail on the pre-Phase-1 baseline.
            self.fail(f"Shared evidence policy is missing: {exc}")

        self.assertEqual(evidence_level(0).key, "display_only")
        self.assertEqual(evidence_level(4).key, "display_only")
        self.assertEqual(evidence_level(5).key, "early_signal")
        self.assertEqual(evidence_level(9).key, "early_signal")
        self.assertEqual(evidence_level(10).key, "moderate_evidence")
        self.assertEqual(evidence_level(19).key, "moderate_evidence")
        self.assertEqual(evidence_level(20).key, "strong_evidence")

    def test_history_deletion_removes_only_link_owned_dependents(self):
        run_id, _link_id = self._link(video_id="phase1vid01")
        self.store.record_performance_snapshot(
            "phase1vid01", 24, views=100, snapshot_window="24h"
        )
        self.store.record_package_experiment(
            "phase1vid01", old_title="Before", new_title="After"
        )
        with self.store._connect() as connection:
            connection.execute(
                """INSERT INTO owned_video_snapshots
                   (video_id, captured_at, title, views, likes)
                   VALUES (?, ?, ?, ?, ?)""",
                ("phase1vid01", datetime.now(timezone.utc).isoformat(), "Owned", 100, 1),
            )
            connection.execute(
                """INSERT INTO video_snapshots
                   (video_id, query, captured_at, view_count)
                   VALUES (?, ?, ?, ?)""",
                ("publicvid01", "public research", datetime.now(timezone.utc).isoformat(), 200),
            )

        self.assertTrue(self.store.delete_analysis_run(run_id))

        with self.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM published_video_links").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM video_performance_snapshots").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM package_experiments").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM owned_video_snapshots").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM video_snapshots").fetchone()[0], 1)

    def test_history_deletion_rolls_back_everything_when_a_child_delete_fails(self):
        run_id, _link_id = self._link(video_id="phase1vid01")
        self.store.record_performance_snapshot(
            "phase1vid01", 24, views=100, snapshot_window="24h"
        )
        self.store.record_package_experiment(
            "phase1vid01", old_title="Before", new_title="After"
        )
        with self.store._connect() as connection:
            connection.execute(
                """CREATE TRIGGER force_package_experiment_delete_failure
                   BEFORE DELETE ON package_experiments
                   BEGIN
                       SELECT RAISE(ABORT, 'forced deletion failure');
                   END"""
            )

        with self.assertRaises(sqlite3.IntegrityError):
            self.store.delete_analysis_run(run_id)

        with self.store._connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM published_video_links").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM video_performance_snapshots").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM package_experiments").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_foreign_keys_are_enabled_for_every_history_connection(self):
        with self.store._connect() as connection:
            enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(enabled, 1)


if __name__ == "__main__":
    unittest.main()
