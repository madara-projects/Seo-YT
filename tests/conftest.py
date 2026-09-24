"""Shared pytest fixtures."""

import os

# Tests must never reach the network. Search-suggestion lookups are on by
# default in the app, so turn them off before any settings object is built;
# tests that exercise demand inject suggestions directly.
os.environ.setdefault("WIN_ENGINE_SEARCH_SUGGEST_ENABLED", "false")
# Retry tests count provider calls; the backup-model switch would add calls, so
# it is off unless a test enables it explicitly.
os.environ.setdefault("WIN_ENGINE_GEMINI_FALLBACK_MODEL", "")

import pytest  # noqa: E402

from win_engine.llm import gemini_client  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_gemini_provider_health():
    """Start every test with a healthy Gemini client.

    The client keeps a module-level count of consecutive transient failures and
    enters a 60-second cooldown at the threshold. Without a reset, failures from
    one test carried into the next, so a retry test passed or failed depending
    on which tests happened to run before it.
    """

    gemini_client.reset_provider_health()
    yield
    gemini_client.reset_provider_health()
