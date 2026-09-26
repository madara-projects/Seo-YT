"""Gemini client fixes: bounded waits, per-purpose cooldowns, request budgets and settings."""

from __future__ import annotations

import contextvars
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
from pydantic import ValidationError

from win_engine.core.config import Settings
from win_engine.llm import gemini_client

ENV = {"WIN_ENGINE_GEMINI_API_KEY": "test", "WIN_ENGINE_GEMINI_MODEL": "test"}


def _success(text: str = '{"title": "t"}', finish_reason: str = "STOP") -> MagicMock:
    response = MagicMock(status_code=200, headers={})
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish_reason}]
    }
    return response


def _status(code: int, headers: dict[str, str] | None = None) -> MagicMock:
    return MagicMock(status_code=code, headers=headers or {})


def _quota_error(retry_delay: str, quota_id: str = "GenerateRequestsPerMinutePerProjectPerModel-FreeTier") -> httpx.Response:
    """A 429 as Gemini sends it: the wait is in the body's RetryInfo, with no Retry-After header."""
    return httpx.Response(429, json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": quota_id}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay},
    ]}})


@patch("win_engine.llm.gemini_client.time.sleep")
@patch("win_engine.llm.gemini_client.httpx.post")
class RetryWaitTests(unittest.TestCase):
    def test_long_retry_after_fails_fast_instead_of_sleeping(self, post, sleep):
        post.return_value = _status(429, {"retry-after": "3600"})
        with patch.dict(os.environ, ENV):
            text, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(text, "")
        self.assertEqual(trace["status"], "gemini_rate_limited")
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()
        self.assertIn("rate_limit:retry_after_exceeds_limit", trace["retry_reasons"])
        self.assertTrue(trace["retry_after_seen"])

    def test_long_retry_after_still_tries_the_backup_model_at_once(self, post, sleep):
        def fake_post(url, **_kwargs):
            return _status(429, {"retry-after": "3600"}) if "/primary:" in url else _success()

        post.side_effect = fake_post
        environment = {**ENV, "WIN_ENGINE_GEMINI_MODEL": "primary", "WIN_ENGINE_GEMINI_FALLBACK_MODEL": "backup"}
        with patch.dict(os.environ, environment):
            text, trace = gemini_client.generate_with_diagnostics("test")
        self.assertTrue(text)
        self.assertTrue(trace["backup_model_used"])
        self.assertEqual(post.call_count, 2)
        sleep.assert_not_called()

    def test_retry_after_within_the_configured_limit_is_honoured(self, post, sleep):
        post.side_effect = [_status(429, {"retry-after": "4"}), _success()]
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_MAX_RETRY_WAIT_SECONDS": "5"}):
            text, _ = gemini_client.generate_with_diagnostics("test")
        self.assertTrue(text)
        self.assertEqual(sleep.call_args.args[0], 4.0)

    def test_retry_after_beyond_the_configured_limit_is_not_slept(self, post, sleep):
        post.return_value = _status(429, {"retry-after": "6"})
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_MAX_RETRY_WAIT_SECONDS": "5"}):
            gemini_client.generate_with_diagnostics("test")
        sleep.assert_not_called()

    def test_a_long_wait_in_the_error_body_ends_the_attempts_on_each_model(self, post, sleep):
        post.return_value = _quota_error("41s")
        environment = {**ENV, "WIN_ENGINE_GEMINI_MODEL": "primary", "WIN_ENGINE_GEMINI_FALLBACK_MODEL": "backup"}
        with patch.dict(os.environ, environment):
            _, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(post.call_count, 2)  # each model once, not three times each
        sleep.assert_not_called()
        self.assertIn("rate_limit:retry_after_exceeds_limit", trace["retry_reasons"])
        self.assertTrue(trace["retry_after_seen"])

    def test_a_short_wait_in_the_error_body_is_honoured(self, post, sleep):
        post.side_effect = [_quota_error("4.5s"), _success()]
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_MAX_RETRY_WAIT_SECONDS": "5"}):
            text, _ = gemini_client.generate_with_diagnostics("test")
        self.assertTrue(text)
        self.assertEqual(sleep.call_args.args[0], 4.5)

    def test_a_spent_daily_quota_moves_straight_to_the_backup_model(self, post, sleep):
        daily = _quota_error("13s", quota_id="GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        post.side_effect = lambda url, **_kwargs: daily if "/primary:" in url else _success()
        environment = {**ENV, "WIN_ENGINE_GEMINI_MODEL": "primary", "WIN_ENGINE_GEMINI_FALLBACK_MODEL": "backup"}
        with patch.dict(os.environ, environment):
            text, trace = gemini_client.generate_with_diagnostics("test")
        self.assertTrue(text)
        self.assertEqual(post.call_count, 2)
        sleep.assert_not_called()
        self.assertIn("rate_limit:daily_quota_exhausted", trace["retry_reasons"])


@patch("win_engine.llm.gemini_client.time.sleep")
@patch("win_engine.llm.gemini_client.httpx.post")
class CooldownIsolationTests(unittest.TestCase):
    def test_truncation_never_starts_the_cooldown(self, post, _sleep):
        post.return_value = _success('{"title": ', finish_reason="MAX_TOKENS")
        environment = {**ENV, "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0", "WIN_ENGINE_GEMINI_COOLDOWN_FAILURE_THRESHOLD": "1"}
        with patch.dict(os.environ, environment):
            _, first = gemini_client.generate_with_diagnostics("test")
            _, second = gemini_client.generate_with_diagnostics("test")
            post.return_value = _success()
            text, third = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(first["status"], "gemini_truncated")
        self.assertFalse(second["cooldown_triggered"])
        self.assertEqual(gemini_client.provider_health()["transient_failure_count"], 0)
        self.assertEqual(third["status"], "gemini_success")
        self.assertTrue(text)

    def test_research_failures_never_pause_package_writing(self, post, _sleep):
        post.return_value = _status(503)
        environment = {**ENV, "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0", "WIN_ENGINE_GEMINI_COOLDOWN_FAILURE_THRESHOLD": "2"}
        with patch.dict(os.environ, environment):
            gemini_client.generate_with_diagnostics("research", purpose="research")
            gemini_client.generate_with_diagnostics("research", purpose="research")
            _, research = gemini_client.generate_with_diagnostics("research", purpose="research")
            post.return_value = _success()
            text, package = gemini_client.generate_with_diagnostics("package")
        self.assertEqual(research["status"], "gemini_cooldown")
        self.assertEqual(package["status"], "gemini_success")
        self.assertTrue(text)
        self.assertEqual(post.call_count, 3)
        self.assertTrue(gemini_client.provider_health("research")["cooldown_active"])
        self.assertFalse(gemini_client.provider_health()["cooldown_active"])
        self.assertIn("research_provider_health", gemini_client.diagnostics())

    def test_success_resets_only_its_own_purpose(self, post, _sleep):
        post.return_value = _status(503)
        environment = {**ENV, "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": "0", "WIN_ENGINE_GEMINI_COOLDOWN_FAILURE_THRESHOLD": "3"}
        with patch.dict(os.environ, environment):
            gemini_client.generate_with_diagnostics("package")
            post.return_value = _success()
            gemini_client.generate_with_diagnostics("research", purpose="research")
        self.assertEqual(gemini_client.provider_health()["transient_failure_count"], 1)


@patch("win_engine.llm.gemini_client.time.sleep")
@patch("win_engine.llm.gemini_client.httpx.post")
class BackupModelRejectionTests(unittest.TestCase):
    ENVIRONMENT = {
        **ENV, "WIN_ENGINE_GEMINI_MODEL": "primary", "WIN_ENGINE_GEMINI_FALLBACK_MODEL": "backup",
        "WIN_ENGINE_GEMINI_RATE_LIMIT_RETRIES": "0", "WIN_ENGINE_GEMINI_COOLDOWN_FAILURE_THRESHOLD": "1",
    }

    def test_rejected_backup_reports_the_rate_limit_and_starts_the_cooldown(self, post, _sleep):
        post.side_effect = lambda url, **_kwargs: _status(429) if "/primary:" in url else _status(404)
        with patch.dict(os.environ, self.ENVIRONMENT):
            text, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(text, "")
        self.assertEqual(trace["status"], "gemini_rate_limited")
        self.assertEqual(trace["failure_category"], "rate_limit")
        self.assertEqual(trace["http_status"], 429)
        self.assertEqual(trace["backup_model_http_status"], 404)
        self.assertIn("backup_model_rejected:404", trace["retry_reasons"])
        self.assertTrue(trace["cooldown_triggered"])
        self.assertTrue(gemini_client.provider_health()["cooldown_active"])

    def test_rejected_primary_is_still_a_configuration_error(self, post, _sleep):
        post.return_value = _status(404)
        with patch.dict(os.environ, self.ENVIRONMENT):
            _, trace = gemini_client.generate_with_diagnostics("test")
        self.assertEqual(trace["status"], "gemini_permanent_error")
        self.assertEqual(trace["failure_category"], "authentication_or_configuration")
        self.assertEqual(post.call_count, 1)


@patch("win_engine.llm.gemini_client.time.sleep")
@patch("win_engine.llm.gemini_client.httpx.post")
class RequestBudgetTests(unittest.TestCase):
    def test_calls_beyond_the_allowance_take_the_unavailable_path(self, post, _sleep):
        post.return_value = _success()
        with patch.dict(os.environ, ENV):
            with gemini_client.request_budget(max_calls=2):
                gemini_client.generate_with_diagnostics("a")
                gemini_client.generate_with_diagnostics("b")
                text, trace = gemini_client.generate_with_diagnostics("c")
            self.assertEqual(text, "")
            self.assertEqual(trace["status"], "gemini_budget_exhausted")
            self.assertEqual(trace["failure_category"], "request_budget_exhausted")
            self.assertEqual(trace["budget_limit"], "call_limit")
            self.assertEqual(trace["attempts"], 0)
            self.assertEqual(post.call_count, 2)
            self.assertTrue(gemini_client.generate("after the request"))
        self.assertEqual(post.call_count, 3)

    def test_no_call_starts_when_the_deadline_leaves_no_time(self, post, _sleep):
        with patch.dict(os.environ, ENV), gemini_client.request_budget(deadline_seconds=1.0):
            _, trace = gemini_client.generate_with_diagnostics("a")
        self.assertEqual(trace["budget_limit"], "deadline")
        post.assert_not_called()

    def test_a_retry_that_cannot_finish_in_time_is_skipped(self, post, sleep):
        post.return_value = _status(429, {"retry-after": "4"})
        with patch.dict(os.environ, ENV), gemini_client.request_budget(deadline_seconds=8.0):
            _, trace = gemini_client.generate_with_diagnostics("a")
        self.assertEqual(trace["status"], "gemini_rate_limited")
        self.assertIn("request_deadline", trace["retry_reasons"])
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()

    def test_attempt_timeout_is_cut_to_the_time_left_and_not_blamed_on_the_provider(self, post, _sleep):
        post.side_effect = httpx.TimeoutException("timed out")
        with patch.dict(os.environ, ENV), gemini_client.request_budget(deadline_seconds=30.0):
            _, trace = gemini_client.generate_with_diagnostics("a")
        self.assertLessEqual(post.call_args.kwargs["timeout"], 30.0)
        self.assertEqual(trace["status"], "gemini_budget_exhausted")
        self.assertEqual(trace["budget_limit"], "deadline")
        self.assertEqual(gemini_client.provider_health()["transient_failure_count"], 0)

    def test_worker_threads_in_a_copied_context_share_the_allowance(self, post, _sleep):
        post.return_value = _success()
        with patch.dict(os.environ, ENV), gemini_client.request_budget(max_calls=1):
            context = contextvars.copy_context()
            with ThreadPoolExecutor(max_workers=1) as pool:
                _, worker = pool.submit(context.run, gemini_client.generate_with_diagnostics, "a").result()
            _, caller = gemini_client.generate_with_diagnostics("b")
        self.assertEqual(worker["status"], "gemini_success")
        self.assertEqual(caller["status"], "gemini_budget_exhausted")
        self.assertEqual(post.call_count, 1)

    def test_a_nested_block_shares_the_outer_allowance(self, post, _sleep):
        post.return_value = _success()
        with patch.dict(os.environ, ENV), gemini_client.request_budget(max_calls=1):
            gemini_client.generate_with_diagnostics("a")
            with gemini_client.request_budget(max_calls=5):
                _, trace = gemini_client.generate_with_diagnostics("b")
        self.assertEqual(trace["budget_limit"], "call_limit")

    def test_default_allowance_comes_from_settings(self, post, _sleep):
        post.return_value = _success()
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_REQUEST_MAX_CALLS": "1"}):
            with gemini_client.request_budget():
                gemini_client.generate_with_diagnostics("a")
                _, trace = gemini_client.generate_with_diagnostics("b")
        self.assertEqual(trace["budget_limit"], "call_limit")


@patch("win_engine.llm.gemini_client.time.sleep")
@patch("win_engine.llm.gemini_client.httpx.post")
class TuningSettingsTests(unittest.TestCase):
    def test_an_env_file_alone_configures_the_client(self, post, _sleep):
        post.return_value = _status(503)
        previous_env_file = Settings.model_config.get("env_file")
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ):
            for name in ("WIN_ENGINE_GEMINI_API_KEY", "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES"):
                os.environ.pop(name, None)
            env_file = Path(folder) / ".env"
            env_file.write_text(
                "WIN_ENGINE_GEMINI_API_KEY=from-file\nWIN_ENGINE_GEMINI_TRANSIENT_RETRIES=0\n", encoding="utf-8",
            )
            Settings.model_config["env_file"] = str(env_file)
            gemini_client._settings_for.cache_clear()
            try:
                available = gemini_client.is_available()
                _, trace = gemini_client.generate_with_diagnostics("test")
            finally:
                Settings.model_config["env_file"] = previous_env_file
                gemini_client._settings_for.cache_clear()
        self.assertTrue(available)
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "from-file")
        self.assertEqual(trace["attempts"], 1)

    def test_invalid_or_out_of_range_values_fall_back_to_defaults(self, post, _sleep):
        post.return_value = _status(503)
        for value in ("abc", "9"):
            with self.subTest(value=value), patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_TRANSIENT_RETRIES": value}):
                post.reset_mock()
                gemini_client.reset_provider_health()
                with self.assertLogs("win_engine.llm.gemini_client", "WARNING") as logs:
                    _, trace = gemini_client.generate_with_diagnostics("test")
                self.assertEqual(trace["failure_category"], "provider_5xx")
                self.assertEqual(post.call_count, 2)
                self.assertTrue(any("gemini_transient_retries" in line for line in logs.output))

    def test_an_invalid_value_is_reported_once_not_on_every_call(self, post, _sleep):
        post.return_value = _success()
        gemini_client._settings_for.cache_clear()
        self.addCleanup(gemini_client._settings_for.cache_clear)
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_TIMEOUT_SECONDS": "1"}):
            with self.assertLogs("win_engine.llm.gemini_client", "WARNING") as logs:
                gemini_client.generate_with_diagnostics("a")
                gemini_client.generate_with_diagnostics("b")
        self.assertEqual(len([line for line in logs.output if "Ignoring invalid" in line]), 1)
        self.assertEqual(post.call_args.kwargs["timeout"], 60.0)

    def test_timeout_override_cannot_bypass_its_bounds(self, post, _sleep):
        post.return_value = _success()
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_TIMEOUT_SECONDS": "1"}):
            gemini_client.generate_with_diagnostics("test")
        self.assertEqual(post.call_args.kwargs["timeout"], 60.0)

    def test_output_token_ceiling_is_read_on_every_call(self, post, _sleep):
        post.return_value = _success()
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_OUTPUT_TOKEN_CEILING": "2048"}):
            gemini_client.generate_with_diagnostics("test", max_tokens=4000)
        self.assertEqual(post.call_args.kwargs["json"]["generationConfig"]["maxOutputTokens"], 2048)

    def test_an_out_of_range_value_stops_settings_at_startup(self, _post, _sleep):
        with patch.dict(os.environ, {"WIN_ENGINE_GEMINI_RATE_LIMIT_RETRIES": "9"}):
            with self.assertRaises(ValidationError):
                Settings()

    def test_blank_model_uses_the_configured_default_not_a_retired_one(self, _post, _sleep):
        with patch.dict(os.environ, {**ENV, "WIN_ENGINE_GEMINI_MODEL": ""}):
            self.assertEqual(gemini_client._get_model(), Settings.model_fields["gemini_model"].default)


class ImportTimeTests(unittest.TestCase):
    def test_no_knob_is_parsed_at_import(self):
        root = Path(__file__).resolve().parents[1]
        environment = {**os.environ, "WIN_ENGINE_GEMINI_OUTPUT_TOKEN_CEILING": "not-a-number", "PYTHONPATH": str(root)}
        result = subprocess.run(
            [sys.executable, "-c", "import win_engine.llm.gemini_client"],
            cwd=root, env=environment, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


class JsonReplyTests(unittest.TestCase):
    def test_reply_shapes_the_model_actually_sends(self):
        expected = {"title": "x", "tags": ["a"]}
        for raw in (
            json.dumps(expected),
            "```json\n" + json.dumps(expected) + "\n```",
            "Here is the package: " + json.dumps(expected) + " Hope this helps.",
            '{"title": "x", "tags": ["a",],}',
            "[" + json.dumps(expected) + "]",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(gemini_client.parse_json_object(raw), expected)

    def test_no_object_means_none(self):
        for raw in ("", "not json", "[1, 2]", '"text"', "{broken"):
            with self.subTest(raw=raw):
                self.assertIsNone(gemini_client.parse_json_object(raw))


if __name__ == "__main__":
    unittest.main()
