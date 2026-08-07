"""POST /parse — fetch and parse a ChatGPT shared conversation.

This route only handles HTTP concerns: binding the request body,
delegating the actual work to `ExportFacade` (see
app/facades/export_facade.py — the pipeline's single entry point, which
itself forwards to `ExportService`), translating a domain-level failure
into the right HTTP status code, and shaping the domain result into this
endpoint's response DTO. It has no business logic of its own.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_export_facade
from app.facades.export_facade import ExportFacade
from app.models.conversation import Message
from app.schemas.conversation import (
    MessageDTO,
    ParseConversationRequest,
    ParseConversationResponse,
    QaSectionDTO,
)
from app.utils.exceptions import AppError
from app.utils.rate_limiter import limiter, rate_limit_value

router = APIRouter(tags=["conversation"])


def _to_message_dto(message: Optional[Message]) -> Optional[MessageDTO]:
    if message is None:
        return None
    return MessageDTO(
        id=message.id,
        role=message.role.value,
        content=message.content,
        order=message.order,
    )


@router.post("/parse", response_model=ParseConversationResponse)
@limiter.limit(rate_limit_value)
async def parse_conversation(
    # Renamed from `request` to `payload`: slowapi's `@limiter.limit`
    # decorator needs an actual Starlette `Request` object present in the
    # endpoint's signature (by convention, a parameter literally named
    # `request` and typed `Request`) to read the client's IP from — this
    # parameter used to occupy that name for the request *body* instead,
    # which would have collided with it. FastAPI binds a body parameter
    # by its Pydantic-model type annotation, not by name, so this rename
    # is purely internal and doesn't change the wire format at all.
    request: Request,
    payload: ParseConversationRequest,
    export_facade: ExportFacade = Depends(get_export_facade),
) -> ParseConversationResponse:
    try:
        conversation = await export_facade.fetch_and_parse(str(payload.url))
    except AppError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc

    return ParseConversationResponse(
        title=conversation.title,
        source_url=conversation.source_url,
        messages=[_to_message_dto(message) for message in conversation.messages],
        sections=[
            QaSectionDTO(
                id=section.id,
                section_index=section.section_index,
                question=_to_message_dto(section.question),
                answer=_to_message_dto(section.answer),
            )
            for section in conversation.sections
        ],
    )
