import unittest
from unittest.mock import patch

from win_engine.generation.quality_refinement import enforce_quality_target, refine_package


class QualityTargetTests(unittest.TestCase):
    def test_green_requires_all_three_scores_and_preserves_original_scores(self):
        for scores, met in [((90, 90, 90), True), ((89, 99, 99), False),
                            ((99, 89, 99), False), ((99, 99, 89), False),
                            ((99, 99, None), False)]:
            with self.subTest(scores=scores):
                quality = dict(zip(("title_score", "description_score", "tag_score"), scores))
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

    @patch("win_engine.generation.quality_refinement._generate_one")
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
