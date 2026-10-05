"""Regression tests for the competitor gap analysis and its go/no-go heuristic.

Missing subscriber counts and durations were read as zero, a fixed 0.5 stood
in for title uniqueness, and a small title-count heuristic was presented as a
"very_high" confidence "market opportunity".
"""

import unittest

from win_engine.ai_enhancement import find_content_similarity
from win_engine.analysis.dynamic_thresholds import get_dynamic_kill_switch
from win_engine.analysis.gap_engine import (
    _competition_meter,
    _competitor_shadow,
    _differentiation_plan,
    _format_lock_in,
    _keyword_gaps,
    _opportunity_score,
    analyze_opportunity_gaps,
)
from win_engine.analysis.keyword_extractor import extract_keyword_signals


def _row(title="video", subscribers=1000, outlier=5.0, duration="PT8M"):
    return {"title": title, "subscriber_count": subscribers, "outlier_score": outlier, "duration": duration}


class KeywordGapTests(unittest.TestCase):
    """A gap is a phrase of the creator's script that the sampled competitors do not use."""

    SHARED = "Some people come into your life for a reason"

    def test_a_phrase_the_sampled_competitors_share_is_not_a_gap(self):
        # Six competitor titles carried the same quote; the old rule counted their
        # mentions into the phrase's own and called it (and five more) "underused".
        results = [_row(f"{self.SHARED} #shorts {index}") for index in range(6)]
        signals = [
            {"keyword": "people come into", "mentions": 7},  # once in the script, in all six results
            {"keyword": "into your life", "mentions": 6},  # a competitor phrase, not in the script
            {"keyword": "quiet goodbye", "mentions": 2},  # the script's own phrase, used by no result
        ]
        gaps = _keyword_gaps(signals, results)
        self.assertEqual([(item["keyword"], item["gap_strength"]) for item in gaps], [("quiet goodbye", "high")])
        self.assertIn("none of the 6 sampled", gaps[0]["reason"])

    def test_phrases_the_extractor_joined_across_stop_words_are_not_gaps(self):
        # The extractor drops stop words before it joins words into phrases, so
        # "people come life" is in no title as written; searched for verbatim,
        # no competitor used it, and every such phrase of a quote all six
        # competitors shared was a "high" gap.
        results = [_row(f"{self.SHARED} #shorts {index}") for index in range(6)]
        signals = extract_keyword_signals(self.SHARED, results)
        self.assertIn("people come life", [item["keyword"] for item in signals])
        self.assertEqual(_keyword_gaps(signals, results), [])
        # The script's own phrase, which no competitor uses, is still one.
        signals.append({"keyword": "quiet goodbye", "mentions": 2})
        self.assertEqual([item["keyword"] for item in _keyword_gaps(signals, results)], ["quiet goodbye"])

    def test_one_user_in_a_sample_of_five_is_a_medium_gap(self):
        signals = [{"keyword": "quiet goodbye", "mentions": 2}]  # once in the script, once in a result
        few = [_row("A quiet goodbye"), _row("Alpha beta gamma"), _row("Delta epsilon zeta")]
        self.assertEqual(_keyword_gaps(signals, few), [])
        enough = few + [_row("Eta theta iota"), _row("Kappa lambda mu")]
        (gap,) = _keyword_gaps(signals, enough)
        self.assertEqual(gap["gap_strength"], "medium")
        self.assertIn("1 of the 5 sampled", gap["reason"])

    def test_the_analysis_no_longer_reports_shared_phrases_as_gaps(self):
        results = [_row(f"{self.SHARED} {index}") for index in range(6)]
        signals = [{"keyword": phrase, "mentions": 7} for phrase in ("people come into", "come into your", "into your life")]
        analysis = analyze_opportunity_gaps(signals, [], results, [], {})
        self.assertEqual(analysis["keyword_gaps"], [])
        self.assertEqual(analysis["opportunity_score"]["components"]["keyword_gap"], 0.0)

    def test_without_sampled_competitors_nothing_is_a_gap(self):
        # Every script phrase read "high: none of the 0 sampled competitor titles use it".
        self.assertEqual(_keyword_gaps([{"keyword": "quiet goodbye", "mentions": 2}], []), [])

    def test_a_longer_word_that_starts_with_the_phrase_is_not_a_use(self):
        # Devanagari vowel signs are not regex word characters, so "सच्चा प्यार"
        # (true love) was found inside "सच्चा प्यारा" (truly lovely) and lost its gap.
        signals = [{"keyword": "सच्चा प्यार", "mentions": 2}]
        results = [_row("सच्चा प्यारा दोस्त")] + [_row(f"title {index}") for index in range(4)]
        self.assertEqual([(gap["keyword"], gap["gap_strength"]) for gap in _keyword_gaps(signals, results)],
                         [("सच्चा प्यार", "high")])
        used = [_row("सच्चा प्यार कहानी")] + results[1:]
        self.assertEqual([gap["gap_strength"] for gap in _keyword_gaps(signals, used)], ["medium"])


class CompetitorShadowTests(unittest.TestCase):
    def test_titles_without_a_known_pattern_have_no_dominant_one(self):
        # max() over all-zero counts named the first pattern: three quote titles read "experiment".
        shadow = _competitor_shadow([_row("Sad love quotes"), _row("Missing you quotes"), _row("Let go")])
        self.assertEqual((shadow["dominant_title_pattern"], shadow["dominant_hook_pattern"]), ("other", "other"))
        self.assertNotIn("experiment", shadow["recommended_differentiation"])

    def test_a_day_count_alone_is_not_an_experiment(self):
        # A '30 days' rule left over from another niche.
        shadow = _competitor_shadow([_row("Sleep music for 30 days of calm"), _row("Rain sounds for 7 days")])
        self.assertEqual(shadow["dominant_title_pattern"], "other")
        tried = _competitor_shadow([_row("I tried cold showers for 30 days"), _row("Rain sounds")])
        self.assertEqual(tried["dominant_title_pattern"], "experiment")


class CompetitionPatternTests(unittest.TestCase):
    def test_thirty_days_titles_add_nothing(self):
        # A leftover of another niche: every "30 days" title added 20 points.
        self.assertEqual(_competition_meter([_row("I tried this for 30 days", outlier=None)], {})["score"], 0)
        self.assertNotIn("30 days", _competition_meter([_row("video")], {})["basis"])

    def test_titles_that_repeat_another_titles_opening_count(self):
        rows = [_row("Some people come into your life for a reason", outlier=None) for _ in range(4)]
        rows.append(_row("Let them go #shorts", outlier=None))
        competition = _competition_meter(rows, {})
        self.assertEqual(competition["repeated_title_patterns"], 3)
        self.assertEqual(competition["score"], 36)  # 60 points at most, by the share of the sample that repeats
        self.assertIn("same opening", competition["basis"])
        plan = _differentiation_plan([], competition, rows)
        self.assertTrue(any("some people come" in item.casefold() for item in plan["avoid_patterns"]))
        self.assertFalse(any("30 days" in item for item in plan["avoid_patterns"]))

    def test_distinct_titles_repeat_nothing(self):
        rows = [_row("Alpha beta gamma delta", outlier=None), _row("Epsilon zeta eta theta", outlier=None),
                _row("Alpha beta kappa lambda", outlier=None)]
        competition = _competition_meter(rows, {})
        self.assertEqual(competition["repeated_title_patterns"], 0)
        self.assertEqual(_differentiation_plan([], competition, rows)["avoid_patterns"], [])


class ScoreConfidenceTests(unittest.TestCase):
    TOP = [{"views_per_day": 1000, "small_channel_outlier": True, "matched_queries": ["a"],
            "subscriber_count": 5000, "view_count": 200000}] * 3
    GAPS = [{"keyword": "gap"}] * 3

    def test_fewer_than_five_sampled_results_cannot_be_medium_confidence(self):
        two = _opportunity_score(self.GAPS, {"score": 25}, self.TOP, research_result_count=2, keyword_signal_count=5)
        five = _opportunity_score(self.GAPS, {"score": 25}, self.TOP, research_result_count=5, keyword_signal_count=5)
        self.assertEqual((two["confidence"], two["breakdown"]["confidence"]), ("LOW", "low"))
        self.assertIn("Only 2 YouTube research result(s)", " ".join(two["breakdown"]["warnings"]))
        self.assertEqual(five["breakdown"]["confidence"], "medium")

    def test_the_score_is_marked_per_run_not_per_title(self):
        result = _opportunity_score(self.GAPS, {"score": 25}, self.TOP, research_result_count=12, keyword_signal_count=5)
        self.assertEqual(result["scope"], "per_run")
        self.assertFalse(result["varies_by_title"])
        self.assertEqual(result["breakdown"]["scope"], "per_run")
        self.assertIn("every package option", result["breakdown"]["statement"])
        unmeasured = analyze_opportunity_gaps([], [], [], [], {})["opportunity_score"]
        self.assertEqual((unmeasured["scope"], unmeasured["breakdown"]["scope"]), ("per_run", "per_run"))


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
