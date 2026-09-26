"""A pull applies every cloud row it can, skips only the rows it cannot, and never loses a deletion."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from win_engine.core.config import Settings
from win_engine.feedback.audit_experiment_store import AuditExperimentStore
from win_engine.feedback.cloud_sync import CloudSyncService, _hash
from win_engine.feedback.history_store import HistoryStore

UPDATED_AT = "2026-08-28T10:00:00+00:00"


class _PullCursor:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def execute(self, _sql, _params=None): return None
    def fetchall(self): return self.rows


class _PullRemote:
    def __init__(self, rows): self.rows = rows
    def cursor(self): return _PullCursor(self.rows)


class CloudPullTests(unittest.TestCase):
    def setUp(self):
        self.source_store, self.source = self._device("device-a")
        self.store, self.service = self._device("device-b")

    def _device(self, name):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self.addCleanup(self._remove, handle.name)
        store = HistoryStore(handle.name)
        service = CloudSyncService(Settings(
            database_path=handle.name, cloud_sync_enabled=True, cloud_sync_device_id=name,
            cloud_sync_host="mysql.example", cloud_sync_database="seo_yt_sync", cloud_sync_user="app",
            cloud_sync_password="not-used", cloud_sync_ssl_ca_path=__file__,
        ))
        return store, service

    @staticmethod
    def _remove(path):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(path + suffix)
            except FileNotFoundError:
                pass

    def _source_package(self, query, video_id=None):
        run_id = self.source_store.record_analysis_run(query, "browse", "emotion", query.title(), 7.0, "LOW",
                                                       "WORKABLE", 50, {"d": query})
        if video_id:
            self.source_store.link_published_video(run_id, video_id, "2026-08-01T10:00:00+00:00")
            self.source_store.record_performance_snapshot(video_id, 24, views=300, snapshot_window="24h")
        self.source._stage_local_packages()
        return run_id

    def _remote_row(self, run_id, *, revision=1, mutate=None, updated_at=UPDATED_AT):
        with sqlite3.connect(self.source_store.database_path) as connection:
            payload = self.source._package_payload(connection, run_id)
            sync_uuid = connection.execute(
                "SELECT sync_uuid FROM cloud_sync_packages WHERE analysis_run_id=?", (run_id,)
            ).fetchone()[0]
        if mutate:
            mutate(payload)
        return (sync_uuid, "device-a", revision, _hash(payload), json.dumps(payload), updated_at, None)

    def _query(self, sql, params=()):
        with sqlite3.connect(self.store.database_path) as connection:
            return connection.execute(sql, params).fetchall()

    def test_a_row_this_version_cannot_apply_is_skipped_and_the_rest_still_apply(self):
        bad = self._source_package("bad package", video_id="video-bad")
        good = self._source_package("good package")
        rows = [
            self._remote_row(bad, mutate=lambda p: p["linked_video"].update(ownership_state="owner_confirmed")),
            self._remote_row(good),
        ]

        with self.assertLogs("win_engine.feedback.cloud_sync", level="WARNING") as logs:
            pulled = self.service._pull(_PullRemote(rows))

        self.assertEqual(pulled, 1)
        self.assertEqual(self.service._last_pull_skipped, 1)
        self.assertEqual(self._query("SELECT query FROM analysis_runs"), [("good package",)])
        self.assertIn(rows[0][0][:8], logs.output[0])

    def test_a_skipped_row_leaves_the_package_and_its_link_untouched(self):
        run_id = self._source_package("linked package", video_id="video-old")
        self.assertEqual(self.service._pull(_PullRemote([self._remote_row(run_id)])), 1)
        link_id = self._query("SELECT id FROM published_video_links")[0][0]
        AuditExperimentStore(self.store).refresh_audit(link_id)

        def relink_with_unknown_state(payload):
            payload["linked_video"].update(youtube_video_id="video-new", ownership_state="owner_confirmed")

        pulled = self.service._pull(_PullRemote([self._remote_row(run_id, revision=2, mutate=relink_with_unknown_state)]))

        self.assertEqual(pulled, 0)
        self.assertEqual(self._query("SELECT id, youtube_video_id FROM published_video_links"), [(link_id, "video-old")])
        self.assertEqual(self._query("SELECT COUNT(*) FROM published_video_audits"), [(1,)])
        self.assertEqual(self._query("PRAGMA foreign_key_check"), [])

    def test_an_unknown_snapshot_status_skips_only_that_snapshot(self):
        run_id = self._source_package("observed package", video_id="video-1")

        def add_future_snapshot(payload):
            payload["linked_video"]["snapshots"].append(
                {"snapshot_window": "7d", "snapshot_status": "archived_v2", "views": 9, "captured_at": UPDATED_AT})

        self.assertEqual(self.service._pull(_PullRemote([self._remote_row(run_id, mutate=add_future_snapshot)])), 1)

        self.assertEqual(self._query("SELECT snapshot_window, views FROM video_performance_snapshots"), [("24h", 300)])

    def test_a_missing_creation_time_falls_back_and_a_selection_without_an_id_is_refused(self):
        dated = self._source_package("undated package")
        selected = self._source_package("selected package")
        rows = [
            self._remote_row(dated, mutate=lambda p: p["analysis"].update(created_at=None)),
            self._remote_row(selected, mutate=lambda p: p.update(selection={"package": {"title": "t"}})),
        ]

        self.assertEqual(self.service._pull(_PullRemote(rows)), 1)

        self.assertEqual(self._query("SELECT query, created_at FROM analysis_runs"), [("undated package", UPDATED_AT)])
        self.assertEqual(self.service._last_pull_skipped, 1)

    def test_a_pushed_delete_that_the_cloud_never_applied_is_queued_again(self):
        run_id = self._source_package("shared package")
        self.service._pull(_PullRemote([self._remote_row(run_id)]))
        local_run = self._query("SELECT id FROM analysis_runs")[0][0]
        self.assertTrue(self.store.delete_analysis_run(local_run))
        # Older versions marked a deletion pushed even when the cloud kept a later revision.
        self._query("UPDATE cloud_sync_tombstones SET pending = 0")

        self.assertEqual(self.service._pull(_PullRemote([self._remote_row(run_id, revision=3)])), 0)

        self.assertEqual(self._query("SELECT pending, revision FROM cloud_sync_tombstones"), [(1, 4)])
        self.assertEqual(self._query("SELECT winner FROM cloud_sync_conflicts"), [("tombstone",)])
        self.assertEqual(self._query("SELECT COUNT(*) FROM analysis_runs"), [(0,)])

    def test_a_remote_delete_over_an_unpushed_local_edit_is_recorded(self):
        run_id = self._source_package("shared package")
        row = self._remote_row(run_id)
        self.service._pull(_PullRemote([row]))
        self._query("UPDATE analysis_runs SET title = 'Local edit'")
        self.assertEqual(self.service._stage_local_packages(), 1)
        tombstone = (row[0], "device-a", 2, "tombstone-hash", "{}", UPDATED_AT, UPDATED_AT)

        self.assertEqual(self.service._pull(_PullRemote([tombstone])), 1)

        self.assertEqual(self._query("SELECT COUNT(*) FROM analysis_runs"), [(0,)])
        self.assertEqual(self._query("SELECT winner, local_revision, remote_revision FROM cloud_sync_conflicts"),
                         [("tombstone", 2, 2)])
        # The losing local edit is kept with the record, so it can be recovered.
        kept = self._query("SELECT local_payload_json FROM cloud_sync_conflicts")[0][0]
        self.assertIn("Local edit", kept)

    def test_a_local_database_outage_fails_the_pull_instead_of_skipping_rows(self):
        run_id = self._source_package("shared package")

        with patch.object(self.service, "_apply_remote_row", side_effect=sqlite3.OperationalError("database is locked")):
            with self.assertRaises(sqlite3.OperationalError):
                self.service._pull(_PullRemote([self._remote_row(run_id)]))

        self.assertIsNone(self.service._pull_watermark)
        self.assertEqual(self.service._last_pull_skipped, 0)

    def test_the_next_pull_tries_a_skipped_row_again(self):
        bad = self._source_package("bad package", video_id="video-bad")
        good = self._source_package("good package")
        rows = [
            self._remote_row(bad, updated_at="2026-08-28T10:00:00+00:00",
                             mutate=lambda p: p["linked_video"].update(ownership_state="owner_confirmed")),
            self._remote_row(good, updated_at="2026-08-28T12:00:00+00:00"),
        ]

        with self.assertLogs("win_engine.feedback.cloud_sync", level="WARNING"):
            self.service._pull(_PullRemote(rows))

        self.assertLessEqual(self.service._pull_since(), "2026-08-28T10:00:00+00:00")

    def test_a_pulled_link_stores_its_format_in_the_cohort_spelling(self):
        spelled = self._source_package("short package", video_id="video-short")
        older_peer = self._source_package("older peer", video_id="video-peer")

        def create_page_spelling(payload):
            payload["linked_video"].update(format="Short", comparable_metadata=None)

        def older_peer_label(payload):
            payload["linked_video"]["comparable_metadata"].update(format="short", sources={"format": "creator"})

        self.service._pull(_PullRemote([
            self._remote_row(spelled, mutate=create_page_spelling), self._remote_row(older_peer, mutate=older_peer_label),
        ]))

        self.assertEqual(self._query(
            """SELECT p.youtube_video_id, m.format, m.format_source FROM published_video_comparable_metadata m
               JOIN published_video_links p ON p.id = m.published_video_link_id ORDER BY 1"""
        ), [("video-peer", "youtube_shorts", "creator"), ("video-short", "youtube_shorts", "package")])

    def test_a_failure_seen_from_another_channel_keeps_the_ownership_verified_here(self):
        run_id = self._source_package("owned package", video_id="video-own")

        def verified(payload):
            payload["linked_video"].update(ownership_state="verified", ownership_verified=True,
                                           verified_channel_id="UC-a", ownership_verified_at=UPDATED_AT)

        def failed_elsewhere(payload, note=""):
            verified(payload)
            payload["linked_video"].update(ownership_state="failed", ownership_verified=False, notes=note)

        self._query("""INSERT INTO youtube_channel_connection
                           (id, encrypted_refresh_token, channel_id, channel_title, connected_at, updated_at)
                       VALUES (1, 'token', 'UC-a', 'A', ?, ?)""", (UPDATED_AT, UPDATED_AT))
        self.service._pull(_PullRemote([self._remote_row(run_id, mutate=verified)]))
        self.service._pull(_PullRemote([self._remote_row(run_id, revision=2, mutate=failed_elsewhere)]))

        # This device is connected to the owning channel and checks the video itself.
        ownership = "SELECT ownership_state, ownership_verified, verified_channel_id FROM published_video_links"
        self.assertEqual(self._query(ownership), [("verified", 1, "UC-a")])

        # A device that cannot check it takes the other device's word.
        self._query("UPDATE youtube_channel_connection SET channel_id = 'UC-b'")
        self.service._pull(_PullRemote([self._remote_row(run_id, revision=3, mutate=lambda p: failed_elsewhere(p, "again"))]))
        self.assertEqual(self._query(ownership), [("failed", 0, "UC-a")])

    def test_a_row_dated_ahead_does_not_move_the_watermark_past_now(self):
        run_id = self._source_package("shared package")

        self.service._pull(_PullRemote([self._remote_row(run_id, updated_at="2099-01-01T00:00:00+00:00")]))

        self.assertLessEqual(self.service._pull_watermark, datetime.now(timezone.utc).isoformat())
        self.assertIsNotNone(self.service._pull_since())


if __name__ == "__main__":
    unittest.main()
