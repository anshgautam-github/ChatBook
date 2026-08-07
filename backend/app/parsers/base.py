"""Abstract base class for HTML-to-domain conversation parsers.

Deliberately a different, lower-level abstraction than
`app.parsers.conversation_parser.ConversationParser` (the URL-based
Strategy interface `ParserFactory`/`ExportService` work with): this one
is "given HTML you already fetched, turn it into a `Conversation`" —
useful for a provider whose share pages are plain server-rendered HTML,
like ChatGPT's (see `ChatGptHtmlParser`). A future provider that needs a
completely different fetch/parse shape (a JSON API response instead of
HTML, for instance) would implement `ConversationParser` directly
without needing this class at all — it's an implementation detail some
providers may find convenient, not something every provider must use.
"""
from abc import ABC, abstractmethod

from app.models.conversation import Conversation


class BaseConversationParser(ABC):
    @abstractmethod
    def parse(self, raw_html: str, source_url: str) -> Conversation:
        """Parse raw HTML into a structured Conversation."""
        raise NotImplementedError
