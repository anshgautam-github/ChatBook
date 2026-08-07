from app.pdf.markdown_renderer import MarkdownRenderer


class TestBasicMarkdownConstructs:
    def test_renders_heading(self) -> None:
        renderer = MarkdownRenderer()
        result = renderer.render("# Title")
        assert "<h1>Title</h1>" in result

    def test_renders_unordered_list(self) -> None:
        renderer = MarkdownRenderer()
        result = renderer.render("- First\n- Second\n- Third")
        assert "<li>First</li>" in result
        assert "<li>Second</li>" in result
        assert "<ul>" in result

    def test_renders_ordered_list(self) -> None:
        renderer = MarkdownRenderer()
        result = renderer.render("1. First\n2. Second")
        assert "<ol>" in result
        assert "<li>First</li>" in result

    def test_renders_table_via_extra_extension(self) -> None:
        renderer = MarkdownRenderer()
        result = renderer.render("| A | B |\n| --- | --- |\n| 1 | 2 |")
        assert "<table>" in result
        assert "<th>A</th>" in result
        assert "<td>1</td>" in result

    def test_single_newline_becomes_br_via_nl2br(self) -> None:
        renderer = MarkdownRenderer()
        result = renderer.render("Line one\nLine two")
        assert "<br" in result


class TestFencedCodeBlocks:
    def test_fenced_code_block_gets_codehilite_wrapper(self) -> None:
        renderer = MarkdownRenderer()
        markdown_text = "```python\ndef f():\n    return 1\n```"
        result = renderer.render(markdown_text)
        assert 'class="codehilite"' in result

    def test_fenced_code_is_syntax_highlighted_with_pygments_spans(self) -> None:
        renderer = MarkdownRenderer()
        markdown_text = "```python\ndef bubble_sort():\n    pass\n```"
        result = renderer.render(markdown_text)
        # Pygments wraps each token in its own <span>, so check for the
        # highlighted function-name token rather than a contiguous string.
        assert 'class="nf">bubble_sort<' in result
        assert 'class="k">def<' in result

    def test_unlabeled_fence_is_not_guessed(self) -> None:
        """guess_lang=False: an unlabeled fence shouldn't get a wrong-guess
        language's highlighting classes applied to it."""
        renderer = MarkdownRenderer()
        markdown_text = "```\nplain text, no language\n```"
        result = renderer.render(markdown_text)
        assert 'class="codehilite"' in result


class TestRendererIndependence:
    def test_each_render_call_is_independent(self) -> None:
        """A fresh Markdown() instance per call means no state (e.g.
        footnote/reference counters) leaks between separate messages."""
        renderer = MarkdownRenderer()
        first = renderer.render("# Heading One")
        second = renderer.render("# Heading Two")
        assert "Heading One" in first
        assert "Heading Two" not in first
        assert "Heading Two" in second
        assert "Heading One" not in second
