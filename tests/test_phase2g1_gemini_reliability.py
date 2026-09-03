"""Phase 2G.1: provider resilience must never weaken final SEO quality."""

from __future__ import annotations

import json
import os
import time
import unittest
from unittest.mock import MagicMock, patch

import httpx

from win_engine.analysis.creator_brief import build_creator_brief
from win_engine.analysis.keyword_research import build_keyword_research
from win_engine.feedback.history_store import HistoryStore
from win_engine.generation.strategy_engine import _content_specific_fallback, build_seo_package
from win_engine.llm import gemini_client
from win_engine.llm.seo_writer import write_multilang_packages_with_source


def _response(package: dict[str, object]) -> MagicMock:
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(package)}]}}]
    }
    return response


def _valid_quote_package() -> dict[str, object]:
    return {
        "title": "Being Genuine Can Feel Misunderstood #shorts",
        "variants": [
            "Being Genuine Can Feel Misunderstood #shorts",
            "The Cost of Being Genuine #shorts",
            "When Being Genuine Feels Misunderstood #shorts",
            "Misunderstood for Being Genuine #shorts",
            "A Quiet Truth About Being Genuine #shorts",
        ],
        "description": "“Being misunderstood is the price we pay for being genuine.” A reflective Short about the words shown on screen.",
        "tags": ["being misunderstood", "being genuine"],
        "hashtags": ["#shorts", "#quotes"],
    }


def _quote_research(script: str, brief: dict[str, object]) -> dict[str, object]:
    keyword_research = build_keyword_research(
        script=script,
        semantic={"primary_topic": "being misunderstood", "secondary_topics": ["being genuine"], "search_intents": [], "keyword_clusters": []},
        creator_brief=brief,
        research_queries=[], entity_signals=[], youtube_results=[], search_opportunities={"opportunities": []},
    )
    return {
        "main_topic": "being misunderstood",
        "keyword_signals": [{"keyword": item["keyword"]} for item in keyword_research["research_targets"]],
        "keyword_research": keyword_research,
        "entity_signals": [], "top_opportunities": [], "youtube_results": [], "research_queries": [],
        "category": "quotes", "creator_brief": brief,
        "language_context": {"language": "english", "region": "global", "audience_type": "general"},
    }


class GeminiProviderReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        gemini_client.reset_provider_health()

    def tearDown(self) -> None:
        gemini_client.reset_provider_health()

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_429_then_success_has_one_bounded_retry(self, post, sleep):
        limited = MagicMock(status_code=429)
        limited.headers = {"retry-after": "1"}
        post.side_effect = [limited, _response(_valid_quote_package())]
        with patch.dict(os.environ, {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}):
            text, trace = gemini_client.generate_with_diagnostics("test")
        self.assertTrue(text)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(trace["status"], "gemini_success")
        self.assertEqual(trace["retry_reasons"], ["rate_limit"])
        self.assertGreaterEqual(sleep.call_args.args[0], 1)

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_repeated_rate_limits_activate_cooldown(self, post, _sleep):
        limited = MagicMock(status_code=429)
        limited.headers = {}
        post.return_value = limited
        environment = {
            "WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test",
            "WIN_ENGINE_GEMINI_RATE_LIMIT_RETRIES": "0", "WIN_ENGINE_GEMINI_COOLDOWN_FAILURE_THRESHOLD": "2",
        }
        with patch.dict(os.environ, environment):
            _, first = gemini_client.generate_with_diagnostics("test")
            _, second = gemini_client.generate_with_diagnostics("test")
            _, cooldown = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(first["failure_category"], "rate_limit")
        self.assertTrue(second["cooldown_triggered"])
        self.assertEqual(cooldown["status"], "gemini_cooldown")
        self.assertEqual(post.call_count, 2)

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_cooldown_expiry_allows_recovery_and_success_resets_health(self, post, _sleep):
        failed = MagicMock(status_code=503)
        post.side_effect = [failed, _response(_valid_quote_package())]
        environment = {
            "WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test",
            "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0", "WIN_ENGINE_GEMINI_COOLDOWN_FAILURE_THRESHOLD": "1",
        }
        with patch.dict(os.environ, environment):
            _, failure = gemini_client.generate_with_diagnostics("test")
            self.assertTrue(failure["cooldown_triggered"])
            with gemini_client._HEALTH_LOCK:  # simulate the local cooldown having elapsed
                gemini_client._PROVIDER_HEALTH["cooldown_until"] = time.monotonic() - 1
            text, success = gemini_client.generate_with_diagnostics("test")
        self.assertTrue(text)
        self.assertEqual(success["status"], "gemini_success")
        self.assertEqual(gemini_client.provider_health()["transient_failure_count"], 0)

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_timeout_and_5xx_are_bounded_transient_failures(self, post, _sleep):
        post.side_effect = httpx.TimeoutException("timed out")
        environment = {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test", "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "1"}
        with patch.dict(os.environ, environment):
            _, timeout = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(timeout["failure_category"], "timeout")
        self.assertEqual(timeout["attempts"], 2)

        gemini_client.reset_provider_health()
        server_error = MagicMock(status_code=503)
        post.side_effect = None
        post.return_value = server_error
        with patch.dict(os.environ, environment):
            _, provider_error = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(provider_error["failure_category"], "provider_5xx")
        self.assertEqual(provider_error["attempts"], 2)

    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_malformed_and_authentication_failures_never_retry(self, post):
        malformed = MagicMock(status_code=200)
        malformed.json.return_value = {"candidates": []}
        post.return_value = malformed
        environment = {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}
        with patch.dict(os.environ, environment):
            _, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(trace["failure_category"], "malformed_provider_response")
        self.assertEqual(post.call_count, 1)

        rejected = MagicMock(status_code=401)
        post.return_value = rejected
        with patch.dict(os.environ, environment):
            _, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(trace["failure_category"], "authentication_or_configuration")
        self.assertEqual(trace["retries"], 0)


class GeminiWriterAndFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        gemini_client.reset_provider_health()
        self.script = "Being misunderstood is the price we pay for being genuine."
        self.brief = build_creator_brief(
            script=self.script, video_format="youtube_shorts", voice_over="none", exact_quote=self.script,
        )

    def tearDown(self) -> None:
        gemini_client.reset_provider_health()

    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_valid_gemini_package_is_used_once_and_quality_checked(self, post):
        post.return_value = _response(_valid_quote_package())
        with patch.dict(os.environ, {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}):
            packages, source = write_multilang_packages_with_source(self.script, languages=["english"], creator_brief=self.brief)
        package = packages["english"]
        self.assertEqual(source, "gemini")
        self.assertIsNotNone(package)
        self.assertEqual(package["generation_trace"]["gemini_call_count"], 1)
        self.assertFalse(package["generation_trace"].get("fallback_used"))

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_timeout_uses_green_deterministic_fallback_with_trace(self, post, _sleep):
        post.side_effect = httpx.TimeoutException("timed out")
        environment = {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test", "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0"}
        with patch.dict(os.environ, environment):
            package = build_seo_package("generate seo", self.script, _quote_research(self.script, self.brief), HistoryStore(":memory:"))
        trace = package["generation_trace"]
        self.assertEqual(package["generation_source"], "fallback")
        self.assertEqual(package["generation_quality"]["verdict"], "GREEN")
        self.assertEqual(trace["provider_failure_category"], "timeout")
        self.assertEqual(trace["fallback_level"], "deterministic")
        self.assertEqual(trace["gemini_call_count"], 1)

    @patch("win_engine.llm.gemini_client.time.sleep")
    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_5xx_uses_green_deterministic_fallback_with_trace(self, post, _sleep):
        post.return_value = MagicMock(status_code=503)
        environment = {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test", "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0"}
        with patch.dict(os.environ, environment):
            package = build_seo_package("generate seo", self.script, _quote_research(self.script, self.brief), HistoryStore(":memory:"))
        self.assertEqual(package["generation_source"], "fallback")
        self.assertEqual(package["generation_quality"]["verdict"], "GREEN")
        self.assertEqual(package["generation_trace"]["provider_failure_category"], "provider_5xx")
        self.assertEqual(post.call_count, 1)

    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_malformed_output_falls_back_without_extra_regeneration(self, post):
        malformed = MagicMock(status_code=200)
        malformed.json.return_value = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
        post.return_value = malformed
        with patch.dict(os.environ, {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}):
            package = build_seo_package("generate seo", self.script, _quote_research(self.script, self.brief), HistoryStore(":memory:"))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(package["generation_quality"]["verdict"], "GREEN")
        self.assertEqual(package["generation_trace"]["provider_failure_category"], "malformed_provider_response")

    @patch("win_engine.llm.seo_writer.gemini_client.is_available", return_value=False)
    def test_missing_configuration_uses_fallback_without_provider_loop(self, _available):
        package = build_seo_package("generate seo", self.script, _quote_research(self.script, self.brief), HistoryStore(":memory:"))
        self.assertEqual(package["generation_source"], "fallback")
        self.assertEqual(package["generation_quality"]["verdict"], "GREEN")
        self.assertFalse(package["generation_trace"]["gemini_attempted"])
        self.assertEqual(package["generation_trace"]["provider_failure_category"], "authentication_or_configuration")

    @patch("win_engine.llm.gemini_client.httpx.post")
    def test_authentication_error_immediately_uses_green_fallback(self, post):
        post.return_value = MagicMock(status_code=401)
        with patch.dict(os.environ, {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}):
            package = build_seo_package("generate seo", self.script, _quote_research(self.script, self.brief), HistoryStore(":memory:"))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(package["generation_quality"]["verdict"], "GREEN")
        self.assertEqual(package["generation_trace"]["provider_failure_category"], "authentication_or_configuration")

    def test_instructional_and_comparison_fallback_titles_stay_readable(self):
        tutorial = _content_specific_fallback(
            "clean burr coffee grinder unplug brush burrs",
            [],
            {"content": "How to clean a burr coffee grinder: unplug it, brush the burrs, and remove stale grounds.", "video_format": "tutorial"},
        )
        comparison = _content_specific_fallback(
            "tcp establishes a connection before data transfer while udp sends packets",
            [],
            {"content": "TCP establishes a connection before data transfer, while UDP sends packets without the same connection setup.", "video_format": "educational"},
        )
        self.assertEqual(tutorial["title"], "How to clean a burr coffee grinder")
        self.assertEqual(comparison["title"], "TCP vs UDP: What's the Difference?")


if __name__ == "__main__":
    unittest.main()
