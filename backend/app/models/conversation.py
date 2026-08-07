"""Domain models representing a parsed conversation.

These are internal representations used by services and parsers. They are
intentionally decoupled from `schemas/` (API DTOs) so the API contract can
evolve independently of internal processing logic.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    """A single message within a conversation."""

    id: str
    role: MessageRole
    content: str
    order: int


@dataclass
class QaSection:
    """A question/answer pair extracted from the conversation.

    Grouping messages into Q&A sections (rather than just the flat message
    list) is what allows the frontend to offer per-section selection. Both
    `question` and `answer` are optional because real conversations aren't
    always tidy pairs: a conversation can end on an unanswered user message,
    or (rarely, e.g. a custom GPT's scripted opener) start with an
    assistant message before any user turn. Modeling that explicitly means
    no real message is ever silently dropped or fabricated just to keep the
    pair shape.
    """

    id: str
    section_index: int
    question: Optional[Message] = None
    answer: Optional[Message] = None


@dataclass
class Conversation:
    """Fully parsed representation of a shared ChatGPT conversation."""

    title: str
    source_url: str
    messages: List[Message] = field(default_factory=list)
    sections: List[QaSection] = field(default_factory=list)
    fetched_at: Optional[datetime] = None
