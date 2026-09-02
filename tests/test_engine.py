import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.content_auditor import audit_content_package
from win_engine.analysis.research_planner import plan_research_queries
from win_engine.analysis.topic_lock import force_hashtags, force_topic_in_tags
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.channel_learning import learning_summary as channel_learning_summary
from win_engine.analysis.gap_engine import _opportunity_score
from win_engine.analysis.pacing_engine import analyze_script_pacing
from win_engine.analysis.strategy_layer import build_upload_timing
from win_engine.api.dashboard_html import DASHBOARD_HTML
from win_engine.feedback.learning_engine import _ctr_prediction
from win_engine.generation.strategy_engine import _content_specific_fallback, _deterministic_score, build_seo_package
from win_engine.generation.seo_generator import format_upload_ready_description, generate_seo_suggestions
from win_engine.core.config import Settings
from win_engine.ingestion.research_service import ResearchService
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

    def test_diagnostics_accepts_the_configured_youtube_key_pool(self):
        service = ResearchService(
            Settings(database_path=self.db_path, youtube_api_keys="pool-key-1,pool-key-2")
        )
        with patch.object(service._youtube, "search_videos", return_value=[]):
            diagnostics = service.diagnostics()

        self.assertEqual(diagnostics["youtube"]["status"], "ok")

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

    def test_current_snapshot_is_replaced_instead_of_duplicated(self):
        self.store.record_performance_snapshot(
            "test_vid_123", 2, views=10, snapshot_window="current", replace_window=True,
        )
        self.store.record_performance_snapshot(
            "test_vid_123", 3, views=25, snapshot_window="current", replace_window=True,
        )
        snapshots = self.store.performance_snapshots("test_vid_123")
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["views"], 25)

    def test_linked_package_report_joins_actual_metadata_and_performance(self):
        package = {
            "title": "Didn’t I Deserve the Bare Minimum? 🌧️ #Shorts",
            "description": "A faithful reflection.\n\n#Shorts #Quotes #Heartbreak",
            "tags": ["bare minimum quote", "heartbreak", "shorts"],
            "hashtags": ["#Shorts", "#Quotes", "#Heartbreak"],
        }
        with self.store._connect() as conn:
            run_id = conn.execute(
                """INSERT INTO analysis_runs
                   (query, created_at, title, title_score, opportunity_score, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("quote", datetime.now(timezone.utc).isoformat(), package["title"], 9, 63.61, json.dumps(package)),
            ).lastrowid
        published = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        link_id = self.store.link_published_video(
            run_id, "Hzkt7KbuV-o", published,
            selected_title=package["title"],
            selected_tags_json=json.dumps(package["tags"]),
            selected_hashtags_json=json.dumps(package["hashtags"]),
            format_val="youtube_shorts", language="english",
        )
        self.store.update_linked_video_metadata(link_id, {
            "title": package["title"],
            "description": package["description"],
            "tags": ["bare minimum quote", "heartbreak", "shorts"],
            "view_count": 125,
            "like_count": 10,
            "comment_count": 2,
        })
        self.store.record_performance_snapshot(
            "Hzkt7KbuV-o", 4, views=125, likes=10, comments=2,
            avg_view_percentage=88.5, snapshot_window="current", replace_window=True,
        )
        report = self.store.linked_package_report(run_id)
        self.assertTrue(report["linked"])
        self.assertTrue(report["package_usage"]["title_match"])
        self.assertEqual(report["package_usage"]["matching_tags"], package["tags"])
        self.assertEqual(report["performance"]["views"], 125)
        self.assertEqual(report["performance"]["like_rate_percent"], 8.0)
        self.assertIn("TOO EARLY", report["diagnosis"]["verdict"])

    def test_future_generation_learning_does_not_overfit_one_linked_video(self):
        with self.store._connect() as conn:
            run_id = conn.execute(
                "INSERT INTO analysis_runs (query, created_at, title) VALUES (?, ?, ?)",
                ("quote", datetime.now(timezone.utc).isoformat(), "A Strong Quote Title"),
            ).lastrowid
        link_id = self.store.link_published_video(
            run_id,
            "learn_vid01",
            (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            selected_tags_json=json.dumps(["quote tag"]),
            format_val="youtube_shorts",
            language="english",
            ownership_state="verified",
            ownership_verified=True,
            verified_channel_id="owner-channel",
            ownership_verified_at=datetime.now(timezone.utc).isoformat(),
        )
        self.store.update_linked_video_metadata(link_id, {
            "title": "A Strong Quote Title", "tags": ["quote tag"], "view_count": 500,
        })
        self.store.record_performance_snapshot(
            "learn_vid01", 48, views=500, avg_view_percentage=91,
            snapshot_window="24h",
        )
        learning = channel_learning_summary(self.db_path)
        self.assertEqual(learning["linked_video_count"], 1)
        self.assertEqual(learning["sample_size"], 1)
        self.assertEqual(learning["confidence"], "collecting")
        prompt_block = seo_writer._build_channel_learning_block(learning)
        self.assertIn("do not imitate or reject", prompt_block)
        self.assertNotIn("linked-video pattern", prompt_block)

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
            self.store.link_published_video(
                run_id, video_id, "2026-07-01T00:00:00Z",
                format_val="tutorial", language="english",
                ownership_state="verified", ownership_verified=True,
                verified_channel_id="owner-channel",
                ownership_verified_at=datetime.now(timezone.utc).isoformat(),
            )
            self.store.record_performance_snapshot(
                video_id, 24, views=views, avg_view_percentage=60,
                snapshot_window="24h",
            )
        analytics = self.store.cohort_analytics(format_filter="tutorial", language_filter="english")
        self.assertEqual(analytics["sample_size"], 5)
        self.assertEqual(analytics["median_views"], 200.0)
        self.assertEqual(analytics["confidence_label"], "Early signal")

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

    def test_learning_summary_recent_runs_include_database_ids(self):
        with self.store._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO analysis_runs
                   (query, created_at, title, title_score, opportunity_score)
                   VALUES (?, ?, ?, ?, ?)""",
                ("linkable", "2026-08-11T17:33:54Z", "Linkable package", 9.0, 63.61),
            )
            run_id = int(cursor.lastrowid)
        recent = self.store.learning_summary()["recent_runs"]
        self.assertEqual(recent[0]["id"], run_id)
        self.assertEqual(recent[0]["title"], "Linkable package")

    @patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source")
    def test_shorts_keep_contextual_tags_without_generic_padding(self, mocked_writer):
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
        self.assertIn("chennai street food", tags)
        self.assertNotIn("shorts", tags)
        self.assertIn("#shorts", package["hashtags"])
        self.assertTrue({"yt", "youtube shorts", "viral shorts"}.isdisjoint(tags))

    def test_only_useful_shorts_format_tag_survives_a_full_tag_list(self):
        incoming = [f"topic tag {index}" for index in range(12)] + [
            "shorts", "yt", "youtube shorts", "viral shorts"
        ]
        tags = force_topic_in_tags(incoming, "specific video topic", "general", max_tags=12)
        self.assertEqual(len(tags), 12)
        self.assertIn("shorts", tags)
        self.assertTrue({"yt", "youtube shorts", "viral shorts"}.isdisjoint(tags))

    def test_quote_length_hashtag_is_rejected_in_favor_of_compact_topic_or_category_tags(self):
        hashtags = force_hashtags(
            ["#shorts", "#quotes", "#InTheEndIWasntAbandonedIWasErased"],
            "in the end i wasn't abandoned i was erased",
            "quotes",
        )
        self.assertNotIn("#InTheEndIWasntAbandonedIWasErased", hashtags)
        self.assertIn("#shorts", hashtags)
        self.assertTrue(all(len(tag) <= 30 for tag in hashtags))

    @patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source")
    def test_search_browse_and_returning_audience_package_intents_remain_distinct(self, mocked_writer):
        mocked_writer.return_value = ({
            "english": {
                "title": "How to Parse CSV Files Without Breaking Rows",
                "variants": [
                    "How to Parse CSV Files Without Breaking Rows",
                    "The CSV Bug Hiding in Your Automation",
                    "I Finally Fixed My Most Annoying CSV Bug",
                    "Why CSV Rows Break in Python Automation",
                    "A Safer Way to Parse CSV Files in Python",
                ],
                "description": "A practical CSV parsing tutorial for safer Python automation.",
                "tags": ["csv parsing tutorial", "python automation"],
                "hashtags": ["#Python", "#CSV"],
            }
        }, "gemini")
        brief = {
            "content": "A practical CSV parsing tutorial for Python automation.",
            "video_format": "tutorial",
            "viewer_promise": "Parse CSV rows safely",
        }
        research = {
            "main_topic": "csv parsing tutorial",
            "keyword_signals": [{"keyword": "csv parsing tutorial"}],
            "entity_signals": [],
            "top_opportunities": [],
            "youtube_results": [],
            "category": "education",
            "creator_brief": brief,
            "language_context": {"language": "english", "region": "global"},
        }
        package = build_seo_package("generate seo", brief["content"], research, self.store)
        self.assertEqual(
            [item["package_intent"] for item in package["title_variants"][:3]],
            ["Search", "Browse", "Existing audience"],
        )
        self.assertEqual(package["title_thumbnail_packages"][2]["best_for"], "Returning viewers / existing audience")

    @patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source")
    def test_generated_history_preserves_the_full_creator_script(self, mocked_writer):
        mocked_writer.return_value = ({"english": None}, "fallback")
        script = "A reflective rainy-road quote Short. " + ("Full creator detail. " * 12)
        research = {
            "main_topic": "rainy road quote",
            "keyword_signals": [{"keyword": "rainy road quote"}],
            "entity_signals": [],
            "top_opportunities": [],
            "youtube_results": [],
            "category": "youtube_shorts",
            "creator_brief": {"video_format": "youtube_shorts"},
            "language_context": {"language": "english", "region": "global"},
        }

        package = build_seo_package("generate seo", script, research, self.store)

        saved = self.store.history_run(package["history_run_id"])
        self.assertEqual(saved["query"], script)
        self.assertGreater(len(saved["query"]), 120)

    def test_history_detail_recovers_full_script_from_legacy_package(self):
        script = "Exact creator script. " * 12
        run_id = self.store.record_analysis_run(
            script[:120], "SUGGESTED", "Story", "Saved title", 8.0,
            "LOW", "WORKABLE", 60.0,
            payload={"creator_brief": {"content": script}, "title": "Saved title"},
        )

        saved = self.store.history_run(run_id)

        self.assertEqual(saved["query"], script)

    def test_long_inferred_topic_does_not_create_an_invalid_tag(self):
        tags = force_topic_in_tags(
            ["missing people", "heart vs mind", "shorts", "yt", "youtube shorts", "viral shorts"],
            "heart has a strange habit of missing people the mind",
            "youtube_shorts",
        )
        self.assertEqual(tags[0], "heart has a strange habit of missing people")
        self.assertTrue(all(len(tag.split()) <= 8 for tag in tags))

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

    def test_owned_performance_preserves_optional_timing_evidence_without_inventing_it(self):
        payload = {
            "channel": {"real_total_views": 100, "timezone": "Asia/Kolkata"},
            "current_28_days": {"views": 20},
            "audience_activity": {
                "reliable": True,
                "sample_size": 14,
                "windows": [{"day": "Thursday", "start_hour": 18, "end_hour": 20, "activity": 80}],
            },
        }
        with self.store._connect() as conn:
            conn.execute(
                "INSERT INTO youtube_channel_syncs (synced_at, payload_json) VALUES (?, ?)",
                ("2026-08-10T12:00:00Z", json.dumps(payload)),
            )
        latest = self.store.owned_performance_summary()["latest_sync"]
        self.assertEqual(latest["timezone"], "Asia/Kolkata")
        self.assertEqual(latest["audience_activity"]["sample_size"], 14)

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
        self.assertEqual(topic, "some sunsets look beautiful because they're endings")
        self.assertTrue(package["title"].startswith("Some sunsets look beautiful because they're endings "))
        self.assertTrue(package["title"].endswith("#shorts"))
        self.assertIn("A beach scene", package["description"])
        self.assertNotIn("Gemini was unavailable", package["description"])
        self.assertNotIn("feeling of being forgotten", package["description"].casefold())
        self.assertIn("some sunsets look beautiful because they're endings", package["tags"])
        self.assertNotIn("background visual", package["tags"])

    def test_quote_topic_keeps_a_natural_search_phrase(self):
        script = (
            'A rainy highway quote Short. The exact on-screen quote is: '
            '“A part of me will always wonder... didn\'t I at least deserve the bare minimum from them?”'
        )
        topic = creator_topic(build_creator_brief(script=script))
        self.assertEqual(topic, "didn't i at least deserve the bare minimum from them")

    def test_structured_quote_beats_unquoted_production_directions_for_fallback_topic(self):
        quote = "In the end, I wasn't abandonded. I was erased."
        brief = build_creator_brief(
            script="Short-form quote video. Background: a road under evening clouds.",
            exact_quote=quote,
            on_screen_text=quote,
            video_format="youtube_shorts",
            visual_requirements="Road with clouds in the evening.",
        )
        self.assertEqual(creator_topic(brief), "in the end i wasn't abandonded i was erased")
        tags = force_topic_in_tags(
            _content_specific_fallback(creator_topic(brief), [], brief)["tags"],
            creator_topic(brief),
            "quotes",
            context=[brief["content"], quote],
        )
        self.assertIn("wasn't abandonded i was erased", tags)
        self.assertTrue(all(len(tag.split()) <= 8 for tag in tags))

    def test_quote_fallback_title_drops_only_an_introductory_lead_in(self):
        quote = "In the end, I wasn't abandoned. I was erased."
        brief = build_creator_brief(
            script="Quote Short over evening road traffic.",
            exact_quote=quote,
            on_screen_text=quote,
            video_format="youtube_shorts",
        )
        package = _content_specific_fallback(creator_topic(brief), [], brief)
        self.assertTrue(package["title"].startswith("I wasn't abandoned. I was erased"))
        self.assertIn("“In the end, I wasn't abandoned. I was erased.”", package["description"])
        self.assertIn("reflective backdrop", package["description"])

    def test_malformed_contraction_tag_is_removed_but_real_contraction_survives(self):
        tags = force_topic_in_tags(
            [
                "part always wonder didn least deserve bare minimum them",
                "didn't i deserve the bare minimum",
                "emotional neglect",
            ],
            "bare minimum quote",
            "quotes",
        )
        self.assertNotIn("part always wonder didn least deserve bare minimum them", tags)
        self.assertIn("didn't i deserve the bare minimum", tags)

    def test_quote_research_queries_use_the_message_not_production_directions(self):
        script = (
            'Rain footage with a typewriter quote: "The worst heartbreak is realizing '
            'you meant less than they meant to you."'
        )
        queries = plan_research_queries(
            script=script,
            creator_brief={
                "content": script,
                "target_audience": "people experiencing unrequited love and heartbreak",
                "viewer_promise": "a relatable heartbreak quote",
                "unique_angle": "typewriter animation over a calming sunset background",
                "video_format": "YouTube Short emotional quote video",
            },
        )
        query_text = " ".join(item["query"] for item in queries).lower()
        self.assertIn("worst heartbreak", queries[0]["query"].lower())
        self.assertIn("unrequited love", query_text)
        self.assertNotIn("typewriter animation over a calming sunset", query_text)

    def test_quote_short_audit_recognizes_visual_retention_mechanics(self):
        script = (
            'A brief pause over rain footage. Ambient music begins. The quote appears '
            'phrase by phrase with a typewriter animation: "The worst heartbreak is '
            'realizing you meant less than they meant to you." Hold, then fade to black.'
        )
        audit = audit_content_package(
            script,
            "When you realize you meant less to them",
            "worst heartbreak realizing meant less",
            "unrequited love",
            "Emotion",
            video_format="YouTube Short emotional quote video",
        )
        self.assertEqual(audit["hook_audit"]["hook_strength"], "HIGH")
        self.assertEqual(audit["first_30_second_simulator"]["predicted_dropoff_risk"], "LOW")
        self.assertEqual(audit["pattern_interrupts"]["assessment"], "STRONG")
        self.assertNotEqual(audit["alignment"]["package_match"], "WEAK")

    def test_quote_short_gets_readability_advice_not_spoken_script_advice(self):
        script = (
            'A vertical YouTube Short on a rainy highway. The on-screen quote is '
            '“A part of me will always wonder... didn\'t I at least deserve the bare minimum from them?”'
        )
        pacing = analyze_script_pacing(script, video_format="youtube_shorts")
        self.assertEqual(pacing["analysis_type"], "quote_short")
        self.assertEqual(pacing["pace_label"], "reflective")
        self.assertEqual(pacing["hook_density"], "single emotional hook")
        self.assertIn("readable", pacing["recommendation"])
        self.assertNotIn("mini-payoffs", pacing["recommendation"])

    def test_single_quoted_screen_text_is_a_quote_short(self):
        script = (
            "Rain footage with typewriter animation: 'The worst heartbreak is realizing "
            "you meant less than they meant to you.' Hold, then fade to black."
        )
        audit = audit_content_package(
            script,
            "When you realize you meant less to them",
            "worst heartbreak realizing meant less",
            "unrequited love",
            "Emotion",
            video_format="YouTube Short emotional quote video",
        )
        self.assertTrue(audit["hook_audit"]["stakes_present"])
        brief = build_creator_brief(script=script, video_format="YouTube Short emotional quote video")
        self.assertTrue(creator_topic(brief).startswith("worst heartbreak"))

    def test_alignment_uses_creator_brief_context(self):
        audit = audit_content_package(
            "A typewriter quote appears over rain footage.",
            "The painful truth about unrequited love...",
            "worst heartbreak realizing meant less",
            "emotional distance",
            "Emotion",
            video_format="YouTube Short emotional quote video",
            context_text="Viewers experiencing unrequited love and heartbreak",
        )
        self.assertNotEqual(audit["alignment"]["package_match"], "WEAK")

    def test_upload_ready_description_adds_emoji_and_hashtag_line(self):
        description = format_upload_ready_description(
            "A quiet reflection for anyone processing unrequited love.",
            ["#heartbreak", "#sadquotes", "#shorts"],
            category="quotes",
            topic="heartbreak quote",
        )
        self.assertTrue(description.startswith("💔 "))
        self.assertTrue(description.endswith("#heartbreak #sadquotes #shorts"))
        self.assertIn("\n\n#heartbreak", description)

    def test_upload_ready_description_does_not_duplicate_existing_hashtags(self):
        description = format_upload_ready_description(
            "🎮 A focused gaming guide.\n\n#gaming",
            ["#gaming", "#tips"],
            category="gaming",
        )
        self.assertEqual(description.lower().count("#gaming"), 1)
        self.assertTrue(description.endswith("#gaming #tips"))

    def test_upload_ready_description_consolidates_gemini_hashtag_lines(self):
        description = format_upload_ready_description(
            "💔 A quiet reflection.\n\n#Heartbreak #SadQuotes #Shorts",
            ["#heartbreak", "#quotes", "#sad"],
            category="quotes",
        )
        self.assertTrue(description.endswith("#heartbreak #quotes #sad"))
        self.assertEqual(len([line for line in description.splitlines() if line.startswith("#")]), 1)

    def test_general_description_does_not_force_an_emoji(self):
        description = format_upload_ready_description(
            "A concise professional summary of the video.",
            ["#analysis"],
            category="general",
        )
        self.assertTrue(description.startswith("A concise professional summary"))

    def test_dashboard_title_quality_meter_uses_title_quality_score(self):
        self.assertIn('meter(ctr.title_quality_score, 10, "ok")', DASHBOARD_HTML)
        self.assertNotIn("meter(ctr.predicted_ctr_percent", DASHBOARD_HTML)

    def test_upload_timing_reports_evidence_instead_of_claiming_a_best_time(self):
        timing = build_upload_timing(
            [
                {"published_at": "2026-08-05T07:30:00Z"},
                {"published_at": "2026-08-12T07:15:00Z"},
            ],
            region="global",
        )
        self.assertEqual(timing["sample_size"], 2)
        self.assertEqual(timing["confidence"], "LOW")
        self.assertEqual(timing["basis"], "public_research_pattern")
        self.assertIn("does not show that publishing then caused", timing["reasoning"])
        self.assertNotIn("best upload window", timing["reasoning"])
        self.assertEqual(timing["timezone"], "UTC")

    def test_upload_timing_day_matches_the_displayed_ist_timezone(self):
        timing = build_upload_timing(
            [{"published_at": "2026-08-05T23:30:00Z"}],
            region="india",
            timezone_name="Asia/Kolkata",
        )
        self.assertEqual(timing["recommended_day"], "Thursday")

    def test_upload_timing_prefers_reliable_personal_audience_activity(self):
        timing = build_upload_timing(
            [{"published_at": "2026-08-05T10:00:00Z"}],
            channel_analytics={
                "timezone": "Asia/Kolkata",
                "audience_activity": {
                    "reliable": True,
                    "sample_size": 30,
                    "windows": [{"day": "Friday", "start_hour": 19, "end_hour": 21, "activity": 92}],
                },
            },
            historical_videos=[{"published_at": "2026-08-01T10:00:00Z", "views": 10}] * 5,
            now=datetime(2026, 8, 28, 9, tzinfo=timezone.utc),
        )
        self.assertEqual(timing["basis"], "personal_audience_activity")
        self.assertEqual(timing["recommended_day"], "Friday")
        self.assertEqual(timing["recommended_time"], "7:00 PM - 9:00 PM")
        self.assertEqual(timing["timezone"], "Asia/Kolkata")
        self.assertTrue(timing["personalized"])

    def test_upload_timing_uses_owned_history_before_public_patterns(self):
        owned = [
            {"published_at": f"2026-08-{day:02d}T13:30:00Z", "views": 100 + day, "average_view_percentage": 70}
            for day in (1, 8, 15, 22, 29)
        ]
        timing = build_upload_timing(
            [{"published_at": "2026-08-05T10:00:00Z"}],
            historical_videos=owned,
            timezone_name="Asia/Kolkata",
        )
        self.assertEqual(timing["basis"], "historical_channel_data")
        self.assertEqual(timing["sample_size"], 5)
        self.assertTrue(timing["personalized"])

    def test_upload_timing_general_fallback_is_honest_and_today_is_dynamic(self):
        timing = build_upload_timing(
            [],
            video_format="youtube_shorts",
            timezone_name="Asia/Kolkata",
            now=datetime(2026, 8, 28, 6, tzinfo=timezone.utc),
        )
        self.assertEqual(timing["basis"], "general_recommendation")
        self.assertFalse(timing["personalized"])
        self.assertIn("Personalized upload timing is not yet established", timing["explanation"])
        self.assertEqual(timing["today_timezone"], "Asia/Kolkata")
        self.assertIn("weaker-evidence day", timing["today_recommendation"])

    @patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source")
    def test_selected_package_description_is_upload_ready(self, mocked_writer):
        mocked_writer.return_value = ({
            "english": {
                "title": "Didn’t I Deserve the Bare Minimum? #Shorts",
                "variants": ["Didn’t I Deserve the Bare Minimum? #Shorts"],
                "description": "A faithful reflection about receiving less than you deserved.",
                "tags": ["bare minimum quote"],
                "hashtags": ["#Shorts", "#Quotes", "#Heartbreak"],
            }
        }, "gemini")
        script = 'Rainy highway quote: “Didn\'t I deserve the bare minimum?”'
        brief = build_creator_brief(script=script, video_format="youtube_shorts")
        research = {
            "history_store": self.store,
            "youtube_results": [],
            "keyword_signals": [{"keyword": "bare minimum quote"}],
            "entity_signals": [],
            "top_opportunities": [],
            "upload_timing": {},
            "thumbnail_intelligence": {},
            "category": "quotes",
        }
        result = generate_seo_suggestions(
            script,
            research,
            context={
                "language": "english",
                "region": "global",
                "category": "quotes",
                "creator_brief": brief,
            },
        )
        description = result["multilang"]["english"]["description"]
        self.assertTrue(description.endswith("#Shorts #Quotes #Heartbreak"))
        self.assertIn("\n\n#Shorts", description)

    def test_opportunity_score_has_no_artificial_high_floor(self):
        result = _opportunity_score([], {"score": 85, "label": "SATURATED"}, [])
        self.assertLess(result["score"], 45)
        self.assertEqual(result["label"], "WEAK")
        self.assertEqual(result["confidence"], "LOW")

    def test_opportunity_score_exposes_normalized_components(self):
        result = _opportunity_score(
            [{"keyword": "gap"}] * 3,
            {"score": 25, "label": "UNDERSERVED"},
            [
                {"views_per_day": 1000, "small_channel_outlier": True, "matched_queries": ["main topic", "viewer problem"]},
                {"views_per_day": 500, "small_channel_outlier": False, "matched_queries": ["main topic"]},
                {"views_per_day": 250, "small_channel_outlier": True, "matched_queries": ["main topic", "format"]},
            ],
        )
        self.assertGreater(result["score"], 45)
        self.assertLess(result["score"], 100)
        self.assertIn("demand_velocity", result["components"])

    def test_title_quality_is_not_claimed_as_ctr(self):
        score = _deterministic_score(
            "Why Genuine Love Feels Different When It Is Real",
            "genuine love",
            context_text="A quote about why genuine love feels calm and natural",
            competitor_titles=["Signs of Fake Love"],
        )
        guidance = _ctr_prediction({"score": score}, {})
        self.assertGreaterEqual(score, 6)
        self.assertIsNone(guidance["actual_ctr_percent"])
        self.assertNotIn("predicted_ctr_percent", guidance)


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
            "A specific script", languages=["english"]
        )
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertEqual(set(packages), {"english"})
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

    def test_quote_package_removes_invented_events_and_unnatural_phrases(self):
        script = (
            'Rainy highway quote Short. On-screen quote: “A part of me will always wonder... '
            'didn\'t I at least deserve the bare minimum from them?”'
        )
        package = {
            "title": "Didn’t I Deserve the Bare Minimum? #Shorts",
            "variants": [
                "Didn’t I Deserve the Bare Minimum? #Shorts",
                "When You Accepted Fractions of Effort",
                "The Painful Reality of Staying in a One-Sided Connection",
            ],
            "description": (
                "A reflection for anyone healing from unrequited effort.\n\n"
                "The hardest truth is that they left, but you stayed. Take a moment to breathe."
            ),
            "tags": ["bare minimum quote"],
            "hashtags": ["#Shorts"],
        }
        cleaned = seo_writer._sanitize_generated_package(package, script)
        self.assertIn("one-sided effort", cleaned["description"])
        self.assertNotIn("they left", cleaned["description"].lower())
        self.assertNotIn("you stayed", cleaned["description"].lower())
        self.assertFalse(any("staying in" in title.lower() for title in cleaned["variants"]))

    def test_tamil_similarity_compares_real_characters(self):
        self.assertLess(
            seo_writer._title_similarity("தமிழ் சமையல் குறிப்புகள்", "சென்னை பயண அனுபவம்"),
            0.86,
        )


if __name__ == "__main__":
    unittest.main()
