"""Regression tests for language detection and the research angle defaults.

"video" counted as a Spanish word, any four non-ASCII characters (Tamil
script, curly quotes, an emoji) meant Hindi, and every video without a stated
audience was pitched "for viewers who relate to the emotion".
"""

import unittest

from win_engine.analysis.language_engine import build_language_strategy
from win_engine.analysis.research_insights import build_research_decision


def _language(script, language="auto"):
    return build_language_strategy(script, {"language": language})["primary_language"]


class LanguageDetectionTests(unittest.TestCase):
    def test_english_that_mentions_video_is_english(self):
        self.assertEqual(_language("In this video I show my video setup and my video editing tips"), "english")

    def test_curly_quotes_and_emoji_do_not_make_english_hindi(self):
        self.assertEqual(_language("“Don’t quit” — the best advice I got 🔥🔥 ‘ever’"), "english")

    def test_scripts_are_detected_by_writing_system(self):
        self.assertEqual(_language("இந்த வீடியோவில் சிக்கன் பிரியாணி செய்வது எப்படி என்று பார்க்கலாம்"), "tamil")
        self.assertEqual(_language("इस वीडियो में हम बिरयानी बनाना सीखेंगे"), "hinglish_or_hindi")
        self.assertEqual(_language("Как приготовить борщ дома"), "unknown")

    def test_marker_languages_still_detected(self):
        self.assertEqual(_language("semma da, vera level video pa, macha"), "tanglish")
        self.assertEqual(_language("yeh kya hai aur kaise karna hai nahi pata"), "hinglish_or_hindi")
        self.assertEqual(_language("como crecer tu canal porque es muy fácil para todos"), "spanish_like")

    def test_selected_language_still_wins(self):
        self.assertEqual(_language("இந்த வீடியோவில்", language="english"), "english")


class ResearchAngleTests(unittest.TestCase):
    def test_tutorial_without_an_audience_gets_no_emotional_defaults(self):
        decision = build_research_decision({"topic": "how to fix a bike chain"}, [])
        text = f"{decision['recommended_angle']} {decision['reason']}".lower()
        self.assertEqual(decision["recommended_angle"], "Lead with how to fix a bike chain.")
        self.assertNotIn("emotion", text)

    def test_quote_video_keeps_the_emotional_defaults(self):
        decision = build_research_decision({"exact_quote": "Some people leave without saying goodbye."}, [])
        self.assertIn("viewers who relate to the emotion", decision["recommended_angle"])
        self.assertIn("emotional recognition", decision["reason"])

    def test_stated_audience_and_promise_are_used(self):
        decision = build_research_decision(
            {"topic": "bike chain repair", "target_audience": "new cyclists", "viewer_promise": "a quiet chain"}, [],
        )
        self.assertEqual(decision["recommended_angle"], "Lead with bike chain repair for new cyclists.")
        self.assertIn("deliver a quiet chain", decision["reason"])


if __name__ == "__main__":
    unittest.main()
