"""Regression tests for matching demand topics to saved watchlist videos.

Tokens were ASCII-only and one shared word was a match: a Tamil topic never
matched an identical title, while "how to make masala tea" matched "How I built
a gaming PC" on "how" and borrowed its outlier result.
"""

import unittest
from datetime import datetime, timedelta, timezone

from win_engine.analysis.demand_explorer import analyze_demand


def _watch(title, status="possible_outlier"):
    return {"id": 1, "video_id": "watched", "title": title, "outlier": {"status": status}}


def _label(count, page_size, *, channels=None, recent=None):
    """The label for ``count`` engaged results over ``channels`` channels; ``recent`` are new, the rest a year old."""
    now = datetime.now(timezone.utc)
    channels, recent = channels or count, count if recent is None else recent
    rows = [{"video_id": str(i), "channel_id": f"c{i % channels}", "view_count": 100, "like_count": 5,
             "comment_count": 1, "published_at": (now if i < recent else now - timedelta(days=400)).isoformat()}
            for i in range(count)]
    research = {"youtube_results": rows, "research_diagnostics": {"page_size": page_size}}
    return analyze_demand("camera", research, [], {})[0]


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


class DemandScaleTests(unittest.TestCase):
    def test_page_size_five_keeps_the_original_counts(self):
        self.assertEqual(_label(8, 5, channels=4, recent=3), "strong_observed_interest")
        self.assertEqual(_label(5, 5, channels=3, recent=2), "active_topic")
        self.assertEqual(_label(3, 5, channels=2, recent=0), "emerging_signal")
        self.assertEqual(_label(2, 5), "insufficient_evidence")

    def test_an_under_filled_page_is_judged_on_the_results_it_returned(self):
        # The bars grew with the page size asked for: a niche topic with 25 of 50 results
        # read as "too sparse", while the same results were strong at a page of 5.
        for page_size in (5, 25, 50):
            with self.subTest(page_size=page_size):
                self.assertEqual(_label(25, page_size, recent=13), "strong_observed_interest")
                self.assertEqual(_label(8, page_size, channels=4, recent=3), "strong_observed_interest")

    def test_a_full_page_of_fifty_needs_the_same_shares_as_eight_results(self):
        self.assertEqual(_label(50, 50), "strong_observed_interest")
        self.assertEqual(_label(50, 50, channels=20, recent=13), "active_topic")
        # 10 channels and 5 recent uploads met the counts set for 8 results; of 50 they are weak, not sparse.
        self.assertEqual(_label(50, 50, channels=10, recent=5), "emerging_signal")

    def test_research_only_detail_is_not_saved_with_the_evidence(self):
        # The evidence is stored and cloud-synced; competitor tags and full descriptions only made it grow.
        row = {"video_id": "v1", "title": "Camera tips", "tags": ["camera"], "full_description": "x" * 4000,
               "default_audio_language": "en"}
        research = {"youtube_results": [row]}
        _, evidence = analyze_demand("camera", research, [], {})
        self.assertEqual(evidence["public_results"], [{"video_id": "v1", "title": "Camera tips"}])
        self.assertIn("tags", research["youtube_results"][0])  # the research itself keeps them


if __name__ == "__main__":
    unittest.main()
