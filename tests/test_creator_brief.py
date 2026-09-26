"""Regression tests for duration and topic inference in the creator brief.

The duration pattern never matched "45 seconds" or "2 minutes" but read
"iPhone 5s" as five seconds, and Tamil text was split at every vowel sign, so a
Tamil script had no topic at all.
"""

import unittest

from win_engine.analysis.creator_brief import _extract_duration, _infer_topic, build_creator_brief


class DurationTests(unittest.TestCase):
    def test_plural_and_hyphenated_units_match(self):
        self.assertEqual(_extract_duration("A 45 seconds quote short"), 45.0)
        self.assertEqual(_extract_duration("Keep it to 2 minutes"), 120.0)
        self.assertEqual(_extract_duration("a 30-second reel"), 30.0)
        self.assertEqual(_extract_duration("about 1.5 mins long"), 90.0)
        self.assertEqual(_extract_duration("30 sec clip"), 30.0)

    def test_bare_letters_are_not_units(self):
        self.assertIsNone(_extract_duration("iPhone 5s camera review"))
        self.assertIsNone(_extract_duration("Money lessons for people in their 30s"))
        self.assertIsNone(_extract_duration("How I reached 5m views"))

    def test_brief_reports_the_inferred_duration(self):
        brief = build_creator_brief(script="Tutorial: set up a budget in 3 minutes", video_format="tutorial")
        self.assertEqual(brief["duration_seconds"], 180.0)
        self.assertEqual(brief["field_provenance"]["duration_seconds"]["source"], "inferred")


class TamilTopicTests(unittest.TestCase):
    def test_tamil_script_gets_a_topic(self):
        self.assertEqual(_infer_topic("நான் இன்று சிக்கன் பிரியாணி செய்கிறேன்", ""), "நான் இன்று சிக்கன் பிரியாணி செய்கிறேன்")

    def test_tamil_quote_words_stay_whole(self):
        self.assertEqual(_infer_topic("", "காதல் ஒரு வலி"), "காதல் ஒரு வலி")

    def test_english_quote_topic_keeps_one_letter_words(self):
        self.assertEqual(_infer_topic("", "I never knew what I had until it was gone."), "i never knew what i had until it was gone")
        self.assertEqual(_infer_topic("", "Life is a journey, not a race"), "life is a journey not a race")


if __name__ == "__main__":
    unittest.main()
