from app.parsers.payload_locator import find_conversation_payload
from tests.parsers.fixtures import (
    build_conversation_data,
    build_legacy_share_html,
    build_modern_share_html,
    user_message,
)


def _sample_data():
    return build_conversation_data(
        title="Sample Chat",
        entries=[("n1", user_message("n1", "Hello"))],
    )


class TestFindConversationPayload:
    def test_modern_format_quoted(self) -> None:
        data = _sample_data()
        html = build_modern_share_html(data, quoted=True)
        found = find_conversation_payload(html)
        assert found is not None
        assert found["title"] == "Sample Chat"

    def test_modern_format_bare_array(self) -> None:
        data = _sample_data()
        html = build_modern_share_html(data, quoted=False)
        found = find_conversation_payload(html)
        assert found is not None
        assert found["title"] == "Sample Chat"

    def test_legacy_format(self) -> None:
        data = _sample_data()
        html = build_legacy_share_html(data)
        found = find_conversation_payload(html)
        assert found is not None
        assert found["title"] == "Sample Chat"

    def test_resilient_to_renamed_route_key(self) -> None:
        """If OpenAI renames the route, the structural fallback still finds it."""
        data = _sample_data()
        html = build_modern_share_html(data, route_key="routes/share.$conversationId")
        found = find_conversation_payload(html)
        assert found is not None
        assert found["title"] == "Sample Chat"

    def test_returns_none_for_unrecognized_html(self) -> None:
        html = "<html><body><p>Just a regular page, not a ChatGPT share.</p></body></html>"
        assert find_conversation_payload(html) is None

    def test_returns_none_for_empty_html(self) -> None:
        assert find_conversation_payload("") is None
