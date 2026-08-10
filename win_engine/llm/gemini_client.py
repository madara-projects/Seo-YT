"""Small Gemini REST client used for AI SEO generation."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from win_engine.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_key() -> str:
    return (os.environ.get("WIN_ENGINE_GEMINI_API_KEY") or get_settings().gemini_api_key or "").strip()


def _get_model() -> str:
    return (os.environ.get("WIN_ENGINE_GEMINI_MODEL") or get_settings().gemini_model or "gemini-1.5-flash").strip()


def is_available() -> bool:
    """A configured key is enough to attempt generation; errors stay non-fatal."""
    return bool(_get_key() and _get_model())


def diagnostics() -> dict[str, object]:
    """Safe configuration state for the local diagnostics endpoint."""
    return {"configured": is_available(), "model": _get_model() if is_available() else None}


def generate(
    prompt: str,
    system: str = "",
    *,
    max_tokens: int = 2048,
    temperature: float = 0.5,
) -> str:
    """Return generated text, or an empty string when Gemini cannot be used."""
    if not is_available():
        return ""

    key = _get_key()
    primary_model = _get_model()
    models_to_try = [primary_model]
    for fallback in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    timeout = float(os.environ.get("WIN_ENGINE_GEMINI_TIMEOUT_SECONDS", "30"))

    payload = {
        "systemInstruction": {"parts": [{"text": system}]} if system else None,
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": min(max(max_tokens, 256), 2048),
            "responseMimeType": "application/json",
        },
    }
    if payload["systemInstruction"] is None:
        del payload["systemInstruction"]

    import time

    for model in models_to_try:
        for attempt in range(3):
            try:
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": key},
                    json=payload,
                    timeout=timeout,
                )
                if response.status_code == 429:
                    logger.warning("Gemini 429 rate limit on %s (attempt %d/3). Retrying in 2s...", model, attempt + 1)
                    time.sleep(2.0)
                    continue
                response.raise_for_status()
                candidates = response.json().get("candidates") or []
                parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
                out_text = "".join(str(part.get("text") or "") for part in parts).strip()
                if out_text:
                    return out_text
            except Exception as exc:
                logger.warning("Gemini model %s attempt %d failed: %s", model, attempt + 1, exc)
                time.sleep(1.0)

    return ""
