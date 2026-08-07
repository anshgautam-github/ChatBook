"""Builds the complete, styled HTML document that gets rasterized to PDF.

This is deliberately the *only* place that assembles the document: cover
page metadata, table-of-contents entries, section numbering/anchors, and
which Jinja2 template file to use. `generator.py` (PDF generation) never
touches any of this — it only knows how to turn a finished HTML string
into PDF bytes. That split is what lets the look of the document (or the
whole template) change without touching PDF-conversion code at all.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.conversation import Message, QaSection
from app.pdf.html_sanitizer import sanitize_html_fragment
from app.pdf.latex_renderer import LatexRenderer
from app.pdf.markdown_renderer import MarkdownRenderer
from app.pdf.syntax_highlighting import get_pygments_css

TEMPLATES_DIR = Path(__file__).parent / "templates"

_DEFAULT_TEMPLATE_NAME = "base_template.html"

# Maps the recognized leading keyword in a Markdown blockquote to which
# callout color/label variant it should render as. Several words map to
# the same variant (e.g. "Caution"/"Important" both read as a warning)
# so writers aren't locked into one exact phrase.
_CALLOUT_KEYWORDS = {
    "note": "note",
    "tip": "tip",
    "hint": "tip",
    "warning": "warning",
    "caution": "warning",
    "important": "warning",
}
_CALLOUT_LABEL_PATTERN = re.compile(
    r"^\s*(note|tip|hint|warning|caution|important)\b\s*[:\-–—]?\s*",
    re.IGNORECASE,
)


def _apply_callout_styling(html_fragment: str) -> str:
    """Turn Markdown blockquotes into highlighted "callout" boxes.

    Every `> ...` blockquote gets a neutral highlighted-quote treatment
    by default (styled entirely in CSS via the `.callout` classes — see
    the template). If its very first words are a recognizable label like
    "Note:", "Tip:", or "Warning:", that keyword is promoted into a small
    colored badge above the box and stripped from the body text (so it
    isn't shown twice) — the same convention technical books use for
    asides, instead of just quoting the model verbatim.
    """
    if "<blockquote" not in html_fragment:
        return html_fragment

    soup = BeautifulSoup(html_fragment, "html.parser")
    for blockquote in soup.find_all("blockquote"):
        blockquote["class"] = ["callout", "callout--quote"]

        # `find(string=True)` would happily match the whitespace-only
        # NavigableString between `<blockquote>` and its first `<p>` (python-
        # markdown pretty-prints block tags onto their own lines) — skip
        # past any purely-whitespace text nodes to the real content.
        first_text_node = next(
            (node for node in blockquote.find_all(string=True) if node.strip()), None
        )
        if first_text_node is None:
            continue

        match = _CALLOUT_LABEL_PATTERN.match(str(first_text_node))
        if not match:
            continue

        callout_type = _CALLOUT_KEYWORDS.get(match.group(1).lower())
        if callout_type is None:
            continue

        blockquote["class"] = ["callout", f"callout--{callout_type}"]
        first_text_node.replace_with(str(first_text_node)[match.end():])

        label = soup.new_tag("p")
        label["class"] = "callout-label"
        # Preserve whichever word the writer actually used (e.g. "Caution"
        # vs "Warning") rather than always normalizing to one spelling.
        label.string = match.group(1).capitalize()
        blockquote.insert(0, label)

    return str(soup)


class HtmlDocumentBuilder:
    """Turns `(title, sections)` into a single, self-contained HTML document.

    "Self-contained" matters for WeasyPrint: all CSS (including the
    Pygments syntax-highlighting theme) and all images (LaTeX renders as
    base64 data URIs) are embedded directly in the returned string, so the
    document never depends on relative file paths or a running server.
    """

    def __init__(
        self,
        markdown_renderer: Optional[MarkdownRenderer] = None,
        latex_renderer: Optional[LatexRenderer] = None,
        template_name: str = _DEFAULT_TEMPLATE_NAME,
    ) -> None:
        self._markdown_renderer = markdown_renderer or MarkdownRenderer()
        self._latex_renderer = latex_renderer or LatexRenderer()
        self._template_name = template_name
        self._env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def build(
        self,
        title: str,
        sections: List[QaSection],
        source_url: Optional[str] = None,
    ) -> str:
        template = self._env.get_template(self._template_name)

        rendered_sections = [
            self._render_section(position, section)
            for position, section in enumerate(sections, start=1)
        ]
        toc_entries = [
            {"anchor": item["anchor"], "index": item["index"], "title": item["toc_title"]}
            for item in rendered_sections
        ]

        return template.render(
            title=title or "Study Notes",
            generated_at=datetime.now().strftime("%B %d, %Y"),
            source_url=source_url,
            section_count=len(sections),
            sections=rendered_sections,
            toc_entries=toc_entries,
            pygments_css=get_pygments_css(),
        )

    def _render_section(self, position: int, section: QaSection) -> Dict[str, Any]:
        question_html = self._render_message(
            section.question, placeholder="No question — conversation opener"
        )
        answer_html = self._render_message(section.answer, placeholder="Awaiting a response")

        return {
            "index": position,
            "anchor": f"section-{position}",
            "question_html": question_html,
            "answer_html": answer_html,
            # Deliberately not derived from the question's content: a
            # short, predictable "Prompt N" label is what actually reads
            # well both in the TOC and as a chapter heading. A
            # content-derived title looked smart for plain-text questions,
            # but degraded badly whenever the question was mostly/only an
            # (inaccessible) image — the placeholder text itself ended up
            # as the heading.
            "toc_title": f"Prompt {position}",
        }

    def _render_message(self, message: Optional[Message], placeholder: str) -> str:
        if message is None:
            return f'<p class="placeholder">{placeholder}</p>'

        # LaTeX is pulled out and rendered to images *before* Markdown
        # conversion, then spliced back into the resulting HTML — see
        # `LatexRenderer` for why the ordering matters.
        protected_text, latex_replacements = self._latex_renderer.extract(message.content)
        html_fragment = self._markdown_renderer.render(protected_text)
        # Sanitize before restoring LaTeX images: `html_fragment` at this
        # point is entirely derived from conversation content this app
        # doesn't trust (see html_sanitizer.py for why), while the LaTeX
        # images restored next are always our own backend-generated
        # markup — sanitizing after restoring them would risk touching
        # trusted output instead of only the untrusted part.
        html_fragment = sanitize_html_fragment(html_fragment)
        html_fragment = self._latex_renderer.restore(html_fragment, latex_replacements)
        html_fragment = _apply_callout_styling(html_fragment)
        return html_fragment
