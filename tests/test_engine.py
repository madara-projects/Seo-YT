import os
import tempfile
import unittest

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.feedback.history_store import HistoryStore


class TestEngineStages(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.store = HistoryStore(self.db_path)

    def tearDown(self):
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except OSError:
            pass

    def test_creator_brief_parsing(self):
        script = "How I built a full YouTube SEO app in Tamil using Python and AI."
        brief = build_creator_brief(script=script, viewer_promise="Learn YouTube SEO automation", unique_angle="Tamil tech tutorial")
        self.assertIn("target_audience", brief)
        self.assertIn("proof", brief)
        self.assertIn("unique_angle", brief)

    def test_link_published_video(self):
        # Record a dummy analysis run first
        with self.store._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO analysis_runs (query, created_at, title, opportunity_score) VALUES (?, ?, ?, ?)",
                ("Test Video Topic", "2026-08-02T12:00:00Z", "How I Mastered Python in 30 Days", 85.0)
            )
            run_id = cursor.lastrowid

        # Link to video
        link_id = self.store.link_published_video(
            analysis_run_id=run_id,
            youtube_video_id="test_vid_123",
            published_at="2026-08-02T14:00:00Z",
            selected_title="How I Mastered Python in 30 Days",
            format_val="tutorial",
            language="english"
        )
        self.assertGreater(link_id, 0)

        # Retrieve link
        links = self.store.published_video_links_list()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["youtube_video_id"], "test_vid_123")
        self.assertEqual(links[0]["package_opportunity_score"], 85.0)
        self.store.record_performance_snapshot("test_vid_123", 24, views=40, snapshot_window="24h")
        self.assertEqual(self.store.published_video_links_list()[0]["latest_performance"]["snapshot_window"], "24h")

    def test_cohort_analytics_confidence(self):
        analytics = self.store.cohort_analytics()
        self.assertIn("Collecting evidence", analytics["confidence_label"])
        self.assertEqual(analytics["sample_size"], 0)

    def test_performance_snapshot_is_preserved_and_exposed(self):
        self.store.record_performance_snapshot(
            youtube_video_id="test_vid_123",
            age_hours=24,
            views=120,
            avg_view_percentage=72.5,
            snapshot_window="24h",
        )
        snapshot = self.store.latest_performance_snapshot("test_vid_123")
        self.assertEqual(snapshot["views"], 120)
        self.assertEqual(snapshot["snapshot_window"], "24h")
        self.assertTrue(self.store.has_snapshot_window("test_vid_123", "24h"))
        self.assertEqual(self.store.published_video_links_list(), [])

    def test_cohort_uses_median_not_a_single_outlier(self):
        runs: list[tuple[int, int]] = []
        with self.store._connect() as conn:
            for index, views in enumerate((100, 150, 9000, 200, 250), start=1):
                run_id = conn.execute(
                    "INSERT INTO analysis_runs (query, created_at, title, opportunity_score) VALUES (?, ?, ?, ?)",
                    (f"Topic {index}", "2026-08-02T12:00:00Z", f"Title {index}", 70.0),
                ).lastrowid
                runs.append((run_id, views))
        for index, (run_id, views) in enumerate(runs, start=1):
            video_id = f"test_video{index:02d}"
            self.store.link_published_video(run_id, video_id, "2026-07-01T00:00:00Z", format_val="tutorial", language="english")
            self.store.record_performance_snapshot(video_id, 168, views=views, avg_view_percentage=60, snapshot_window="7d")
        analytics = self.store.cohort_analytics(format_filter="tutorial", language_filter="english")
        self.assertEqual(analytics["sample_size"], 5)
        self.assertEqual(analytics["median_views"], 200.0)
        self.assertIn("Directional observation", analytics["confidence_label"])


if __name__ == "__main__":
    unittest.main()
