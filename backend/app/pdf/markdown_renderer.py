"""Renders Markdown-flavored message content into styled HTML fragments.

Kept separate from `PDFGenerator` so the same rendering logic can later be
reused for EPUB export or an in-app rich-text preview.

Uses python-markdown (rather than markdown2) specifically for its
`codehilite` extension, which wraps fenced code blocks with Pygments-
generated syntax highlighting — the matching stylesheet is produced by
`syntax_highlighting.get_pygments_css()` and embedded once per document.
"""
import markdown

_EXTENSIONS = ["extra", "codehilite", "sane_lists", "nl2br"]
_EXTENSION_CONFIGS = {
    "codehilite": {
        "css_class": "codehilite",
        # Never guess a language for unlabeled fences — a wrong guess would
        # highlight plain text with misleading colors. ChatGPT almost
        # always labels its fences (```python, ```bash, ...) anyway.
        "guess_lang": False,
    },
}


class MarkdownRenderer:
    """Converts one message's Markdown content into an HTML fragment.

    A fresh `markdown.Markdown` instance is created per call: python-
    markdown instances accumulate internal state (footnote counters,
    reference definitions, etc.) across `.convert()` calls, and each
    message must render independently of any other section in the PDF.
    """

    def render(self, markdown_text: str) -> str:
        renderer = markdown.Markdown(extensions=_EXTENSIONS, extension_configs=_EXTENSION_CONFIGS)
        return renderer.convert(markdown_text)
