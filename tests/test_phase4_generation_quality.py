from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.generation_quality import (
    apply_quality_gate,
    evaluate_package_quality,
    evidence_trace,
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


def valid_package(title: str = "Did I Deserve More Than the Bare Minimum?") -> dict:
    quote = "Didn't I at least deserve the bare minimum from them?"
    return {
        "title": title,
        "variants": [title, "The Question I Could Never Ask Them"],
        "description": f'"{quote}" A rainy-road quote Short that preserves the creator\'s exact question.',
        "tags": ["bare minimum quote", "rainy road quote", "shorts", "yt", "youtube shorts", "viral shorts"],
        "hashtags": ["#Shorts", "#Quotes", "#SelfWorth"],
    }


class Phase4QualityTests(unittest.TestCase):
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

    def test_required_shorts_tags_are_checked(self):
        package = valid_package()
        package["tags"] = ["bare minimum quote"]
        gate = evaluate_package_quality(package, script="A quote Short")
        self.assertIn("missing_required_shorts_tags", {item["code"] for item in gate["issues"]})

    def test_tamil_and_tanglish_unicode_validation(self):
        tamil = {"title": "மழையில் ஒரு நினைவு", "variants": ["மழையில் ஒரு நினைவு"], "description": "மழையில் தோன்றிய ஒரு உண்மையான நினைவு.", "tags": ["rain quote"], "hashtags": []}
        self.assertTrue(evaluate_package_quality(tamil, script="மழை காட்சி", language="tamil")["passed"])
        tanglish = {"title": "Mazhaiyil vandha oru ninaivu", "variants": ["Mazhaiyil vandha oru ninaivu"], "description": "Indha mazhai oru pazhaya ninaivai thirumba kondu vandhadhu.", "tags": ["rain quote"], "hashtags": []}
        self.assertTrue(evaluate_package_quality(tanglish, script="Rain visual", language="tanglish")["passed"])
        self.assertTrue(unicode_words("தமிழ் mixed English"))

    def test_recent_title_similarity_rejects_repetition(self):
        package = valid_package("A Better Way to Plan a Chennai Day Trip")
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
