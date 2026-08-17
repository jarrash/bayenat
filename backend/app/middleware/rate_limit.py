from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request, Response, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(events[0] + self.window_seconds - now))
                return False, retry_after
            events.append(now)
            if len(self._events) > 10000:
                self._events = defaultdict(deque, {item: values for item, values in self._events.items() if values and values[-1] > cutoff})
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit: int, window_seconds: int, exempt_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.limiter = SlidingWindowLimiter(limit, window_seconds)
        self.exempt_paths = exempt_paths or {"/health"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        allowed, retry_after = self.limiter.allow(f"http:{client}")
        if not allowed:
            return Response(status_code=429, content="Rate limit exceeded", headers={"Retry-After": str(retry_after)})
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.limit)
        return response


def websocket_client_key(websocket: WebSocket) -> str:
    client = websocket.client
    return f"ws:{client.host if client else 'unknown'}"
