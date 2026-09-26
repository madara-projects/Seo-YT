"""Regression tests for the package audit's topic and engagement checks.

An empty topic is contained in every string and a Tamil topic normalised to
"", so both earned free alignment credit; the quote branch guessed engagement
from mood words such as "rain" and "music".
"""

import unittest

from win_engine.analysis.content_auditor import _alignment_score, _contains_topic, audit_content_package


class TopicAlignmentTests(unittest.TestCase):
    def test_tamil_topic_earns_no_credit_on_an_unrelated_title(self):
        self.assertEqual(_alignment_score("Unrelated cooking recipe title", "some script words here", "காதல் வலி", ""), 0.0)

    def test_empty_topics_earn_no_credit(self):
        # Only the title words found in the script count now: 0.7, not 1.0.
        self.assertEqual(_alignment_score("Cold brew coffee recipe", "cold brew coffee recipe", "", ""), 0.7)
        self.assertFalse(_contains_topic("any opening at all", "", ""))

    def test_tamil_topic_and_title_are_matched(self):
        title = "காதல் வலி ஒரு நினைவு"
        script = "இது காதல் வலி பற்றிய ஒரு நினைவு"
        self.assertEqual(_alignment_score(title, script, "காதல் வலி", ""), 1.0)
        self.assertTrue(_contains_topic(script, "காதல் வலி", ""))

    def test_tamil_long_form_topic_is_named_early(self):
        script = "சிக்கன் பிரியாணி செய்வது எப்படி என்று இந்த வீடியோவில் பார்க்கலாம். " * 30
        audit = audit_content_package(script, "சிக்கன் பிரியாணி", "சிக்கன் பிரியாணி", "", video_format="tutorial")
        self.assertTrue(audit["hook_audit"]["keyword_in_opening"])


class QuoteBranchTests(unittest.TestCase):
    SCRIPT = (
        'A brief pause over rain footage. Ambient music begins. The quote appears phrase by phrase with a '
        'typewriter animation: "The worst heartbreak is realizing you meant less than they meant to you." '
        'Hold, then fade to black.'
    )

    def test_engagement_is_not_guessed_from_mood_words(self):
        audit = audit_content_package(self.SCRIPT, "When you realize you meant less to them", "worst heartbreak",
                                      "unrequited love", video_format="YouTube Short emotional quote video")
        self.assertEqual(audit["first_30_second_simulator"]["engagement_strength"], "UNKNOWN")
        self.assertIn("not a measurement", audit["first_30_second_simulator"]["basis"])
        # The rest of the quote branch is unchanged.
        self.assertEqual(audit["hook_audit"]["hook_strength"], "HIGH")
        self.assertTrue(audit["hook_audit"]["stakes_present"])
        self.assertEqual(audit["first_30_second_simulator"]["predicted_dropoff_risk"], "LOW")
        self.assertEqual(audit["pattern_interrupts"]["assessment"], "STRONG")

    def test_missing_secondary_topic_does_not_mark_the_topic_as_present(self):
        audit = audit_content_package(self.SCRIPT, "When you realize you meant less to them", "cold brew coffee", "",
                                      video_format="YouTube Short emotional quote video")
        self.assertFalse(audit["hook_audit"]["keyword_in_opening"])
        self.assertIn("Bring the main topic into the first few lines faster.", audit["retention_risk"]["notes"])


if __name__ == "__main__":
    unittest.main()
