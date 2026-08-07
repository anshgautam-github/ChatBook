"""Renders LaTeX math segments found in Markdown text to inline images.

WeasyPrint rasterizes static HTML/CSS — it cannot execute the JavaScript
that client-side renderers like MathJax/KaTeX rely on. To still get real
typeset math in the PDF, LaTeX segments are pulled out of the raw Markdown
*before* Markdown conversion (so Markdown never mangles backslashes/
underscores/carets inside them), rendered independently to standalone SVG
images via Matplotlib's `mathtext` engine, and spliced back into the
rendered HTML afterwards.

Matplotlib's `mathtext` supports a useful subset of LaTeX math (fractions,
roots, sub/superscripts, Greek letters, sums, integrals, etc.) but not full
LaTeX — things like `\\begin{bmatrix}` environments aren't supported. When
rendering an expression fails, it degrades to a plainly-styled monospace
fallback showing the original LaTeX source rather than dropping the
content or failing the whole PDF, per the "preserve LaTeX rendering if
possible" requirement.
"""
from __future__ import annotations

import base64
import html
import io
import re
from typing import Dict, Optional, Tuple

# Matches, in precedence order, the four LaTeX delimiter styles ChatGPT
# actually emits. Order matters: `$$...$$` must be tried before the single
# `$...$` pattern, or the display form would be chopped into two bogus
# inline matches.
_LATEX_PATTERN = re.compile(
    r"""
      \$\$(?P<display_dollar>.+?)\$\$
    | \\\[(?P<display_bracket>.+?)\\\]
    | \\\((?P<inline_paren>.+?)\\\)
    | \$(?!\s)(?P<inline_dollar>[^\n$]+?)(?<!\s)\$
    """,
    re.VERBOSE | re.DOTALL,
)

# Code (fenced ```...``` blocks and inline `...` spans) is never treated as
# LaTeX, even though it may legitimately contain bare `$` characters (shell
# variables like `$HOME`, `$1`, etc). Match spans are computed once up
# front and any LaTeX-looking match that starts inside one is left alone.
_FENCED_CODE_PATTERN = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")

_PLACEHOLDER_TEMPLATE = "LATEXPLACEHOLDER{index}"

# Lazily-initialized so importing this module (or the rest of the app)
# never pays Matplotlib's import cost unless a PDF actually contains LaTeX.
_pyplot = None


def _get_pyplot():
    global _pyplot
    if _pyplot is None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _pyplot = plt
    return _pyplot


def _match_body(match: "re.Match[str]") -> Tuple[Optional[str], bool]:
    """Return (latex_source, is_display) for whichever alternative matched."""
    if match.group("display_dollar") is not None:
        return match.group("display_dollar"), True
    if match.group("display_bracket") is not None:
        return match.group("display_bracket"), True
    if match.group("inline_paren") is not None:
        return match.group("inline_paren"), False
    if match.group("inline_dollar") is not None:
        return match.group("inline_dollar"), False
    return None, False  # pragma: no cover - unreachable, one group always matches


class LatexRenderer:
    """Extracts LaTeX from Markdown text and renders it to standalone images.

    Usage is a two-step "protect, then restore" dance around Markdown
    conversion:

        protected_text, replacements = renderer.extract(raw_markdown)
        html_fragment = markdown_renderer.render(protected_text)
        html_fragment = renderer.restore(html_fragment, replacements)
    """

    def __init__(self, fontsize: float = 13.0) -> None:
        self._fontsize = fontsize

    def extract(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Replace every LaTeX segment in `text` with an opaque placeholder.

        Returns the placeholder-substituted text plus a
        `{placeholder: rendered_html}` map to splice back in after Markdown
        conversion. The placeholder itself is a plain uppercase token with
        no Markdown-special characters, so Markdown always passes it
        through untouched regardless of what element it ends up inside.
        """
        code_spans = [
            match.span()
            for pattern in (_FENCED_CODE_PATTERN, _INLINE_CODE_PATTERN)
            for match in pattern.finditer(text)
        ]

        replacements: Dict[str, str] = {}
        counter = 0

        def _inside_code(start: int) -> bool:
            return any(span_start <= start < span_end for span_start, span_end in code_spans)

        def _replace(match: "re.Match[str]") -> str:
            nonlocal counter
            if _inside_code(match.start()):
                # A bare `$` in a code block (e.g. `$HOME`, `$1`) is shell
                # syntax, not math — leave it exactly as written.
                return match.group(0)

            body, is_display = _match_body(match)
            if body is None:  # pragma: no cover - defensive, see _match_body
                return match.group(0)

            placeholder = _PLACEHOLDER_TEMPLATE.format(index=counter)
            counter += 1
            replacements[placeholder] = self._render_one(body.strip(), is_display)
            return placeholder

        protected = _LATEX_PATTERN.sub(_replace, text)
        return protected, replacements

    def restore(self, rendered_html: str, replacements: Dict[str, str]) -> str:
        """Splice the rendered LaTeX images back into converted HTML.

        Markdown conversion can wrap a placeholder in `<p>`/`<code>`/etc,
        but never alters the placeholder text itself (it contains no
        Markdown-special characters), so a plain substitution is safe and
        doesn't require re-parsing the HTML.
        """
        for placeholder, html_snippet in replacements.items():
            rendered_html = rendered_html.replace(placeholder, html_snippet)
        return rendered_html

    def _render_one(self, latex_source: str, is_display: bool) -> str:
        wrapper = "div" if is_display else "span"
        css_class = "latex-display" if is_display else "latex-inline"

        try:
            data_uri = self._render_to_data_uri(latex_source)
        except Exception:
            # Matplotlib's mathtext only supports a subset of LaTeX (no
            # \begin{...} environments, no \substack, etc). Anything it
            # can't parse degrades to the raw source instead of vanishing.
            escaped = html.escape(latex_source)
            return f'<{wrapper} class="latex-fallback"><code>{escaped}</code></{wrapper}>'

        alt = html.escape(latex_source)
        return f'<{wrapper} class="{css_class}"><img src="{data_uri}" alt="{alt}" /></{wrapper}>'

    def _render_to_data_uri(self, latex_source: str) -> str:
        plt = _get_pyplot()

        fig = plt.figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0.0)
        # mathtext requires the whole string to be wrapped in a single pair
        # of `$...$`; this is independent of (and unrelated to) the
        # original Markdown delimiter the source was written with.
        fig.text(0, 0, f"${latex_source}$", fontsize=self._fontsize)

        buffer = io.BytesIO()
        fig.savefig(buffer, format="svg", bbox_inches="tight", pad_inches=0.04, transparent=True)
        plt.close(fig)

        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
