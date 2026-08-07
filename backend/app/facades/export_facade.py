"""ExportFacade — the single entry point into the export pipeline.

API routes only ever call `ExportFacade`. Everything the export pipeline
actually does — validating URLs, fetching a conversation, picking the
right provider parser, normalizing it into domain messages/sections, and
rendering a PDF — already lives behind `ExportService`
(app/services/export_service.py), which coordinates `ParserFactory` ->
`ConversationParser` -> `PDFGenerator`. `ExportFacade` does not re-decide
any of that; it exists purely so that a route's only dependency is one
small, stable class, instead of reaching past it into the business layer.

    API Route -> ExportFacade -> ExportService -> ParserFactory -> ConversationParser
    API Route -> ExportFacade -> ExportService -> PDF Generator

Two methods, not one `export(...)`, on purpose: the API itself is a
deliberate two-step contract (POST /parse to fetch + parse and let the
user choose sections, then POST /generate-pdf to render only the chosen
subset — see `ExportService`'s own docstring for why that split exists).
Collapsing both steps into a single facade call would change that
contract and the frontend's section-selection flow, which this refactor
must not do. `ExportFacade` mirrors the same two steps `ExportService`
already exposes; it does not fuse or reinterpret them.
"""
from __future__ import annotations

from typing import List, Optional

from app.models.conversation import Conversation, QaSection
from app.services.export_service import ExportService


class ExportFacade:
    """Orchestrates by delegating, nothing else.

    Every method here is a one-line forward to the equivalent
    `ExportService` method — no validation, branching, or transformation
    of its own. That's deliberate: this class's only responsibility is
    being *the* thing routes call, not deciding *how* the export pipeline
    works. `ExportService` continues to own that.

    Constructor injection (the collaborator is optional and defaults to
    the real `ExportService`) matches the pattern already used throughout
    `app/services/`, `app/parsers/`, and `app/pdf/` — real wiring is just
    the default, so tests can substitute a fake `ExportService` instead.
    """

    def __init__(self, export_service: Optional[ExportService] = None) -> None:
        self._export_service = export_service or ExportService()

    async def fetch_and_parse(self, url: str) -> Conversation:
        """Step 1 of the export pipeline: fetch + parse a share URL.

        Pure delegation to `ExportService.fetch_and_parse` — any `AppError`
        it raises (invalid URL, fetch failure, unrecognized page, unsupported
        provider) propagates unchanged; translating that into an HTTP
        response is the calling route's job, not this facade's.
        """
        return await self._export_service.fetch_and_parse(url)

    def generate_pdf(
        self,
        title: str,
        sections: List[QaSection],
        source_url: Optional[str] = None,
    ) -> bytes:
        """Step 2 of the export pipeline: render a section selection to PDF.

        Pure delegation to `ExportService.generate_pdf` — including its
        "at least one section" validation, which stays a business rule
        owned by the service, not duplicated here.
        """
        return self._export_service.generate_pdf(title=title, sections=sections, source_url=source_url)
