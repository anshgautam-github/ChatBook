"""Tests for `ChatGPTParser` — the ChatGPT `ConversationParser` Strategy
implementation (see app/parsers/chatgpt_parser.py).

`can_handle` is deliberately a coarse host-only check (see the docstring
on `ConversationParser.can_handle`), so these tests only assert on host
matching, not full URL shape — that full validation is `ChatFetcher`'s
job and is already covered by test_chat_fetcher.py. `parse()` here is
tested purely as wiring: does it hand off to the injected fetcher then
the injected html_parser, in order, with the right arguments, and let
errors from either one propagate unchanged.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from app.models.conversation import Conversation
from app.parsers.chatgpt_parser import ChatGPTParser
from app.utils.exceptions import ConversationFetchError, ConversationParseError


class _FakeFetcher:
    def __init__(self, html: str = "<html>fake</html>", error: Optional[Exception] = None) -> None:
        self.html = html
        self.error = error
        self.requested_urls: list[str] = []

    async def fetch_html(self, url: str) -> str:
        self.requested_urls.append(url)
        if self.error is not None:
            raise self.error
        return self.html


class _FakeHtmlParser:
    def __init__(self, conversation: Optional[Conversation] = None, error: Optional[Exception] = None) -> None:
        self.conversation = conversation
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def parse(self, raw_html: str, source_url: str) -> Conversation:
        self.calls.append((raw_html, source_url))
        if self.error is not None:
            raise self.error
        return self.conversation


class TestCanHandle:
    @pytest.mark.parametrize(
        "url",
        [
            "https://chatgpt.com/share/abc-123",
            "https://chat.openai.com/share/abc-123",
            "https://CHATGPT.COM/share/abc-123",  # host matching is case-insensitive
            "https://chatgpt.com/c/some-private-chat",  # coarse check: host matches even for private paths
        ],
    )
    def test_true_for_chatgpt_hosts(self, url: str) -> None:
        assert ChatGPTParser().can_handle(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://claude.ai/share/abc-123",
            "https://gemini.google.com/share/abc-123",
            "https://example.com",
            "not-a-url-at-all",
            "",
        ],
    )
    def test_false_for_non_chatgpt_hosts(self, url: str) -> None:
        assert ChatGPTParser().can_handle(url) is False

    def test_false_for_url_that_fails_to_parse(self) -> None:
        # A malformed IPv6-style authority raises ValueError out of
        # urlparse().hostname — can_handle must swallow that as "no",
        # not propagate it (routing checks must never raise).
        assert ChatGPTParser().can_handle("https://[not-valid") is False


class TestParse:
    def test_delegates_to_fetcher_then_html_parser_in_order(self) -> None:
        expected_conversation = Conversation(
            title="Fake", source_url="https://chatgpt.com/share/abc", messages=[], sections=[]
        )
        fetcher = _FakeFetcher(html="<html>raw page</html>")
        html_parser = _FakeHtmlParser(conversation=expected_conversation)
        parser = ChatGPTParser(fetcher=fetcher, html_parser=html_parser)

        result = asyncio.run(parser.parse("https://chatgpt.com/share/abc"))

        assert result is expected_conversation
        assert fetcher.requested_urls == ["https://chatgpt.com/share/abc"]
        assert html_parser.calls == [("<html>raw page</html>", "https://chatgpt.com/share/abc")]

    def test_propagates_fetcher_errors_unchanged(self) -> None:
        fetcher = _FakeFetcher(error=ConversationFetchError("network is down"))
        parser = ChatGPTParser(fetcher=fetcher, html_parser=_FakeHtmlParser())

        with pytest.raises(ConversationFetchError):
            asyncio.run(parser.parse("https://chatgpt.com/share/abc"))

    def test_propagates_html_parser_errors_unchanged(self) -> None:
        fetcher = _FakeFetcher(html="<html>unrecognized</html>")
        html_parser = _FakeHtmlParser(error=ConversationParseError("could not find conversation data"))
        parser = ChatGPTParser(fetcher=fetcher, html_parser=html_parser)

        with pytest.raises(ConversationParseError):
            asyncio.run(parser.parse("https://chatgpt.com/share/abc"))

    def test_html_parser_is_never_called_when_fetch_fails(self) -> None:
        fetcher = _FakeFetcher(error=ConversationFetchError("timed out"))
        html_parser = _FakeHtmlParser()
        parser = ChatGPTParser(fetcher=fetcher, html_parser=html_parser)

        with pytest.raises(ConversationFetchError):
            asyncio.run(parser.parse("https://chatgpt.com/share/abc"))

        assert html_parser.calls == []


class TestConstructorInjectionDefaults:
    def test_omitted_collaborators_default_to_real_implementations(self) -> None:
        from app.parsers.chatgpt_html_parser import ChatGptHtmlParser
        from app.services.chat_fetcher import ChatFetcher

        parser = ChatGPTParser()

        assert isinstance(parser._fetcher, ChatFetcher)
        assert isinstance(parser._html_parser, ChatGptHtmlParser)
