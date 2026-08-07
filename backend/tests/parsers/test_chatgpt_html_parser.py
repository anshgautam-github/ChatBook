"""End-to-end tests: raw HTML in, `Conversation` domain object out.

These exercise the full pipeline (`loader_extraction` ->
`payload_locator` -> `conversation_builder` -> `message_content`) the way
`ChatGPTParser` actually uses it, and specifically check that
Markdown, fenced code blocks, lists, tables, and LaTeX all survive
untouched end to end.
"""
import pytest

from app.parsers.chatgpt_html_parser import ChatGptHtmlParser
from app.utils.exceptions import ConversationParseError
from tests.parsers.fixtures import (
    assistant_message,
    build_conversation_data,
    build_legacy_share_html,
    build_modern_share_html,
    system_message,
    tool_message,
    user_message,
)

CODE_ANSWER = (
    "Bubble sort works by repeatedly stepping through the list.\n\n"
    "- Compare adjacent elements\n"
    "- Swap if out of order\n"
    "- Repeat until the list is sorted\n\n"
    "```python\n"
    "def bubble_sort(arr):\n"
    "    n = len(arr)\n"
    "    for i in range(n):\n"
    "        for j in range(n - i - 1):\n"
    "            if arr[j] > arr[j + 1]:\n"
    "                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n"
    "    return arr\n"
    "```"
)

TABLE_AND_LATEX_ANSWER = (
    "| Algorithm | Best | Worst |\n"
    "| --- | --- | --- |\n"
    "| Bubble Sort | O(n) | O(n^2) |\n"
    "| Quick Sort | O(n log n) | O(n^2) |\n\n"
    "The quadratic formula is:\n\n"
    r"$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$"
)


def _rich_conversation_data():
    return build_conversation_data(
        title="Gigawatt Data Centers & Algorithms",
        entries=[
            ("sys", system_message("sys")),
            ("n1", user_message("n1", "Explain bubble sort and show it in Python.")),
            ("n2", assistant_message("n2", CODE_ANSWER)),
            ("n3", user_message("n3", "Now give me a comparison table and the quadratic formula.")),
            ("n4", assistant_message("n4", TABLE_AND_LATEX_ANSWER)),
        ],
    )


class TestEndToEndParsing:
    def test_parses_modern_share_page(self) -> None:
        html = build_modern_share_html(_rich_conversation_data())
        conversation = ChatGptHtmlParser().parse(html, source_url="https://chatgpt.com/share/abc123")

        assert conversation.title == "Gigawatt Data Centers & Algorithms"
        assert conversation.source_url == "https://chatgpt.com/share/abc123"
        assert len(conversation.messages) == 4
        assert len(conversation.sections) == 2

    def test_parses_legacy_share_page(self) -> None:
        html = build_legacy_share_html(_rich_conversation_data())
        conversation = ChatGptHtmlParser().parse(html, source_url="https://chat.openai.com/share/abc123")

        assert conversation.title == "Gigawatt Data Centers & Algorithms"
        assert len(conversation.messages) == 4

    def test_preserves_markdown_lists(self) -> None:
        html = build_modern_share_html(_rich_conversation_data())
        conversation = ChatGptHtmlParser().parse(html, source_url="https://chatgpt.com/share/abc123")
        answer = conversation.sections[0].answer.content
        assert "- Compare adjacent elements" in answer
        assert "- Swap if out of order" in answer

    def test_preserves_fenced_code_blocks(self) -> None:
        html = build_modern_share_html(_rich_conversation_data())
        conversation = ChatGptHtmlParser().parse(html, source_url="https://chatgpt.com/share/abc123")
        answer = conversation.sections[0].answer.content
        assert "```python" in answer
        assert "def bubble_sort(arr):" in answer
        assert answer.strip().endswith("```")

    def test_preserves_markdown_tables(self) -> None:
        html = build_modern_share_html(_rich_conversation_data())
        conversation = ChatGptHtmlParser().parse(html, source_url="https://chatgpt.com/share/abc123")
        answer = conversation.sections[1].answer.content
        assert "| Algorithm | Best | Worst |" in answer
        assert "| Bubble Sort | O(n) | O(n^2) |" in answer

    def test_preserves_latex(self) -> None:
        html = build_modern_share_html(_rich_conversation_data())
        conversation = ChatGptHtmlParser().parse(html, source_url="https://chatgpt.com/share/abc123")
        answer = conversation.sections[1].answer.content
        assert r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}" in answer
        assert answer.count("$$") == 2


class TestErrorHandling:
    def test_raises_on_empty_html(self) -> None:
        with pytest.raises(ConversationParseError):
            ChatGptHtmlParser().parse("", source_url="https://chatgpt.com/share/x")

    def test_raises_when_no_payload_found(self) -> None:
        html = "<html><body>Not a ChatGPT share page at all.</body></html>"
        with pytest.raises(ConversationParseError):
            ChatGptHtmlParser().parse(html, source_url="https://chatgpt.com/share/x")

    def test_raises_when_no_visible_messages_extracted(self) -> None:
        data = build_conversation_data(
            title="Only hidden content",
            entries=[
                ("sys", system_message("sys", "hidden system prompt")),
                ("tool1", tool_message("tool1", "tool output only")),
            ],
        )
        html = build_modern_share_html(data)
        with pytest.raises(ConversationParseError):
            ChatGptHtmlParser().parse(html, source_url="https://chatgpt.com/share/x")
