import asyncio

import httpx
import pytest

from app.services.chat_fetcher import ChatFetcher
from app.utils.exceptions import ConversationFetchError, InvalidShareUrlError


class TestValidateUrl:
    def test_accepts_valid_chatgpt_share_link(self) -> None:
        ChatFetcher().validate_url("https://chatgpt.com/share/abc-123")

    def test_accepts_legacy_host(self) -> None:
        ChatFetcher().validate_url("https://chat.openai.com/share/abc-123")

    def test_rejects_non_https(self) -> None:
        with pytest.raises(InvalidShareUrlError):
            ChatFetcher().validate_url("http://chatgpt.com/share/abc-123")

    def test_rejects_unrelated_host(self) -> None:
        with pytest.raises(InvalidShareUrlError):
            ChatFetcher().validate_url("https://evil.example.com/share/abc-123")

    def test_rejects_private_chat_link(self) -> None:
        with pytest.raises(InvalidShareUrlError):
            ChatFetcher().validate_url("https://chatgpt.com/c/abc-123")

    def test_rejects_malformed_url(self) -> None:
        with pytest.raises(InvalidShareUrlError):
            ChatFetcher().validate_url("not a url at all")


def _fetcher_with_response(status_code: int, text: str = "") -> ChatFetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=text, request=request)

    return ChatFetcher(transport=httpx.MockTransport(handler))


class TestFetchHtml:
    def test_returns_body_text_on_success(self) -> None:
        fetcher = _fetcher_with_response(200, text="<html>conversation</html>")
        html = asyncio.run(fetcher.fetch_html("https://chatgpt.com/share/abc-123"))
        assert html == "<html>conversation</html>"

    def test_404_raises_conversation_fetch_error(self) -> None:
        fetcher = _fetcher_with_response(404)
        with pytest.raises(ConversationFetchError):
            asyncio.run(fetcher.fetch_html("https://chatgpt.com/share/missing"))

    def test_403_raises_conversation_fetch_error(self) -> None:
        fetcher = _fetcher_with_response(403)
        with pytest.raises(ConversationFetchError):
            asyncio.run(fetcher.fetch_html("https://chatgpt.com/share/private"))

    def test_500_raises_conversation_fetch_error(self) -> None:
        fetcher = _fetcher_with_response(500)
        with pytest.raises(ConversationFetchError):
            asyncio.run(fetcher.fetch_html("https://chatgpt.com/share/broken"))

    def test_invalid_url_raises_before_any_request(self) -> None:
        fetcher = _fetcher_with_response(200)
        with pytest.raises(InvalidShareUrlError):
            asyncio.run(fetcher.fetch_html("https://evil.example.com/share/abc"))
