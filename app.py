"""Entry point for the YouTube SEO Analyzer backend (FastAPI)."""

import os
import uvicorn

from win_engine.api.app import create_app

app = create_app()


if __name__ == "__main__":
    # Use a direct local run by default. The Windows auto-reloader has
    # been unreliable in this environment due to named-pipe permissions.
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
