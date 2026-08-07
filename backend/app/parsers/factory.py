"""ParserFactory — selects the right `ConversationParser` strategy for a URL.

This is the only place in the app that knows there is more than one
possible provider, or which one a given URL belongs to. `ExportService`
never branches on the URL itself — it asks this factory for a parser and
calls `parser.parse(url)` (see app/services/export_service.py).

Supporting a new provider (Claude, Gemini, ...) means writing one new
`ConversationParser` implementation and adding it to `_default_parsers()`
below. Nothing else in the app needs to change.
"""
from __future__ import annotations

from typing import List, Optional

from app.parsers.chatgpt_parser import ChatGPTParser
from app.parsers.conversation_parser import ConversationParser
from app.utils.exceptions import InvalidShareUrlError


def _default_parsers() -> List[ConversationParser]:
    # Built fresh per `ParserFactory` instance rather than as a shared
    # module-level list, so each `ChatGPTParser()` gets its own
    # `ChatFetcher`/`ChatGptHtmlParser` — consistent with how every other
    # service in this app defaults its own collaborators instead of
    # sharing mutable global instances.
    return [ChatGPTParser()]


class ParserFactory:
    """Holds an ordered list of `ConversationParser` strategies and picks
    the first one whose `can_handle(url)` returns True.

    Constructor injection (a custom `parsers` list can be supplied, e.g.
    in tests) follows the same pattern used throughout `app/services/`
    and `app/pdf/` — the real registry of providers is just the default.
    """

    def __init__(self, parsers: Optional[List[ConversationParser]] = None) -> None:
        self._parsers = parsers if parsers is not None else _default_parsers()

    def get_parser(self, url: str) -> ConversationParser:
        for parser in self._parsers:
            if parser.can_handle(url):
                return parser

        raise InvalidShareUrlError(
            f"'{url}' isn't a supported conversation link. Currently supported: "
            "ChatGPT share links like https://chatgpt.com/share/<id>."
        )
