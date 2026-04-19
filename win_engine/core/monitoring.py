"""Error tracking and monitoring for YouTube Win-Engine."""
from __future__ import annotations

import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastAPIIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlAlchemyIntegration
from typing import Optional, Dict, Any
import structlog


class ErrorTracker:
    """Central error tracking and monitoring."""

    def __init__(self, dsn: Optional[str] = None, environment: str = "development"):
        self.dsn = dsn or os.getenv("SENTRY_DSN")
        self.environment = environment
        self.initialized = False

    def initialize(self) -> None:
        """Initialize error tracking."""
        if not self.dsn or self.initialized:
            return

        sentry_sdk.init(
            dsn=self.dsn,
            environment=self.environment,
            integrations=[
                FastAPIIntegration(),
                RedisIntegration(),
                SqlAlchemyIntegration(),
            ],
            # Performance monitoring
            traces_sample_rate=0.1 if self.environment == "production" else 1.0,
            # Error tracking
            send_default_pii=False,
            # Release tracking
            release=os.getenv("APP_VERSION", "1.0.0"),
            # Custom sampling
            before_send=self._before_send,
            # User feedback
            enable_tracing=True,
        )

        self.initialized = True
        logger = structlog.get_logger(__name__)
        logger.info("Error tracking initialized", environment=self.environment)

    def _before_send(self, event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Filter and enhance error events before sending."""
        # Don't send client errors (4xx)
        if "request" in event and "status_code" in event.get("request", {}):
            status_code = event["request"]["status_code"]
            if 400 <= status_code < 500:
                return None

        # Add custom context
        if "tags" not in event:
            event["tags"] = {}

        event["tags"].update({
            "component": "youtube_win_engine",
            "service": "seo_platform"
        })

        return event

    def capture_exception(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Capture and report exceptions."""
        if not self.initialized:
            return

        with sentry_sdk.configure_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_tag(key, str(value))

            sentry_sdk.capture_exception(error)

    def capture_message(self, message: str, level: str = "info", context: Optional[Dict[str, Any]] = None) -> None:
        """Capture custom messages."""
        if not self.initialized:
            return

        with sentry_sdk.configure_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_tag(key, str(value))

            sentry_sdk.capture_message(message, level=level)

    def set_user_context(self, user_id: str, email: Optional[str] = None, username: Optional[str] = None) -> None:
        """Set user context for error tracking."""
        if not self.initialized:
            return

        sentry_sdk.set_user({
            "id": user_id,
            "email": email,
            "username": username,
        })

    def add_breadcrumb(self, message: str, category: str = "default", level: str = "info") -> None:
        """Add breadcrumb for debugging."""
        if not self.initialized:
            return

        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level
        )


# Global error tracker instance
error_tracker = ErrorTracker()


def initialize_error_tracking() -> None:
    """Initialize error tracking for the application."""
    from win_engine.core.config import get_settings

    settings = get_settings()
    error_tracker.environment = settings.app_environment
    error_tracker.initialize()


# Performance monitoring decorator
def monitor_performance(operation: str):
    """Decorator to monitor function performance."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000

                # Log performance
                logger = structlog.get_logger(__name__)
                logger.info(
                    "Operation completed",
                    operation=operation,
                    function=func.__name__,
                    duration_ms=round(duration, 2)
                )

                # Track in Sentry if slow
                if duration > 5000:  # 5 seconds
                    error_tracker.capture_message(
                        f"Slow operation: {operation}",
                        level="warning",
                        context={
                            "operation": operation,
                            "function": func.__name__,
                            "duration_ms": round(duration, 2)
                        }
                    )

                return result

            except Exception as e:
                duration = (time.time() - start_time) * 1000

                # Log error with context
                logger = structlog.get_logger(__name__)
                logger.error(
                    "Operation failed",
                    operation=operation,
                    function=func.__name__,
                    duration_ms=round(duration, 2),
                    error=str(e),
                    exc_info=True
                )

                # Track error
                error_tracker.capture_exception(e, {
                    "operation": operation,
                    "function": func.__name__,
                    "duration_ms": round(duration, 2)
                })

                raise

        return wrapper
    return decorator