from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from win_engine.analysis.keyword_research import _classify, build_keyword_research, select_final_tags
from win_engine.analysis.search_opportunities import discover_search_opportunities
from win_engine.generation.strategy_engine import _content_specific_fallback
from win_engine.llm import gemini_client


class GeminiRateLimitTests(unittest.TestCase):
    def setUp(self):
        gemini_client.reset_provider_health()

    def tearDown(self):
        gemini_client.reset_provider_health()

    def _success(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
        return response

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_transient_429_retries_and_succeeds(self, post, sleep):
        limited = MagicMock(status_code=429)
        limited.headers = {"retry-after": "2"}
        post.side_effect = [limited, self._success()]
        with patch.dict(os.environ, {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}):
            text, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(text, "{}")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(trace["status"], "gemini_success")
        self.assertEqual(trace["retries"], 1)
        self.assertTrue(trace["rate_limited_before_success"])
        self.assertGreaterEqual(sleep.call_args.args[0], 2)

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_repeated_429_has_bounded_safe_failure(self, post, _sleep):
        limited = MagicMock(status_code=429)
        limited.headers = {}
        post.return_value = limited
        with patch.dict(os.environ, {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}):
            text, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(text, "")
        self.assertEqual(trace["status"], "gemini_rate_limited")
        self.assertEqual(post.call_count, 3)
        self.assertEqual(trace["retries"], 2)


class FallbackAndGroundingTests(unittest.TestCase):
    def test_narrative_fallback_is_coherent_and_not_instructional(self):
        script = "He kept checking the same empty road every evening, even after he knew she wasn't coming back."
        package = _content_specific_fallback("waiting on an empty road", [], {
            "content": script, "video_format": "youtube_shorts", "creator_intent": "Cinematic story",
        })
        self.assertNotIn("how ", package["title"].casefold())
        self.assertNotIn("step-by-step", package["description"].casefold())
        self.assertIn("waiting", package["title"].casefold())

    def test_creator_instruction_and_fragments_are_rejected(self):
        terms = {"message", "three", "words", "keyboard", "mechanical", "membrane"}
        for value in (
            "emotional short story without inventing the message",
            "minimal motivational content without a specific life problem",
            "silent reflective quote", "minimal reflection", "fast near", "one room", "slow one",
            "checking same", "walks through green hills while", "used talk every then neither", "value only after",
            "between tcp", "udp user",
        ):
            _, rejected = _classify(value, "long_tail", terms, set())
            self.assertIsNotNone(rejected, value)

    @patch("win_engine.analysis.search_opportunities.gemini_client.is_available", return_value=True)
    @patch("win_engine.analysis.search_opportunities.gemini_client.generate")
    def test_research_cannot_add_unsupported_gaming_context(self, generate, _available):
        generate.return_value = '{"viewer_intent":"comparison","opportunities":[{"concept":"gaming performance","intent":"comparison","cluster":"gaming","script_relevance":98,"research_relevance":90}]}'
        result = discover_search_opportunities(
            script="Mechanical keyboards are tactile; membrane keyboards are quieter.",
            semantic={"viewer_intent": "comparison"}, creator_brief={},
            youtube_results=[{"title": "Gaming keyboard performance", "description": "comparison"}],
        )
        self.assertEqual(result["opportunities"], [])

    @patch("win_engine.analysis.search_opportunities.gemini_client.is_available", return_value=True)
    @patch("win_engine.analysis.search_opportunities.gemini_client.generate")
    def test_research_cannot_invent_cloud_region_choice(self, generate, _available):
        generate.return_value = '{"viewer_intent":"explanation","opportunities":[{"concept":"choosing the correct cloud region","intent":"explanation","cluster":"cloud","script_relevance":98,"research_relevance":90}]}'
        result = discover_search_opportunities(
            script="An availability zone is an isolated location used for resilient cloud workloads.",
            semantic={"viewer_intent": "explanation"}, creator_brief={},
            youtube_results=[{"title": "Choose the best cloud region", "description": "cloud"}],
        )
        self.assertEqual(result["opportunities"], [])

    def test_research_tag_has_source_support_provenance(self):
        research = build_keyword_research(
            script="TCP establishes a connection before transferring data, while UDP sends packets without the same connection setup.",
            semantic={"primary_topic": "TCP vs UDP", "secondary_topics": [], "search_intents": [], "keyword_clusters": []},
            creator_brief={}, research_queries=[], entity_signals=[], youtube_results=[],
            search_opportunities={"opportunities": [{"concept": "TCP connection oriented", "semantic_confirmed": True,
                "script_relevance_score": 90, "research_relevance_score": 60, "intent": "comparison", "cluster": "tcp"}]},
        )
        tags, evidence = select_final_tags(research, generated_tags=[], title="TCP vs UDP", script="TCP establishes a connection before transferring data, while UDP sends packets without the same connection setup.")
        self.assertIn("tcp connection oriented", tags)
        selected = next(item for item in evidence["selected_keywords"] if item["keyword"] == "tcp connection oriented")
        self.assertGreaterEqual(selected["source_support_score"], 70)
        self.assertTrue(selected["source_support"])

    def test_sparse_fallback_does_not_become_a_guide(self):
        package = _content_specific_fallback("keep going", [], {
            "content": "Keep going.", "video_format": "youtube_shorts", "creator_intent": "Minimal reflection",
        })
        self.assertNotIn("guide", " ".join([package["title"], package["description"], *package["hashtags"]]).casefold())

    def test_quote_fragment_is_not_promoted_by_research_evidence(self):
        quote = "Some people only value you when they need you."
        research = build_keyword_research(
            script=quote,
            semantic={"primary_topic": "being valued", "secondary_topics": [], "search_intents": [], "keyword_clusters": []},
            creator_brief={"exact_quote": quote}, research_queries=[{"query": "some people only value you"}],
            entity_signals=[], youtube_results=[{"title": "Some people only value you", "description": quote}],
        )
        tags, _ = select_final_tags(research, generated_tags=["some people only value when"], title="Being valued #shorts", script=quote, creator_brief={"exact_quote": quote})
        self.assertNotIn("some people only value when", tags)


if __name__ == "__main__":
    unittest.main()
