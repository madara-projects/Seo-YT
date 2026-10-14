import unittest
from unittest.mock import patch

from win_engine.generation.quality_refinement import enforce_quality_target, refine_package
from win_engine.analysis.keyword_research import synchronize_tag_evidence


class QualityTargetTests(unittest.TestCase):
    def test_evidence_is_rebuilt_from_final_tags(self):
        evidence = {
            "candidates": [
                {"keyword": "being forgotten", "classification": "core_topic", "source_classification": "combined", "source_support_score": 100, "evidence_count": 4},
                {"keyword": "loneliness", "classification": "secondary_topic", "source_classification": "combined", "source_support_score": 100, "evidence_count": 2},
            ],
            "selected_keywords": [{"keyword": "loneliness", "classification": "secondary_topic", "source_classification": "combined", "source_support_score": 100, "evidence_count": 2}],
            "selected_result_evidence": {"tags_with_matching_results": ["loneliness"]},
        }
        synced = synchronize_tag_evidence(evidence, ["being forgotten", "yt", "shorts"])
        self.assertEqual(synced["selected_tags"], ["being forgotten", "yt", "shorts"])
        self.assertEqual(synced["selected_result_evidence"]["tags_with_matching_results"], ["being forgotten"])
        self.assertNotIn("loneliness", synced["selected_result_evidence"]["tags_with_matching_results"])

    def test_green_requires_all_three_scores_and_preserves_original_scores(self):
        for scores, met in [((90, 90, 90), True), ((89, 99, 99), False),
                            ((99, 89, 99), False), ((99, 99, 89), False),
                            ((99, 99, None), False)]:
            with self.subTest(scores=scores):
                quality = dict(zip(("title_score", "description_score", "tag_score"), scores, strict=True))
                original = {"verdict": "GREEN", "final_seo_quality": {**quality, "verdict": "GREEN"}}
                result = enforce_quality_target(original)
                self.assertEqual(result["quality_target"]["met"], met)
                self.assertEqual(result["verdict"], "GREEN" if met else "YELLOW")
                self.assertEqual(original["verdict"], "GREEN")
                for field, score in quality.items():
                    self.assertEqual(result["final_seo_quality"][field], score)

    def test_target_never_promotes_red(self):
        gate = {"verdict": "RED", "final_seo_quality": {"verdict": "RED"}}
        self.assertEqual(enforce_quality_target(gate)["verdict"], "RED")

    def _refine_tags(self, rows):
        script = ("Cold brew coffee at home: coarse grounds steep in a mason jar of cold water for 12 to 18 hours, "
                  "then strain through a paper filter for a smooth, less bitter cup.")
        package = {"title": "Cold brew coffee at home in a mason jar", "variants": [],
                   "description": "Make smooth cold brew coffee at home in a mason jar with coarse grounds and cold water.",
                   "tags": [keyword for keyword, _ in rows], "hashtags": ["#ColdBrew"]}
        evidence = {"selected_keywords": [{"keyword": k, "keyword_relevance_score": s, "source_support_score": 100}
                                          for k, s in rows]}
        with patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=False):
            return refine_package(package, script=script, brief={"content": script, "video_format": "tutorial"},
                                  language="english", region="global", evidence=evidence, competitors=[])

    def test_grounded_tags_are_not_pruned_to_lift_the_average(self):
        rows = [("cold brew coffee", 88), ("cold brew at home", 86), ("mason jar coffee", 85), ("cold brew ratio", 84),
                ("coarse ground coffee", 83), ("cold brew steeping time", 82), ("paper filter coffee", 80),
                ("smooth coffee", 75)]
        refined, trace = self._refine_tags(rows)
        self.assertEqual(refined["tags"], [keyword for keyword, _ in rows])
        self.assertNotIn("pruned_tags", trace)

    def test_weak_tags_are_pruned_but_pruning_does_not_earn_green(self):
        rows = [("cold brew coffee", 96), ("cold brew at home", 94), ("mason jar coffee", 92), ("cold brew ratio", 90),
                ("coffee hacks", 68), ("kitchen tips", 72)]
        refined, trace = self._refine_tags(rows)
        self.assertEqual(trace["pruned_tags"], ["coffee hacks", "kitchen tips"])
        self.assertEqual(refined["tags"], ["cold brew coffee", "cold brew at home", "mason jar coffee", "cold brew ratio"])
        self.assertLess(trace["tag_score_before_pruning"], 90)
        gate = {"verdict": "GREEN", "final_seo_quality": {"title_score": 95, "description_score": 95, "tag_score": 93}}
        result = enforce_quality_target(gate, tag_score_before_pruning=trace["tag_score_before_pruning"])
        self.assertEqual(result["verdict"], "YELLOW")
        self.assertFalse(result["quality_target"]["met"])
        self.assertEqual(result["quality_target"]["shortfalls"], ["tag_score"])
        self.assertEqual(result["final_seo_quality"]["tag_score"], 93)
        self.assertEqual(enforce_quality_target(gate, tag_score_before_pruning=92)["verdict"], "GREEN")

    def test_an_explicit_quote_short_flag_alone_does_not_crash(self):
        gate = {"verdict": "GREEN", "final_seo_quality": {"title_score": 95, "description_score": 95, "tag_score": 95}}
        target = enforce_quality_target(gate, quote_short=True)["quality_target"]
        self.assertIn("title_score", target["not_counted"])
        self.assertTrue(target["met"])

    @patch("win_engine.generation.quality_refinement.generate_one")
    @patch("win_engine.generation.quality_refinement.gemini_client.is_available", return_value=True)
    @patch("win_engine.generation.quality_refinement.evaluate_package_quality")
    def test_failed_repair_keeps_valid_package_and_research_tags(self, evaluate, available, generate):
        def score(package, **kwargs):
            bad = package["title"] == "Invented claim"
            return {"passed": not bad, "final_seo_quality": {
                "title_score": 100 if bad else 80, "description_score": 100 if bad else 90}}
        evaluate.side_effect = score
        generate.return_value = {"title": "Invented claim", "variants": [], "description": "invented",
                                 "tags": ["viral"], "hashtags": ["#viral"]}
        package = {"title": "Grounded title", "variants": [], "description": "Source", "tags": ["source"], "hashtags": []}
        result, trace = refine_package(package, script="Source", brief={}, language="english",
                                       region="global", evidence={}, competitors=[])
        self.assertEqual(result["title"], "Grounded title")
        self.assertEqual(result["tags"], ["source"])
        self.assertFalse(trace["accepted"])
        self.assertEqual(generate.call_count, 1)
