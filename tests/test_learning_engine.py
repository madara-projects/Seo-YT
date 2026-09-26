"""Regression tests for the local learning engine's patterns and history comparisons."""

from __future__ import annotations

import unittest

from win_engine.feedback.learning_engine import build_feedback_package


def _package(score: float = 7.5, opportunity: float | None = None) -> dict:
    return {
        "title": "Current title", "content_angle": "Story",
        "title_optimization": {"scored_variants": [{"title": "Current title", "score": score}]},
        "opportunity_gap_analysis": {"opportunity_score": {"score": opportunity}},
    }


def _feedback(scorecard: dict, *, research: dict | None = None, angles: list | None = None, package: dict | None = None) -> dict:
    learning = {"angle_effectiveness": angles or [], "winning_titles": [{"title": "Best title"}]}
    return build_feedback_package(package or _package(), research or {"youtube_results": []}, learning, scorecard)


class WinningPatternTests(unittest.TestCase):
    def test_a_one_run_angle_does_not_hide_a_recurring_leader(self):
        angles = [
            {"content_angle": "Story", "run_count": 1, "avg_title_score": 9.5},
            {"content_angle": "Tutorial", "run_count": 30, "avg_title_score": 8.0},
            {"content_angle": "Listicle", "run_count": 12, "avg_title_score": 7.0},
        ]
        patterns = _feedback({"total_runs": 43}, angles=angles)["winning_patterns"]
        self.assertEqual(patterns["best_angle_so_far"], "Tutorial")
        self.assertEqual(patterns["sample_size"], 43)
        self.assertIn("at least 3 times", patterns["observation"])

    def test_no_recurring_angle_means_no_winning_pattern(self):
        angles = [{"content_angle": angle, "run_count": 2, "avg_title_score": 8.0} for angle in ("Story", "Tutorial", "Vlog")]
        patterns = _feedback({"total_runs": 6}, angles=angles)["winning_patterns"]
        self.assertEqual(patterns["best_angle_so_far"], "UNKNOWN")
        self.assertEqual(patterns["best_title_so_far"], "")


class PerformanceSyncTests(unittest.TestCase):
    def test_missing_outlier_scores_are_left_out_of_the_average(self):
        research = {"youtube_results": [
            {"view_count": 100, "outlier_score": 4.0}, {"view_count": 50}, {"view_count": 70, "outlier_score": 2.0},
        ]}
        self.assertEqual(_feedback({"total_runs": 0}, research=research)["performance_sync"]["average_outlier_score"], 3.0)

    def test_no_outlier_score_is_unmeasured(self):
        for research in ({"youtube_results": [{"view_count": 100}]}, {"youtube_results": []}):
            self.assertIsNone(_feedback({"total_runs": 0}, research=research)["performance_sync"]["average_outlier_score"])

    def test_no_history_is_not_a_score_of_zero(self):
        # Older scorecards reported 0.0 averages when no run had been saved.
        for scorecard in ({"total_runs": 0, "avg_title_score": None, "avg_opportunity_score": None},
                          {"total_runs": 0, "avg_title_score": 0.0, "avg_opportunity_score": 0.0}):
            feedback = _feedback(scorecard, package=_package(score=7.5, opportunity=50.0))
            sync, comparison = feedback["performance_sync"], feedback["historical_comparison"]
            self.assertIsNone(sync["historical_title_score_avg"])
            self.assertIsNone(sync["title_score_vs_history"])
            self.assertEqual(sync["current_title_score"], 7.5)
            self.assertIsNone(comparison["title_score_vs_average"])
            self.assertIsNone(comparison["opportunity_score_vs_average"])
            self.assertIn("still collecting history", comparison["summary"])

    def test_history_averages_are_compared_when_they_exist(self):
        feedback = _feedback({"total_runs": 6, "avg_title_score": 7.0, "avg_opportunity_score": 40.0},
                             package=_package(score=7.5, opportunity=50.0))
        self.assertEqual(feedback["performance_sync"]["historical_title_score_avg"], 7.0)
        self.assertEqual(feedback["performance_sync"]["title_score_vs_history"], 0.5)
        self.assertEqual(feedback["historical_comparison"]["title_score_vs_average"], 0.5)
        self.assertEqual(feedback["historical_comparison"]["opportunity_score_vs_average"], 10.0)
        self.assertIn("above your recent average on both", feedback["historical_comparison"]["summary"])

    def test_missing_averages_do_not_break_the_summary(self):
        unscored = _feedback({"total_runs": 6, "avg_title_score": None, "avg_opportunity_score": None})
        self.assertIn("still collecting history", unscored["historical_comparison"]["summary"])

        no_opportunity_history = _feedback({"total_runs": 6, "avg_title_score": 7.0, "avg_opportunity_score": None},
                                           package=_package(score=7.5, opportunity=50.0))
        comparison = no_opportunity_history["historical_comparison"]
        self.assertIsNone(comparison["opportunity_score_vs_average"])
        self.assertIn("opportunity has no earlier measurements", comparison["summary"])


if __name__ == "__main__":
    unittest.main()
