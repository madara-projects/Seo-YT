"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from win_engine.api.routes import router
from win_engine.core.logging import configure_logging
from win_engine.core.middleware import request_context_middleware
from win_engine.core.rate_limit import InMemoryRateLimiter
from win_engine.feedback.snapshot_collector import SnapshotCollector

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    configure_logging()
    from win_engine.core.config import get_settings

    settings = get_settings()
    collector = SnapshotCollector(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        collector.start()
        try:
            yield
        finally:
            collector.stop()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="YouTube-first SEO and opportunity analyzer with dashboard, research, and strategy layers.",
        lifespan=lifespan,
    )
    app.state.snapshot_collector = collector
    # The extracted frontend is served by FastAPI itself. Keeping the mount
    # same-origin avoids a second frontend server and works identically in
    # local and Docker deployments.
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    app_start = time.time()
    rate_limiter = InMemoryRateLimiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    analyze_rate_limiter = InMemoryRateLimiter(
        max_requests=settings.analyze_rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.middleware("http")(request_context_middleware(app_start))

    @app.middleware("http")
    async def rate_limit_requests(request: Request, call_next):
        client_host = request.client.host if request.client else "unknown"
        limiter = analyze_rate_limiter if request.url.path == "/analyze" else rate_limiter
        limiter_key = f"{client_host}:{request.url.path}"
        allowed, retry_after = limiter.check(limiter_key)
        if not allowed:
            request_id = getattr(request.state, "request_id", "unavailable")
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests. Please retry shortly.",
                        "request_id": request_id,
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "base-uri 'self'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", "unavailable")
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": detail,
                    "request_id": request_id,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "unavailable")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request payload is invalid.",
                    "request_id": request_id,
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unavailable")
        logger.exception("Unhandled application error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred.",
                    "request_id": request_id,
                }
            },
        )

    app.include_router(router)
    return app
