"""ChatGPTParser — the `ConversationParser` Strategy implementation for
ChatGPT share links.

Combines `ChatFetcher` (network I/O — app/services/chat_fetcher.py) and
`ChatGptHtmlParser` (HTML -> domain — app/parsers/chatgpt_html_parser.py)
behind the `ConversationParser` interface. This is the only file in the
app that knows "chatgpt.com" and "chat.openai.com" are the hostnames
this provider owns; `ParserFactory` and `ExportService` don't.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from app.models.conversation import Conversation
from app.parsers.chatgpt_html_parser import ChatGptHtmlParser
from app.parsers.conversation_parser import ConversationParser
from app.services.chat_fetcher import ChatFetcher

# Used only for the coarse `can_handle` routing check below. Full
# share-link shape validation (https scheme required, path must be
# `/share/<id>` and not a private `/c/...` link) already lives in
# `ChatFetcher.validate_url`, reached via `fetch_html()` inside
# `parse()` — kept there rather than duplicated here, so a rejected URL
# still gets that specific, existing error message (e.g. "looks like a
# private ChatGPT link") instead of a generic "unsupported" one from the
# factory.
_CHATGPT_HOSTS = {"chatgpt.com", "chat.openai.com"}


class ChatGPTParser(ConversationParser):
    def __init__(
        self,
        fetcher: Optional[ChatFetcher] = None,
        html_parser: Optional[ChatGptHtmlParser] = None,
    ) -> None:
        self._fetcher = fetcher or ChatFetcher()
        self._html_parser = html_parser or ChatGptHtmlParser()

    def can_handle(self, url: str) -> bool:
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            return False
        return host in _CHATGPT_HOSTS

    async def parse(self, url: str) -> Conversation:
        raw_html = await self._fetcher.fetch_html(url)
        return self._html_parser.parse(raw_html, source_url=url)
