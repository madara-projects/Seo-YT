"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from google.auth.exceptions import RefreshError
from starlette.exceptions import HTTPException as StarletteHTTPException

from win_engine.api.routes import router
from win_engine.core.config import host_name
from win_engine.core.logging import configure_logging
from win_engine.core.rate_limit import InMemoryRateLimiter
from win_engine.feedback.cloud_sync import CloudSyncService
from win_engine.feedback.history_store import DatabaseUnavailable, HistoryStore, RelinkWouldDeleteEvidence
from win_engine.feedback.snapshot_collector import SnapshotCollector
from win_engine.integrations.youtube_channel import YouTubeUnavailable

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
# A path segment the id parser reads as a number: besides "12" it accepts
# "1.0", "+1", " 1" (sent as "%201") and "1_0", so each spelling would open a
# fresh budget for the same route. A pattern, not the router's own matching,
# because FastAPI's route layout changes between releases.
_RECORD_ID = re.compile(r"/[\s+-]*\d[\d_.\s]*(?=/|$)")
# Writes that spend YouTube quota, Gemini calls or a cloud round trip. They get
# the stricter budget, shared by every record id on the same route.
_COSTLY_PATHS = frozenset(
    {"/analyze", "/diagnostics", "/api/demand/research", "/api/watchlist/channels", "/api/watchlist/videos", "/api/cloud-sync/run"}
)
_COSTLY_SUFFIXES = ("/research", "/generate", "/demand-research", "/refresh", "/link-video")
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "connect-src 'self'; "
        # Public YouTube thumbnails on the Channel and research views.
        "img-src 'self' data: https://i.ytimg.com; "
        # The React interface loads its typefaces from Google Fonts; inline
        # styles stay allowed for component styling.
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        # Neither interface has inline scripts or event handlers, so injected
        # markup cannot run script even if escaping were ever missed.
        "script-src 'self'; "
        "base-uri 'self'; frame-ancestors 'none'"
    ),
}


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    headers: dict[str, str] | None = None,
    details: Any = None,
) -> JSONResponse:
    """The one error envelope every failure uses, carrying the request id."""
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", "unavailable"),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error}, headers=headers)


def request_host(request: Request) -> str:
    """The Host header's name, lower-cased, without port or IPv6 brackets."""
    return host_name(request.headers.get("host", ""))


def is_cross_site_write(request: Request) -> bool:
    """True for a request that changes data and was sent by another website.

    Binding to localhost keeps the network out, but not a page open in the
    same browser: a plain form on any site can POST here. Browsers label every
    request with Sec-Fetch-Site, so anything other than this app's own pages
    (or the user typing an address) is refused. Clients that send no such
    header, such as curl, scripts and tests, are judged by Origin instead and
    allowed when they send none.
    """
    if request.method in _SAFE_METHODS:
        return False
    site = request.headers.get("sec-fetch-site")
    if site:
        return site not in {"same-origin", "none"}
    origin = request.headers.get("origin")
    if not origin:
        return False
    try:
        origin_netloc = urlsplit(origin).netloc
    except ValueError:
        return True  # not a URL, so not this site
    return origin_netloc.lower() != request.headers.get("host", "").lower()


def route_template(path: str) -> str:
    """`/api/ideas/12/generate` → `/api/ideas/{id}/generate`: one budget per route, not per record."""
    return _RECORD_ID.sub("/{id}", path)


def is_costly(request: Request) -> bool:
    if request.method != "POST":
        return False
    path = request.url.path
    return path in _COSTLY_PATHS or path.endswith(_COSTLY_SUFFIXES)


def _validation_message(errors: list[dict[str, Any]]) -> str:
    """The first problem in words, e.g. "topic: String should have at least 1 character"."""
    if not errors:
        return "The request payload is invalid."
    first = errors[0]
    message = str(first.get("msg") or "Invalid value.").removeprefix("Value error, ")
    location = [str(part) for part in first.get("loc", ()) if part != "body"]
    return f"{'.'.join(location)}: {message}" if location else message


def create_app() -> FastAPI:
    from win_engine.core.config import get_settings

    settings = get_settings()
    configure_logging(settings.log_level)
    collector = SnapshotCollector(settings)
    cloud_sync = CloudSyncService(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Migrate once, before any background thread opens its own connection
        # to a database that may still be on an older schema.
        try:
            await asyncio.to_thread(HistoryStore, settings.database_path)
        except Exception as exc:
            logger.error("The database could not be prepared (%s); background work retries it on its schedule.", type(exc).__name__)
        # Each run of either prepares the database first and, while it cannot,
        # fails and waits for its next run, so both start either way.
        collector.start()
        cloud_sync.start()
        try:
            yield
        finally:
            cloud_sync.stop()
            collector.stop()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="YouTube-first SEO and opportunity analyzer with dashboard, research, and strategy layers.",
        lifespan=lifespan,
        # The interactive docs load their assets from a CDN the Content Security
        # Policy refuses, so they could only render blank. The schema stays at
        # /openapi.json for `npm run gen:api`.
        docs_url=None,
        redoc_url=None,
    )
    app.state.snapshot_collector = collector
    app.state.cloud_sync = cloud_sync
    # The interface is served by FastAPI itself, same-origin, so there is no
    # second frontend server in local or Docker runs. Its hashed assets are
    # mounted only when the bundle exists, so a checkout without a frontend
    # build still boots; the page routes report the missing build themselves.
    react_dir = STATIC_DIR / "app"
    if react_dir.is_dir():
        app.mount("/app-assets", StaticFiles(directory=react_dir), name="react-assets")
    else:
        logger.info("Frontend build not found at %s; the pages will report it.", react_dir)

    app_start = time.time()
    allowed_hosts = settings.allowed_host_set
    general_limiter = InMemoryRateLimiter(
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    costly_limiter = InMemoryRateLimiter(
        max_requests=settings.analyze_rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    # Middleware registered later runs earlier. Execution order is therefore:
    # request context → host and cross-site checks → body size → rate limit.

    @app.middleware("http")
    async def limit_request_rate(request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        limiter = costly_limiter if is_costly(request) else general_limiter
        allowed, retry_after = limiter.check(f"{client}:{request.method}:{route_template(request.url.path)}")
        if not allowed:
            return error_response(
                request, 429, "rate_limit_exceeded", "Too many requests. Please retry shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)

    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        declared = request.headers.get("content-length")
        if declared is not None:
            if not declared.isdigit():
                return error_response(request, 400, "invalid_content_length", "The Content-Length header is invalid.")
            if int(declared) > settings.max_request_bytes:
                return error_response(request, 413, "payload_too_large", "The request body is too large.")
        elif request.method not in _SAFE_METHODS and "chunked" in request.headers.get("transfer-encoding", "").lower():
            # Every client of this API sends a length; a streamed body cannot be sized up front.
            return error_response(request, 411, "length_required", "Send the request with a Content-Length header.")
        return await call_next(request)

    @app.middleware("http")
    async def guard_host_and_origin(request: Request, call_next):
        # A page that rebinds its own domain to 127.0.0.1 passes the loopback
        # bind and the same-origin checks, but still names its domain in Host.
        if request_host(request) not in allowed_hosts:
            return error_response(request, 400, "invalid_host", "This server answers only to its own host name.")
        if is_cross_site_write(request):
            return error_response(
                request, 403, "cross_site_request", "Requests from other websites cannot change data here."
            )
        return await call_next(request)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Caught here rather than by an exception handler so the 500 still
            # carries the request id and headers, and is logged exactly once.
            logger.exception("Unhandled error on %s %s (request %s)", request.method, request.url.path, request_id)
            response = error_response(request, 500, "internal_server_error", "An unexpected error occurred.")
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
        response.headers["X-App-Uptime-S"] = str(int(time.time() - app_start))
        response.headers.update(_SECURITY_HEADERS)
        # React build files carry a content hash in their name, so a cached copy
        # can never go stale; everything else, including the HTML, stays uncached.
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if request.url.path.startswith("/app-assets/assets/") and response.status_code == 200
            else "no-store"
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return error_response(request, exc.status_code, "http_error", message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = list(exc.errors())
        return error_response(
            request, 422, "validation_error", _validation_message(errors), details=jsonable_encoder(errors)
        )

    @app.exception_handler(YouTubeUnavailable)
    async def youtube_unavailable_handler(request: Request, exc: YouTubeUnavailable):
        return error_response(request, exc.status_code, "youtube_unavailable", str(exc))

    @app.exception_handler(RelinkWouldDeleteEvidence)
    async def relink_conflict_handler(request: Request, exc: RelinkWouldDeleteEvidence):
        # The client can ask the creator, then repeat the request with replace_existing_evidence.
        return error_response(
            request, 409, "relink_would_delete_evidence", str(exc),
            details={"youtube_video_id": exc.youtube_video_id, "evidence": exc.evidence},
        )

    @app.exception_handler(DatabaseUnavailable)
    async def database_unavailable_handler(request: Request, exc: DatabaseUnavailable):
        return error_response(request, 503, "database_unavailable", str(exc), headers={"Retry-After": "60"})

    @app.exception_handler(RefreshError)
    async def youtube_grant_revoked_handler(request: Request, exc: RefreshError):
        # Only a new connection can replace a revoked or expired grant.
        return error_response(
            request,
            401,
            "youtube_reconnect_required",
            "Your YouTube connection has expired or was revoked. Select Connect Channel to reconnect it.",
        )

    app.include_router(router)
    return app
