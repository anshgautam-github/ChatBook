"""Parses raw ChatGPT shared-page HTML into a structured `Conversation`.

This is the lowest-level ChatGPT-specific piece: given HTML you already
have, turn it into a `Conversation`. It has no idea how that HTML was
obtained, and no idea it's being used as part of a `ConversationParser`
Strategy implementation (`ChatGPTParser`, in app/parsers/chatgpt_parser.py,
is what wires this together with `ChatFetcher` and exposes the
URL-based `can_handle`/`parse` Strategy interface). Everything that
knows about ChatGPT's actual HTML/JSON structure lives under
`app/parsers/`:

- `loader_extraction.py` — pulls raw embedded JSON out of `<script>` tags
- `payload_locator.py`   — finds the conversation dict within that JSON
- `conversation_builder.py` — turns that dict into `Message`/`QaSection`s
- `message_content.py`   — turns one message's `content` into Markdown

If OpenAI changes their page structure, only those modules (all inside
this package) need to change — `services/`, `api/`, and the frontend never
see anything HTML-shaped.
"""
from __future__ import annotations

from app.models.conversation import Conversation
from app.parsers.base import BaseConversationParser
from app.parsers.conversation_builder import build_conversation
from app.parsers.payload_locator import find_conversation_payload
from app.utils.exceptions import ConversationParseError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ChatGptHtmlParser(BaseConversationParser):
    """Converts a ChatGPT share page's raw HTML into a `Conversation` domain object."""

    def parse(self, raw_html: str, source_url: str) -> Conversation:
        if not raw_html or not raw_html.strip():
            raise ConversationParseError("The fetched page was empty.")

        payload = find_conversation_payload(raw_html)
        if payload is None:
            raise ConversationParseError(
                "Could not find conversation data in this page. OpenAI may have "
                "changed the share page structure, or this isn't a valid ChatGPT "
                "share link."
            )

        conversation = build_conversation(payload, source_url=source_url)

        if not conversation.messages:
            raise ConversationParseError(
                "No user or assistant messages could be extracted from this "
                "conversation. The share page structure may have changed."
            )

        logger.info(
            "Parsed conversation %r: %d messages, %d sections",
            conversation.title,
            len(conversation.messages),
            len(conversation.sections),
        )
        return conversation
