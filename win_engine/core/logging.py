from __future__ import annotations

import logging
from logging.config import dictConfig


def configure_logging() -> None:
    """Configure application-wide logging."""

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": "INFO",
                }
            },
            "root": {"handlers": ["console"], "level": "INFO"},
        }
    )

    logging.getLogger("uvicorn").setLevel(logging.INFO)
