"""Small Gemini REST client used only when the local Ollama writer is unavailable."""

from __future__ import annotations

import logging
import os

import httpx


logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("WIN_ENGINE_GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("WIN_ENGINE_GEMINI_MODEL", "gemini-3.5-flash").strip()
GEMINI_TIMEOUT = float(os.environ.get("WIN_ENGINE_GEMINI_TIMEOUT_SECONDS", "30"))


def is_available() -> bool:
    """A configured key is enough to attempt generation; errors stay non-fatal."""

    return bool(GEMINI_API_KEY and GEMINI_MODEL)


def diagnostics() -> dict[str, object]:
    """Safe configuration state for the local diagnostics endpoint."""

    return {"configured": is_available(), "model": GEMINI_MODEL if is_available() else None}


def generate(
    prompt: str,
    system: str = "",
    *,
    max_tokens: int = 1100,
    temperature: float = 0.5,
) -> str:
    """Return generated text, or an empty string when Gemini cannot be used."""

    if not is_available():
        return ""

    payload = {
        "systemInstruction": {"parts": [{"text": system}]} if system else None,
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            # Gemini 3.5 uses part of this allowance for reasoning.  The SEO
            # JSON itself is sizeable (five titles plus a description), so the
            # local Ollama budget of 1100 would otherwise truncate valid JSON.
            "maxOutputTokens": max(max_tokens, 2400),
            "responseMimeType": "application/json",
        },
    }
    if payload["systemInstruction"] is None:
        del payload["systemInstruction"]

    try:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json=payload,
            timeout=GEMINI_TIMEOUT,
        )
        response.raise_for_status()
        candidates = response.json().get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        return "".join(str(part.get("text") or "") for part in parts).strip()
    except Exception as exc:  # noqa: BLE001 - optional provider must never break generation
        logger.warning("Gemini generate failed: %s", exc)
        return ""
