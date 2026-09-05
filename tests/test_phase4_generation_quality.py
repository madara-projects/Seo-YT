from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.package_builder import build_title_thumbnail_packages
from win_engine.generation.expansion_engine import build_chapters
from win_engine.generation.strategy_engine import _content_specific_fallback
from win_engine.analysis.generation_quality import (
    apply_quality_gate,
    evaluate_package_quality,
    evidence_trace,
    normalize_unicode,
    title_copies_quote,
    title_similarity,
    unicode_words,
)
from win_engine.feedback.history_store import HistoryStore
from win_engine.feedback.migrations import CURRENT_SCHEMA_VERSION, connect_managed, prepare_database
from win_engine.llm import seo_writer


DIVERSE_BRIEFS = [
    ("solar cooking", "How a Cardboard Solar Oven Cooked Rice"),
    ("rainy quote", "Did I Deserve More Than the Bare Minimum?"),
    ("python tutorial", "Parse a CSV Safely in Python in Three Steps"),
    ("budget travel", "What Rs 500 Buys on a Chennai Day Trip"),
    ("phone review", "Pixel Battery After 30 Days of Real Use"),
    ("fitness form", "Fix Your Squat Depth Without Adding Weight"),
    ("dosa recipe", "Crisp Dosa Batter Using a Simple Fermentation Test"),
    ("gaming", "The Final Move That Saved This Ranked Match"),
    ("study", "A 20 Minute Revision Method for Dense Chapters"),
    ("camera", "Why This Window Light Makes Interviews Look Softer"),
    ("gardening", "Rescue Basil Leaves Before the Roots Start Rotting"),
    ("music", "Building a Lo-Fi Beat From One Recorded Train Sound"),
    ("finance", "Where My Monthly Grocery Budget Actually Went"),
    ("history", "How This Forgotten Bridge Changed a Trade Route"),
    ("drawing", "Shade a Realistic Eye With Only One Pencil"),
    ("productivity", "I Removed Notifications for Seven Honest Days"),
    ("cycling", "What I Packed for a 100 Kilometre Ride"),
    ("pet care", "Teach a Rescue Dog to Trust the Doorway"),
    ("language", "Five Tamil Phrases I Use at the Market"),
    ("woodwork", "Cut a Clean Dovetail With a Hand Saw"),
    ("science", "Watch Salt Crystals Grow Across Seven Days"),
    ("makeup", "A Humidity Proof Base Tested on a Commute"),
    ("book review", "The Chapter That Changed How I Read Failure"),
    ("car repair", "Find a Battery Drain With a Multimeter"),
    ("meditation", "A Two Minute Breathing Reset Before Work"),
    ("street food", "Inside a Midnight Parotta Stall in Madurai"),
    ("coding", "The Race Condition Hidden in This Async Function"),
    ("home repair", "Stop a Leaking Tap Without Replacing the Sink"),
    ("photography", "Freeze Rain Drops Using Manual Camera Settings"),
    ("documentary", "One Fisherman's Morning Before the City Wakes"),
]


def valid_package(title: str = "Did I Deserve More Than the Bare Minimum? 💔 #shorts") -> dict:
    quote = "Didn't I at least deserve the bare minimum from them?"
    return {
        "title": title,
        "variants": [title, "The Question I Could Never Ask Them 🌧️ #shorts"],
        "description": f'"{quote}" A rainy-road quote Short that preserves the creator\'s exact question.',
        "tags": ["bare minimum quote", "rainy road quote", "shorts"],
        "hashtags": ["#Shorts", "#Quotes", "#SelfWorth"],
    }


class Phase4QualityTests(unittest.TestCase):
    def test_unquoted_quote_marker_is_separated_from_visual_direction(self):
        brief = build_creator_brief(
            script=(
                "the quote is- You don't give up overnight on someone. You reach a point "
                "where your heart quietly says, Enough and the background of the video is "
                "rainy weather, someone holding a cup of tea by a window"
            )
        )
        self.assertEqual(
            brief["exact_quote"],
            "You don't give up overnight on someone. You reach a point where your heart quietly says, Enough",
        )
        self.assertIn("rainy weather", brief["visual_requirements"])
        self.assertNotIn("background", brief["exact_quote"].casefold())
        self.assertTrue(brief["topic"].startswith("you don't give up overnight"))

    def test_malformed_input_marker_title_is_rejected(self):
        package = valid_package("How to is- you don't give overnight someone reach point #shorts")
        gate = evaluate_package_quality(package, script="A quote Short about knowing when to let go")
        codes = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("malformed_title_fragment", codes)

    def test_shorts_never_receive_synthetic_chapters(self):
        chapters = build_chapters(
            "A reflective quote Short",
            [{"keyword": "Spell Shorts"}, {"keyword": "Love Spell"}],
            {"video_format": "youtube_shorts", "duration_seconds": 20},
        )
        self.assertEqual(chapters, [])

    def test_latest_broken_input_has_natural_fallback_package(self):
        source = (
            'the quote is- You don\'t give up overnight on someone. You reach a point where '
            'your heart quietly says, "Enough and the background of the video is rainy weather, '
            'someone holding a cup of tea by a window'
        )
        brief = build_creator_brief(script=source)
        package = _content_specific_fallback(brief["topic"], [], brief)
        combined = " ".join([package["title"], package["description"], *package["tags"]]).casefold()
        self.assertNotIn("how to is-", combined)
        self.assertNotIn("background of the video is", package["description"].casefold())
        self.assertIn("you don't give up overnight on someone", package["title"].casefold())
        self.assertIn("rainy weather", package["description"].casefold())
        self.assertIn("knowing when to let go", package["tags"])

    def test_silence_quote_fallback_is_a_complete_human_package(self):
        quote = "at the end, it's only me and the silence that knows everything.."
        brief = build_creator_brief(
            script=quote,
            video_format="youtube_shorts",
            exact_quote=quote,
            on_screen_text=quote,
            visual_requirements="One person walking alone in quiet streets.",
            creator_intent="A reflective Short about solitude, silence, and private thoughts.",
        )
        package = _content_specific_fallback(brief["topic"], [], brief)
        self.assertGreaterEqual(len(package["variants"]), 4)
        self.assertTrue(package["title"].startswith("Some Things Only Silence Knows "))
        self.assertTrue(package["title"].endswith(" #shorts"))
        self.assertIn("A lone person walks through quiet streets.", package["description"])
        self.assertNotIn("A One person", package["description"])
        self.assertIn("inner silence", package["tags"])
        self.assertEqual(package["hashtags"], ["#shorts", "#DeepThoughts", "#Solitude"])

        title_rows = [{"title": title, "package_intent": "Browse"} for title in package["variants"]]
        choices = build_title_thumbnail_packages(title_rows, brief, validated=True)
        self.assertGreaterEqual(len(choices), 4)
        self.assertEqual(choices[0]["thumbnail_text"], "SILENCE KNOWS")
        self.assertIn("walking alone", choices[0]["thumbnail_visual"].casefold())
        self.assertNotEqual(choices[0]["viewer_promise"], "A clear, truthful reason to watch.")

    def test_rarity_quote_fallback_complements_quote_and_thumbnail(self):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        brief = build_creator_brief(
            script=quote, video_format="youtube_shorts", exact_quote=quote,
            visual_requirements="One person walking alone.",
            creator_intent="A reflection about recognizing a person's rarity and worth.",
        )
        package = _content_specific_fallback(brief["topic"], [], brief)
        self.assertTrue(package["title"].startswith("Know Your Worth—You're Hard to Replace"))
        self.assertGreaterEqual(len(package["variants"]), 4)
        self.assertIn("being valued", package["tags"])
        choices = build_title_thumbnail_packages(
            [{"title": title} for title in package["variants"]], brief, validated=True,
        )
        self.assertEqual(choices[0]["thumbnail_text"], "KNOW YOUR WORTH")

    def test_full_quote_title_is_rejected_when_complementary_titles_exist(self):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        copied = quote + " ✨ #shorts"
        package = {
            "title": copied,
            "variants": [copied, "Know Your Worth—You're Hard to Replace ✨ #shorts", "You're Rarer Than You Realize 🤍 #shorts"],
            "description": f'“{quote}”\n\nA reflection about recognizing your worth.',
            "tags": ["know your worth", "being valued", "hard to replace"],
            "hashtags": ["#shorts", "#KnowYourWorth"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "creator_intent": "recognizing your worth"},
            enforce_final_tag_rules=False,
        )
        rejected = {item["title"]: {reason["code"] for reason in item["issues"]} for item in gate["rejected_candidates"]}
        self.assertIn("title_duplicates_on_screen_quote", rejected[copied])
        self.assertNotEqual(gate["accepted_candidates"][0]["title"], copied)
        self.assertTrue(title_copies_quote(
            "You deserve somebody who knows how hard it is to find… 🌙 #shorts", quote,
        ))

    def test_semantically_proven_worth_tags_pass_final_grounding(self):
        quote = "You deserve somebody who knows how hard it is to find somebody like you"
        tags = ["being valued", "genuine appreciation", "rare personal qualities"]
        evidence = {
            "selected_keywords": [
                {"keyword": tag, "source_support_score": 80, "source_classification": "combined", "source_support": "rarity-and-worth semantic bridge", "keyword_relevance_score": 75}
                for tag in tags
            ]
        }
        package = {
            "title": "Know Your Worth—You're Hard to Replace ✨ #shorts",
            "variants": ["Know Your Worth—You're Hard to Replace ✨ #shorts"],
            "description": f'“{quote}”\n\nA reflection about recognizing your worth.',
            "tags": tags,
            "hashtags": ["#shorts", "#KnowYourWorth"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "creator_intent": "recognizing personal rarity and worth"},
            tag_evidence=evidence,
        )
        self.assertNotIn("unrelated_tag", {item["code"] for item in gate["issues"]})
        self.assertTrue(gate["passed"])


    def test_structured_brief_has_truthful_provenance_and_completeness(self):
        brief = build_creator_brief(script='Rainy road. On-screen quote: "Keep going."')
        self.assertEqual(brief["field_provenance"]["target_audience"]["source"], "unknown")
        self.assertEqual(brief["field_provenance"]["exact_quote"]["source"], "inferred")
        self.assertLess(brief["completeness"], 100)
        self.assertIn("target_audience", brief["missing_fields"])

    def test_creator_supplied_is_not_confused_with_inferred(self):
        brief = build_creator_brief(script="A repair tutorial", target_audience="New homeowners", video_format="tutorial")
        self.assertEqual(brief["field_provenance"]["target_audience"]["source"], "creator_supplied")
        self.assertEqual(brief["field_provenance"]["topic"]["source"], "inferred")

    def test_duplicate_candidate_is_rejected_and_not_padded(self):
        package = valid_package()
        package["variants"] = [package["title"], "Did I Really Deserve More Than the Bare Minimum?"]
        gate = evaluate_package_quality(package, script='Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts')
        cleaned = apply_quality_gate(package, gate)
        self.assertLess(len(cleaned["variants"]), 3)
        self.assertTrue(any(item["code"] == "fewer_legitimate_alternatives" for item in gate["warnings"]))

    def test_exact_quote_title_and_one_tag_cannot_be_green(self):
        quote = "At the end, it's only me and the silence that knows everything."
        package = {
            "title": quote + " #shorts",
            "variants": [quote + " #shorts"],
            "description": f'“{quote}” A reflective moment about silence.',
            "tags": ["inner silence"],
            "hashtags": ["#shorts"],
        }
        gate = evaluate_package_quality(
            package,
            script=quote,
            creator_brief={
                "exact_quote": quote,
                "video_format": "youtube_shorts",
                "visual_requirements": "One person walking alone in quiet streets.",
                "creator_intent": "A reflective Short about solitude and private thoughts.",
            },
        )
        self.assertEqual(gate["verdict"], "YELLOW")
        warning_codes = {item["code"] for item in gate["warnings"] + gate["final_seo_quality"]["warnings"]}
        self.assertIn("title_duplicates_on_screen_quote", warning_codes)
        self.assertIn("sparse_tag_set", warning_codes)

    def test_broken_article_description_is_rejected(self):
        package = valid_package()
        package["description"] = "A One person walking alone is the visual."
        gate = evaluate_package_quality(package, script="A quote Short about walking alone")
        self.assertIn("broken_description_grammar", {item["code"] for item in gate["issues"]})

    def test_quote_package_cannot_invent_night_darkness_or_comfort(self):
        quote = "At the end, it's only me and the silence that knows everything."
        package = {
            "title": "Finding Comfort on Empty Streets at Night 🌙 #shorts",
            "variants": ["Thinking Out Loud While Walking in the Dark 🌌 #shorts"],
            "description": f'“{quote}” A peaceful moment of healing and comfort.',
            "tags": ["silence"],
            "hashtags": ["#shorts"],
        }
        gate = evaluate_package_quality(
            package, script=quote,
            creator_brief={"exact_quote": quote, "video_format": "youtube_shorts", "visual_requirements": "A person walking alone in streets."},
        )
        rejected_codes = {reason["code"] for row in gate["rejected_candidates"] for reason in row["issues"]}
        self.assertIn("unsupported_context", rejected_codes)
        self.assertIn("unsupported_action", rejected_codes)
        self.assertIn("unsupported_context", {item["code"] for item in gate["issues"]})

    def test_unicode_normalization_preserves_emoji_joiners(self):
        self.assertEqual(normalize_unicode("Walking 🚶‍♂️"), "Walking 🚶‍♂️")

    def test_quote_fidelity_failure_is_structured(self):
        package = valid_package()
        package["description"] = "A generic emotional quote without the original words."
        gate = evaluate_package_quality(package, script='Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts')
        self.assertFalse(gate["passed"])
        self.assertIn("quote_fidelity", {item["code"] for item in gate["issues"]})

    def test_unsupported_relationship_is_rejected(self):
        package = valid_package("They Left Because I Asked for the Bare Minimum")
        gate = evaluate_package_quality(package, script='Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts')
        codes = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("relationship_event", codes)

    def test_platform_format_tags_are_rejected_from_video_tags(self):
        package = valid_package()
        package["tags"] = ["bare minimum quote", "shorts"]
        gate = evaluate_package_quality(package, script="A quote Short")
        self.assertIn("platform_tag_filler", {item["code"] for item in gate["issues"]})

    def test_short_title_contract_requires_one_shorts_hashtag_and_contextual_emoji(self):
        missing = valid_package("Did I Deserve More Than the Bare Minimum?")
        gate = evaluate_package_quality(
            missing,
            script='A rainy quote Short: "Didn\'t I at least deserve the bare minimum from them?"',
        )
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("missing_shorts_title_hashtag", rejected)
        self.assertIn("missing_contextual_title_emoji", {item["code"] for item in gate["warnings"]})

        duplicated = valid_package("Did I Deserve More? 💔 #shorts #Shorts")
        gate = evaluate_package_quality(duplicated, script="A rainy quote Short")
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("duplicate_shorts_title_hashtag", rejected)

    def test_non_short_title_does_not_accept_shorts_label(self):
        package = {
            "title": "How to Parse a CSV Safely #shorts",
            "variants": ["How to Parse a CSV Safely #shorts"],
            "description": "A practical CSV parsing tutorial.",
            "tags": ["csv parsing tutorial"],
            "hashtags": [],
        }
        gate = evaluate_package_quality(package, script="A long-form CSV parsing tutorial")
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("unexpected_shorts_title_hashtag", rejected)

    def test_repeated_emoji_template_is_rejected_from_recent_history(self):
        package = valid_package()
        gate = evaluate_package_quality(
            package,
            script='A rainy quote Short: "Didn\'t I at least deserve the bare minimum from them?"',
            recent_titles=["First reflection 💔 #shorts", "Second reflection 💔 #shorts", "Third reflection 💔 #shorts"],
        )
        rejected = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("repeated_emoji_template", rejected)

    def test_tamil_and_tanglish_unicode_validation(self):
        tamil = {"title": "மழையில் ஒரு நினைவு", "variants": ["மழையில் ஒரு நினைவு"], "description": "மழையில் தோன்றிய ஒரு உண்மையான நினைவு.", "tags": ["மழை காட்சி"], "hashtags": []}
        self.assertTrue(evaluate_package_quality(tamil, script="மழை காட்சி", language="tamil")["passed"])
        tanglish = {"title": "Mazhaiyil vandha oru ninaivu", "variants": ["Mazhaiyil vandha oru ninaivu"], "description": "Indha mazhai oru pazhaya ninaivai thirumba kondu vandhadhu.", "tags": ["rain quote"], "hashtags": []}
        self.assertTrue(evaluate_package_quality(tanglish, script="Rain visual", language="tanglish")["passed"])
        self.assertTrue(unicode_words("தமிழ் mixed English"))

    def test_recent_title_similarity_rejects_repetition(self):
        package = {"title": "A Better Way to Plan a Chennai Day Trip", "variants": ["A Better Way to Plan a Chennai Day Trip"], "description": "Plan a Chennai day trip.", "tags": ["chennai day trip"], "hashtags": []}
        gate = evaluate_package_quality(package, script="Plan a Chennai day trip", recent_titles=["A Better Way to Plan Your Chennai Day Trip"])
        codes = {reason["code"] for item in gate["rejected_candidates"] for reason in item["issues"]}
        self.assertIn("recent_title_repetition", codes)

    def test_insufficient_evidence_is_not_personalized(self):
        trace = evidence_trace({"cohort": {"sample_size": 4, "learning_allowed": False}})
        self.assertFalse(trace["learning_allowed"])
        self.assertEqual(trace["status"], "insufficient_evidence")

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer._generate_one")
    def test_one_repair_maximum(self, mocked_generate, _available):
        broken = valid_package("They Left Because I Asked for More")
        broken["description"] += " They left after I asked for more."
        repaired = valid_package()
        mocked_generate.side_effect = [broken, repaired]
        packages, source = seo_writer.write_multilang_packages_with_source(
            'Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts', languages=["english"]
        )
        self.assertEqual(mocked_generate.call_count, 2)
        self.assertEqual(source, "gemini")
        self.assertTrue(packages["english"]["generation_trace"]["repair_succeeded"])

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer._generate_one")
    def test_missing_shorts_title_format_uses_the_single_repair(self, mocked_generate, _available):
        broken = valid_package("Did I Deserve More Than the Bare Minimum?")
        broken["variants"] = ["Did I Deserve More Than the Bare Minimum?", "The Question I Could Never Ask Them"]
        mocked_generate.side_effect = [broken, valid_package()]
        packages, source = seo_writer.write_multilang_packages_with_source(
            'A rainy quote Short: "Didn\'t I at least deserve the bare minimum from them?"',
            languages=["english"],
        )
        self.assertEqual(mocked_generate.call_count, 2)
        self.assertEqual(source, "gemini")
        self.assertEqual(packages["english"]["title"].lower().count("#shorts"), 1)
        self.assertTrue(packages["english"]["generation_trace"]["repair_succeeded"])

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer._generate_one")
    def test_failed_repair_retains_bounded_quality_reasons(self, mocked_generate, _available):
        broken = valid_package("They Left Because I Asked for More #shorts")
        broken["variants"] = [broken["title"]]
        mocked_generate.side_effect = [dict(broken), dict(broken)]
        packages, source = seo_writer.write_multilang_packages_with_source(
            'Quote: "Didn\'t I at least deserve the bare minimum from them?" Shorts', languages=["english"]
        )
        self.assertEqual(source, "fallback")
        self.assertIsNone(packages["english"])
        trace = seo_writer.last_generation_diagnostics()["english"]
        self.assertEqual(trace["fallback_reason"], "quality_gate_rejection")
        self.assertTrue(trace["initial_quality_rejection"]["rejected_titles"])
        self.assertTrue(trace["repair_quality_rejection"]["rejected_titles"])
        self.assertIn("gemini_quality_rejection_after_repair", trace["events"])

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=True)
    @patch("win_engine.llm.seo_writer._generate_one", return_value=None)
    def test_empty_or_quota_result_does_not_trigger_repair(self, mocked_generate, _available):
        packages, source = seo_writer.write_multilang_packages_with_source("A video", languages=["english"])
        self.assertEqual(mocked_generate.call_count, 1)
        self.assertIsNone(packages["english"])
        self.assertEqual(source, "fallback")

    def test_thirty_brief_acceptance_fixture_is_materially_cross_topic(self):
        self.assertGreaterEqual(len(DIVERSE_BRIEFS), 30)
        titles = [title for _topic, title in DIVERSE_BRIEFS]
        self.assertEqual(len(titles), len({title.casefold() for title in titles}))
        self.assertTrue(all(title_similarity(left, right) < 0.82 for i, left in enumerate(titles) for right in titles[i + 1:]))
        self.assertFalse(any(title.casefold().startswith("the honest truth about") for title in titles))


class Phase4PersistenceTests(unittest.TestCase):
    def _record(self, store: HistoryStore) -> int:
        return store.record_analysis_run(
            "script", "SEARCH", "Authority", "Primary title", 8.0, "low", "WORKABLE", 60.0,
            payload={
                "title": "Primary title", "description": "Description", "tags": ["topic"], "hashtags": ["#Topic"],
                "selected_language": "english", "generation_quality": {"status": "pass"},
                "title_thumbnail_packages": [
                    {"package_id": "package-a", "title": "Primary title"},
                    {"package_id": "package-b", "title": "Alternative title"},
                ],
            },
        )

    def test_selected_package_persists_and_rejects_client_invention(self):
        store = HistoryStore(":memory:")
        run_id = self._record(store)
        with self.assertRaises(ValueError):
            store.select_generated_package(run_id, "invented")
        selected = store.select_generated_package(run_id, "package-b")
        self.assertEqual(selected["package"]["title"], "Alternative title")
        self.assertEqual(store.history_run(run_id)["selected_package"]["generated_package_id"], "package-b")

    def test_link_association_is_reported_without_inference(self):
        store = HistoryStore(":memory:")
        run_id = self._record(store)
        store.select_generated_package(run_id, "package-b")
        store.link_published_video(run_id, "abcdefghijk", "2026-08-20T00:00:00+00:00")
        self.assertTrue(store.package_selection(run_id)["later_associated_with_video"])

    def test_v2_to_v3_migration_is_additive_and_integral(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.db"
            store = HistoryStore(str(path))
            run_id = self._record(store)
            with connect_managed(str(path)) as connection:
                connection.execute("DROP TABLE analysis_package_selections")
                connection.execute("PRAGMA user_version = 2")
            result = prepare_database(str(path))
            self.assertEqual(result.new_version, CURRENT_SCHEMA_VERSION)
            with connect_managed(str(path)) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_runs WHERE id = ?", (run_id,)).fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
