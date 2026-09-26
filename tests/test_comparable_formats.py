"""Every spelling of a format joins one cohort, and "long_form" means every known format but Shorts."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from win_engine.api import routes
from win_engine.feedback import channel_learning, migrations
from win_engine.feedback.history_store import HistoryStore, comparable_format, known_filter


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class FormatCohortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = str(Path(self.dir.name) / "formats.db")
        self.store = HistoryStore(self.path)

    def video(self, video_id: str, format_val: str | None) -> int:
        """A verified video with completed 24h evidence, linked as the brief spelled its format."""
        payload = {"retention_assistant": {"rule_version": "phase5-v1", "opening": {"clarity": "clear"}}}
        run_id = self.store.record_analysis_run(video_id, "browse", "emotion", video_id, 7.0, "LOW", "WORKABLE", 50, payload)
        link_id = self.store.link_published_video(
            run_id, video_id, _iso(40), format_val=format_val, language="english",
            ownership_state="verified", ownership_verified=True,
            verified_channel_id="UC-owner", ownership_verified_at=_iso(39),
        )
        self.store.record_performance_snapshot(video_id, 24, views=100, avg_view_percentage=60.0, snapshot_window="24h")
        return link_id

    def samples(self, format_filter: str | None, language_filter: str | None = "english") -> tuple[int, int, int]:
        """The sample each learning reader finds: cohort, retention learning and channel learning."""
        return (
            self.store.cohort_analytics(format_filter=format_filter, language_filter=language_filter)["sample_size"],
            self.store.retention_learning_summary(format_filter=format_filter, language_filter=language_filter)["sample_size"],
            len(channel_learning.learning_summary(
                self.path, format_filter=format_filter, language_filter=language_filter)["linked_evidence"]),
        )

    def test_every_spelling_of_shorts_joins_one_cohort(self):
        spellings = ("Short", "youtube_shorts", "YouTube Shorts", "shorts", "youtube-short")
        for index, spelling in enumerate(spellings):
            self.video(f"shortsvid{index:02d}", spelling)
        self.video("tutorialv01", "tutorial")

        self.assertEqual({comparable_format(spelling) for spelling in spellings}, {"youtube_shorts"})
        # Free text that names the platform's format first is a Short; other free text is unknown.
        self.assertEqual(comparable_format("YouTube Short emotional quote video"), "youtube_shorts")
        self.assertIsNone(comparable_format("YouTube shortcuts tutorial"))
        self.assertIsNone(comparable_format("Emotional quote video"))
        for link in self.store.published_video_links_list():
            if link["youtube_video_id"].startswith("shortsvid"):
                self.assertEqual(link["comparable_metadata"]["format"], "youtube_shorts")
        # The Create page's "Short" and the brief inference's key read the same evidence.
        self.assertEqual(self.samples("Short"), (5, 5, 5))
        self.assertEqual(self.samples("youtube_shorts"), (5, 5, 5))

    def test_long_form_means_every_known_format_except_shorts(self):
        for video_id, spelling in (
            ("longform001", "Long form"), ("tutorial001", "tutorial"), ("vlogvideo01", "vlog"),
            ("shortsvid01", "Short"), ("quotevid001", "quote"), ("freetext001", "My special upload"),
        ):
            self.video(video_id, spelling)

        # Shorts (a quote video is one here) and unknown formats are never long form.
        self.assertEqual(self.samples("long_form"), (3, 3, 3))
        self.assertEqual(self.store.cohort_analytics(format_filter="long_form")["total_links_considered"], 3)

    def test_a_creator_can_label_a_video_long_form_and_short_is_stored_as_the_shorts_key(self):
        link_id = self.video("editedvid01", None)

        self.store.update_comparable_metadata(link_id, {"format": "long_form"})
        self.assertEqual(self.store.comparable_metadata(link_id)["format"], "long_form")
        self.store.update_comparable_metadata(link_id, {"format": "short"})
        metadata = self.store.comparable_metadata(link_id)
        self.assertEqual((metadata["format"], metadata["sources"]["format"]), ("youtube_shorts", "creator"))
        with self.assertRaises(ValueError):
            self.store.update_comparable_metadata(link_id, {"format": "made-up"})

    def test_unknown_or_blank_filters_nothing_in_every_reader(self):
        self.video("tutorial001", "tutorial")
        self.video("shortsvid01", "youtube_shorts")

        for value in (None, "", "unknown", " unknown "):
            self.assertIsNone(known_filter(value))
        self.assertEqual(known_filter(" tutorial "), "tutorial")
        self.assertEqual(self.samples("unknown", "unknown"), (2, 2, 2))
        self.assertEqual(routes._personal_evidence(self.store, "unknown", "")["sample_size"], 2)
        # A format that is not a known one still selects nothing rather than everything.
        self.assertEqual(self.samples("My special upload"), (0, 0, 0))


class FormatMigrationTests(unittest.TestCase):
    def test_version_10_stores_each_format_in_the_cohort_spelling(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "v9.db"
            migrations.prepare_database(str(path))
            connection = sqlite3.connect(path)
            rows = (
                ("videoshort1", "Short", "package"), ("videoshort2", "short", "creator"),
                ("videofree01", "YouTube Short quote video", "package"), ("videotut001", "tutorial", "creator"),
                ("videofree02", "Behind the scenes montage", "package"),
            )
            for link_id, (video_id, value, source) in enumerate(rows, start=1):
                connection.execute("INSERT INTO analysis_runs (id, query, created_at) VALUES (?, 'q', '2026-08-01')", (link_id,))
                connection.execute(
                    """INSERT INTO published_video_links (id, analysis_run_id, youtube_video_id, published_at, format,
                           linked_at, updated_at) VALUES (?, ?, ?, '2026-08-01', ?, '2026-08-01', '2026-08-01')""",
                    (link_id, link_id, video_id, value),
                )
                connection.execute(
                    """INSERT INTO published_video_comparable_metadata (published_video_link_id, format, format_source,
                           created_at, updated_at) VALUES (?, ?, ?, '2026-08-01', '2026-08-01')""",
                    (link_id, value, source),
                )
            _downgrade_to_version_9(connection)
            connection.commit()
            connection.close()

            migrations.prepare_database(str(path))

            connection = sqlite3.connect(path)
            try:
                stored = connection.execute(
                    "SELECT format, format_source FROM published_video_comparable_metadata ORDER BY published_video_link_id"
                ).fetchall()
                # The package's own text is kept on the link itself.
                link_format = connection.execute("SELECT format FROM published_video_links WHERE id = 3").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(stored, [
                ("youtube_shorts", "package"), ("youtube_shorts", "creator"), ("youtube_shorts", "package"),
                ("tutorial", "creator"), ("unknown", "unknown"),
            ])
            self.assertEqual(link_format, "YouTube Short quote video")


def _downgrade_to_version_9(connection: sqlite3.Connection) -> None:
    """Undo what version 10 added, so prepare_database migrates the file again."""
    connection.execute("ALTER TABLE cloud_sync_conflicts DROP COLUMN local_payload_json")
    if "channel_id" in {row[1] for row in connection.execute("PRAGMA table_info(owned_video_snapshots)")}:
        connection.execute("ALTER TABLE owned_video_snapshots DROP COLUMN channel_id")
    connection.execute("DELETE FROM schema_migrations WHERE version = 10")
    connection.execute("PRAGMA user_version = 9")


if __name__ == "__main__":
    unittest.main()
