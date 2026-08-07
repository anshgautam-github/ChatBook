"""Per-client-IP rate limiting for the API's more expensive endpoints.

`/parse` (an outbound network fetch to chatgpt.com) and `/generate-pdf`
(CPU-bound HTML/LaTeX/PDF rendering) both do meaningfully more work per
request than a typical endpoint, which makes them the obvious targets
for accidental abuse (a retry loop, a buggy client) or intentional abuse
without any limit in place — one open, unauthenticated endpoint that
happily re-renders a full PDF on every call is a cheap denial-of-service
lever otherwise.

Built on `slowapi` (a Starlette/FastAPI-native wrapper around the
well-established `limits` library) rather than a hand-rolled limiter.
Everything route-facing lives in this one module so the actual numeric
limit has exactly one source of truth (`Settings.rate_limit_per_minute`)
and every limited route reads it the same way, instead of each route
carrying its own hardcoded limit string.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config.settings import get_settings

# `get_remote_address` keys on `request.client.host` — the direct TCP
# peer address Starlette sees for this connection. If this API is ever
# deployed behind a reverse proxy/load balancer, *that* proxy needs to be
# configured to preserve and forward the real client IP (e.g. Uvicorn's
# `--proxy-headers` together with a `--forwarded-allow-ips` allowlist of
# the proxy itself) for per-client limiting to keep working correctly.
# A custom key function reading `X-Forwarded-For` directly here instead
# would trust a header any client can set for itself unless the proxy in
# front of this process is guaranteed to always overwrite it — not
# something this module can verify, so it isn't assumed by default.
limiter = Limiter(key_func=get_remote_address)


def rate_limit_value() -> str:
    """The configured limit as a `slowapi`/`limits`-format string (e.g. `"15/minute"`).

    A function, not a constant, so every decorated route always reads
    the *current* `Settings` — in particular so tests can lower
    `RATE_LIMIT_PER_MINUTE` and see it take effect immediately (after
    clearing `get_settings`'s cache) without needing to reload this
    module or re-import the decorated routes.
    """
    return f"{get_settings().rate_limit_per_minute}/minute"


async def rate_limit_exceeded_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn slowapi's internal exception into this API's normal error shape.

    Every other error path in this API (see `app/utils/exceptions.py` and
    the route layer) returns `{"detail": "<message>"}` via `HTTPException`.
    Matching that shape here — rather than slowapi's own default handler,
    which returns `{"error": "..."}` — means an API client only ever has
    to handle one error response shape, not two; the extension's existing
    `detail?.detail || response.statusText` handling (see
    `extension/shared/panel/api.js`) already understands this without any
    changes on that side.
    """
    if not isinstance(exc, RateLimitExceeded):
        raise exc  # pragma: no cover - defensive; only ever registered for RateLimitExceeded

    response = JSONResponse(
        status_code=429,
        content={
            "detail": (
                f"Too many requests ({exc.detail}). Please wait a moment and try again."
            )
        },
    )
    # Adds standard `Retry-After` / `X-RateLimit-*` response headers so a
    # well-behaved client knows how long to back off, matching what
    # slowapi's own default handler does — only the JSON body differs.
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)
