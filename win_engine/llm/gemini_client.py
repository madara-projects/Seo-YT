"""Small Gemini REST client used for AI SEO generation."""

from __future__ import annotations

import json
import logging
import os
import random
import re
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Iterator, Mapping

import httpx
from pydantic import ValidationError

from win_engine.core.config import Settings

logger = logging.getLogger(__name__)
# Read-only default: a context that never set a diagnostic shares this one object.
_LAST_DIAGNOSTIC: ContextVar[Mapping[str, object]] = ContextVar(
    "gemini_last_diagnostic", default=MappingProxyType({"status": "not_attempted", "attempts": 0, "retries": 0})
)
_HEALTH_LOCK = threading.Lock()


def _healthy() -> dict[str, object]:
    return {"transient_failure_count": 0, "cooldown_until": 0.0, "last_failure_category": None}


# Each purpose has its own circuit breaker. Research side calls that keep
# failing must not switch off package writing, the result the creator waits
# for; "package" is the default purpose.
_PROVIDER_HEALTH: dict[str, object] = _healthy()
_PURPOSE_HEALTH: dict[str, dict[str, object]] = {"package": _PROVIDER_HEALTH}
# An attempt with less time left than the shortest timeout Settings allows
# would be cut off mid-generation.
_MIN_ATTEMPT_SECONDS = 5.0


def _gemini_settings() -> Settings:
    """Settings as the current WIN_ENGINE_GEMINI_* environment defines them.

    get_settings() is built once per process, so a variable set afterwards
    (tests patch os.environ) was either ignored or, when the first build
    happened while it was set, kept for good. Each distinct Gemini environment
    is validated once against the Field bounds. A value outside them falls
    back to its default with a warning instead of failing every call; at
    startup the same value already stops the app.
    """
    environment = tuple(sorted(
        (name.upper(), value) for name, value in os.environ.items()
        if name.upper().startswith("WIN_ENGINE_GEMINI_")
    ))
    return _settings_for(environment)


@lru_cache(maxsize=8)
def _settings_for(environment: tuple[tuple[str, str], ...]) -> Settings:
    # Settings reads os.environ and .env itself; the argument only keys the cache.
    # The fallback is built in here so that it is cached too: lru_cache keeps no
    # exception, and every read rebuilt Settings and repeated the warning.
    try:
        return Settings()
    except ValidationError as exc:
        invalid = sorted({str(error["loc"][0]) for error in exc.errors() if error.get("loc")})
        logger.warning("Ignoring invalid setting(s) %s; using the defaults.", ", ".join(invalid))
        return Settings(**{name: Settings.model_fields[name].default for name in invalid})


def _get_key() -> str:
    return (_gemini_settings().gemini_api_key or "").strip()


def _get_model() -> str:
    configured = (_gemini_settings().gemini_model or "").strip()
    return configured or str(Settings.model_fields["gemini_model"].default)


def _get_fallback_model() -> str:
    return (_gemini_settings().gemini_fallback_model or "").strip()


def is_available() -> bool:
    """A configured key is enough to attempt generation; errors stay non-fatal."""
    return bool(_get_key() and _get_model())


def diagnostics() -> dict[str, object]:
    """Safe configuration state for the local diagnostics endpoint."""
    return {
        "configured": is_available(),
        "model": _get_model() if is_available() else None,
        "provider_health": provider_health(),
        "research_provider_health": provider_health("research"),
    }


def last_generation_diagnostic() -> dict[str, object]:
    """Return safe per-request diagnostics for the immediately preceding call."""
    return dict(_LAST_DIAGNOSTIC.get())


def set_last_generation_diagnostic(diagnostic: dict[str, object]) -> None:
    """Record a post-parse diagnostic without retaining any provider content."""
    _LAST_DIAGNOSTIC.set(dict(diagnostic))


def parse_json_object(raw: str) -> dict[str, Any] | None:
    """Return the JSON object in a model reply, or None when there is none.

    Replies can still arrive in a Markdown fence, with prose around the
    object, or with a trailing comma before "]" or "}", the model's most
    common JSON slip. Repairing that costs nothing, whereas failing sent a
    usable package to the local fallback writer.
    """
    if not raw:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match and match.group(0) != text:
        candidates.append(match.group(0))
    for candidate in candidates:
        for attempt in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):
            try:
                value = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    return None


class _RequestBudget:
    """The Gemini allowance of one API request, shared by every call made in it."""

    def __init__(self, max_calls: int, deadline_seconds: float) -> None:
        self.max_calls = max_calls
        self.calls = 0
        self._deadline = time.monotonic() + deadline_seconds
        # Worker threads running in a copy of the request context share this object.
        self._lock = threading.Lock()

    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    def claim_call(self) -> str | None:
        """Count one logical call, or return the limit that refuses it."""
        with self._lock:
            if self.calls >= self.max_calls:
                return "call_limit"
            if self.remaining_seconds() < _MIN_ATTEMPT_SECONDS:
                return "deadline"
            self.calls += 1
            return None


_REQUEST_BUDGET: ContextVar[_RequestBudget | None] = ContextVar("gemini_request_budget", default=None)


@contextmanager
def request_budget(max_calls: int | None = None, deadline_seconds: float | None = None) -> Iterator[None]:
    """Bound the Gemini calls that one API request can make.

    Unbounded, one analysis could chain seven logical calls, each with retries
    and a backup model, and hold its request for over ten minutes. Inside the
    block, a call beyond ``max_calls`` or after the deadline returns no text
    and a ``gemini_budget_exhausted`` diagnostic, so callers fall back exactly
    as they do when the provider is unavailable. No retry is started that
    cannot finish in time, and each attempt's timeout is cut to the time left.
    Defaults come from Settings.

    The allowance lives in a context variable, so it also covers worker threads
    that run in a copy of the caller's context (``contextvars.copy_context()``,
    ``asyncio.to_thread``, Starlette's threadpool); a thread started without
    one is not covered. A nested block shares the outer allowance.
    """
    if _REQUEST_BUDGET.get() is not None:
        yield
        return
    settings = _gemini_settings()
    token = _REQUEST_BUDGET.set(_RequestBudget(
        settings.gemini_request_max_calls if max_calls is None else max_calls,
        settings.gemini_request_deadline_seconds if deadline_seconds is None else deadline_seconds,
    ))
    try:
        yield
    finally:
        _REQUEST_BUDGET.reset(token)


def _budget_diagnostic(
    limit: str, *, attempts: int = 0, retries: int = 0, retry_reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "status": "gemini_budget_exhausted",
        "failure_category": "request_budget_exhausted",
        "budget_limit": limit,
        "attempts": attempts,
        "retries": retries,
        "retry_reasons": retry_reasons or [],
    }


def _health(purpose: str) -> dict[str, object]:
    """The breaker of one purpose; the caller holds _HEALTH_LOCK."""
    return _PURPOSE_HEALTH.setdefault(purpose, _healthy())


def provider_health(purpose: str = "package") -> dict[str, object]:
    """Return local, secret-free provider health used for circuit protection."""
    now = time.monotonic()
    with _HEALTH_LOCK:
        health = _health(purpose)
        remaining = max(0.0, float(health["cooldown_until"]) - now)
        return {
            "transient_failure_count": int(health["transient_failure_count"]),
            "cooldown_active": remaining > 0,
            "cooldown_remaining_seconds": round(remaining, 2),
            "last_failure_category": health["last_failure_category"],
        }


def reset_provider_health() -> None:
    """Clear the in-process circuit state (primarily useful for tests/startup)."""
    with _HEALTH_LOCK:
        for health in _PURPOSE_HEALTH.values():
            health.update(_healthy())


def _record_provider_success(purpose: str) -> None:
    with _HEALTH_LOCK:
        _health(purpose).update(_healthy())


def _record_transient_failure(category: str, purpose: str = "package") -> dict[str, object]:
    settings = _gemini_settings()
    now = time.monotonic()
    with _HEALTH_LOCK:
        health = _health(purpose)
        failures = int(health["transient_failure_count"]) + 1
        health["transient_failure_count"] = failures
        health["last_failure_category"] = category
        cooldown_triggered = failures >= settings.gemini_cooldown_failure_threshold
        if cooldown_triggered:
            health["cooldown_until"] = now + settings.gemini_cooldown_seconds
        remaining = max(0.0, float(health["cooldown_until"]) - now)
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


def _error_details(response: httpx.Response) -> list[dict[str, Any]]:
    """The google.rpc detail objects of an error body; none for any other body."""
    try:
        error = response.json().get("error")
    except (AttributeError, TypeError, ValueError):
        return []
    details = error.get("details") if isinstance(error, dict) else None
    return [item for item in details if isinstance(item, dict)] if isinstance(details, list) else []


def _daily_quota_exhausted(response: httpx.Response) -> bool:
    """A 429 for a per-day quota, which no wait within one request can clear."""
    return any(
        "PerDay" in str(violation.get("quotaId") or "")
        for detail in _error_details(response)
        if isinstance(detail.get("violations"), list)
        for violation in detail["violations"]
        if isinstance(violation, dict)
    )


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """The wait a 429 asks for: its Retry-After header, else the body's RetryInfo.

    Gemini sends no header; its wait is a "retryDelay" such as "41s" in the
    body. Read from the header alone, a 429 asking for 41 seconds was retried
    after one, twice on each model.
    """
    value = str(response.headers.get("retry-after") or "").strip()
    if not value:
        for detail in _error_details(response):
            match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(detail.get("retryDelay") or "").strip())
            if match:
                return float(match.group(1))
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


def _backoff_delay(attempt: int, retry_after: float | None) -> float | None:
    """Seconds to wait before a retry, or None when the server asks for longer than allowed."""
    settings = _gemini_settings()
    limit = settings.gemini_max_retry_wait_seconds
    if retry_after is not None and retry_after > limit:
        return None
    base = settings.gemini_retry_base_seconds
    jitter = random.uniform(0.0, min(base, 0.5))
    calculated = min(12.0, base * (2 ** attempt)) + jitter
    return min(max(calculated, retry_after or 0.0), limit)


def generate_with_diagnostics(
    prompt: str,
    system: str = "",
    *,
    max_tokens: int = 1200,
    temperature: float = 0.7,
    purpose: str = "package",
) -> tuple[str, dict[str, object]]:
    """Return generated text and safe bounded-retry diagnostics.

    A 429 is transient until the bounded retry budget is exhausted.  The
    diagnostic is intentionally free of prompts, keys, and response bodies.
    ``purpose`` picks the circuit breaker: research side calls pass
    "research", so their failures never pause package writing.
    """
    if not is_available():
        diagnostic = _configuration_diagnostic()
        _LAST_DIAGNOSTIC.set(diagnostic)
        return "", diagnostic

    health = provider_health(purpose)
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

    budget = _REQUEST_BUDGET.get()
    refused = budget.claim_call() if budget is not None else None
    if refused:
        diagnostic = _budget_diagnostic(refused)
        _LAST_DIAGNOSTIC.set(diagnostic)
        return "", diagnostic

    settings = _gemini_settings()
    key = _get_key()
    model = _get_model()
    fallback_model = _get_fallback_model()
    switched_model = False
    # The failure that sent this call to the backup model, with its HTTP status.
    switch_cause: tuple[str, int | None] | None = None

    # 30s timed out routinely on full packages, costing a dead wait plus a retry.
    timeout = settings.gemini_timeout_seconds
    ceiling = settings.gemini_output_token_ceiling

    payload = {
        "systemInstruction": {"parts": [{"text": system}]} if system else None,
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": min(max(max_tokens, 256), ceiling),
            "responseMimeType": "application/json",
        },
    }
    if payload["systemInstruction"] is None:
        del payload["systemInstruction"]

    transient_retries = settings.gemini_transient_retries
    rate_limit_retries = settings.gemini_rate_limit_retries
    attempts = 0
    retries = 0
    rate_limited = False
    retry_after_seen = False
    retry_reasons: list[str] = []

    def seconds_left() -> float:
        return budget.remaining_seconds() if budget is not None else float("inf")

    def note_deadline() -> None:
        if "request_deadline" not in retry_reasons:
            retry_reasons.append("request_deadline")

    def transient_failure(category: str, http_status: int | None) -> dict[str, object]:
        diagnostic: dict[str, object] = {
            "status": "gemini_rate_limited" if category == "rate_limit" else "gemini_timeout" if category == "timeout" else "gemini_transport_error",
            "failure_category": category,
            "attempts": attempts,
            "retries": retries,
            "retry_reasons": retry_reasons,
            **_record_transient_failure(category, purpose),
        }
        if http_status is not None:
            diagnostic["http_status"] = http_status
        if category == "rate_limit":
            diagnostic["retry_after_seen"] = retry_after_seen
        return diagnostic

    def backup_rejected(http_status: int | None) -> dict[str, object]:
        # A misnamed or unauthorised backup model is a configuration slip, but
        # reporting only that hid the primary's rate limit and kept the
        # cooldown from ever starting. The failure that caused the switch
        # stays the outcome.
        assert switch_cause is not None
        logger.warning("Backup Gemini model %s rejected the request with HTTP %s.", model, http_status)
        retry_reasons.append(f"backup_model_rejected:{http_status}")
        diagnostic = transient_failure(*switch_cause)
        diagnostic["backup_model_http_status"] = http_status
        return diagnostic

    def retry_or_finish(
        *,
        category: str,
        retry_limit: int,
        retry_after: float | None = None,
        http_status: int | None = None,
    ) -> tuple[bool, dict[str, object] | None]:
        nonlocal retries, model, switched_model, switch_cause
        if retries < retry_limit:
            delay = _backoff_delay(retries, retry_after)
            if delay is None:
                # Sleeping out a long Retry-After would hold the request for
                # minutes; this model counts as exhausted instead.
                retry_reasons.append(f"{category}:retry_after_exceeds_limit")
            elif delay + _MIN_ATTEMPT_SECONDS > seconds_left():
                note_deadline()
            else:
                retries += 1
                retry_reasons.append(category)
                logger.warning("Gemini %s; retrying %d/%d after %.2fs.", category, retries, retry_limit, delay)
                time.sleep(delay)
                return True, None
        # An overloaded or rate-limited model is not an unavailable provider:
        # other models draw on separate capacity and quota. Try the backup
        # once before counting a failure toward the cooldown.
        if (
            category in {"rate_limit", "provider_5xx", "timeout"}
            and fallback_model and fallback_model != model and not switched_model
        ):
            if seconds_left() >= _MIN_ATTEMPT_SECONDS:
                logger.warning("Gemini %s on %s; switching to backup model %s.", category, model, fallback_model)
                retry_reasons.append(f"{category}:switched_to_backup_model")
                model = fallback_model
                switched_model = True
                switch_cause = (category, http_status)
                retries = 0
                return True, None
            note_deadline()
        return False, transient_failure(category, http_status)

    while True:
        attempts += 1
        attempt_timeout = min(timeout, seconds_left())
        try:
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json=payload,
                timeout=attempt_timeout,
            )
            if response.status_code == 429:
                rate_limited = True
                retry_after = _retry_after_seconds(response)
                retry_after_seen = retry_after_seen or retry_after is not None
                daily_quota = _daily_quota_exhausted(response)
                if daily_quota:
                    # Spent until tomorrow whatever wait RetryInfo names, so this
                    # model gets no retry; the backup draws on its own quota.
                    retry_reasons.append("rate_limit:daily_quota_exhausted")
                should_retry, diagnostic = retry_or_finish(
                    category="rate_limit", retry_limit=0 if daily_quota else rate_limit_retries,
                    retry_after=retry_after, http_status=429,
                )
                if should_retry:
                    continue
                assert diagnostic is not None
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            if response.status_code in {400, 401, 403, 404}:
                logger.warning("Gemini request rejected for model %s with HTTP %d; not retrying.", model, response.status_code)
                if switch_cause is not None:
                    diagnostic = backup_rejected(response.status_code)
                else:
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
            finish_reason = str(candidates[0].get("finishReason") or "").upper() if candidates else ""
            # A truncated candidate still carries text, so without this check the caller
            # receives half a JSON object labelled "success", fails to parse it, and the
            # run is misreported as "Gemini unavailable".
            if finish_reason == "MAX_TOKENS":
                current_cap = int(payload["generationConfig"].get("maxOutputTokens") or 0)
                widened = min(current_cap * 2, ceiling)
                if widened > current_cap and retries < transient_retries and seconds_left() >= _MIN_ATTEMPT_SECONDS:
                    retries += 1
                    retry_reasons.append("output_token_limit")
                    payload["generationConfig"]["maxOutputTokens"] = widened
                    logger.warning(
                        "Gemini truncated at %d output tokens; retrying %d/%d with %d.",
                        current_cap, retries, transient_retries, widened,
                    )
                    continue
                # Truncation follows from the prompt and the token budget, not
                # from provider health, so it never counts toward the cooldown.
                health = provider_health(purpose)
                diagnostic = {"status": "gemini_truncated", "failure_category": "output_token_limit",
                              "attempts": attempts, "retries": retries, "retry_reasons": retry_reasons,
                              "max_output_tokens": current_cap,
                              "transient_failure_count": health["transient_failure_count"],
                              "cooldown_triggered": False,
                              "cooldown_remaining_seconds": health["cooldown_remaining_seconds"]}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
            if out_text:
                _record_provider_success(purpose)
                diagnostic = {"status": "gemini_success", "attempts": attempts, "retries": retries,
                              "retry_reasons": retry_reasons, "rate_limited_before_success": rate_limited,
                              "retry_after_seen": retry_after_seen, "failure_category": None,
                              "model": model, "backup_model_used": switched_model}
                _LAST_DIAGNOSTIC.set(diagnostic)
                return out_text, diagnostic
            diagnostic = {"status": "gemini_invalid_response", "failure_category": "malformed_provider_response",
                          "attempts": attempts, "retries": retries, "retry_reasons": retry_reasons}
            _LAST_DIAGNOSTIC.set(diagnostic)
            return "", diagnostic
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if isinstance(exc, httpx.TimeoutException) and attempt_timeout < timeout:
                # The request's own deadline cut this attempt short, which says
                # nothing about the provider's health.
                diagnostic = _budget_diagnostic(
                    "deadline", attempts=attempts, retries=retries, retry_reasons=retry_reasons,
                )
                _LAST_DIAGNOSTIC.set(diagnostic)
                return "", diagnostic
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
            if switch_cause is not None:
                diagnostic = backup_rejected(status)
            else:
                diagnostic = {"status": "gemini_permanent_error", "failure_category": "deterministic_provider_error",
                              "attempts": attempts, "retries": retries, "retry_reasons": retry_reasons,
                              "http_status": status}
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
    purpose: str = "package",
) -> str:
    """Compatibility wrapper returning generated text only."""
    text, _ = generate_with_diagnostics(
        prompt, system, max_tokens=max_tokens, temperature=temperature, purpose=purpose,
    )
    return text
