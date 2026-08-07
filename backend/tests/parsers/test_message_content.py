from app.parsers.message_content import extract_markdown_from_content


class TestTextContent:
    def test_joins_multiple_parts(self) -> None:
        content = {"content_type": "text", "parts": ["First part.", "Second part."]}
        assert extract_markdown_from_content(content) == "First part.\n\nSecond part."

    def test_preserves_markdown_lists_and_emphasis(self) -> None:
        text = "**Steps:**\n\n- First\n- Second\n- Third"
        content = {"content_type": "text", "parts": [text]}
        assert extract_markdown_from_content(content) == text

    def test_preserves_fenced_code_blocks_already_in_text(self) -> None:
        text = "Here:\n\n```python\ndef f():\n    return 1\n```"
        content = {"content_type": "text", "parts": [text]}
        assert extract_markdown_from_content(content) == text

    def test_preserves_markdown_tables(self) -> None:
        text = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        content = {"content_type": "text", "parts": [text]}
        assert extract_markdown_from_content(content) == text

    def test_preserves_latex(self) -> None:
        text = r"The formula is $$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$"
        content = {"content_type": "text", "parts": [text]}
        assert extract_markdown_from_content(content) == text

    def test_empty_parts_returns_none(self) -> None:
        content = {"content_type": "text", "parts": []}
        assert extract_markdown_from_content(content) is None

    def test_whitespace_only_part_returns_none(self) -> None:
        content = {"content_type": "text", "parts": ["   \n  "]}
        assert extract_markdown_from_content(content) is None


class TestCodeContent:
    def test_wraps_in_fenced_block_with_language(self) -> None:
        content = {"content_type": "code", "language": "python", "text": "print('hi')"}
        assert extract_markdown_from_content(content) == "```python\nprint('hi')\n```"

    def test_unknown_language_has_no_language_tag(self) -> None:
        content = {"content_type": "code", "language": "unknown", "text": "echo hi"}
        assert extract_markdown_from_content(content) == "```\necho hi\n```"

    def test_empty_code_returns_none(self) -> None:
        content = {"content_type": "code", "language": "python", "text": ""}
        assert extract_markdown_from_content(content) is None


class TestMultimodalContent:
    def test_keeps_text_segments(self) -> None:
        content = {"content_type": "multimodal_text", "parts": ["Look at this:"]}
        assert extract_markdown_from_content(content) == "Look at this:"

    def test_unresolvable_image_pointer_becomes_placeholder(self) -> None:
        """A `sediment://` pointer needs an authenticated API call to resolve
        — not something a public, anonymous share-page fetch can do."""
        content = {
            "content_type": "multimodal_text",
            "parts": [
                "Here's a photo:",
                {"content_type": "image_asset_pointer", "asset_pointer": "sediment://file-abc"},
            ],
        }
        result = extract_markdown_from_content(content)
        assert result is not None
        assert "Here's a photo:" in result
        assert "not available" in result.lower()
        assert "![" not in result

    def test_public_https_image_pointer_becomes_markdown_image(self) -> None:
        """A directly-fetchable https URL is preserved as a real image,
        not just a placeholder, so it can be rendered later (e.g. in a PDF)."""
        content = {
            "content_type": "multimodal_text",
            "parts": [
                "Here's a photo:",
                {
                    "content_type": "image_asset_pointer",
                    "asset_pointer": "https://files.oaiusercontent.com/abc123.png",
                },
            ],
        }
        result = extract_markdown_from_content(content)
        assert result is not None
        assert "![Image](https://files.oaiusercontent.com/abc123.png)" in result

    def test_no_segments_returns_none(self) -> None:
        content = {"content_type": "multimodal_text", "parts": []}
        assert extract_markdown_from_content(content) is None


class TestTetherQuote:
    def test_formats_as_blockquote_with_title(self) -> None:
        content = {"content_type": "tether_quote", "text": "quoted text", "title": "Source"}
        result = extract_markdown_from_content(content)
        assert result == "> **Source**\n> quoted text"


class TestSkippedContentTypes:
    def test_thoughts_is_skipped(self) -> None:
        content = {"content_type": "thoughts", "thoughts": [{"summary": "s", "content": "c"}]}
        assert extract_markdown_from_content(content) is None

    def test_reasoning_recap_is_skipped(self) -> None:
        content = {"content_type": "reasoning_recap", "content": "Thought for 4s"}
        assert extract_markdown_from_content(content) is None

    def test_user_editable_context_is_skipped(self) -> None:
        content = {
            "content_type": "user_editable_context",
            "user_profile": "...",
            "user_instructions": "...",
        }
        assert extract_markdown_from_content(content) is None

    def test_model_editable_context_is_skipped(self) -> None:
        content = {"content_type": "model_editable_context", "model_set_context": "..."}
        assert extract_markdown_from_content(content) is None


class TestUnknownContentType:
    def test_falls_back_to_parts_if_present(self) -> None:
        content = {"content_type": "some_future_type", "parts": ["still readable"]}
        assert extract_markdown_from_content(content) == "still readable"

    def test_returns_none_without_parts(self) -> None:
        content = {"content_type": "some_future_type", "weird_field": 123}
        assert extract_markdown_from_content(content) is None
