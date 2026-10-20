"""Audit reproductions: a validated citation must not launder an unrelated reading, and a tag must name the creator's product variant."""

from __future__ import annotations

import unittest

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.keyword_research import _source_support, build_keyword_research, select_final_tags
from win_engine.analysis.semantic_research import _validated_concept_evidence


class UnrelatedInterpretationTests(unittest.TestCase):
    QUOTE = "Small steps every day build lasting strength."

    def test_a_reading_sharing_no_word_with_the_source_is_not_validated_evidence(self):
        evidence = _validated_concept_evidence(
            [
                {"concept": "cryptocurrency investing", "source_phrase": self.QUOTE, "relationship": "metaphor"},
                {"concept": "daily small steps", "source_phrase": "Small steps every day", "relationship": "direct"},
            ],
            self.QUOTE,
        )
        self.assertEqual([item["concept"] for item in evidence], ["daily small steps"])

    def test_an_injected_citation_does_not_give_an_unrelated_phrase_source_support(self):
        semantic = {
            "primary_topic": "cryptocurrency investing", "concept_evidence_validated": True,
            "concept_evidence": [
                {"concept": "cryptocurrency investing", "source_phrase": self.QUOTE, "relationship": "metaphor"}],
        }
        brief = build_creator_brief(script=self.QUOTE, exact_quote=self.QUOTE)
        research = build_keyword_research(
            script=self.QUOTE, semantic=semantic, youtube_results=[], research_queries=[], entity_signals=[],
            creator_brief=brief,
        )
        row = next((row for row in research["candidates"] if row["keyword"] == "cryptocurrency investing"), None)
        self.assertLess(int(row["source_support_score"]) if row else 0, 50)
        tags, _ = select_final_tags(
            research, generated_tags=["cryptocurrency investing"], title="Small steps", script=self.QUOTE,
            creator_brief=brief, is_short=True,
        )
        self.assertNotIn("cryptocurrency investing", tags)

    def test_an_inflected_paraphrase_keeps_its_validated_support(self):
        quote = "Some days change everything you believed about yourself."
        semantic = {
            "primary_topic": "life changing events", "concept_evidence_validated": True,
            "concept_evidence": [
                {"concept": "life changing events", "source_phrase": "Some days change everything", "relationship": "paraphrase"}],
        }
        research = build_keyword_research(
            script=quote, semantic=semantic, youtube_results=[], research_queries=[], entity_signals=[],
            creator_brief=build_creator_brief(script=quote, exact_quote=quote),
        )
        row = next(row for row in research["candidates"] if row["keyword"] == "life changing events")
        self.assertGreaterEqual(int(row["source_support_score"]), 85)


class ProductVariantTests(unittest.TestCase):
    SCRIPT = "Samsung Galaxy S24 review after one month: camera, battery and the display in daily use."

    def test_an_unsupported_model_qualifier_rejects_the_tag(self):
        source_terms = set(self.SCRIPT.casefold().replace(":", " ").replace(",", " ").replace(".", " ").split())
        self.assertEqual(_source_support("samsung galaxy s24", source_terms)[0], 100)
        self.assertLess(_source_support("samsung galaxy s24 ultra", source_terms)[0], 50)
        self.assertLess(_source_support("iphone 15 review", {"iphone", "14", "review"})[0], 50)
        # A one-digit count is a list, not a product variant.
        self.assertGreaterEqual(_source_support("5 budgeting habits", {"five", "budgeting", "habits"})[0], 50)

    def test_the_final_tags_name_the_creators_variant(self):
        brief = build_creator_brief(script=self.SCRIPT)
        research = build_keyword_research(
            script=self.SCRIPT, semantic={"primary_topic": "Samsung Galaxy S24 review", "entities": ["Samsung Galaxy S24"]},
            youtube_results=[], research_queries=[], entity_signals=[], creator_brief=brief,
        )
        tags, evidence = select_final_tags(
            research, generated_tags=["samsung galaxy s24", "samsung galaxy s24 ultra"], title="Galaxy S24 review",
            script=self.SCRIPT, creator_brief=brief,
        )
        # The selector may fold the bare phrase into a longer tag it already
        # delivers ("samsung galaxy s24 review"); the creator's variant is named either way.
        self.assertTrue(any(tag.startswith("samsung galaxy s24") for tag in tags), tags)
        self.assertFalse(any("ultra" in tag for tag in tags), tags)
        rejected = {row["keyword"]: row["reason"] for row in evidence["rejected_candidates"]}
        self.assertEqual(rejected.get("samsung galaxy s24 ultra"), "weak_source_support")


if __name__ == "__main__":
    unittest.main()
