"""Entry point for the YouTube SEO Analyzer backend (FastAPI)."""

import os

import uvicorn

from win_engine.api.app import create_app
from win_engine.core.config import get_settings

app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.bind_host,
        port=int(os.getenv("PORT", "8000")),
        # Keep the app's own logging configuration. Access lines are off: they
        # would log every health check, and full query strings, which carry the
        # OAuth code on the way back from Google.
        log_config=None,
        access_log=False,
    )
