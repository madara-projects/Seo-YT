"""Regression tests for matching demand topics to saved watchlist videos.

Tokens were ASCII-only and one shared word was a match: a Tamil topic never
matched an identical title, while "how to make masala tea" matched "How I built
a gaming PC" on "how" and borrowed its outlier result.
"""

import unittest

from win_engine.analysis.demand_explorer import analyze_demand


def _watch(title, status="possible_outlier"):
    return {"id": 1, "video_id": "watched", "title": title, "outlier": {"status": status}}


def _matches(topic, title):
    _, evidence = analyze_demand(topic, {"youtube_results": []}, [_watch(title)], {})
    return evidence["watchlist_evidence"]


class DemandWatchlistMatchTests(unittest.TestCase):
    def test_function_words_do_not_match(self):
        self.assertEqual(_matches("how to make masala tea", "How I built a gaming PC"), [])
        self.assertEqual(_matches("how to make masala tea", "How to make cold coffee"), [])

    def test_two_shared_words_match(self):
        self.assertEqual(len(_matches("how to make masala tea", "Street style masala tea recipe")), 1)

    def test_one_word_topic_needs_that_word(self):
        self.assertEqual(len(_matches("camera", "best camera test")), 1)
        self.assertEqual(_matches("camera", "best phone test"), [])

    def test_tamil_topic_matches_tamil_title(self):
        self.assertEqual(len(_matches("சிக்கன் பிரியாணி", "சிக்கன் பிரியாணி செய்வது எப்படி")), 1)

    def test_unrelated_match_adds_no_outlier_reason(self):
        _, evidence = analyze_demand("how to make masala tea", {"youtube_results": []}, [_watch("How I built a gaming PC")], {})
        self.assertFalse(any("watchlist" in reason for reason in evidence["reasons"]))


if __name__ == "__main__":
    unittest.main()
