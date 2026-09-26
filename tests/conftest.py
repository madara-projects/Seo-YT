"""Shared pytest fixtures.

Tests are hermetic: they never read the developer's settings or keys, never
open the live database, and never reach the network.
"""

import os
import socket
import tempfile

# Keys can arrive as environment variables too (compose's env_file,
# `docker compose exec`, a shell export), not only through .env: drop every
# app setting, then set only what the tests rely on.
for _name in [name for name in os.environ if name.startswith("WIN_ENGINE_")]:
    del os.environ[_name]
# Search-suggestion lookups are on by default in the app; tests that exercise
# demand inject suggestions directly.
os.environ["WIN_ENGINE_SEARCH_SUGGEST_ENABLED"] = "false"
# Retry tests count provider calls; the backup-model switch would add calls, so
# it is off unless a test enables it explicitly.
os.environ["WIN_ENGINE_GEMINI_FALLBACK_MODEL"] = ""
# Starlette's TestClient addresses the app as "testserver"; the Host check
# refuses any name it is not told about.
os.environ["WIN_ENGINE_ALLOWED_HOSTS"] = "127.0.0.1,localhost,::1,testserver"
# The default path is the live app's database; a test that forgets to pass its
# own path gets a throwaway file instead.
os.environ["WIN_ENGINE_DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="win-engine-tests-"), "tests.db")
os.environ["WIN_ENGINE_CLOUD_SYNC_ENABLED"] = "false"
os.environ["WIN_ENGINE_SNAPSHOT_COLLECTOR_ENABLED"] = "false"

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _refuse_remote(sock: socket.socket, address) -> None:
    host = address[0] if isinstance(address, tuple) else None
    if sock.family in (socket.AF_INET, socket.AF_INET6) and host not in _LOCAL_HOSTS:
        raise OSError(f"Tests must not reach the network (tried to connect to {host}).")


def _local_connect(sock, address):
    _refuse_remote(sock, address)
    return _real_connect(sock, address)


def _local_connect_ex(sock, address):
    _refuse_remote(sock, address)
    return _real_connect_ex(sock, address)


# A patch the test forgot fails loudly here instead of spending YouTube or
# Gemini quota, or writing to the cloud database.
socket.socket.connect = _local_connect
socket.socket.connect_ex = _local_connect_ex

import pytest  # noqa: E402

from win_engine.core.config import Settings, get_settings  # noqa: E402
from win_engine.llm import gemini_client  # noqa: E402

# Tests never read the developer's .env either.
Settings.model_config["env_file"] = None
# get_settings() is cached for the process. Build it here, from the environment
# above, so the first test to call it cannot cache values from its own patches.
get_settings()


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
