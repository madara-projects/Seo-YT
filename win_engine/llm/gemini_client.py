"""Small Gemini REST client used for AI SEO generation."""

from __future__ import annotations

import logging
import os
import random
import threading
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
_HEALTH_LOCK = threading.Lock()
_PROVIDER_HEALTH: dict[str, object] = {
    "transient_failure_count": 0,
    "cooldown_until": 0.0,
    "last_failure_category": None,
}


def _get_key() -> str:
    return (os.environ.get("WIN_ENGINE_GEMINI_API_KEY") or get_settings().gemini_api_key or "").strip()


def _get_model() -> str:
    return (os.environ.get("WIN_ENGINE_GEMINI_MODEL") or get_settings().gemini_model or "gemini-1.5-flash").strip()


def is_available() -> bool:
    """A configured key is enough to attempt generation; errors stay non-fatal."""
    return bool(_get_key() and _get_model())


def diagnostics() -> dict[str, object]:
    """Safe configuration state for the local diagnostics endpoint."""
    return {
        "configured": is_available(),
        "model": _get_model() if is_available() else None,
        "provider_health": provider_health(),
    }


def last_generation_diagnostic() -> dict[str, object]:
    """Return safe per-request diagnostics for the immediately preceding call."""
    return dict(_LAST_DIAGNOSTIC.get())


def set_last_generation_diagnostic(diagnostic: dict[str, object]) -> None:
    """Record a post-parse diagnostic without retaining any provider content."""
    _LAST_DIAGNOSTIC.set(dict(diagnostic))


def provider_health() -> dict[str, object]:
    """Return local, secret-free provider health used for circuit protection."""
    now = time.monotonic()
    with _HEALTH_LOCK:
        remaining = max(0.0, float(_PROVIDER_HEALTH["cooldown_until"]) - now)
        return {
            "transient_failure_count": int(_PROVIDER_HEALTH["transient_failure_count"]),
            "cooldown_active": remaining > 0,
            "cooldown_remaining_seconds": round(remaining, 2),
            "last_failure_category": _PROVIDER_HEALTH["last_failure_category"],
        }


def reset_provider_health() -> None:
    """Clear the in-process circuit state (primarily useful for tests/startup)."""
    with _HEALTH_LOCK:
        _PROVIDER_HEALTH.update({
            "transient_failure_count": 0,
            "cooldown_until": 0.0,
            "last_failure_category": None,
        })


def _record_provider_success() -> None:
    reset_provider_health()


def _record_transient_failure(category: str) -> dict[str, object]:
    threshold = max(1, min(5, int(os.environ.get("WIN_ENGINE_GEMINI_COOLDOWN_FAILURE_THRESHOLD", "2"))))
    cooldown_seconds = max(5.0, min(900.0, float(os.environ.get("WIN_ENGINE_GEMINI_COOLDOWN_SECONDS", "60"))))
    now = time.monotonic()
    with _HEALTH_LOCK:
        failures = int(_PROVIDER_HEALTH["transient_failure_count"]) + 1
        _PROVIDER_HEALTH["transient_failure_count"] = failures
        _PROVIDER_HEALTH["last_failure_category"] = category
        cooldown_triggered = failures >= threshold
        if cooldown_triggered:
            _PROVIDER_HEALTH["cooldown_until"] = now + cooldown_seconds
        remaining = max(0.0, float(_PROVIDER_HEALTH["cooldown_until"]) - now)
    return {
        "transient_failure_count": failures,
        "cooldown_triggered": cooldown_triggered,
        "cooldown_remaining_seconds": round(remaining, 2),
    }


def _configuration_diagnostic() -> dict[str, object]:
    return {
        "status": "gemini_unavailable",
        "failure_category": "authentication_or_configuration",
        "attempts": 0,
        "retries": 0,
        "retry_reasons": [],
    }


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
        diagnostic = _configuration_diagnostic()
        _LAST_DIAGNOSTIC.set(diagnostic)
        return "", diagnostic

    health = provider_health()
    if health["cooldown_active"]:
        diagnostic = {
            "status": "gemini_cooldown",
            "failure_category": "provider_cooldown",
            "attempts": 0,
            "retries": 0,
            "retry_reasons": [],
            "cooldown_remaining_seconds": health["cooldown_remaining_seconds"],
        }
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
            "maxOutputTokens": min(max(max_tokens, 256), 4096),
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
    retry_reasons: list[str] = []

    def retry_or_finish(
        *,
        category: str,
        retry_limit: int,
        retry_after: float | None = None,
        http_status: int | None = None,
    ) -> tuple[bool, dict[str, object] | None]:
        nonlocal retries
        if retries < retry_limit:
            delay = _backoff_delay(retries, retry_after)
            retries += 1
            retry_reasons.append(category)
            logger.warning("Gemini %s; retrying %d/%d after %.2fs.", category, retries, retry_limit, delay)
            time.sleep(delay)
            return True, None
        health_update = _record_transient_failure(category)
        diagnostic: dict[str, object] = {
            "status": "gemini_rate_limited" if category == "rate_limit" else "gemini_timeout" if category == "timeout" else "gemini_transport_error",
            "failure_category": category,
            "attempts": attempts,
            "retries": retries,
            "retry_reasons": retry_reasons,
            **health_update,
        }
        if http_status is not None:
            diagnostic["http_status"] = http_status
        return False, diagnostic

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
                should_retry, diagnostic = retry_or_finish(
                    category="rate_limit", retry_limit=rate_limit_retries, retry_after=retry_after, http_status=429,
                )
                if should_retry:
                    continue
                assert diagnostic is not None
                diagnostic["retry_after_seen"] = retry_after_seen
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            if response.status_code in {400, 401, 403, 404}:
                logger.warning("Gemini request rejected for model %s with HTTP %d; not retrying.", model, response.status_code)
                diagnostic = {"status": "gemini_permanent_error", "attempts": attempts, "retries": retries,
                              "retry_reasons": retry_reasons, "http_status": response.status_code,
                              "failure_category": "authentication_or_configuration"}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            if response.status_code == 408 or response.status_code >= 500:
                category = "timeout" if response.status_code == 408 else "provider_5xx"
                should_retry, diagnostic = retry_or_finish(
                    category=category, retry_limit=transient_retries, http_status=response.status_code,
                )
                if should_retry:
                    continue
                assert diagnostic is not None
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            response.raise_for_status()
            try:
                body = response.json()
            except (TypeError, ValueError):
                diagnostic = {"status": "gemini_invalid_response", "failure_category": "malformed_provider_response",
                              "attempts": attempts, "retries": retries, "retry_reasons": retry_reasons}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            candidates = body.get("candidates") or [] if isinstance(body, dict) else []
            parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
            out_text = "".join(str(part.get("text") or "") for part in parts).strip()
            if out_text:
                _record_provider_success()
                diagnostic = {"status": "gemini_success", "attempts": attempts, "retries": retries,
                              "retry_reasons": retry_reasons, "rate_limited_before_success": rate_limited,
                              "retry_after_seen": retry_after_seen, "failure_category": None}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return out_text, diagnostic
            diagnostic = {"status": "gemini_invalid_response", "failure_category": "malformed_provider_response",
                          "attempts": attempts, "retries": retries, "retry_reasons": retry_reasons}
            _LAST_DIAGNOSTIC.set(diagnostic)
            return "", diagnostic
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            category = "timeout" if isinstance(exc, httpx.TimeoutException) else "network_error"
            should_retry, diagnostic = retry_or_finish(category=category, retry_limit=transient_retries)
            if should_retry:
                continue
            assert diagnostic is not None
            _LAST_DIAGNOSTIC.set(diagnostic)
            return "", diagnostic
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.warning("Gemini request returned a non-retryable HTTP status: %s", status)
            diagnostic = {"status": "gemini_permanent_error", "failure_category": "deterministic_provider_error",
                          "attempts": attempts, "retries": retries, "retry_reasons": retry_reasons, "http_status": status}
            _LAST_DIAGNOSTIC.set(diagnostic)
            return "", diagnostic
        except Exception as exc:
            logger.warning("Gemini request failed without retry: %s", type(exc).__name__)
            diagnostic = {"status": "gemini_application_error", "failure_category": "deterministic_application_error",
                          "attempts": attempts, "retries": retries, "retry_reasons": retry_reasons}
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
