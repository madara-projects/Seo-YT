from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response


def request_context_middleware(app_start_time: float):
    """Factory for FastAPI HTTP middleware that injects request id and timing headers."""

    async def middleware(request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()

        response: Response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
        response.headers["X-App-Uptime-S"] = f"{int(time.time() - app_start_time)}"

        return response

    return middleware
