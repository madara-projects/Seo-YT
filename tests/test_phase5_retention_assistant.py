from __future__ import annotations

import unittest
from datetime import datetime, timezone

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.retention_assistant import RULE_VERSION, analyze_retention_assistant
from win_engine.feedback.history_store import HistoryStore


def analyze(script: str, **brief_values):
    brief = build_creator_brief(script=script, **brief_values) if script else {}
    return analyze_retention_assistant(script, creator_brief=brief)


class Phase5DeterministicAnalysisTests(unittest.TestCase):
    def test_strong_opening(self):
        result = analyze("I tested three phone batteries for 30 days. Here is why one failed.", video_format="tutorial")
        self.assertGreaterEqual(result["opening"]["score"], 70)
        self.assertFalse(result["opening"]["generic_setup"])

    def test_generic_opening(self):
        result = analyze("Hey guys, welcome back to my channel. Today we talk about batteries.")
        self.assertIn("generic_opening", self._codes(result))

    def test_delayed_value_quote_opening(self):
        setup = "First let me explain all the background details that happened before this moment and why the scenery matters to me personally. "
        result = analyze(setup + 'On-screen quote: "Keep going even when the road feels empty."', video_format="youtube_shorts")
        self.assertIn("quote_context_delay", self._codes(result))

    def test_unsupported_promise(self):
        script = "A tutorial showing my current editing workflow."
        brief = build_creator_brief(script=script, viewer_promise="This will guarantee viral growth")
        result = analyze_retention_assistant(script, creator_brief=brief, packages=[{"package_id": "package-a", "title": "Guaranteed Viral Growth"}])
        self.assertIn("unsupported_opening_promise", self._codes(result))

    def test_missing_opening_information(self):
        result = analyze_retention_assistant("", creator_brief={})
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["opening"]["score"], None)

    def test_long_first_frame_text(self):
        text = " ".join(f"word{i}" for i in range(30))
        result = analyze("Quote Short", on_screen_text=text, video_format="youtube_shorts")
        self.assertIn("first_frame_text_overload", self._codes(result))

    def test_short_readable_first_frame_text(self):
        result = analyze("Simple cooking Short", on_screen_text="Crisp dosa in three steps", video_format="youtube_shorts")
        self.assertEqual(result["first_frame"]["readability"], "readable")

    def test_missing_visual_information_is_unavailable(self):
        result = analyze("A spoken tutorial about database indexes.", voice_over="present")
        self.assertEqual(result["first_frame"]["status"], "unavailable")

    def test_visual_subject_identification(self):
        result = analyze("Basil root rot tutorial", visual_requirements="Basil roots and damaged leaves", video_format="tutorial")
        self.assertIn(result["first_frame"]["main_subject_identifiable"], {True, False})
        self.assertEqual(result["first_frame"]["visual_analysis_basis"], "creator_description_only")

    def test_quote_heavy_opening(self):
        quote = "Some endings look beautiful because they teach us how to release what can no longer stay with us"
        result = analyze(f'Quote Short: "{quote}"', video_format="youtube_shorts")
        self.assertEqual(result["quote_presentation"]["status"], "available")
        self.assertGreater(result["quote_presentation"]["word_count"], 14)

    def test_quote_reading_burden(self):
        quote = " ".join(f"thought{i}" for i in range(28))
        result = analyze(f'Quote Short: "{quote}"', video_format="youtube_shorts", voice_over="none")
        self.assertIn("quote_reading_burden", self._codes(result))
        self.assertIn("quote_visual_only_load", self._codes(result))

    def test_voice_over_visual_contradiction(self):
        result = analyze("The narration explains the scene while text appears.", voice_over="none")
        self.assertIn("voice_over_visual_contradiction", self._codes(result))

    def test_explicit_no_voice_over_is_not_a_contradiction(self):
        result = analyze("There is no voice-over; a road visual holds on screen.", voice_over="none", visual_requirements="Road visual")
        self.assertNotIn("voice_over_visual_contradiction", self._codes(result))

    def test_quote_text_conflict_does_not_rewrite_quote(self):
        quote = "Keep the exact words intact"
        result = analyze(f'Quote: "{quote}"', exact_quote=quote, on_screen_text="Different words")
        self.assertIn("quote_text_conflict", self._codes(result))
        alternative_text = " ".join(str(item) for item in result["alternatives"])
        self.assertNotIn("Different replacement quote", alternative_text)

    def test_short_form_pacing_overload(self):
        script = " ".join(f"detail{i}" for i in range(110))
        result = analyze(script + " shorts", video_format="youtube_shorts", duration_seconds=20, voice_over="present")
        self.assertIn("short_form_overload", self._codes(result))

    def test_long_form_pacing(self):
        result = analyze("First explain the tool. Then demonstrate it. Finally review the result.", video_format="tutorial", duration_seconds=300, voice_over="present")
        self.assertEqual(result["pacing"]["format_assessment"], "long_form_or_unspecified")

    def test_missing_duration_uses_relative_stages(self):
        result = analyze("A clear subject appears first and then the example follows.")
        self.assertEqual(result["trace"]["timing_basis"], "relative_stage_only")
        self.assertEqual(result["risk_map"][0]["stage"], "opening")

    def test_duration_enables_timing_bands(self):
        result = analyze("A quote Short with a quick reveal.", duration_seconds=20, video_format="youtube_shorts")
        self.assertEqual(result["risk_map"][0]["stage"], "0-3 seconds")

    def test_no_fabricated_timing_without_duration(self):
        result = analyze("A tutorial where the result appears after the explanation.")
        self.assertTrue(all(item["timing_basis"] == "relative_stage_only" for item in result["risk_map"]))

    def test_repeated_idea_detection(self):
        result = analyze("This method saves editing time. This method saves editing time. Then I show the result.")
        self.assertIn("repeated_idea", self._codes(result))

    def test_late_payoff_for_short(self):
        setup = " ".join(f"setup{i}" for i in range(55))
        result = analyze(f"{setup} Finally the result appears. shorts", video_format="youtube_shorts")
        self.assertIn("late_payoff", self._codes(result))

    def test_recommendations_have_no_guarantee(self):
        result = analyze("Hey guys, welcome back. A simple camera tutorial follows.")
        self.assertTrue(result["recommendations"])
        self.assertTrue(all(item["guarantee"] is False for item in result["recommendations"]))

    def test_alternatives_preserve_exact_quote(self):
        quote = "A long road can still lead somewhere gentle if you keep moving through every uncertain night"
        result = analyze(f'Long setup before quote. "{quote}" shorts', exact_quote=quote, video_format="youtube_shorts")
        self.assertTrue(any(item["preserves_source"] == quote for item in result["alternatives"]))

    def test_package_alignment_uses_package_id(self):
        script = "A battery test after thirty days"
        brief = build_creator_brief(script=script)
        result = analyze_retention_assistant(script, creator_brief=brief, packages=[{"package_id": "package-b", "title": "Battery Test After 30 Days"}])
        self.assertEqual(result["package_alignment"][0]["package_id"], "package-b")

    def test_insufficient_evidence_is_explicit(self):
        result = analyze_retention_assistant("Clear tutorial opening", retention_learning={"sample_size": 4, "learning_allowed": False})
        self.assertEqual(result["retention_learning"]["status"], "insufficient_evidence")
        self.assertEqual(result["retention_learning"]["patterns"], [])

    def test_mature_evidence_is_labelled_correlation(self):
        result = analyze_retention_assistant("Clear tutorial opening", retention_learning={
            "sample_size": 5, "minimum_samples": 5, "learning_allowed": True,
            "confidence_label": "Early signal", "snapshot_window": "24h",
            "patterns": [{"interpretation": "observed_correlation_not_causation"}],
        })
        self.assertEqual(result["retention_learning"]["status"], "observed_correlations")
        self.assertEqual(result["retention_learning"]["patterns"][0]["interpretation"], "observed_correlation_not_causation")

    @staticmethod
    def _codes(result):
        return {risk["risk_code"] for stage in result.get("risk_map", []) for risk in stage.get("risks", [])}


class Phase5HistoryLearningTests(unittest.TestCase):
    def setUp(self):
        self.store = HistoryStore(":memory:")

    def _add_video(self, index: int, retention: float, *, select: bool = False):
        script = "Battery result shown immediately. Then the test details follow."
        brief = build_creator_brief(script=script, video_format="youtube_shorts", language="english")
        assistant = analyze_retention_assistant(
            script, creator_brief=brief,
            packages=[{"package_id": "package-a", "title": "Battery Result After 30 Days"}],
        )
        run_id = self.store.record_analysis_run(
            script, "SEARCH", "Experiment", "Battery Result After 30 Days", 8.0,
            "low", "WORKABLE", 60.0,
            payload={
                "title": "Battery Result After 30 Days", "retention_assistant": assistant,
                "title_thumbnail_packages": [{"package_id": "package-a", "title": "Battery Result After 30 Days"}],
                "generation_quality": {"status": "pass"},
            },
        )
        if select:
            self.store.select_generated_package(run_id, "package-a")
        video_id = f"phase5vid{index:02d}"
        self.store.link_published_video(
            run_id, video_id, "2026-08-01T00:00:00+00:00",
            format_val="youtube_shorts", language="english",
            ownership_state="verified", ownership_verified=True,
            verified_channel_id="owner-channel",
            ownership_verified_at=datetime.now(timezone.utc).isoformat(),
        )
        self.store.record_performance_snapshot(
            video_id, 24, views=100 + index, avg_view_percentage=retention,
            snapshot_window="24h",
        )
        return run_id

    def test_history_traceability_without_new_schema(self):
        run_id = self._add_video(1, 70)
        run = self.store.history_run(run_id)
        self.assertEqual(run["package"]["retention_assistant"]["rule_version"], RULE_VERSION)

    def test_selected_package_keeps_retention_attribution(self):
        run_id = self._add_video(1, 70, select=True)
        selection = self.store.package_selection(run_id)
        self.assertEqual(selection["package"]["retention_trace"]["rule_version"], RULE_VERSION)
        self.assertEqual(selection["package"]["retention_trace"]["package_alignment"]["package_id"], "package-a")

    def test_four_samples_remain_insufficient(self):
        for index in range(1, 5):
            self._add_video(index, 65 + index)
        result = self.store.retention_learning_summary(format_filter="youtube_shorts", language_filter="english")
        self.assertFalse(result["learning_allowed"])
        self.assertEqual(result["sample_size"], 4)

    def test_five_samples_enable_observed_correlations(self):
        for index in range(1, 6):
            self._add_video(index, 65 + index)
        result = self.store.retention_learning_summary(format_filter="youtube_shorts", language_filter="english")
        self.assertTrue(result["learning_allowed"])
        self.assertEqual(result["sample_size"], 5)
        self.assertTrue(result["patterns"])
        self.assertTrue(all(item["interpretation"] == "observed_correlation_not_causation" for item in result["patterns"]))

    def test_missing_retention_metric_is_not_evidence(self):
        run_id = self._add_video(1, 70)
        link = self.store.published_video_link_by_run(run_id)
        self.store.record_performance_snapshot(
            link["youtube_video_id"], 24, views=120, avg_view_percentage=None,
            snapshot_window="24h", replace_window=True,
        )
        result = self.store.retention_learning_summary(format_filter="youtube_shorts", language_filter="english")
        self.assertEqual(result["sample_size"], 0)


if __name__ == "__main__":
    unittest.main()
