"""API request/response DTOs for conversation parsing.

Kept separate from `models/` so changes to the wire format (versioning,
renamed fields, etc.) never require touching internal domain logic.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ParseConversationRequest(BaseModel):
    url: HttpUrl = Field(..., description="A public ChatGPT shared conversation URL")


class MessageDTO(BaseModel):
    id: str
    role: str
    # Bounded well above any realistic single-message length (ChatGPT
    # itself caps a single response far below this) so a client calling
    # /generate-pdf directly — bypassing /parse entirely, which this
    # endpoint has no way to detect — can't hand the PDF/LaTeX renderers
    # an arbitrarily large string per message as a cheap resource-exhaustion
    # lever.
    content: str = Field(..., max_length=200_000)
    order: int


class QaSectionDTO(BaseModel):
    id: str
    section_index: int
    # Optional because a real conversation can end on an unanswered question,
    # or (rarely) start with an assistant message before any user turn.
    question: Optional[MessageDTO] = None
    answer: Optional[MessageDTO] = None


class ParseConversationResponse(BaseModel):
    title: str
    source_url: str
    # The complete, ordered list of every extracted user/assistant message —
    # the authoritative source of truth. `sections` is a derived, best-effort
    # Q&A pairing of the same messages for the section-picker UI.
    messages: List[MessageDTO]
    sections: List[QaSectionDTO]
