"""Audit reproduction: copy that reverses the source's facts must not be GREEN.

Word overlap scored "excellent camera", "twenty hours" and "supported" as
grounded in a script that says the camera is poor, battery life is six hours
and wireless charging is not supported (title 100 / description 90, GREEN).
"""

from __future__ import annotations

import unittest

from win_engine.analysis.generation_quality import evaluate_package_quality, factual_contradictions

SCRIPT = (
    "Honest review of the Zenfone budget phone after two weeks. The camera is poor, "
    "especially in low light. Battery life is six hours of screen time on a full charge. "
    "Wireless charging is not supported, so you are stuck with the cable. "
    "The display is bright and the speakers are loud enough for a small room."
)
BRIEF = {"creator_intent": "An honest budget phone review that names the trade-offs.", "video_format": "review"}

REVERSED_TITLE = "Zenfone review: excellent camera and twenty hours of battery"
REVERSED_DESCRIPTION = (
    "Wireless charging supported, excellent camera, 20 hours of battery life. "
    "The Zenfone budget phone after two weeks of daily use."
)
CONSISTENT_TITLE = "Zenfone review: poor camera, six hours of battery, no wireless charging"
CONSISTENT_DESCRIPTION = (
    "The camera is poor in low light, the battery lasts 6 hours of screen time and wireless charging "
    "is not supported. The display is bright and the speakers are loud enough for a small room."
)


def package(title: str, description: str) -> dict:
    return {
        "title": title,
        "variants": [title],
        "description": description,
        "tags": ["zenfone review", "budget phone camera test"],
        "hashtags": ["#zenfone"],
    }


class FactualContradictionTests(unittest.TestCase):
    def test_reversed_facts_are_reported_for_title_and_description(self):
        issues = factual_contradictions(SCRIPT, REVERSED_TITLE, REVERSED_DESCRIPTION)
        self.assertTrue(issues)
        self.assertEqual({item["code"] for item in issues}, {"factual_contradiction"})
        self.assertEqual({item["field"] for item in issues}, {"title", "description"})
        messages = " ".join(item["message"] for item in issues)
        self.assertIn('"20 hour"', messages)
        self.assertIn('"6 hour"', messages)
        self.assertIn('"supported"', messages)
        self.assertIn('"not supported"', messages)
        self.assertIn('"excellent"', messages)
        self.assertIn('"poor"', messages)

    def test_consistent_copy_has_no_contradiction(self):
        self.assertEqual(factual_contradictions(SCRIPT, CONSISTENT_TITLE, CONSISTENT_DESCRIPTION), [])

    def test_each_contradiction_shape_is_caught_alone(self):
        self.assertTrue(factual_contradictions(SCRIPT, "Zenfone battery test: 20 hours of screen time", ""))
        self.assertTrue(factual_contradictions(SCRIPT, "Zenfone review: wireless charging supported", ""))
        self.assertTrue(factual_contradictions(SCRIPT, "The Zenfone camera is excellent", ""))
        # The reverse direction: the copy denies what the source states.
        self.assertTrue(factual_contradictions("Wireless charging is supported.", "No wireless charging on this phone", ""))
        # A matching number, a question, and a fact the source states both ways are left alone.
        self.assertEqual(factual_contradictions(SCRIPT, "Six hours of battery: Zenfone review", ""), [])
        self.assertEqual(factual_contradictions(SCRIPT, "Is the Zenfone camera excellent?", ""), [])
        self.assertEqual(
            factual_contradictions("The camera is poor in low light. The camera is great in daylight.", "Great camera in daylight", ""),
            [],
        )

    def test_reversed_package_is_not_green(self):
        gate = evaluate_package_quality(package(REVERSED_TITLE, REVERSED_DESCRIPTION), script=SCRIPT, creator_brief=BRIEF)
        final = gate["final_seo_quality"]
        self.assertEqual(final["verdict"], "RED")
        self.assertEqual(gate["verdict"], "RED")
        codes = {item["code"] for item in final["critical_issues"]}
        self.assertIn("factual_contradiction", codes)
        self.assertLessEqual(final["title_score"], 35)
        self.assertLessEqual(final["description_score"], 35)

    def test_consistent_package_is_unaffected(self):
        gate = evaluate_package_quality(package(CONSISTENT_TITLE, CONSISTENT_DESCRIPTION), script=SCRIPT, creator_brief=BRIEF)
        final = gate["final_seo_quality"]
        codes = {item["code"] for item in final["critical_issues"] + final["warnings"]}
        self.assertNotIn("factual_contradiction", codes)
        self.assertGreater(final["title_score"], 35)
        self.assertGreater(final["description_score"], 35)


if __name__ == "__main__":
    unittest.main()
