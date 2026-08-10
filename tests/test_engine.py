import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.topic_lock import force_topic_in_tags
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.strategy_engine import _content_specific_fallback, build_seo_package
from win_engine.integrations.youtube_channel import _ordered_upload_rows
from win_engine.llm import gemini_client, seo_writer


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

    def test_recent_generated_titles_returns_newest_first(self):
        with self.store._connect() as conn:
            conn.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES (?, ?, ?)",
                ("older", "2026-08-01T00:00:00Z", "Older title"),
            )
            conn.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES (?, ?, ?)",
                ("newer", "2026-08-02T00:00:00Z", "Newer title"),
            )
        self.assertEqual(self.store.recent_generated_titles(2), ["Newer title", "Older title"])

    @patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source")
    def test_shorts_keep_required_fixed_tags(self, mocked_writer):
        mocked_writer.return_value = ({"english": None}, "fallback")
        research = {
            "main_topic": "street food in Chennai",
            "keyword_signals": [{"keyword": "chennai street food"}],
            "entity_signals": [],
            "top_opportunities": [],
            "youtube_results": [],
            "category": "cooking",
            "creator_brief": {"video_format": "youtube_shorts"},
            "language_context": {"language": "english", "region": "india"},
        }
        package = build_seo_package("generate seo", "A short about Chennai street food", research, self.store)
        tags = package["tags"]
        for required in ("shorts", "yt", "youtube shorts", "viral shorts"):
            self.assertIn(required, tags)

    def test_required_shorts_tags_survive_a_full_tag_list(self):
        incoming = [f"topic tag {index}" for index in range(12)] + [
            "shorts", "yt", "youtube shorts", "viral shorts"
        ]
        tags = force_topic_in_tags(incoming, "specific video topic", "general", max_tags=12)
        self.assertEqual(len(tags), 12)
        for required in ("shorts", "yt", "youtube shorts", "viral shorts"):
            self.assertIn(required, tags)

    def test_local_fallback_changes_with_the_video_topic(self):
        food = _content_specific_fallback("Chennai street food", [], {"video_format": "youtube_shorts"})
        coding = _content_specific_fallback("Python automation", [], {"video_format": "tutorial"})
        self.assertNotEqual(food["title"], coding["title"])
        self.assertIn("Chennai street food", food["description"])
        self.assertIn("Python automation", coding["description"])

    def test_owned_performance_keeps_lifetime_and_28_day_views_separate(self):
        payload = {
            "channel": {"real_total_views": 9999, "subscribers": 321, "video_count": 7},
            "period": {"start": "2026-07-13", "end": "2026-08-09"},
            "current_28_days": {"views": 456, "likes": 12, "estimatedMinutesWatched": 789},
        }
        with self.store._connect() as conn:
            conn.execute(
                "INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES (?, ?)",
                ("2026-08-10T12:00:00Z", json.dumps(payload)),
            )
        summary = self.store.owned_performance_summary()
        self.assertEqual(summary["lifetime_views"], 9999)
        self.assertEqual(summary["views_28_days"], 456)
        self.assertEqual(summary["total_views"], 456)
        self.assertEqual(summary["subscribers"], 321)

    def test_youtube_upload_rows_are_newest_first_even_when_details_are_random(self):
        playlist = [
            {"contentDetails": {"videoId": "older"}, "snippet": {"position": 1}},
            {"contentDetails": {"videoId": "newer"}, "snippet": {"position": 0}},
        ]
        details = [
            {"id": "older", "snippet": {"title": "Older", "publishedAt": "2026-08-01T00:00:00Z"}, "statistics": {"viewCount": "20"}},
            {"id": "newer", "snippet": {"title": "Newer", "publishedAt": "2026-08-09T00:00:00Z"}, "statistics": {"viewCount": "10"}},
        ]
        rows = _ordered_upload_rows(playlist, details)
        self.assertEqual([row["video_id"] for row in rows], ["newer", "older"])
        self.assertIsNone(rows[0]["averageViewPercentage"])

    def test_quote_fallback_preserves_exact_on_screen_message(self):
        script = (
            'Background visual is beach scene and the on the screen quote is '
            '"Some sunsets look beautiful because they\'re endings."'
        )
        brief = build_creator_brief(script=script)
        topic = creator_topic(brief)
        package = _content_specific_fallback(topic, [], brief)
        self.assertEqual(topic, "sunsets beautiful endings")
        self.assertEqual(
            package["title"],
            "Some sunsets look beautiful because they're endings #Shorts",
        )
        self.assertIn("a beach scene", package["description"])
        self.assertNotIn("Gemini was unavailable", package["description"])
        self.assertIn("beautiful endings", package["tags"])
        self.assertNotIn("background visual", package["tags"])


class TestGeminiGeneration(unittest.TestCase):
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_quota_response_is_not_retried(self, mocked_post):
        response = MagicMock(status_code=429)
        mocked_post.return_value = response
        env = {"WIN_ENGINE_GEMINI_API_KEY": "test-key", "WIN_ENGINE_GEMINI_MODEL": "test-model"}
        with patch.dict(os.environ, env), patch("time.sleep"):
            self.assertEqual(gemini_client.generate("test"), "")
        self.assertEqual(mocked_post.call_count, 1)

    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_transient_server_error_gets_only_one_retry(self, mocked_post):
        mocked_post.return_value = MagicMock(status_code=500)
        env = {"WIN_ENGINE_GEMINI_API_KEY": "test-key", "WIN_ENGINE_GEMINI_MODEL": "test-model"}
        with patch.dict(os.environ, env), patch("time.sleep"):
            self.assertEqual(gemini_client.generate("test"), "")
        self.assertEqual(mocked_post.call_count, 2)

    @patch("win_engine.llm.seo_writer._generate_one")
    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    def test_selected_language_uses_one_generation_call(self, _mocked_available, mocked_generate):
        mocked_generate.return_value = {
            "title": "A specific title",
            "variants": ["A specific title"],
            "description": "A specific description",
            "tags": ["specific topic"],
            "hashtags": ["#SpecificTopic"],
        }
        packages, source = seo_writer.write_multilang_packages_with_source(
            "A specific script", languages=["tamil"]
        )
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertEqual(set(packages), {"tamil"})
        self.assertEqual(source, "gemini")

    def test_recent_title_pattern_is_not_selected_when_fresh_variant_exists(self):
        package = {
            "title": "The Truth About Building a YouTube Channel",
            "variants": [
                "The Truth About Building a YouTube Channel",
                "I Built a Channel for 30 Days—Here Is What Worked",
            ],
        }
        result = seo_writer._prefer_fresh_titles(
            package,
            {"recent_titles": ["The Truth About Building Your YouTube Channel"]},
        )
        self.assertEqual(result["title"], "I Built a Channel for 30 Days—Here Is What Worked")

    def test_tamil_similarity_compares_real_characters(self):
        self.assertLess(
            seo_writer._title_similarity("தமிழ் சமையல் குறிப்புகள்", "சென்னை பயண அனுபவம்"),
            0.86,
        )


if __name__ == "__main__":
    unittest.main()
