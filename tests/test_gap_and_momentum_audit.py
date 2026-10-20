"""Audit regressions: missing statistics made affirmative claims.

Five result titles with no view or subscriber counts, plus six keyword gaps,
read as "45 / WORKABLE" beside an UNDERSERVED competition, and a lifetime
average of views per day was described as current momentum.
"""

import unittest
from datetime import datetime, timedelta, timezone

from win_engine.analysis.gap_engine import _competition_meter, analyze_opportunity_gaps
from win_engine.scoring.outlier_engine import score_outliers

AFFIRMATIVE_COMPETITION = {"UNDERSERVED", "COMPETITIVE", "SATURATED"}
AFFIRMATIVE_OPPORTUNITY = {"STRONG", "WORKABLE", "WEAK"}


def _title_only(index):
    return {"title": f"Night thoughts {index}", "description": "a quote"}


def _gap_signals():
    # Six phrases of the script that no sampled title uses: six keyword gaps.
    return [
        {"keyword": keyword, "mentions": 2}
        for keyword in ("quiet goodbye", "late apology", "empty chair", "unsent letter", "borrowed time", "last train")
    ]


class MissingStatisticsTests(unittest.TestCase):
    def test_all_missing_channel_sizes_are_not_an_underserved_competition(self):
        competition = _competition_meter([_title_only(index) for index in range(5)], {})
        self.assertEqual(competition["label"], "UNKNOWN")
        self.assertNotIn(competition["label"], AFFIRMATIVE_COMPETITION)
        self.assertFalse(competition["measured"])
        self.assertEqual(competition["unknown_channel_size_count"], 5)
        self.assertIn("could not be measured", competition["reason"])
        self.assertIn("not a sign of an underserved topic", competition["reason"])

    def test_more_than_half_missing_is_unmeasured_and_half_or_less_is_not(self):
        with_counts = {"title": "x", "subscriber_count": 1000, "outlier_score": 5.0}
        mostly_missing = _competition_meter([with_counts, _title_only(1), _title_only(2)], {})
        self.assertEqual(mostly_missing["label"], "UNKNOWN")
        half_missing = _competition_meter([with_counts, _title_only(1)], {})
        self.assertIn(half_missing["label"], AFFIRMATIVE_COMPETITION)
        self.assertTrue(half_missing["measured"])
        self.assertIn("Channel size was unavailable for 1 result(s)", half_missing["reason"])

    def test_all_missing_stats_do_not_make_a_workable_verdict(self):
        results = [_title_only(index) for index in range(5)]
        analysis = analyze_opportunity_gaps(_gap_signals(), [], results, results, {})

        self.assertEqual(len(analysis["keyword_gaps"]), 6)
        self.assertEqual(analysis["competition"]["label"], "UNKNOWN")

        score = analysis["opportunity_score"]
        self.assertEqual(score["label"], "UNVERIFIED")
        self.assertNotIn(score["label"], AFFIRMATIVE_OPPORTUNITY)
        self.assertEqual(score["confidence"], "LOW")
        self.assertFalse(score["measured"])
        # The existing keys stay for the frontend; the reason is in the warnings.
        for key in ("score", "label", "confidence", "reason", "scope", "components", "breakdown"):
            self.assertIn(key, score)
        self.assertIn("could not be measured", score["reason"])
        self.assertTrue(any("unverified" in warning for warning in score["breakdown"]["warnings"]))
        self.assertEqual(score["breakdown"]["confidence"], "low")

        self.assertEqual(analysis["viability_verdict"]["status"], "unknown")
        self.assertNotIn(analysis["viability_verdict"]["status"], {"green", "yellow"})
        self.assertEqual(analysis["idea_kill_switch"]["status"], "insufficient_evidence")
        self.assertNotIn("strong enough", analysis["idea_kill_switch"]["reason"])
        self.assertIn("not a verdict", analysis["idea_kill_switch"]["reason"])

    def test_a_measured_sample_keeps_its_affirmative_labels(self):
        results = [
            {"title": f"Night thoughts {index}", "subscriber_count": 1000, "outlier_score": 5.0}
            for index in range(5)
        ]
        analysis = analyze_opportunity_gaps(_gap_signals(), [], results, results, {})
        self.assertEqual(analysis["competition"]["label"], "UNDERSERVED")
        self.assertTrue(analysis["competition"]["measured"])
        self.assertIn(analysis["opportunity_score"]["label"], AFFIRMATIVE_OPPORTUNITY)
        self.assertNotEqual(analysis["viability_verdict"]["status"], "unknown")


class LifetimeViewsPerDayTests(unittest.TestCase):
    def test_views_per_day_is_described_as_a_lifetime_average_not_momentum(self):
        published = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        row = score_outliers([{
            "title": "old video", "view_count": 200000, "subscriber_count": 5000,
            "like_count": 100, "comment_count": 10, "published_at": published,
        }])[0]

        self.assertAlmostEqual(row["views_per_day"], 2000.0, delta=1)
        self.assertEqual(row["lifetime_views_per_day"], row["views_per_day"])

        reasons = " ".join(row["opportunity_reasons"])
        self.assertIn("views per day since publication", reasons)
        self.assertIn("lifetime, not current", reasons)
        for claim in ("momentum", "current audience pull", "attracting viewers now", "topic is moving"):
            self.assertNotIn(claim, reasons)

    def test_the_alias_is_none_when_views_per_day_is_unknown(self):
        row = score_outliers([{"title": "no date", "view_count": 1000, "subscriber_count": 10}])[0]
        self.assertIsNone(row["views_per_day"])
        self.assertIsNone(row["lifetime_views_per_day"])


if __name__ == "__main__":
    unittest.main()
