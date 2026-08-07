"""Turns a finished HTML document into PDF bytes — nothing else.

This is intentionally the *only* place that imports WeasyPrint or knows
anything about PDF byte generation. Everything about how the document
looks (cover page, table of contents, typography, syntax-highlighting
theme, LaTeX rendering) lives in `HtmlDocumentBuilder` and the Jinja2
template it renders. That split means the visual design can be reworked
— or a whole alternate template swapped in — without touching this class
at all, and this class can be tested/reused against any HTML, not just
documents `HtmlDocumentBuilder` produced.
"""
from __future__ import annotations

from typing import List, Optional

from app.models.conversation import QaSection
from app.pdf.html_renderer import HtmlDocumentBuilder
from app.utils.exceptions import PdfGenerationError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PDFGenerator:
    def __init__(self, html_builder: Optional[HtmlDocumentBuilder] = None) -> None:
        self._html_builder = html_builder or HtmlDocumentBuilder()

    def generate(
        self,
        title: str,
        sections: List[QaSection],
        source_url: Optional[str] = None,
    ) -> bytes:
        """Build the HTML document for `sections` and rasterize it to PDF bytes."""
        html_content = self._html_builder.build(title=title, sections=sections, source_url=source_url)
        return self.render_html_to_pdf(html_content)

    @staticmethod
    def render_html_to_pdf(html_content: str) -> bytes:
        """Pure HTML-string -> PDF-bytes conversion — no document knowledge here.

        NOTE: The WeasyPrint import is deferred into this method (rather
        than module scope) because it pulls in native system libraries
        (Pango, Cairo) that shouldn't be required just to import the rest
        of the app in environments where they aren't installed yet.
        """
        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise PdfGenerationError(
                "WeasyPrint is not installed or its system dependencies are missing"
            ) from exc

        try:
            return HTML(string=html_content).write_pdf()
        except Exception as exc:
            logger.error("PDF rendering failed: %s", exc)
            raise PdfGenerationError(f"Failed to render PDF: {exc}") from exc
