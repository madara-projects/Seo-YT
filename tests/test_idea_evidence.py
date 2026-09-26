"""Regression tests for saved idea research.

The snapshot dropped keyword_research, so "Generate from idea" chose tags
without candidates or search-demand evidence, and a raw outlier score of 3
counted almost every result as a possible outlier.
"""

import unittest

from win_engine.analysis.idea_workspace import build_idea_evidence, evidence_to_research


def _result(score, **extra):
    return {"title": "Public result", "outlier_score": score, **extra}


class IdeaResearchFieldsTests(unittest.TestCase):
    def test_keyword_research_and_search_demand_survive_the_snapshot(self):
        keyword_research = {
            "candidates": [{"keyword": "cold brew coffee", "source": "search_demand"}],
            "search_demand": {"status": "ok", "grounded_suggestions": ["cold brew coffee at home"]},
        }
        evidence = build_idea_evidence({
            "youtube_results": [], "research_queries": [],
            "keyword_research": keyword_research, "search_demand": {"status": "ok"},
        })
        research = evidence_to_research(evidence)
        self.assertEqual(research["keyword_research"], keyword_research)
        self.assertEqual(research["search_demand"], {"status": "ok"})

    def test_old_snapshots_rehydrate_empty_evidence(self):
        research = evidence_to_research({"youtube_results": [], "cache_policy": None})
        self.assertEqual(research["keyword_research"], {})
        self.assertEqual(research["search_demand"], {})


class PossibleOutlierTests(unittest.TestCase):
    def test_ordinary_videos_are_not_possible_outliers(self):
        # 20k views on a 150k-subscriber channel scored 17.93 and used to count.
        evidence = build_idea_evidence({"youtube_results": [_result(17.93), _result(20.0), _result(15.0)]})
        self.assertEqual(evidence["signals"]["possible_outlier_count"], 0)

    def test_a_result_far_above_the_sample_median_counts(self):
        results = [_result(score) for score in (10.0, 12.0, 14.0, 16.0, 18.0)] + [_result(90.0)]
        evidence = build_idea_evidence({"youtube_results": results})
        self.assertEqual(evidence["signals"]["possible_outlier_count"], 1)

    def test_small_sample_has_no_relative_baseline(self):
        evidence = build_idea_evidence({"youtube_results": [_result(10.0), _result(900.0)]})
        self.assertEqual(evidence["signals"]["possible_outlier_count"], 0)

    def test_small_channel_breakout_counts_but_unmeasured_rows_do_not(self):
        evidence = build_idea_evidence({"youtube_results": [
            _result(40.0, small_channel_outlier=True),
            _result(None, small_channel_outlier=True),
            _result(None),
        ]})
        self.assertEqual(evidence["signals"]["possible_outlier_count"], 1)
        self.assertIn("Outlier stats were unavailable for 2 result(s).", evidence["opportunity_explanation"])
        self.assertIn("not monthly search volume", evidence["opportunity_explanation"])


if __name__ == "__main__":
    unittest.main()
