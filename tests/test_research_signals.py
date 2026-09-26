"""Regression tests: research signals must not be invented or inflated.

Covers a missing subscriber count read as a "small" channel, duration buckets
parsed by string splitting, keyword signals promoted to "high" strength by a
leftover growth-word list, competitor phrases standing in for a Tamil script,
and follow-up spokes made up when no validated phrase exists.
"""

import unittest

from win_engine.analysis.keyword_extractor import extract_keyword_signals
from win_engine.analysis.strategy_layer import (
    build_channel_intelligence,
    build_content_graph_strategy,
    diverse_followups,
)

TAMIL_BIRYANI = (
    "இந்த வீடியோவில் வீட்டிலேயே சுலபமாக செட்டிநாடு சிக்கன் பிரியாணி எப்படி செய்வது என்று "
    "பார்க்கலாம். பாஸ்மதி அரிசி, சிக்கன், தயிர், வெங்காயம் தேவை."
)


class ChannelIntelligenceTests(unittest.TestCase):
    def test_withheld_subscriber_count_is_unknown_not_small(self):
        for row in ({"subscriber_count": None}, {}, {"subscriber_count": ""}):
            with self.subTest(row=row):
                intelligence = build_channel_intelligence([{"title": "A cold brew recipe", "duration": "PT10M", **row}])
                self.assertEqual(intelligence["dominant_channel_size"], "unknown")
                self.assertNotIn("small", intelligence["summary"])
                self.assertIn("unknown size", intelligence["summary"])

    def test_reported_counts_still_bucket(self):
        sizes = [
            build_channel_intelligence([{"title": "t", "subscriber_count": count}])["dominant_channel_size"]
            for count in ("0", "9999", "10000", "250000")
        ]
        self.assertEqual(sizes, ["small", "small", "mid-sized", "large"])

    def test_durations_are_read_as_iso_8601(self):
        cases = {
            "PT45S": "short-form", "PT1M59S": "short-form", "PT2M": "mid-length", "PT8M59S": "mid-length",
            "PT9M": "long-form", "PT1H": "long-form",
            # Day parts were "unknown" under the old string splitting.
            "P1DT2H": "long-form",
            # Live and upcoming broadcasts report P0D, which says nothing about length.
            "P0D": "unknown", "": "unknown", None: "unknown",
        }
        for duration, expected in cases.items():
            with self.subTest(duration=duration):
                intelligence = build_channel_intelligence([{"title": "t", "subscriber_count": "5", "duration": duration}])
                self.assertEqual(intelligence["dominant_video_length"], expected)


class KeywordSignalTests(unittest.TestCase):
    def test_growth_words_do_not_promote_a_single_mention(self):
        for script, phrase in (
            ("easy cooking tips for beginners at home", "cooking tips"),
            # A region flag once made any phrase with a growth word "high" in India.
            ("honest phone reviews of budget models", "phone reviews"),
        ):
            with self.subTest(phrase=phrase):
                signals = {row["keyword"]: row for row in extract_keyword_signals(script, [])}
                self.assertIn(phrase, signals)
                self.assertEqual(signals[phrase]["mentions"], 1)
                self.assertEqual(signals[phrase]["strength"], "low")
                # A region flag that could only ever be False is not reported.
                self.assertNotIn("region_relevant", signals[phrase])

    def test_strength_follows_mentions(self):
        results = [{"title": "Cold brew coffee recipe", "description": ""}] * 5
        signals = {row["keyword"]: row for row in extract_keyword_signals("cold brew coffee at home", results)}
        self.assertEqual(signals["cold brew coffee"]["mentions"], 6)
        self.assertEqual(signals["cold brew coffee"]["strength"], "high")

    def test_competitor_phrases_do_not_replace_a_tamil_script(self):
        rows = [{"title": "iPhone Pro review: iphone pro camera test", "description": "iphone pro"}] * 3
        keywords = [row["keyword"] for row in extract_keyword_signals(TAMIL_BIRYANI, rows)]
        self.assertTrue(keywords)
        self.assertFalse([keyword for keyword in keywords if "iphone" in keyword])
        self.assertTrue(any("பிரியாணி" in keyword for keyword in keywords))
        # "இந்த வீடியோவில்" ("in this video") names no subject.
        self.assertFalse([keyword for keyword in keywords if "இந்த" in keyword or "வீடியோவில்" in keyword])

    def test_a_script_without_words_admits_no_result_phrases(self):
        rows = [{"title": "iPhone Pro review", "description": "iphone pro camera"}] * 3
        self.assertEqual(extract_keyword_signals("", rows), [])


class ContentGraphTests(unittest.TestCase):
    def test_no_spokes_are_invented_without_validated_phrases(self):
        graph = build_content_graph_strategy("cold brew")
        self.assertEqual(graph["hub_topic"], "cold brew")
        self.assertEqual(graph["supporting_topics"], [])
        text = str(graph)
        for invented in ("mistakes", "engagement tutorial", "There Nothing", "case study"):
            self.assertNotIn(invented, text)

    def test_followups_still_skip_near_duplicates_of_the_hub(self):
        phrases = ["cold brew", "cold brew coffee", "mason jar coffee", "coffee brewing methods"]
        self.assertEqual(diverse_followups("cold brew", phrases), ["mason jar coffee", "coffee brewing methods"])


if __name__ == "__main__":
    unittest.main()
