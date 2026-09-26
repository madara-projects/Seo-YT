"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.config import dictConfig

# Kept at WARNING whatever the app's level. At DEBUG, requests_oauthlib logs
# the token request (auth code, client secret, PKCE verifier) and the tokens
# Google returns; googleapiclient, google_auth_httplib2 and urllib3 log request
# URLs that carry the API key; httpx logs every URL at INFO. Uvicorn's own
# startup and error lines stay; its access log is off (app.py).
_QUIET_LIBRARY_LOGGERS = (
    "requests_oauthlib",
    "oauthlib",
    "googleapiclient",
    "google_auth_httplib2",
    "httplib2",
    "google.auth",
    "google.oauth2",
    "google_auth_oauthlib",
    "urllib3",
    "httpx",
    "httpcore",
    "uvicorn.access",
)


def configure_logging(log_level: str = "INFO") -> None:
    """Configure concise console logging for local and container runs."""
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": log_level,
                }
            },
            "root": {"handlers": ["console"], "level": log_level},
        }
    )
    for name in _QUIET_LIBRARY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
