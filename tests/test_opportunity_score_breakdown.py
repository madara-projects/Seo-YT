"""The Opportunity Score shows its five inputs, its missing data and its confidence.

The heuristic itself is unchanged: the same inputs give the same score. The
breakdown says where each input came from, and that the score is a local
heuristic, not a prediction of views.
"""

import math
import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.gap_engine import OPPORTUNITY_INPUTS, _opportunity_score, analyze_opportunity_gaps
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.seo_generator import generate_seo_suggestions
from win_engine.llm import gemini_client


def _legacy_score(keyword_gaps, competition, top_opportunities):
    """The formula exactly as it shipped before the breakdown was added."""
    opportunities = [item for item in top_opportunities[:3] if isinstance(item, dict)]
    velocity_scores = [
        min(100.0, 25.0 * math.log10(1.0 + max(float(item["views_per_day"]), 0.0)))
        for item in opportunities
        if item.get("views_per_day") is not None
    ]
    demand = sum(velocity_scores) / len(velocity_scores) if velocity_scores else 0.0
    gap = min((len(keyword_gaps) / 6.0) * 100.0, 100.0)
    room = 100.0 - min(max(float(competition.get("score") or 0), 0.0), 100.0)
    breakout = (
        sum(1 for item in opportunities if item.get("small_channel_outlier")) / len(opportunities) * 100.0
        if opportunities else 0.0
    )
    relevance = (
        sum(min(len(item.get("matched_queries") or []) / 3.0, 1.0) for item in opportunities) / len(opportunities) * 100.0
        if opportunities else 0.0
    )
    score = round((demand * 0.35) + (room * 0.25) + (gap * 0.20) + (breakout * 0.10) + (relevance * 0.10), 2)
    return min(max(score, 0.0), 100.0)


def _video(views_per_day, *, outlier=False, queries=("main topic",), subscribers=50000, views=20000):
    return {
        "views_per_day": views_per_day, "small_channel_outlier": outlier, "matched_queries": list(queries),
        "subscriber_count": subscribers, "view_count": views,
    }


TOP = [
    _video(1000, outlier=True, queries=("main topic", "viewer problem"), subscribers=5000, views=200000),
    _video(500, queries=("main topic",)),
    _video(250, outlier=True, queries=("main topic", "format", "angle"), subscribers=8000, views=150000),
]
GAPS = [{"keyword": "gap"}] * 3


def _inputs(result):
    return {item["key"]: item for item in result["breakdown"]["inputs"]}


class BreakdownMathTests(unittest.TestCase):
    def test_the_score_is_unchanged_for_the_same_inputs(self):
        cases = (
            ([], {"score": 85, "label": "SATURATED"}, []),
            (GAPS, {"score": 25}, TOP),
            ([{"keyword": "gap"}] * 8, {"score": 140}, TOP[:1]),
            ([], {"score": None}, [{"views_per_day": None}]),
            ([{"keyword": "gap"}], {"score": 55}, [{"views_per_day": 1000}, {"views_per_day": None}]),
        )
        for gaps, competition, top in cases:
            with self.subTest(competition=competition, top=len(top)):
                self.assertEqual(_opportunity_score(gaps, competition, top)["score"], _legacy_score(gaps, competition, top))

    def test_five_weighted_inputs_reproduce_the_score(self):
        result = _opportunity_score(GAPS, {"score": 25}, TOP, research_result_count=12, keyword_signal_count=5)
        breakdown = result["breakdown"]
        self.assertEqual(
            [item["key"] for item in breakdown["inputs"]],
            ["demand_velocity", "competition_room", "keyword_gap", "small_channel_breakout", "research_relevance"],
        )
        self.assertEqual([item["weight"] for item in breakdown["inputs"]], [0.35, 0.25, 0.2, 0.1, 0.1])
        self.assertEqual([weight for _, _, weight in OPPORTUNITY_INPUTS], [0.35, 0.25, 0.2, 0.1, 0.1])
        for item in breakdown["inputs"]:
            self.assertAlmostEqual(item["contribution"], item["value"] * item["weight"], delta=0.005)
            self.assertTrue(item["name"] and item["basis"])
        self.assertAlmostEqual(sum(item["contribution"] for item in breakdown["inputs"]), result["score"], delta=0.01)
        self.assertEqual(breakdown["score"], result["score"])
        # The values are the components the score already exposed.
        self.assertEqual({key: item["value"] for key, item in _inputs(result).items()}, result["components"])

    def test_complete_inputs_are_high_confidence_with_no_warnings(self):
        result = _opportunity_score(GAPS, {"score": 25}, TOP, research_result_count=12, keyword_signal_count=5)
        breakdown = result["breakdown"]
        sources = {key: item["source"] for key, item in _inputs(result).items()}
        self.assertEqual(sources, {
            "demand_velocity": "youtube_measured", "competition_room": "local_heuristic",
            "keyword_gap": "local_heuristic", "small_channel_breakout": "youtube_measured",
            "research_relevance": "local_heuristic",
        })
        self.assertEqual(breakdown["warnings"], [])
        self.assertEqual(breakdown["confidence"], "high")
        self.assertEqual(result["confidence"], "HIGH")
        self.assertEqual(breakdown["inputs_with_data"], 5)
        self.assertEqual(breakdown["top_videos_used"], 3)
        self.assertEqual(breakdown["research_results"], 12)

    def test_it_says_it_is_a_heuristic_not_a_prediction(self):
        breakdown = _opportunity_score(GAPS, {"score": 25}, TOP)["breakdown"]
        self.assertEqual(breakdown["kind"], "local_heuristic")
        self.assertIn("local heuristic", breakdown["statement"].lower())
        self.assertIn("not a prediction of views", breakdown["statement"].lower())
        self.assertIn("not how likely", breakdown["confidence_reason"].lower())
        text = " ".join([breakdown["statement"], breakdown["confidence_reason"], *(i["basis"] for i in breakdown["inputs"])]).lower()
        for claim in ("will get", "predicted views", "expected views", "guarantee"):
            self.assertNotIn(claim, text)


class MissingDataTests(unittest.TestCase):
    def test_no_top_videos_defaults_three_inputs_and_says_so(self):
        result = _opportunity_score([], {"score": 85, "label": "SATURATED"}, [], research_result_count=10, keyword_signal_count=4)
        sources = {key: item["source"] for key, item in _inputs(result).items()}
        for key in ("demand_velocity", "small_channel_breakout", "research_relevance"):
            self.assertEqual(sources[key], "missing_default", key)
            self.assertEqual(_inputs(result)[key]["value"], 0.0)
        self.assertEqual(sources["competition_room"], "local_heuristic")
        self.assertIn("No research video qualified as a top opportunity", " ".join(result["breakdown"]["warnings"]))
        self.assertEqual(result["breakdown"]["confidence"], "low")
        self.assertEqual(result["confidence"], "LOW")

    def test_an_unmeasured_velocity_is_left_out_and_reported(self):
        result = _opportunity_score([], {"score": 25}, [_video(1000), _video(None)], keyword_signal_count=3)
        demand = _inputs(result)["demand_velocity"]
        self.assertEqual(demand["value"], 75.01)
        self.assertEqual(demand["source"], "youtube_measured")
        warnings = " ".join(result["breakdown"]["warnings"])
        self.assertIn("View velocity was unavailable for 1 of the top 2", warnings)
        self.assertIn("Only 2 top research video(s)", warnings)
        self.assertEqual(result["breakdown"]["confidence"], "medium")

    def test_no_velocity_at_all_is_a_default(self):
        result = _opportunity_score([], {"score": 25}, [_video(None), _video(None)])
        self.assertEqual(_inputs(result)["demand_velocity"]["source"], "missing_default")
        self.assertIn("None of the top videos had a view velocity", " ".join(result["breakdown"]["warnings"]))

    def test_hidden_subscriber_counts_are_not_breakouts_and_are_flagged(self):
        top = [_video(10, subscribers=None, queries=("a",))] * 3
        result = _opportunity_score([], {"score": 10}, top)
        self.assertEqual(_inputs(result)["small_channel_breakout"]["source"], "missing_default")
        self.assertIn("Subscriber or view count was unavailable for 3 of the top 3", " ".join(result["breakdown"]["warnings"]))

    def test_no_keywords_from_the_script_is_a_default(self):
        result = _opportunity_score([], {"score": 10}, TOP, keyword_signal_count=0)
        self.assertEqual(_inputs(result)["keyword_gap"]["source"], "missing_default")
        self.assertIn("No keywords were extracted from your script", " ".join(result["breakdown"]["warnings"]))

    def test_unknown_channel_sizes_and_few_results_are_flagged(self):
        result = _opportunity_score(GAPS, {"score": 20, "unknown_channel_size_count": 2}, TOP, research_result_count=3)
        warnings = " ".join(result["breakdown"]["warnings"])
        self.assertIn("Channel size was unavailable for 2 sampled result(s)", warnings)
        self.assertIn("Only 3 YouTube research result(s) were sampled", warnings)
        self.assertNotEqual(result["breakdown"]["confidence"], "high")

    def test_unmeasured_competition_is_a_default(self):
        result = _opportunity_score(GAPS, {"score": None, "label": "UNKNOWN"}, TOP)
        room = _inputs(result)["competition_room"]
        self.assertEqual(room["source"], "missing_default")
        self.assertEqual(room["value"], 100.0)

    def test_without_competitor_results_there_is_no_score_and_it_says_why(self):
        score = analyze_opportunity_gaps([], [], [], [], {})["opportunity_score"]
        self.assertIsNone(score["score"])
        self.assertEqual(score["label"], "UNMEASURED")
        self.assertIsNone(score["breakdown"]["score"])
        self.assertEqual(score["breakdown"]["confidence"], "none")
        self.assertTrue(score["breakdown"]["warnings"][0].startswith("No competitor results"))
        self.assertIn("not a prediction of views", score["breakdown"]["statement"])

    def test_the_analysis_passes_its_research_counts(self):
        results = [{"title": f"video {index}", "subscriber_count": 5000, "outlier_score": 5.0} for index in range(12)]
        signals = [{"keyword": "cold brew", "mentions": 3}, {"keyword": "mason jar", "mentions": 2}]
        score = analyze_opportunity_gaps(signals, [], results, TOP, {})["opportunity_score"]
        self.assertEqual(score["breakdown"]["research_results"], 12)
        self.assertEqual(score["breakdown"]["top_videos_used"], 3)
        self.assertEqual(_inputs(score)["keyword_gap"]["source"], "local_heuristic")
        self.assertEqual(score["breakdown"]["score"], score["score"])


COLD_BREW = (
    "In this video I show you how to make cold brew coffee at home without any special "
    "equipment. You only need coarse ground coffee, a large mason jar, and cold water. "
    "Mix one cup of coffee grounds with four cups of water, stir, and let it steep in the "
    "fridge for 12 to 18 hours. Then strain it twice and compare it with hot coffee."
)


class SavedPackageTests(unittest.TestCase):
    def test_the_saved_package_keeps_the_breakdown_of_its_score(self):
        store = HistoryStore(":memory:")
        results = [
            {"video_id": f"vid{index:08d}", "title": f"Cold brew video {index}", "subscriber_count": 5000,
             "view_count": 20000, "outlier_score": 5.0, "published_at": "2026-09-01T00:00:00Z"}
            for index in range(6)
        ]
        research = {
            "history_store": store, "youtube_results": results, "entity_signals": [], "top_opportunities": TOP,
            "upload_timing": {}, "thumbnail_intelligence": {},
            "keyword_signals": [{"keyword": "cold brew coffee", "mentions": 3}],
        }
        writer = {"title": "Cold Brew Coffee at Home With Just a Mason Jar", "variants": [],
                  "description": "Make cold brew coffee at home with a mason jar.", "tags": ["cold brew coffee"],
                  "hashtags": ["#ColdBrew"]}
        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source",
                   return_value=({"english": writer}, "fallback")), \
             patch.object(gemini_client, "is_available", return_value=False):
            response = generate_seo_suggestions(COLD_BREW, research, context={
                "language": "english", "region": "global", "creator_brief": build_creator_brief(script=COLD_BREW),
            })
        delivered = response["opportunity_gap_analysis"]["opportunity_score"]
        saved = store.history_run(response["history_run_id"])
        stored = saved["package"]["opportunity_gap_analysis"]["opportunity_score"]
        self.assertEqual(stored["breakdown"], delivered["breakdown"])
        self.assertEqual(saved["opportunity_score"], round(stored["breakdown"]["score"], 2))
        self.assertEqual(len(stored["breakdown"]["inputs"]), 5)


if __name__ == "__main__":
    unittest.main()
