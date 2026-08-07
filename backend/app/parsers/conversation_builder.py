"""Builds the `Conversation` domain model from a raw ChatGPT conversation payload.

The payload shape mirrors OpenAI's internal `ApiConversation`: a `mapping`
of node id -> `{id, message, parent, children}` forming a tree (edits and
regenerations create branches), plus either a `linear_conversation` list
that already picks one path through the tree, or a `current_node` pointer
that lets us walk `parent` links back to the root ourselves.

This module knows the *shape* of a conversation but not how it got out of
the HTML (that's `payload_locator.py`) and not how an individual message's
`content` becomes Markdown (that's `message_content.py`).
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional

from app.models.conversation import Conversation, Message, MessageRole, QaSection
from app.parsers.message_content import extract_markdown_from_content
from app.utils.logger import get_logger

logger = get_logger(__name__)

_VISIBLE_ROLES = {"user", "assistant"}


def _ordered_node_ids(data: Mapping[str, Any]) -> List[str]:
    """Return conversation node ids in display order.

    Prefers `linear_conversation` (an already-ordered list OpenAI includes
    on share pages) and falls back to walking `mapping` parent links from
    `current_node` — the same technique the ChatGPT web app itself uses to
    resolve the active branch of a conversation that has edits/regens.
    """
    linear = data.get("linear_conversation")
    if isinstance(linear, list) and linear:
        ids = [entry.get("id") for entry in linear if isinstance(entry, Mapping)]
        resolved = [node_id for node_id in ids if isinstance(node_id, str)]
        if resolved:
            return resolved

    mapping = data.get("mapping")
    if not isinstance(mapping, dict):
        return []

    current_node = data.get("current_node")
    start_id = current_node if isinstance(current_node, str) and current_node in mapping else None

    if start_id is None:
        # No explicit current_node: fall back to any leaf (a node with no children).
        leaf_candidates = [
            node_id
            for node_id, node in mapping.items()
            if isinstance(node, Mapping) and not node.get("children")
        ]
        start_id = leaf_candidates[0] if leaf_candidates else None

    if start_id is None:
        return []

    ordered: List[str] = []
    visited: set = set()
    current: Optional[str] = start_id
    while current is not None and current not in visited:
        visited.add(current)
        ordered.append(current)
        node = mapping.get(current)
        current = node.get("parent") if isinstance(node, Mapping) else None

    ordered.reverse()
    return ordered


def _should_include_message(message: Mapping[str, Any]) -> bool:
    """Filter out anything that isn't part of the visible user<->assistant transcript."""
    author = message.get("author")
    role = author.get("role") if isinstance(author, Mapping) else None
    if role not in _VISIBLE_ROLES:
        return False

    metadata = message.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("is_visually_hidden_from_conversation"):
        return False

    # A message addressed to a tool (recipient != "all") is the assistant
    # "thinking out loud" to a plugin/browser/code tool, not a reply to the
    # user, so it's excluded from the visible transcript.
    recipient = message.get("recipient")
    if isinstance(recipient, str) and recipient not in ("all", ""):
        return False

    return True


def _extract_ordered_messages(data: Mapping[str, Any]) -> List[Message]:
    mapping = data.get("mapping")
    if not isinstance(mapping, dict):
        return []

    messages: List[Message] = []
    for node_id in _ordered_node_ids(data):
        node = mapping.get(node_id)
        if not isinstance(node, Mapping):
            continue

        raw_message = node.get("message")
        if not isinstance(raw_message, Mapping) or not _should_include_message(raw_message):
            continue

        content = raw_message.get("content")
        if not isinstance(content, Mapping):
            continue

        markdown = extract_markdown_from_content(content)
        if markdown is None:
            continue

        author = raw_message.get("author") or {}
        role_value = author.get("role") if isinstance(author, Mapping) else None
        try:
            role = MessageRole(role_value)
        except ValueError:
            logger.warning("Skipping message with unrecognized author role: %r", role_value)
            continue

        message_id = raw_message.get("id") or node_id
        messages.append(
            Message(id=str(message_id), role=role, content=markdown, order=len(messages))
        )

    return messages


def _merge_run(run: List[Message]) -> Message:
    """Collapse a run of consecutive same-role messages into one Message.

    A single assistant turn is occasionally split across multiple mapping
    nodes (e.g. a continued/regenerated response). Merging keeps each
    section reading as one coherent turn instead of several fragments.
    """
    if len(run) == 1:
        return run[0]
    combined = "\n\n".join(message.content for message in run)
    first = run[0]
    return Message(id=first.id, role=first.role, content=combined, order=first.order)


def _group_into_sections(messages: List[Message]) -> List[QaSection]:
    """Pair adjacent user/assistant runs into Q&A sections.

    A leading assistant-only run (rare — e.g. a custom GPT's scripted
    opener) becomes a section with `question=None`; a trailing user message
    with no reply yet becomes a section with `answer=None`. Both are
    modeled explicitly rather than dropped or fabricated, so real content
    never silently disappears.
    """
    sections: List[QaSection] = []
    index = 0
    pending_question: Optional[Message] = None

    position = 0
    while position < len(messages):
        role = messages[position].role
        run = [messages[position]]
        position += 1
        while position < len(messages) and messages[position].role == role:
            run.append(messages[position])
            position += 1
        merged = _merge_run(run)

        if merged.role == MessageRole.USER:
            if pending_question is not None:
                # Two user turns in a row with no assistant reply between them.
                sections.append(
                    QaSection(id=f"section-{index}", section_index=index, question=pending_question)
                )
                index += 1
            pending_question = merged
        else:
            sections.append(
                QaSection(
                    id=f"section-{index}",
                    section_index=index,
                    question=pending_question,
                    answer=merged,
                )
            )
            index += 1
            pending_question = None

    if pending_question is not None:
        sections.append(QaSection(id=f"section-{index}", section_index=index, question=pending_question))

    return sections


def build_conversation(data: Mapping[str, Any], source_url: str) -> Conversation:
    """Turn a raw ChatGPT conversation payload into our domain `Conversation`."""
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "Untitled Conversation"

    messages = _extract_ordered_messages(data)
    sections = _group_into_sections(messages)

    return Conversation(
        title=title.strip(),
        source_url=source_url,
        messages=messages,
        sections=sections,
    )
