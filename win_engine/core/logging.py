from __future__ import annotations

import logging
import sys
from logging.config import dictConfig
import structlog
from typing import Any, Dict
import time
from contextlib import contextmanager


def configure_logging(log_level: str = "INFO") -> None:
    """Configure application-wide structured logging."""

    # Configure standard logging
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.JSONRenderer(),
                    "foreign_pre_chain": [
                        structlog.stdlib.filter_by_level,
                        structlog.processors.TimeStamper(fmt="iso"),
                        structlog.processors.StackInfoRenderer(),
                        structlog.processors.format_exc_info,
                        structlog.processors.UnicodeDecoder(),
                        add_request_context,
                    ],
                },
                "console": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.LogfmtRenderer(),
                    "foreign_pre_chain": [
                        structlog.stdlib.filter_by_level,
                        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                        structlog.processors.StackInfoRenderer(),
                        structlog.processors.format_exc_info,
                        structlog.processors.UnicodeDecoder(),
                        add_request_context,
                    ],
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "level": log_level,
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": "win_engine.log",
                    "formatter": "json",
                    "level": log_level,
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": log_level
            },
        }
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            add_request_context,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Suppress noisy loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def add_request_context(logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add request context to log entries."""
    from win_engine.core.config import get_settings

    settings = get_settings()
    event_dict.update({
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "app_environment": settings.app_environment,
    })

    return event_dict


@contextmanager
def performance_logger(operation: str, threshold_ms: float = 1000.0):
    """Context manager to log operation performance."""
    start_time = time.time()
    logger = structlog.get_logger()

    try:
        yield
        duration = (time.time() - start_time) * 1000

        if duration > threshold_ms:
            logger.warning(
                "Slow operation detected",
                operation=operation,
                duration_ms=round(duration, 2),
                threshold_ms=threshold_ms
            )
        else:
            logger.info(
                "Operation completed",
                operation=operation,
                duration_ms=round(duration, 2)
            )
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            "Operation failed",
            operation=operation,
            duration_ms=round(duration, 2),
            error=str(e),
            exc_info=True
        )
        raise


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
