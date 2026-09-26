"""Research-call fixes: Tamil grounding, entity objects, shared parsing and call purposes."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from win_engine.analysis import search_opportunities
from win_engine.analysis.search_opportunities import discover_search_opportunities
from win_engine.analysis.semantic_research import (
    analyze_script_semantics,
    fallback_viewer_intent,
    refine_research_semantics,
)

TAMIL_RECIPE = "செட்டிநாடு சிக்கன் பிரியாணி செய்வது எப்படி"
RESULTS = [{"title": "Biryani recipe", "description": "Restaurant style biryani at home"}]


def _opportunities(*concepts: str) -> str:
    return json.dumps({"viewer_intent": "how_to", "opportunities": [
        {"concept": concept, "intent": "how_to", "cluster": "recipe",
         "script_relevance": 95, "research_relevance": 80, "reason": "Viewers search for the dish by name."}
        for concept in concepts
    ]})


@patch("win_engine.analysis.search_opportunities.gemini_client.is_available", return_value=True)
@patch("win_engine.analysis.search_opportunities.gemini_client.generate")
class SearchOpportunityGroundingTests(unittest.TestCase):
    def test_english_concepts_are_grounded_in_a_tamil_source(self, generate, _available):
        generate.return_value = _opportunities("chettinad chicken biryani", "சிக்கன் பிரியாணி")
        result = discover_search_opportunities(script=TAMIL_RECIPE, semantic={}, youtube_results=RESULTS)
        self.assertEqual(result["status"], "gemini_confirmed")
        self.assertEqual(
            [item["concept"] for item in result["opportunities"]],
            ["chettinad chicken biryani", "சிக்கன் பிரியாணி"],
        )
        self.assertTrue(all(item["source_support_score"] == 100 for item in result["opportunities"]))

    def test_a_tamil_source_still_rejects_unsupported_context(self, generate, _available):
        generate.return_value = _opportunities("family biryani recipe")
        result = discover_search_opportunities(script=TAMIL_RECIPE, semantic={}, youtube_results=RESULTS)
        self.assertEqual(result["opportunities"], [])
        self.assertEqual(result["rejected_count"], 1)

    def test_latin_sources_do_not_accept_sound_alikes(self, generate, _available):
        generate.return_value = _opportunities("bitter coffee")
        result = discover_search_opportunities(
            script="How I make better coffee at home every morning.", semantic={},
            youtube_results=[{"title": "Coffee at home", "description": "morning coffee"}],
        )
        self.assertEqual(result["opportunities"], [])

    def test_opportunities_call_is_a_research_call_with_room_for_reasoning(self, generate, _available):
        generate.return_value = _opportunities()
        discover_search_opportunities(script=TAMIL_RECIPE, semantic={}, youtube_results=RESULTS)
        self.assertEqual(generate.call_args.kwargs["purpose"], "research")
        self.assertGreaterEqual(generate.call_args.kwargs["max_tokens"], 1600)

    def test_a_trailing_comma_reply_is_repaired(self, generate, _available):
        generate.return_value = '{"viewer_intent": "how_to", "opportunities": [],}'
        result = discover_search_opportunities(script=TAMIL_RECIPE, semantic={}, youtube_results=RESULTS)
        self.assertEqual(result["status"], "gemini_confirmed")


class ViewerIntentTests(unittest.TestCase):
    def test_both_research_steps_read_intent_the_same_way(self):
        for script in (
            "How to clean a burr grinder step by step",
            "Why the sky is blue, explained",
            "Latest news from the launch today",
            "I miss the way we used to talk",
            "A quiet walk through the hills",
        ):
            with self.subTest(script=script):
                self.assertEqual(search_opportunities._intent({}, script), fallback_viewer_intent(script))


@patch("win_engine.analysis.semantic_research.gemini_client.is_available", return_value=True)
@patch("win_engine.analysis.semantic_research.gemini_client.generate")
class SemanticResearchTests(unittest.TestCase):
    SCRIPT = "Samsung Galaxy S25 Ultra review: camera, battery and display tested for a month."

    def test_entity_objects_keep_their_names(self, generate, _available):
        generate.return_value = json.dumps({
            "primary_topic": "Samsung Galaxy S25 Ultra review",
            "entities": [{"name": "Samsung Galaxy S25 Ultra", "type": "product"}, {"type": "unnamed"}, "Samsung"],
        })
        result = analyze_script_semantics(self.SCRIPT)
        self.assertEqual(result["source"], "gemini")
        self.assertEqual(result["entities"], ["Samsung Galaxy S25 Ultra", "Samsung"])

    def test_semantic_calls_use_the_research_breaker(self, generate, _available):
        generate.return_value = json.dumps({"primary_topic": "Samsung Galaxy S25 Ultra review"})
        analyze_script_semantics(self.SCRIPT)
        refine_research_semantics(self.SCRIPT, {}, [{"query": "galaxy s25 ultra review"}])
        self.assertTrue(generate.call_args_list)
        self.assertTrue(all(call.kwargs.get("purpose") == "research" for call in generate.call_args_list))


class GroundingTokenTests(unittest.TestCase):
    def test_words_of_every_script_are_anchors(self):
        from win_engine.analysis.semantic_research import _ground_tokens

        # A Hindi source used to have no anchors, so every proposed concept was "ungrounded".
        self.assertEqual(_ground_tokens("गाजर का हलवा रेसिपी"), {"गाजर", "हलवा", "रेसिपी"})
        self.assertIn("பிரியாணி", _ground_tokens(TAMIL_RECIPE))
        self.assertIn("biryani", _ground_tokens("Easy Biryani at home"))


if __name__ == "__main__":
    unittest.main()
