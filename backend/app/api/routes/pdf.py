"""POST /generate-pdf — render selected sections into a downloadable PDF.

This route only handles HTTP concerns: binding the request body,
delegating to `ExportFacade` (see app/facades/export_facade.py — the
pipeline's single entry point, which itself forwards to `ExportService`),
translating a domain-level failure into the right HTTP status code, and
building the binary PDF response. It has no business logic of its own.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.api.deps import get_export_facade
from app.facades.export_facade import ExportFacade
from app.models.conversation import Message, MessageRole, QaSection
from app.schemas.conversation import MessageDTO
from app.schemas.pdf import GeneratePdfRequest
from app.utils.exceptions import AppError
from app.utils.rate_limiter import limiter, rate_limit_value

router = APIRouter(tags=["pdf"])


def _to_domain_message(dto: Optional[MessageDTO]) -> Optional[Message]:
    if dto is None:
        return None
    return Message(id=dto.id, role=MessageRole(dto.role), content=dto.content, order=dto.order)


@router.post("/generate-pdf")
@limiter.limit(rate_limit_value)
async def generate_pdf(
    # Renamed from `request` to `payload` — see the same rename in
    # parse.py for why: slowapi's `@limiter.limit` needs an actual
    # Starlette `Request` in the signature named `request`, which used to
    # collide with this parameter's name. FastAPI binds a body parameter
    # by its Pydantic-model type, not by name, so nothing about the wire
    # format changes.
    request: Request,
    payload: GeneratePdfRequest,
    export_facade: ExportFacade = Depends(get_export_facade),
) -> Response:
    # Belt-and-suspenders with `GeneratePdfRequest.selected_sections`'
    # `min_length=1` (see app/schemas/pdf.py): that already rejects an
    # empty list at the request-schema layer with a 422 before this route
    # body ever runs, so this line is unreachable through the API today.
    # It stays as an explicit HTTP-layer guard anyway — `ExportService`
    # enforces the same rule again internally (see its docstring), but
    # that's a domain rule for its own correctness independent of HTTP,
    # not a substitute for this route's own contract.
    if not payload.selected_sections:
        raise HTTPException(status_code=400, detail="No sections selected")

    domain_sections = [
        QaSection(
            id=section.id,
            section_index=section.section_index,
            question=_to_domain_message(section.question),
            answer=_to_domain_message(section.answer),
        )
        for section in payload.selected_sections
    ]

    try:
        pdf_bytes = export_facade.generate_pdf(
            title=payload.title or "Study Notes",
            sections=domain_sections,
            source_url=payload.source_url,
        )
    except AppError as exc:
        raise HTTPException(status_code=500, detail=exc.message) from exc

    # A plain `Response` (not `StreamingResponse`) on purpose: `pdf_bytes` is
    # already a complete, fully-buffered byte string — there's nothing left
    # to stream. Returning it this way lets Starlette set a real
    # `Content-Length` header instead of `Transfer-Encoding: chunked`, which
    # matters in practice: some browsers (Safari in particular) can hang
    # indefinitely on `response.blob()` for a chunked response with no
    # `Content-Length`, even though the bytes already fully arrived.
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=study-notes.pdf"},
    )
