"""Links, snapshots and cohorts keep evidence and report only what was measured."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from win_engine.feedback import history_store as history_module
from win_engine.feedback import migrations
from win_engine.feedback.audit_experiment_store import AuditExperimentStore
from win_engine.feedback.history_store import DatabaseUnavailable, HistoryStore, RelinkWouldDeleteEvidence


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class HistoryStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "history.db")
        self.store = HistoryStore(self.path)

    def tearDown(self) -> None:
        self.dir.cleanup()

    def run_id(self, title: str = "Package") -> int:
        with self.store._connect() as connection:
            return int(connection.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES (?, ?, ?)", (title, _iso(0), title)
            ).lastrowid)

    def link(self, run_id: int, video_id: str, *, verified: bool = False, **extra) -> int:
        return self.store.link_published_video(
            run_id, video_id, _iso(40),
            ownership_state="verified" if verified else "unverified",
            ownership_verified=verified,
            verified_channel_id="UC-owner" if verified else None,
            ownership_verified_at=_iso(1) if verified else None,
            **extra,
        )


class RelinkTests(HistoryStoreTestCase):
    def test_relinking_away_from_collected_evidence_needs_consent(self):
        run = self.run_id()
        self.link(run, "firstvideo1")
        self.store.record_performance_snapshot("firstvideo1", 24, views=100, snapshot_window="24h")

        with self.assertRaises(RelinkWouldDeleteEvidence) as raised:
            self.link(run, "secondvide2")
        self.assertEqual(raised.exception.evidence["snapshots"], 1)
        # Nothing changed: the old link and its snapshot are intact.
        self.assertEqual(self.store.published_video_link_by_run(run)["youtube_video_id"], "firstvideo1")
        self.assertIsNotNone(self.store.completed_evidence_snapshot("firstvideo1", "24h"))

        self.link(run, "secondvide2", replace_existing_evidence=True)
        self.assertEqual(self.store.published_video_link_by_run(run)["youtube_video_id"], "secondvide2")
        self.assertEqual(self.store.performance_snapshots("firstvideo1"), [])

    def test_relinking_a_link_without_evidence_needs_no_consent(self):
        run = self.run_id()
        self.link(run, "firstvideo1")
        self.link(run, "secondvide2")
        self.assertEqual(self.store.published_video_link_by_run(run)["youtube_video_id"], "secondvide2")

    def test_relinking_without_a_connected_channel_keeps_verified_ownership(self):
        run = self.run_id()
        self.link(run, "ownedvideo1", verified=True)
        self.link(run, "ownedvideo1", verified=False)

        link = self.store.published_video_link_by_run(run)
        self.assertTrue(link["ownership_verified"])
        self.assertEqual(link["ownership_state"], "verified")
        self.assertEqual(link["verified_channel_id"], "UC-owner")
        self.assertEqual([item["youtube_video_id"] for item in self.store.due_snapshot_links()], ["ownedvideo1"])

    def test_package_format_follows_a_relink_but_creator_edits_do_not_change(self):
        run = self.run_id()
        link_id = self.link(run, "videoformat", format_val="Behind the scenes montage", language="hindi")
        comparable = self.store.comparable_metadata(link_id)
        # Free text would form a cohort of one, so it counts as unknown.
        self.assertEqual(comparable["format"], "unknown")
        self.assertEqual(comparable["language"], "hindi")

        self.store.update_comparable_metadata(link_id, {"language": "tamil"})
        self.link(run, "videoformat", format_val="tutorial", language="english")
        comparable = self.store.comparable_metadata(link_id)
        self.assertEqual((comparable["format"], comparable["sources"]["format"]), ("tutorial", "package"))
        self.assertEqual((comparable["language"], comparable["sources"]["language"]), ("tamil", "creator"))


class SnapshotTests(HistoryStoreTestCase):
    def test_a_failed_retry_neither_hides_data_nor_poses_as_a_baseline(self):
        run = self.run_id()
        self.link(run, "snapvideo01", verified=True)
        self.store.record_performance_snapshot("snapvideo01", 900, views=500, likes=5, snapshot_window="current")
        self.store.record_snapshot_attempt("snapvideo01", "7d", status="failed_retryable", failure_reason="analytics_request_failed")

        latest = self.store.latest_performance_snapshot("snapvideo01")
        self.assertEqual((latest["views"], latest["snapshot_window"]), (500, "current"))
        self.assertEqual(self.store.published_video_link_by_run(run) and self.store.published_video_links_list()[0]["latest_performance"]["views"], 500)

    def test_a_completed_window_is_preferred_over_a_display_count(self):
        run = self.run_id()
        self.link(run, "snapvideo02", verified=True)
        self.store.record_performance_snapshot("snapvideo02", 168, views=300, snapshot_window="7d")
        self.store.record_performance_snapshot("snapvideo02", 900, views=900, snapshot_window="current")
        self.assertEqual(self.store.latest_performance_snapshot("snapvideo02")["snapshot_window"], "7d")

    def test_retries_do_not_move_the_capture_time(self):
        run = self.run_id()
        self.link(run, "snapvideo03", verified=True)
        self.store.record_snapshot_attempt("snapvideo03", "24h", status="empty_retryable", failure_reason="analytics_returned_no_rows")
        first = self.store.snapshot_window_state("snapvideo03", "24h")
        self.store.record_snapshot_attempt("snapvideo03", "24h", status="empty_retryable", failure_reason="analytics_returned_no_rows")
        second = self.store.snapshot_window_state("snapvideo03", "24h")
        self.assertEqual(first["captured_at"], second["captured_at"])
        self.assertEqual(second["attempt_count"], 2)

    def test_the_collector_takes_the_least_recently_attempted_links_first(self):
        for video_id in ("dueattempt1", "dueattempt2", "duefresh001"):
            self.link(self.run_id(video_id), video_id, verified=True)
        self.store.record_snapshot_attempt("dueattempt1", "24h", status="failed_retryable", failure_reason="x")
        self.store.record_snapshot_attempt("dueattempt2", "24h", status="failed_retryable", failure_reason="x")

        order = [item["youtube_video_id"] for item in self.store.due_snapshot_links()]
        self.assertEqual(order[0], "duefresh001")
        self.assertEqual(set(order), {"dueattempt1", "dueattempt2", "duefresh001"})

    def test_an_experiment_after_figure_must_end_after_the_change(self):
        run = self.run_id()
        self.link(run, "experiment1", verified=True)
        self.store.record_package_experiment("experiment1", old_title="Old", new_title="New")
        today = datetime.now(timezone.utc).date()

        early = {"views": 10, "snapshot_window": "24h", "source_start_date": str(today - timedelta(days=30)),
                 "source_end_date": str(today - timedelta(days=29))}
        self.assertEqual(self.store.complete_due_experiment_snapshots("experiment1", early), 0)

        later = {**early, "snapshot_window": "28d", "source_end_date": str(today + timedelta(days=1))}
        self.assertEqual(self.store.complete_due_experiment_snapshots("experiment1", later), 1)
        after = self.store.get_package_experiments("experiment1")[0]["performance_after"]
        self.assertTrue(after["coverage"]["includes_days_before_change"])


class ReportTests(HistoryStoreTestCase):
    COMPARABLE = {"format": "tutorial", "language": "english", "duration_bucket": "3_to_10m", "topic_category": "tech"}

    def verified_video(self, video_id: str, views: int) -> int:
        run = self.run_id(video_id)
        link_id = self.link(run, video_id, verified=True)
        self.store.update_comparable_metadata(link_id, dict(self.COMPARABLE))
        self.store.record_performance_snapshot(video_id, 672, views=views, avg_view_percentage=50.0, snapshot_window="28d")
        return run

    def test_the_verdict_compares_the_same_window_not_lifetime_counts(self):
        for index in range(5):
            self.verified_video(f"peervideo{index:02d}", 1000)
        target = self.verified_video("targetvide1", 10)
        # A later lifetime count is shown, but never compared with a 28-day median.
        self.store.record_performance_snapshot("targetvide1", 2000, views=5000, snapshot_window="current")

        report = self.store.linked_package_report(target)
        self.assertEqual(report["performance"]["views"], 5000)
        self.assertEqual(report["baseline"]["median_views"], 1000.0)
        self.assertEqual(report["diagnosis"]["verdict"], "BELOW BASELINE")

    def test_missing_counts_are_unknown_not_zero(self):
        run = self.run_id()
        self.link(run, "nocountvid1")
        report = self.store.linked_package_report(run)
        self.assertIsNone(report["performance"]["views"])
        self.assertIsNone(report["performance"]["like_rate_percent"])

    def test_cohorts_and_baselines_apply_every_evidence_rule(self):
        for index in range(5):
            self.verified_video(f"peervideo{index:02d}", 1000)
        for index in range(4):
            self.verified_video(f"badvideo{index:02d}", 1)
        # Each of these fails one rule of evidence_policy.sample_is_eligible.
        with self.store._connect() as connection:
            connection.execute("UPDATE published_video_links SET verified_channel_id = ' ' WHERE youtube_video_id = 'badvideo00'")
            connection.execute("UPDATE published_video_links SET ownership_verified_at = '' WHERE youtube_video_id = 'badvideo01'")
            connection.execute("UPDATE video_performance_snapshots SET completed_at = NULL WHERE youtube_video_id = 'badvideo02'")
            connection.execute("UPDATE video_performance_snapshots SET views = NULL WHERE youtube_video_id = 'badvideo03'")
        target = self.verified_video("targetvide1", 10)

        self.assertEqual(self.store.cohort_analytics(format_filter="tutorial", snapshot_window="28d")["sample_size"], 6)
        self.assertEqual(self.store.linked_package_report(target)["baseline"]["sample_size"], 5)

    def test_a_count_youtube_now_hides_is_not_kept_from_an_earlier_lookup(self):
        run = self.run_id()
        link_id = self.link(run, "hiddenlike1")
        api = {"title": "Title", "description": "About", "tags": ["a"], "metadata_source": "youtube_data_api"}
        self.store.update_linked_video_metadata(link_id, {**api, "like_count": 50, "comment_count": 5})
        self.store.update_linked_video_metadata(link_id, {**api, "like_count": None, "comment_count": None})

        metadata = self.store.published_video_link(link_id)["youtube_metadata"]
        self.assertEqual((metadata["like_count"], metadata["comment_count"]), (None, None))
        self.assertIsNone(self.store.linked_package_report(run)["performance"]["likes"])

        # oEmbed cannot report a description, tags or date: those keep their values.
        self.store.update_linked_video_metadata(link_id, {
            "title": "New title", "description": None, "tags": None, "published_at": None, "metadata_source": "oembed",
        })
        metadata = self.store.published_video_link(link_id)["youtube_metadata"]
        self.assertEqual((metadata["title"], metadata["description"], metadata["tags"]), ("New title", "About", ["a"]))

    def test_an_audit_loads_its_package_once(self):
        run = self.verified_video("auditvideo1", 100)
        link_id = self.store.published_video_link_by_run(run)["id"]
        with patch.object(self.store, "history_run", wraps=self.store.history_run) as history_run:
            AuditExperimentStore(self.store).refresh_audit(link_id)
        self.assertEqual(history_run.call_count, 1)

    def test_the_cohort_denominator_uses_the_same_filters(self):
        self.verified_video("cohortvid01", 100)
        music = self.run_id("music")
        link_id = self.link(music, "cohortvid02", verified=True)
        self.store.update_comparable_metadata(link_id, {**self.COMPARABLE, "topic_category": "music"})

        cohort = self.store.cohort_analytics(topic_category_filter="tech", snapshot_window="28d")
        self.assertEqual(cohort["sample_size"], 1)
        self.assertEqual(cohort["total_links_considered"], 1)
        self.assertEqual(cohort["excluded_count"], 0)


class StartupTests(unittest.TestCase):
    def test_a_database_that_fails_to_prepare_is_not_retried_on_every_request(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "broken.db")
            with patch.object(history_module, "prepare_database", side_effect=migrations.MigrationError("boom")) as prepare:
                # The first failure is a 503 like the later ones, with its cause kept.
                with self.assertRaises(DatabaseUnavailable) as first:
                    HistoryStore(path)
                self.assertIsInstance(first.exception.__cause__, migrations.MigrationError)
                with self.assertRaises(DatabaseUnavailable):
                    HistoryStore(path)
            self.assertEqual(prepare.call_count, 1)
            history_module._PREPARE_FAILURES.clear()

    def test_a_foreign_key_violation_from_old_data_does_not_fail_only_the_first_start(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "v9.db"
            migrations.prepare_database(str(path))
            connection = sqlite3.connect(path)
            connection.execute("""INSERT INTO video_performance_snapshots
                                  (published_video_link_id, youtube_video_id, age_hours, captured_at)
                                  VALUES (999, 'orphanvid01', 1, '2026-01-01T00:00:00+00:00')""")
            _downgrade_to_version_9(connection)
            connection.commit()
            connection.close()

            # Logged, as at every later start-up, instead of failing this start only.
            with self.assertLogs(migrations.logger, level="WARNING") as logs:
                result = migrations.prepare_database(str(path))
            self.assertEqual((result.old_version, result.new_version), (9, 10))
            self.assertIn("foreign-key violation", logs.output[0])

    def test_a_negative_schema_version_is_refused_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "negative.db"
            migrations.prepare_database(str(path))
            connection = sqlite3.connect(path)
            connection.execute("PRAGMA user_version = -1")
            connection.commit()
            connection.close()

            with self.assertRaises(migrations.MigrationError):
                migrations.prepare_database(str(path))
            connection = sqlite3.connect(path)
            try:
                self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], -1)
            finally:
                connection.close()
            self.assertFalse((Path(folder) / "backups").exists())

    def test_a_refused_legacy_database_is_not_backed_up(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.db"
            connection = sqlite3.connect(path)
            for table in migrations._APPLICATION_TABLES - {"published_video_links"}:
                connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE published_video_links (id INTEGER PRIMARY KEY, analysis_run_id INTEGER)")
            connection.executemany("INSERT INTO published_video_links (analysis_run_id) VALUES (?)", [(1,), (1,)])
            connection.commit()
            connection.close()

            with self.assertRaises(migrations.MigrationError):
                migrations.prepare_database(str(path))
            self.assertFalse((Path(folder) / "backups").exists())

    def test_a_version_9_database_gains_the_conflict_payload_column(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "v9.db"
            migrations.prepare_database(str(path))
            connection = sqlite3.connect(path)
            connection.execute("ALTER TABLE cloud_sync_conflicts DROP COLUMN local_payload_json")
            connection.execute("DELETE FROM schema_migrations WHERE version = 10")
            connection.execute("PRAGMA user_version = 9")
            connection.commit()
            connection.close()

            result = migrations.prepare_database(str(path))
            self.assertEqual((result.old_version, result.new_version), (9, 10))
            connection = sqlite3.connect(path)
            try:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(cloud_sync_conflicts)")}
                self.assertIn("local_payload_json", columns)
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            finally:
                connection.close()

    def test_old_backups_are_pruned(self):
        with tempfile.TemporaryDirectory() as folder:
            backups = Path(folder) / "backups"
            backups.mkdir()
            for index in range(migrations._BACKUPS_KEPT + 3):
                name = f"source.backup-2026010{index:02d}T000000000000Z.sqlite3"
                for suffix in ("", "-wal", "-shm"):
                    (backups / (name + suffix)).write_bytes(b"")
            source = Path(folder) / "source.db"
            sqlite3.connect(source).close()
            migrations.online_backup(str(source))
            kept = {path.name for path in backups.glob("source.backup-*.sqlite3")}
            self.assertEqual(len(kept), migrations._BACKUPS_KEPT)
            # A pruned backup's -wal and -shm files go with it.
            for sidecar in [*backups.glob("*.sqlite3-wal"), *backups.glob("*.sqlite3-shm")]:
                self.assertIn(sidecar.name.rsplit("-", 1)[0], kept)


def _downgrade_to_version_9(connection: sqlite3.Connection) -> None:
    """Undo what version 10 added, so prepare_database migrates the file again."""
    connection.execute("ALTER TABLE cloud_sync_conflicts DROP COLUMN local_payload_json")
    if "channel_id" in {row[1] for row in connection.execute("PRAGMA table_info(owned_video_snapshots)")}:
        connection.execute("ALTER TABLE owned_video_snapshots DROP COLUMN channel_id")
    connection.execute("DELETE FROM schema_migrations WHERE version = 10")
    connection.execute("PRAGMA user_version = 9")


if __name__ == "__main__":
    unittest.main()
