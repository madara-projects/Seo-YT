"""Minimal Ollama HTTP client.

Stateless. Lazy. Imports do not touch the network. All callers tolerate the
service being unavailable: failures degrade to an empty string instead of
raising, so the rest of the pipeline keeps working when Ollama is offline.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "20"))
_REACH_TIMEOUT = 2.0


def is_available() -> bool:
    """Cheap reachability check used by /ready."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=_REACH_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def _payload(prompt: str, system: str, model: Optional[str],
             max_tokens: int, temperature: float) -> dict:
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    return {
        "model": model or OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }


def generate(prompt: str, system: str = "", model: Optional[str] = None,
             max_tokens: int = 250, temperature: float = 0.7) -> str:
    """Synchronous generation. Returns "" on any error."""
    try:
        r = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=_payload(prompt, system, model, max_tokens, temperature),
            timeout=OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()
    except Exception as exc:
        logger.warning("Ollama generate failed: %s", exc)
        return ""
