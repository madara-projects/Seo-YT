"""FastAPI application factory."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from win_engine.api.routes import router
from win_engine.core.logging import configure_logging
from win_engine.core.middleware import request_context_middleware
from win_engine.core.rate_limit import InMemoryRateLimiter

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    configure_logging()
    from win_engine.core.config import get_settings

    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="YouTube-first SEO and opportunity analyzer with dashboard, research, and strategy layers.",
    )

    app_start = time.time()
    rate_limiter = InMemoryRateLimiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.middleware("http")(request_context_middleware(app_start))

    @app.middleware("http")
    async def rate_limit_requests(request: Request, call_next):
        client_host = request.client.host if request.client else "unknown"
        limiter_key = f"{client_host}:{request.url.path}"
        allowed, retry_after = rate_limiter.check(limiter_key)
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
        return await call_next(request)

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
