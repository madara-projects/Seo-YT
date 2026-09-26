"""Regression tests for thumbnail competition claims.

Search results list default, medium and high thumbnails for every video, so
"competitive_strength" was "strong" for any three results, and results with no
thumbnail metadata were reported as "low-resolution".
"""

import unittest

from win_engine.analysis.thumbnail_classifier import build_thumbnail_strategy
from win_engine.analysis.thumbnail_intelligence import analyze_thumbnails

_SEARCH_THUMBNAILS = {"default": {"width": 120}, "medium": {"width": 320}, "high": {"width": 480}}


class ThumbnailStrengthTests(unittest.TestCase):
    def test_standard_search_sizes_do_not_claim_strength(self):
        intelligence = analyze_thumbnails([{"thumbnails": dict(_SEARCH_THUMBNAILS)} for _ in range(5)])
        self.assertEqual(intelligence["low_resolution_count"], 0)
        self.assertIn("cannot show how strong", intelligence["recommendation"])
        self.assertEqual(build_thumbnail_strategy(intelligence, "Cold brew at home", "Tutorial")["competitive_strength"], "unknown")

    def test_missing_thumbnail_metadata_is_not_low_resolution(self):
        intelligence = analyze_thumbnails([{"title": "no thumbnails"} for _ in range(3)])
        self.assertNotIn("low-resolution", intelligence["recommendation"])

    def test_mostly_low_resolution_sample_is_reported(self):
        intelligence = analyze_thumbnails([{"thumbnails": {"default": {"width": 120}}} for _ in range(3)])
        self.assertEqual(intelligence["low_resolution_count"], 3)
        self.assertIn("skew low-resolution", intelligence["recommendation"])
        self.assertEqual(build_thumbnail_strategy(intelligence, "Cold brew at home", "Tutorial")["competitive_strength"], "weak")


if __name__ == "__main__":
    unittest.main()
