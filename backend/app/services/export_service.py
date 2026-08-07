"""Orchestrates the AI-conversation-share-link-to-PDF export workflow.

This is the Service Layer: the one place that coordinates fetching +
parsing (via whichever provider strategy applies), validating a section
selection, and PDF generation. Every API route calls exactly one method
here and does nothing else besides translating between HTTP (request
DTOs, status codes, response bodies) and this service's plain
domain-typed calls.

    API Route -> ExportService -> ParserFactory -> ConversationParser (strategy) -> Response
    API Route -> ExportService -> PDF Generator -> Response

`ExportService` has no fetching, parsing, rendering, or **provider**
logic of its own — it doesn't know ChatGPT, Claude, or Gemini exist.
Picking the right provider strategy for a URL is entirely
`ParserFactory`'s job (app/parsers/factory.py); this service just asks
for a parser and calls `parser.parse(url)`. That's what makes adding a
new provider a change to `app/parsers/` alone — nothing here needs to
change.

The export workflow has two steps because the API (and the extension's
UI built on top of it) does too: a conversation is fetched and parsed
first so the user can choose which sections to keep, and only the chosen
subset is ever turned into a PDF. `fetch_and_parse` and `generate_pdf`
mirror that exactly — nothing here merges them into one call, since that
would change the API's existing two-step contract.
"""
from __future__ import annotations

from typing import List, Optional

from app.models.conversation import Conversation, QaSection
from app.parsers.factory import ParserFactory
from app.pdf.generator import PDFGenerator
from app.utils.exceptions import PdfGenerationError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ExportService:
    """Coordinates `ParserFactory` -> `ConversationParser` strategy -> `PDFGenerator`.

    Constructor injection (both collaborators are optional and default
    to their real implementations) keeps this swappable with fakes in
    tests, matching the pattern already used throughout `app/services/`
    and `app/pdf/`.
    """

    def __init__(
        self,
        parser_factory: Optional[ParserFactory] = None,
        pdf_generator: Optional[PDFGenerator] = None,
    ) -> None:
        self._parser_factory = parser_factory or ParserFactory()
        self._pdf_generator = pdf_generator or PDFGenerator()

    async def fetch_and_parse(self, url: str) -> Conversation:
        """Step 1: turn a share URL into a structured `Conversation`.

        `ParserFactory` picks whichever registered provider strategy
        (`ConversationParser` implementation) claims this URL; that
        strategy owns fetching and parsing for its own provider end to
        end. Either step can raise an `AppError` subclass (invalid URL,
        network failure, unrecognized page structure, unsupported
        provider) — the caller (the `/parse` route) is responsible for
        translating that into an HTTP response; this method just lets it
        propagate.
        """
        logger.info("Fetching conversation from %s", url)
        parser = self._parser_factory.get_parser(url)
        return await parser.parse(url)

    def generate_pdf(
        self,
        title: str,
        sections: List[QaSection],
        source_url: Optional[str] = None,
    ) -> bytes:
        """Step 2: turn a user's section selection into PDF bytes.

        Validates the selection itself before rendering — a real business
        rule ("a PDF needs at least one section"), not an HTTP concern, so
        it belongs here rather than in the route. The `/generate-pdf`
        route additionally enforces this at the request-schema layer
        (`GeneratePdfRequest.selected_sections` has `min_length=1`), so in
        practice this never fires through the API — it's what makes this
        method independently correct for any other caller, HTTP or not.
        """
        self._validate_selection(sections)
        logger.info("Generating PDF for %d section(s)", len(sections))
        return self._pdf_generator.generate(title=title, sections=sections, source_url=source_url)

    @staticmethod
    def _validate_selection(sections: List[QaSection]) -> None:
        if not sections:
            raise PdfGenerationError("No sections selected — choose at least one to generate a PDF.")
