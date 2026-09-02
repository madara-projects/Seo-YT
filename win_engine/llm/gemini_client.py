"""Small Gemini REST client used for AI SEO generation."""

from __future__ import annotations

import logging
import os
import random
import time
from contextvars import ContextVar
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

import httpx
from win_engine.core.config import get_settings

logger = logging.getLogger(__name__)
_LAST_DIAGNOSTIC: ContextVar[dict[str, object]] = ContextVar(
    "gemini_last_diagnostic", default={"status": "not_attempted", "attempts": 0, "retries": 0}
)


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


def last_generation_diagnostic() -> dict[str, object]:
    """Return safe per-request diagnostics for the immediately preceding call."""
    return dict(_LAST_DIAGNOSTIC.get())


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = str(response.headers.get("retry-after") or "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, IndexError):
            return None


def _backoff_delay(attempt: int, retry_after: float | None) -> float:
    base = max(0.1, float(os.environ.get("WIN_ENGINE_GEMINI_RETRY_BASE_SECONDS", "0.75")))
    jitter = random.uniform(0.0, min(base, 0.5))
    calculated = min(12.0, base * (2 ** attempt)) + jitter
    return max(calculated, retry_after or 0.0)


def generate_with_diagnostics(
    prompt: str,
    system: str = "",
    *,
    max_tokens: int = 1200,
    temperature: float = 0.7,
) -> tuple[str, dict[str, object]]:
    """Return generated text and safe bounded-retry diagnostics.

    A 429 is transient until the bounded retry budget is exhausted.  The
    diagnostic is intentionally free of prompts, keys, and response bodies.
    """
    if not is_available():
        diagnostic = {"status": "gemini_unavailable", "attempts": 0, "retries": 0}
        _LAST_DIAGNOSTIC.set(diagnostic)
        return "", diagnostic

    key = _get_key()
    model = _get_model()

    timeout = float(os.environ.get("WIN_ENGINE_GEMINI_TIMEOUT_SECONDS", "30"))

    payload = {
        "systemInstruction": {"parts": [{"text": system}]} if system else None,
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": min(max(max_tokens, 256), 1200),
            "responseMimeType": "application/json",
        },
    }
    if payload["systemInstruction"] is None:
        del payload["systemInstruction"]

    transient_retries = max(0, min(4, int(os.environ.get("WIN_ENGINE_GEMINI_TRANSIENT_RETRIES", "1"))))
    rate_limit_retries = max(0, min(4, int(os.environ.get("WIN_ENGINE_GEMINI_RATE_LIMIT_RETRIES", "2"))))
    attempts = 0
    retries = 0
    rate_limited = False
    retry_after_seen = False

    while True:
        attempts += 1
        try:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json=payload,
                timeout=timeout,
            )
            if response.status_code == 429:
                rate_limited = True
                retry_after = _retry_after_seconds(response)
                retry_after_seen = retry_after_seen or retry_after is not None
                if retries < rate_limit_retries:
                    delay = _backoff_delay(retries, retry_after)
                    retries += 1
                    logger.warning("Gemini rate limited for %s; retrying %d/%d after %.2fs.", model, retries, rate_limit_retries, delay)
                    time.sleep(delay)
                    continue
                diagnostic = {"status": "gemini_rate_limited", "attempts": attempts, "retries": retries,
                              "retry_after_seen": retry_after_seen}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            if response.status_code in {400, 401, 403, 404}:
                logger.warning("Gemini request rejected for model %s with HTTP %d; not retrying.", model, response.status_code)
                diagnostic = {"status": "gemini_permanent_error", "attempts": attempts, "retries": retries,
                              "http_status": response.status_code}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            if response.status_code == 408 or response.status_code >= 500:
                if retries < transient_retries:
                    delay = _backoff_delay(retries, None)
                    retries += 1
                    time.sleep(delay)
                    continue
                logger.warning("Gemini transient failure for model %s after one retry (HTTP %d).", model, response.status_code)
                diagnostic = {"status": "gemini_transport_error", "attempts": attempts, "retries": retries,
                              "http_status": response.status_code}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            response.raise_for_status()
            candidates = response.json().get("candidates") or []
            parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
            out_text = "".join(str(part.get("text") or "") for part in parts).strip()
            if out_text:
                diagnostic = {"status": "gemini_success", "attempts": attempts, "retries": retries,
                              "rate_limited_before_success": rate_limited, "retry_after_seen": retry_after_seen}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return out_text, diagnostic
            diagnostic = {"status": "gemini_invalid_response", "attempts": attempts, "retries": retries}
            _LAST_DIAGNOSTIC.set(diagnostic)
            return "", diagnostic
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if retries < transient_retries:
                delay = _backoff_delay(retries, None)
                retries += 1
                time.sleep(delay)
                continue
            logger.warning("Gemini network request failed after one retry: %s", type(exc).__name__)
            status = "gemini_timeout" if isinstance(exc, httpx.TimeoutException) else "gemini_transport_error"
            diagnostic = {"status": status, "attempts": attempts, "retries": retries}
            _LAST_DIAGNOSTIC.set(diagnostic)
            return "", diagnostic
        except Exception as exc:
            logger.warning("Gemini request failed without retry: %s", type(exc).__name__)
            diagnostic = {"status": "gemini_transport_error", "attempts": attempts, "retries": retries}
            _LAST_DIAGNOSTIC.set(diagnostic)
            return "", diagnostic


def generate(
    prompt: str,
    system: str = "",
    *,
    max_tokens: int = 1200,
    temperature: float = 0.7,
) -> str:
    """Compatibility wrapper returning generated text only."""
    text, _ = generate_with_diagnostics(prompt, system, max_tokens=max_tokens, temperature=temperature)
    return text
