"""Correlation-ID middleware.

Every request gets a correlation ID (reused from the X-Correlation-Id
request header if the caller already has one, e.g. a mobile client
retrying, otherwise generated). It is echoed on the response header and
included in every error envelope, so a customer support case can be traced
across client logs, backend logs and (once S1V2-01-005 lands) the shared
observability stack without ever needing request bodies, which may contain
device/user data.

Implemented as a plain ASGI middleware (not Starlette's BaseHTTPMiddleware):
BaseHTTPMiddleware is known to interfere with FastAPI's registered
exception handlers for non-HTTPException types (the handler never runs,
the raw exception propagates instead) — see
https://github.com/tiangolo/fastapi/discussions/8027. A plain ASGI
middleware does not have this problem.
"""

import uuid

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Correlation-Id"
HEADER_BYTES = HEADER.lower().encode("latin-1")


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        correlation_id = request.headers.get(HEADER) or str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((HEADER_BYTES, correlation_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)


def get_correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")
