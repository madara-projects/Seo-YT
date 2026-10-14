"""Regression tests for matching demand topics to saved watchlist videos.

Tokens were ASCII-only and one shared word was a match: a Tamil topic never
matched an identical title, while "how to make masala tea" matched "How I built
a gaming PC" on "how" and borrowed its outlier result.
"""

import unittest
from datetime import datetime, timezone

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


class DemandScaleTests(unittest.TestCase):
    def test_thresholds_follow_the_page_size(self):
        # Set for pages of 5 results; at 25 almost any topic read as strong interest.
        now = datetime.now(timezone.utc).isoformat()

        def research(count, page_size):
            rows = [{"video_id": str(i), "channel_id": f"c{i}", "published_at": now, "view_count": 100,
                     "like_count": 5, "comment_count": 1} for i in range(count)]
            return {"youtube_results": rows, "research_diagnostics": {"page_size": page_size}}

        self.assertEqual(analyze_demand("camera", research(8, 5), [], {})[0], "strong_observed_interest")
        self.assertEqual(analyze_demand("camera", research(8, 25), [], {})[0], "insufficient_evidence")
        self.assertEqual(analyze_demand("camera", research(40, 25), [], {})[0], "strong_observed_interest")
        self.assertEqual(analyze_demand("camera", research(8, 1), [], {})[0], "strong_observed_interest")

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
