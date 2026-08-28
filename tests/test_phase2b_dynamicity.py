from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from win_engine.analysis.creator_brief import build_creator_brief, creator_topic
from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.topic_lock import force_topic_in_tags
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.strategy_engine import _content_specific_fallback, build_seo_package


class Phase2BDynamicityTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = handle.name
        handle.close()
        self.store = HistoryStore(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    @staticmethod
    def _research(brief: dict, keyword: str, category: str) -> dict:
        return {
            "main_topic": keyword,
            "keyword_signals": [{"keyword": keyword}],
            "entity_signals": [],
            "top_opportunities": [],
            "youtube_results": [],
            "category": category,
            "creator_brief": brief,
            "language_context": {"language": "english", "region": "global"},
        }

    def test_local_fallback_matrix_is_topic_specific_and_has_three_strategies(self):
        cases = [
            ("tech", "A practical Python tutorial showing how to parse CSV files safely.", "python csv parsing"),
            ("travel", "A local Chennai street food walking tour through small evening stalls.", "Chennai street food"),
            ("food", "A dosa recipe using fermented rice batter for a crisp breakfast.", "dosa recipe"),
            ("gaming", "A Free Fire ranked clutch using a careful loadout and final zone.", "Free Fire ranked clutch"),
        ]
        outputs: dict[str, dict] = {}
        with patch("win_engine.generation.strategy_engine.write_multilang_packages_with_source", return_value=({"english": None}, "fallback")):
            for label, script, keyword in cases:
                brief = build_creator_brief(script=script)
                outputs[label] = build_seo_package(
                    "generate seo", script, self._research(brief, keyword, "education" if label == "tech" else label), self.store
                )

        titles = {label: item["title"].casefold() for label, item in outputs.items()}
        self.assertEqual(len(set(titles.values())), len(cases))
        descriptions = {label: item["description"].casefold() for label, item in outputs.items()}
        self.assertEqual(len(set(descriptions.values())), len(cases))
        for label, package in outputs.items():
            self.assertGreaterEqual(len(package["title_thumbnail_packages"]), 3, label)
            self.assertEqual(
                [item["package_intent"] for item in package["title_thumbnail_packages"][:3]],
                ["Search", "Browse", "Existing audience"],
            )
            self.assertIn(" ".join(package["creator_brief"]["topic"].split()[:3]).casefold(), package["description"].casefold())

        forbidden = {
            "tech": ("dosa", "free fire", "chennai"),
            "travel": ("python", "dosa", "free fire"),
            "food": ("python", "free fire", "chennai street"),
            "gaming": ("python", "dosa", "chennai street"),
        }
        for label, terms in forbidden.items():
            text = " ".join([outputs[label]["title"], outputs[label]["description"], *outputs[label]["tags"]]).casefold()
            self.assertFalse(any(term in text for term in terms), label)

    def test_inferred_topic_keeps_core_terms_for_arbitrary_non_quote_input(self):
        brief = build_creator_brief(script="A practical Python tutorial showing how to parse CSV files safely.")
        topic = creator_topic(brief)
        self.assertIn("python", topic)
        self.assertIn("csv", topic)
        self.assertIn("files", topic)

    def test_fallback_description_uses_source_context_not_a_universal_placeholder(self):
        first = build_creator_brief(script="A tutorial for repairing a bicycle chain with a multitool.")
        second = build_creator_brief(script="A guide to cooking lemon rice with roasted peanuts.")
        one = _content_specific_fallback(creator_topic(first), [], first)
        two = _content_specific_fallback(creator_topic(second), [], second)
        self.assertNotEqual(one["description"], two["description"])
        self.assertNotIn("actual details shown in the video", one["description"])
        self.assertIn("bicycle", one["description"].casefold())
        self.assertIn("lemon", two["description"].casefold())

    def test_generic_and_unrelated_tags_are_removed_or_rejected(self):
        locked = force_topic_in_tags(
            ["python csv parsing", "youtube", "viral", "trending", "chicken recipe", "shorts"],
            "python csv parsing", "education", context=["A Python tutorial parsing CSV files safely"],
        )
        self.assertEqual(locked, ["python csv parsing", "shorts"])
        gate = evaluate_package_quality(
            {
                "title": "How to Parse CSV Files Safely in Python",
                "variants": ["How to Parse CSV Files Safely in Python"],
                "description": "A practical Python CSV parsing tutorial.",
                "tags": ["python csv parsing", "youtube", "viral", "trending"],
                "hashtags": [],
            },
            script="A practical Python tutorial showing how to parse CSV files safely.",
        )
        self.assertIn("generic_tag_filler", {item["code"] for item in gate["issues"]})

    def test_short_fallback_keeps_semantic_emoji_and_single_shorts_tag(self):
        rain = build_creator_brief(script='Rainy road Short with the quote "I miss the quiet after goodbye."')
        moon = build_creator_brief(script='Night sky Short with the quote "Some memories glow after midnight."')
        rain_package = _content_specific_fallback(creator_topic(rain), [], rain)
        moon_package = _content_specific_fallback(creator_topic(moon), [], moon)
        self.assertEqual(rain_package["title"].casefold().count("#shorts"), 1)
        self.assertEqual(moon_package["title"].casefold().count("#shorts"), 1)
        self.assertNotEqual(rain_package["title"], moon_package["title"])
        self.assertIn("shorts", rain_package["tags"])
        self.assertIn("shorts", moon_package["tags"])


if __name__ == "__main__":
    unittest.main()
