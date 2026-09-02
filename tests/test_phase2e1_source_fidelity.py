from __future__ import annotations

import unittest

from win_engine.analysis.generation_quality import evaluate_package_quality
from win_engine.analysis.keyword_research import build_keyword_research, select_final_tags
from win_engine.llm.seo_writer import _build_user_prompt


def _silent_quote_brief(quote: str) -> dict[str, str]:
    return {
        "video_format": "youtube_shorts", "voice_over": "none", "exact_quote": quote,
        "on_screen_text": quote, "visual_requirements": "Two people standing on a road.",
    }


class SourceFidelityTests(unittest.TestCase):
    def test_silent_misunderstood_quote_rejects_fabricated_advice_in_every_field(self):
        quote = "Being misunderstood is the price we pay for being genuine."
        gate = evaluate_package_quality(
            {
                "title": "Coping with being misunderstood #shorts",
                "variants": ["Being misunderstood without losing yourself #shorts"],
                "description": f"{quote}\n\nWe break down practical tips and common questions about how to cope.",
                "tags": ["coping with being misunderstood", "being genuine"],
                "hashtags": ["#shorts", "#authenticity"],
            }, script=quote, creator_brief=_silent_quote_brief(quote), require_shorts_tags=False,
        )
        flagged = {(item["field"], item["code"]) for item in [*gate["issues"], *(issue for rejected in gate["rejected_candidates"] for issue in rejected["issues"])]}
        self.assertIn(("title", "unsupported_instructional_framing"), flagged)
        self.assertIn(("description", "unsupported_instructional_framing"), flagged)
        self.assertIn(("tags", "unsupported_instructional_framing"), flagged)
        self.assertTrue(gate["silent_quote_only_checked"])

    def test_other_silent_quote_rejects_counseling_and_explanation_framing(self):
        quote = "Some people only value you when they need you."
        gate = evaluate_package_quality(
            {
                "title": "When people only value you #shorts",
                "variants": ["A thought about being valued #shorts"],
                "description": f"{quote}\n\nThis explains relationship counseling strategies and ways to overcome it.",
                "tags": ["feeling valued", "relationship counseling"], "hashtags": ["#shorts"],
            }, script=quote, creator_brief=_silent_quote_brief(quote), require_shorts_tags=False,
        )
        self.assertIn("unsupported_instructional_framing", {item["code"] for item in gate["issues"]})

    def test_structured_source_wins_over_an_expanded_research_query(self):
        quote = "Being misunderstood is the price we pay for being genuine."
        expanded_query = quote + " In this video we walk through methods, practical tips, and common questions."
        gate = evaluate_package_quality(
            {
                "title": "Coping with being misunderstood #shorts",
                "variants": ["Being misunderstood without losing yourself #shorts"],
                "description": f"{quote}\n\nWe share practical tips for coping.",
                "tags": ["coping with being misunderstood"], "hashtags": ["#shorts"],
            }, script=expanded_query, creator_brief={**_silent_quote_brief(quote), "content": quote}, require_shorts_tags=False,
        )
        self.assertTrue(gate["silent_quote_only_checked"])
        self.assertIn("unsupported_instructional_framing", {item["code"] for item in gate["issues"]})

    def test_silent_quote_tag_selection_excludes_instructional_research_concept(self):
        quote = "Being misunderstood is the price we pay for being genuine."
        brief = {**_silent_quote_brief(quote), "content": quote}
        research = build_keyword_research(
            script=quote,
            semantic={
                "primary_topic": "authenticity", "secondary_topics": ["being genuine"],
                "search_intents": ["coping with being misunderstood"], "keyword_clusters": [],
            },
            youtube_results=[{"title": "Being genuine", "description": "Authenticity and feeling misunderstood."}],
            research_queries=[{"type": "topic", "query": "authenticity"}], entity_signals=[], creator_brief=brief,
        )
        tags, _ = select_final_tags(
            research, generated_tags=["coping with being misunderstood", "being genuine"],
            title="Being genuine without approval #shorts", script=quote, creator_brief=brief,
        )
        self.assertNotIn("coping with being misunderstood", tags)
        self.assertTrue(tags)
        self.assertFalse(any("coping" in tag or "how to" in tag for tag in tags))

    def test_actual_bicycle_tutorial_keeps_instructional_language(self):
        script = "Here are three ways to fix a slipping bicycle chain. First inspect tension, then align the wheel, then test ride safely."
        gate = evaluate_package_quality(
            {
                "title": "How to Fix a Slipping Bicycle Chain", "variants": ["Three Ways to Fix a Slipping Bicycle Chain"],
                "description": "Here are three practical steps to fix a slipping bicycle chain and test it safely.",
                "tags": ["how to fix a slipping bicycle chain", "bicycle chain repair"], "hashtags": ["#bicycle"],
            }, script=script, creator_brief={"video_format": "tutorial", "voice_over": "present"},
        )
        self.assertNotIn("unsupported_instructional_framing", {item["code"] for item in gate["issues"]})
        self.assertFalse(gate["silent_quote_only_checked"])

    def test_prompt_tells_gemini_not_to_invent_instruction_for_silent_quote(self):
        quote = "Being misunderstood is the price we pay for being genuine."
        prompt = _build_user_prompt(quote, "", "english", "global", "general", "quotes", _silent_quote_brief(quote), {})
        self.assertIn("silent quote-only Short", prompt)
        self.assertIn("must never claim", prompt)


if __name__ == "__main__":
    unittest.main()
