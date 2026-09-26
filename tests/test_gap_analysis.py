"""Regression tests for the competitor gap analysis and its go/no-go heuristic.

Missing subscriber counts and durations were read as zero, a fixed 0.5 stood
in for title uniqueness, and a small title-count heuristic was presented as a
"very_high" confidence "market opportunity".
"""

import unittest

from win_engine.ai_enhancement import find_content_similarity
from win_engine.analysis.dynamic_thresholds import get_dynamic_kill_switch
from win_engine.analysis.gap_engine import _competition_meter, _format_lock_in, _opportunity_score, analyze_opportunity_gaps


def _row(title="video", subscribers=1000, outlier=5.0, duration="PT8M"):
    return {"title": title, "subscriber_count": subscribers, "outlier_score": outlier, "duration": duration}


class CompetitionMeterTests(unittest.TestCase):
    def test_missing_subscriber_count_is_unknown_not_small(self):
        known = _competition_meter([_row(subscribers=300000), _row(subscribers=5000)], {})
        hidden = _competition_meter([_row(subscribers=300000), _row(subscribers=None)], {})
        self.assertEqual(known["unknown_channel_size_count"], 0)
        self.assertEqual(hidden["big_channel_count"], 1)
        self.assertEqual(hidden["unknown_channel_size_count"], 1)
        self.assertIn("Channel size was unavailable for 1 result(s)", hidden["reason"])

    def test_competition_is_a_low_confidence_heuristic(self):
        competition = _competition_meter([_row(f"video {index}") for index in range(10)], {})
        self.assertEqual(competition["label"], "UNDERSERVED")
        self.assertEqual(competition["confidence"], "low")
        self.assertEqual(competition["evidence_state"], "heuristic")
        self.assertIn("10 sampled results", competition["basis"])

    def test_unmeasured_outlier_scores_add_nothing(self):
        measured = _competition_meter([_row(outlier=5.0)], {})
        unmeasured = _competition_meter([_row(outlier=None)], {})
        self.assertEqual(measured["score"], 5)
        self.assertEqual(unmeasured["score"], 0)

    def test_unmeasured_velocity_is_not_averaged_in_as_zero(self):
        result = _opportunity_score([], {"score": 25}, [{"views_per_day": 1000}, {"views_per_day": None}])
        self.assertEqual(result["components"]["demand_velocity"], 75.01)


class KillSwitchTests(unittest.TestCase):
    def test_typical_underserved_sample_makes_no_market_claim(self):
        competition = _competition_meter([_row(f"video {index}") for index in range(10)], {})
        result = get_dynamic_kill_switch([{"outlier_score": 900}], competition, [])
        text = f"{result['reason']} {result['recommended_action']}".lower()
        self.assertTrue(result["proceed"])
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["evidence_state"], "heuristic")
        self.assertNotIn("market opportunity", text)
        self.assertNotIn("aggressively", text)

    def test_gap_count_at_the_threshold_proceeds(self):
        gaps = [{"gap_strength": "high"}, {"gap_strength": "high"}]
        result = get_dynamic_kill_switch([{"outlier_score": 10}], {"label": "COMPETITIVE"}, gaps)
        self.assertTrue(result["proceed"])
        self.assertIn("breakout room", result["reason"])

    def test_fewer_gaps_than_the_threshold_still_kills(self):
        result = get_dynamic_kill_switch([{"outlier_score": 10}], {"label": "COMPETITIVE"}, [{"gap_strength": "high"}])
        self.assertFalse(result["proceed"])
        self.assertEqual(result["confidence"], "low")

    def test_unmeasured_top_score_is_not_a_weak_signal(self):
        for top in ([{"outlier_score": None}], []):
            result = get_dynamic_kill_switch(top, {"label": "SATURATED"}, [])
            self.assertTrue(result["proceed"], top)

    def test_thresholds_are_the_fixed_defaults(self):
        for label, expected in (("UNDERSERVED", 480.0), ("COMPETITIVE", 800.0), ("SATURATED", 1200.0), ("UNKNOWN", 800.0)):
            result = get_dynamic_kill_switch([{"outlier_score": 5000}], {"label": label}, [])
            self.assertEqual(result["thresholds_used"], {"outlier_threshold": expected, "gap_threshold": 2})


class UniquenessTests(unittest.TestCase):
    def test_no_competitors_means_unknown_uniqueness(self):
        self.assertIsNone(analyze_opportunity_gaps([], [], [], [], {}, target_title="Cold brew at home")["ai_uniqueness_score"])
        self.assertIsNone(analyze_opportunity_gaps([], [], [_row("Cold brew at home")], [], {})["ai_uniqueness_score"])

    def test_identical_tamil_titles_are_not_unique(self):
        title = "சிக்கன் பிரியாணி செய்வது எப்படி"
        self.assertEqual(find_content_similarity(title, title), 1.0)
        result = analyze_opportunity_gaps([], [], [_row(title)], [], {}, target_title=title)
        self.assertEqual(result["ai_uniqueness_score"], 0.0)

    def test_english_similarity_is_unchanged(self):
        self.assertEqual(find_content_similarity("How to make cold brew coffee", "Cold brew coffee at home"), 0.5)


class FormatLockTests(unittest.TestCase):
    def test_missing_and_live_durations_do_not_lock_long_form(self):
        result = _format_lock_in([_row(duration=None), _row(duration="P0D"), _row(duration="")], [], {})
        self.assertEqual(result["recommended_format"], "unknown")
        self.assertEqual(result["recommended_length"], "unknown")

    def test_unknown_durations_are_left_out_of_the_vote(self):
        result = _format_lock_in([_row(duration="PT45S"), _row(duration=None), _row(duration="PT30S")], [], {})
        self.assertEqual(result["recommended_format"], "short-form")
        self.assertIn("1 compared video(s) had no known duration", result["reason"])

    def test_known_durations_use_the_three_minute_shorts_boundary(self):
        # A Short runs up to three minutes, as in research filtering and the
        # watchlist; a 60-second cut called a 90-second Short long-form.
        self.assertEqual(_format_lock_in([_row(duration="PT1M30S")], [], {})["recommended_format"], "short-form")
        self.assertEqual(_format_lock_in([_row(duration="PT3M")], [], {})["recommended_length"], "3 minutes or less")
        self.assertEqual(_format_lock_in([_row(duration="PT3M1S")], [], {})["recommended_length"], "6-12 minutes")
        self.assertEqual(_format_lock_in([_row(duration="P1DT2H")], [], {})["recommended_format"], "long-form")


if __name__ == "__main__":
    unittest.main()
