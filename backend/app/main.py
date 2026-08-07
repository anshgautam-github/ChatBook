"""FastAPI application entrypoint."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import api_router
from app.config.settings import get_settings
from app.utils.logger import get_logger
from app.utils.rate_limiter import limiter, rate_limit_exceeded_handler

settings = get_settings()
logger = get_logger(__name__)

app = FastAPI(
    title="gptTOpdf API",
    description="Converts ChatGPT shared conversations into structured study notes and PDFs.",
    version="0.1.0",
)

# Per-client-IP rate limiting for /parse and /generate-pdf — see
# app/utils/rate_limiter.py for the limiter itself and why those two
# endpoints specifically. Registering `limiter` on `app.state` (rather
# than only importing it directly into route modules) is what lets
# slowapi's exception handler and middleware find it via `request.app.state`.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # The browser extension's panel runs from an extension-scheme origin
    # — `chrome-extension://<id>` on Chrome, `safari-web-extension://<id>`
    # on Safari — and that `<id>` is only assigned once the extension is
    # loaded (and differs per machine/profile for an unpacked/unsigned
    # build), so there's no single fixed value to add to
    # `cors_origin_list`. This matters even for local testing, not just
    # public deployment: Safari's panel origin needs this regex to reach
    # `localhost:8000` too. A regex is the standard way CORSMiddleware
    # supports "any origin matching this shape" without falling back to
    # `allow_origins=["*"]`, which would open the API to every website.
    allow_origin_regex=r"(chrome|safari-web)-extension://.*",
    # No cookie/session auth exists anywhere in this API — every request
    # is a plain, credential-less fetch — so there's nothing for
    # `allow_credentials` to protect and no reason to accept
    # cookies/Authorization headers cross-origin.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort safety net for anything a route's own error handling misses.

    Every route already catches its own domain-specific `AppError`
    subclasses and turns them into a friendly `HTTPException`. This exists
    for what's left over — most plausibly an OpenAI share-page HTML/JSON
    shape neither the parser's structural fallback nor its own guards
    anticipated. Without this handler, that surfaces to the extension as a
    bare, unstyled 500 with no message; with it, the user still sees a
    normal "something went wrong" error in the panel instead of the
    request just failing silently, and the real exception is logged
    server-side (not exposed to the client, which never needs to see a
    stack trace or internal exception text).
    """
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again in a moment."},
    )
