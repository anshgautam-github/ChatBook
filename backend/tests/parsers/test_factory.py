"""Tests for `ParserFactory` — the only place in the app that chooses
*which* `ConversationParser` strategy handles a given URL (see
app/parsers/factory.py).

Uses small fake `ConversationParser` strategies rather than
`ChatGPTParser` so these tests are about the factory's selection logic
only (first-match-wins, ordering, the "no parser claims this URL" error)
and don't depend on ChatGPT-specific behavior at all. One of the fakes
below stands in for a hypothetical future provider (e.g. Claude) purely
to demonstrate that adding a new strategy to the list is all it takes —
exactly the extensibility the Strategy + Factory combination is meant to
provide.
"""
from __future__ import annotations

import asyncio

import pytest

from app.models.conversation import Conversation
from app.parsers.chatgpt_parser import ChatGPTParser
from app.parsers.conversation_parser import ConversationParser
from app.parsers.factory import ParserFactory
from app.utils.exceptions import InvalidShareUrlError


class _FakeParser(ConversationParser):
    """A `ConversationParser` strategy double that claims URLs whose
    host matches `host`, standing in for one hypothetical provider."""

    def __init__(self, host: str, label: str) -> None:
        self.host = host
        self.label = label

    def can_handle(self, url: str) -> bool:
        return self.host in url

    async def parse(self, url: str) -> Conversation:
        return Conversation(title=self.label, source_url=url, messages=[], sections=[])


class TestGetParser:
    def test_returns_the_parser_whose_can_handle_matches(self) -> None:
        chatgpt_like = _FakeParser(host="chatgpt.com", label="chatgpt")
        claude_like = _FakeParser(host="claude.ai", label="claude")
        factory = ParserFactory(parsers=[chatgpt_like, claude_like])

        assert factory.get_parser("https://chatgpt.com/share/abc") is chatgpt_like
        assert factory.get_parser("https://claude.ai/share/xyz") is claude_like

    def test_returns_the_first_match_when_multiple_parsers_would_claim_the_url(self) -> None:
        first = _FakeParser(host="chatgpt.com", label="first")
        second = _FakeParser(host="chatgpt.com", label="second")
        factory = ParserFactory(parsers=[first, second])

        assert factory.get_parser("https://chatgpt.com/share/abc") is first

    def test_raises_invalid_share_url_error_when_no_parser_claims_the_url(self) -> None:
        factory = ParserFactory(parsers=[_FakeParser(host="chatgpt.com", label="chatgpt")])

        with pytest.raises(InvalidShareUrlError):
            factory.get_parser("https://some-unsupported-provider.example/share/abc")

    def test_adding_a_new_provider_requires_no_change_to_existing_parsers(self) -> None:
        """Demonstrates the extensibility goal directly: registering a new
        fake "provider" strategy alongside ChatGPTParser is enough for the
        factory to route to it — nothing about ChatGPTParser, or the
        factory's own code, has to change."""
        future_provider = _FakeParser(host="claude.ai", label="claude")
        factory = ParserFactory(parsers=[ChatGPTParser(), future_provider])

        assert factory.get_parser("https://claude.ai/share/xyz") is future_provider
        assert factory.get_parser("https://chatgpt.com/share/abc") is not future_provider


class TestConstructorDefaults:
    def test_omitting_parsers_defaults_to_the_real_provider_registry(self) -> None:
        factory = ParserFactory()

        assert len(factory._parsers) >= 1
        assert any(isinstance(p, ChatGPTParser) for p in factory._parsers)

    def test_default_registry_handles_a_real_chatgpt_share_url(self) -> None:
        factory = ParserFactory()

        parser = factory.get_parser("https://chatgpt.com/share/some-id")

        assert isinstance(parser, ChatGPTParser)
