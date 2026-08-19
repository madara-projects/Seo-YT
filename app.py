"""Entry point for the YouTube SEO Analyzer backend (FastAPI)."""

import os
import uvicorn

from win_engine.api.app import create_app
from win_engine.core.config import get_settings

app = create_app()


if __name__ == "__main__":
    # Use a direct local run by default. The Windows auto-reloader has
    # been unreliable in this environment due to named-pipe permissions.
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.bind_host,
        port=int(os.getenv("PORT", "8000")),
    )
