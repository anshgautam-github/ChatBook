"""ConversationParser — the Strategy interface for turning a conversation
share URL from some AI provider into a structured `Conversation`.

Every supported provider (ChatGPT today; Claude, Gemini, etc. tomorrow)
implements this as its own class — see `app/parsers/chatgpt_parser.py`
for the ChatGPT implementation. `ParserFactory`
(app/parsers/factory.py) is the only thing in the app that ever chooses
*which* concrete implementation runs for a given URL; `ExportService`
(app/services/export_service.py) just asks the factory for a parser and
calls `parser.parse(url)` — it never branches on the URL itself.

Adding a new provider means writing one new class that implements this
interface and registering it with `ParserFactory`. No existing code
(least of all `ExportService`) needs to change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.conversation import Conversation


class ConversationParser(ABC):
    """One AI provider's strategy for recognizing and parsing its share links."""

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True if this parser's provider owns `url`.

        Deliberately a coarse, cheap, side-effect-free check (e.g. "is
        this host chatgpt.com?") used only to route to the right parser
        — NOT full validation of the URL's shape (private vs. shared
        link, share-ID format, etc.). That level of detail is each
        parser's own business and belongs in `parse()`, where a rejected
        URL can raise a specific, helpful `AppError` instead of
        `ParserFactory` falling back to one generic "unsupported" message
        for every possible way a URL can be invalid.
        """
        raise NotImplementedError

    @abstractmethod
    async def parse(self, url: str) -> Conversation:
        """Fetch and parse `url` into a `Conversation`.

        Only ever called by `ParserFactory.get_parser(url)` after
        `can_handle(url)` has already returned True for this instance.
        May raise any `AppError` subclass (invalid URL shape, network
        failure, unrecognized page structure) — callers are expected to
        translate that into an HTTP response, not this method.
        """
        raise NotImplementedError
