"""Fetches raw HTML for a ChatGPT shared conversation URL.

A plain HTTP GET is enough in practice: ChatGPT's share pages are
server-rendered (the conversation JSON is embedded directly in the initial
HTML response — see `app/parsers/loader_extraction.py`), so no JavaScript
execution is needed to see the data our parser needs. If OpenAI ever moves
share pages to a fully client-rendered model, this would need a headless-
browser fallback (e.g. Playwright) — not implemented since it isn't
currently needed, and pulling in that dependency ahead of actually
needing it would just mean shipping an unused browser-automation stack.
"""
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.config.settings import get_settings
from app.utils.exceptions import ConversationFetchError, InvalidShareUrlError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Both the current (`chatgpt.com`) and legacy (`chat.openai.com`) hosts are
# accepted since the parser also supports the legacy Next.js page format.
_ALLOWED_HOSTS = {"chatgpt.com", "chat.openai.com"}
_SHARE_PATH_PATTERN = re.compile(r"^/share/[A-Za-z0-9-]+/?$")

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://chatgpt.com/",
}


class ChatFetcher:
    """Responsible only for retrieving raw HTML — no parsing logic lives here."""

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._settings = get_settings()
        # Optional transport injection point: production code never sets
        # this (real network), but it lets tests swap in an
        # `httpx.MockTransport` instead of monkeypatching `httpx` globally.
        self._transport = transport

    def validate_url(self, url: str) -> None:
        """Reject anything that isn't a plausible public ChatGPT share link.

        This runs before any network request, so a malformed or
        out-of-scope URL never reaches `httpx` at all.
        """
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            raise InvalidShareUrlError(f"'{url}' is not a valid URL.") from exc

        if parsed.scheme != "https":
            raise InvalidShareUrlError("The share link must use https.")

        host = (parsed.hostname or "").lower()
        if host not in _ALLOWED_HOSTS:
            raise InvalidShareUrlError(
                f"'{host or url}' isn't a ChatGPT host. Expected a link like "
                "https://chatgpt.com/share/<id>."
            )

        if not _SHARE_PATH_PATTERN.match(parsed.path):
            raise InvalidShareUrlError(
                "That looks like a private ChatGPT link (e.g. '/c/...'), not a "
                "shared conversation. Use the public share link — "
                "https://chatgpt.com/share/<id> — copied from ChatGPT's Share "
                "dialog."
            )

    async def fetch_html(self, url: str) -> str:
        """Fetch the page via plain HTTP and return the raw HTML."""
        self.validate_url(url)
        timeout = self._settings.chatgpt_fetch_timeout_seconds

        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, transport=self._transport
            ) as client:
                response = await client.get(url, headers=_REQUEST_HEADERS)
        except httpx.TimeoutException as exc:
            raise ConversationFetchError(
                "Timed out waiting for chatgpt.com to respond. Please try again."
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch conversation HTML: %s", exc)
            raise ConversationFetchError(f"Could not fetch conversation: {exc}") from exc

        if response.status_code == 404:
            raise ConversationFetchError(
                "This share link doesn't exist or has been deleted."
            )
        if response.status_code in (401, 403):
            raise ConversationFetchError(
                "Access to this conversation was denied. Only public 'Share' "
                "links are supported — private chat links require being "
                "logged in as the owner."
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Unexpected status fetching conversation: %s", exc)
            raise ConversationFetchError(
                f"chatgpt.com returned an unexpected error ({response.status_code})."
            ) from exc

        return response.text
