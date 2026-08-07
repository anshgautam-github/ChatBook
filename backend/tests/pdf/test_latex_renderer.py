from app.pdf.latex_renderer import LatexRenderer


class TestDelimiterStyles:
    """Each of the four LaTeX delimiter styles ChatGPT emits should be
    recognized and pulled out into a placeholder + rendered replacement."""

    def test_display_dollar_is_extracted(self) -> None:
        renderer = LatexRenderer()
        text = r"Energy: $$E = mc^2$$ done."
        protected, replacements = renderer.extract(text)
        assert "$$" not in protected
        assert len(replacements) == 1
        (html_snippet,) = replacements.values()
        assert 'class="latex-display"' in html_snippet or 'class="latex-fallback"' in html_snippet

    def test_display_bracket_is_extracted(self) -> None:
        renderer = LatexRenderer()
        text = r"\[ x = \frac{1}{2} \]"
        protected, replacements = renderer.extract(text)
        assert r"\[" not in protected
        assert len(replacements) == 1

    def test_inline_paren_is_extracted(self) -> None:
        renderer = LatexRenderer()
        text = r"The value \(x + y\) is small."
        protected, replacements = renderer.extract(text)
        assert r"\(" not in protected
        assert len(replacements) == 1

    def test_inline_dollar_is_extracted(self) -> None:
        renderer = LatexRenderer()
        text = r"We know $a^2 + b^2 = c^2$ from geometry."
        protected, replacements = renderer.extract(text)
        assert len(replacements) == 1
        assert "We know" in protected
        assert "from geometry" in protected

    def test_display_tried_before_inline_for_double_dollar(self) -> None:
        """`$$...$$` must not be chopped into two bogus `$...$` matches."""
        renderer = LatexRenderer()
        text = r"$$a + b$$"
        _, replacements = renderer.extract(text)
        assert len(replacements) == 1


class TestCurrencyIsNotMistakenForMath:
    def test_two_currency_amounts_are_left_untouched(self) -> None:
        renderer = LatexRenderer()
        text = "It costs $5 and $10 depending on size."
        protected, replacements = renderer.extract(text)
        assert protected == text
        assert replacements == {}

    def test_single_currency_amount_is_left_untouched(self) -> None:
        renderer = LatexRenderer()
        text = "The total was $42 after tax."
        protected, replacements = renderer.extract(text)
        assert protected == text
        assert replacements == {}


class TestCodeIsProtectedFromLatexExtraction:
    def test_dollar_inside_fenced_code_block_is_untouched(self) -> None:
        renderer = LatexRenderer()
        text = "```bash\necho $HOME\necho $1\n```"
        protected, replacements = renderer.extract(text)
        assert protected == text
        assert replacements == {}

    def test_dollar_inside_inline_code_span_is_untouched(self) -> None:
        renderer = LatexRenderer()
        text = "Run `echo $PATH` in your shell."
        protected, replacements = renderer.extract(text)
        assert protected == text
        assert replacements == {}

    def test_real_math_outside_code_is_still_extracted_when_code_also_present(self) -> None:
        renderer = LatexRenderer()
        text = "Use `$HOME` but note that $a + b = c$ holds."
        protected, replacements = renderer.extract(text)
        assert "$HOME" in protected
        assert len(replacements) == 1


class TestFallbackForUnsupportedLatex:
    def test_bmatrix_environment_falls_back_to_raw_source(self) -> None:
        """matplotlib's mathtext doesn't support \\begin{...} environments;
        rendering must degrade gracefully rather than raise."""
        renderer = LatexRenderer()
        text = r"$$\begin{bmatrix} 1 & 0 \\ 0 & 1 \end{bmatrix}$$"
        protected, replacements = renderer.extract(text)
        assert len(replacements) == 1
        (html_snippet,) = replacements.values()
        assert "latex-fallback" in html_snippet
        assert "bmatrix" in html_snippet


class TestRestore:
    def test_restore_splices_all_placeholders_back_in(self) -> None:
        renderer = LatexRenderer()
        text = r"First $a+b$ and second $c+d$."
        protected, replacements = renderer.extract(text)
        # Simulate what Markdown conversion would do: wrap the protected
        # text in a paragraph tag, leaving placeholders untouched.
        pseudo_html = f"<p>{protected}</p>"
        restored = renderer.restore(pseudo_html, replacements)
        assert "LATEXPLACEHOLDER" not in restored
        for html_snippet in replacements.values():
            assert html_snippet in restored

    def test_restore_is_a_no_op_when_there_is_nothing_to_replace(self) -> None:
        renderer = LatexRenderer()
        html = "<p>No math here.</p>"
        assert renderer.restore(html, {}) == html


class TestNoLatexPresent:
    def test_plain_text_is_returned_unchanged(self) -> None:
        renderer = LatexRenderer()
        text = "Just a plain sentence with no math at all."
        protected, replacements = renderer.extract(text)
        assert protected == text
        assert replacements == {}
