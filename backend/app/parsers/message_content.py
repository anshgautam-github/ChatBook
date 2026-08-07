"""Converts a raw ChatGPT message `content` dict into a Markdown string.

ChatGPT's API represents a message body as `{"content_type": "...", ...}`
with a handful of possible shapes (plain text, legacy plugin code, mixed
text+image, hidden reasoning traces, etc). This module is the single place
that knows about those shapes, so a new `content_type` value only needs a
new branch here.

Crucially, `content_type: "text"` messages already store the *raw Markdown
source* the model produced — Markdown emphasis, fenced code blocks
(```lang ... ```), ordered/unordered lists, pipe tables, and LaTeX
(`\\(...\\)`, `\\[...\\]`, `$$...$$`) are all just plain characters in that
string. As long as we extract `parts` verbatim (no HTML rendering, no
stripping), every one of those constructs survives untouched — which is
exactly why this parser reads the embedded JSON instead of the rendered DOM.
"""
from __future__ import annotations

from typing import Any, List, Mapping, Optional

# Content types that represent visible conversational text/code and should
# be converted to Markdown and kept.
_TEXT_LIKE_CONTENT_TYPES = {"text", "code", "multimodal_text", "tether_quote", "execution_output"}

# Content types that are internal bookkeeping, not part of the visible
# conversation, and should be dropped entirely (never surfaced as a
# Message). Kept as an explicit allowlist-of-exclusions, with reasoning
# spelled out, so it's obvious what a future "include reasoning traces"
# feature would need to change.
_SKIPPED_CONTENT_TYPES = {
    # Hidden chain-of-thought from reasoning models — not shown in the
    # ChatGPT UI transcript itself.
    "thoughts",
    "reasoning_recap",
    # Custom instructions / memory injected into the system turn, not
    # something the user "asked" or the assistant "answered".
    "user_editable_context",
    "model_editable_context",
}


def _extract_text_parts(parts: Any) -> List[str]:
    if not isinstance(parts, list):
        return []
    return [part for part in parts if isinstance(part, str) and part.strip()]


def _render_image_part(part: Mapping[str, Any]) -> str:
    """Render one `image_asset_pointer` part as Markdown, if it's reachable.

    ChatGPT's authenticated app resolves image pointers via a
    `sediment://`-style handle that requires a logged-in API call — not
    something a public, anonymous share-page fetch can do. When the
    pointer is instead already a plain `https://` URL (as some asset
    pointers are), it's preserved as a real Markdown image so it renders
    (and later prints) like any other image; otherwise it degrades to a
    clearly-labeled placeholder instead of silently vanishing.
    """
    asset_pointer = part.get("asset_pointer")
    if isinstance(asset_pointer, str) and asset_pointer.startswith("https://"):
        return f"![Image]({asset_pointer})"
    return "*[img not available]*"


def extract_markdown_from_content(content: Mapping[str, Any]) -> Optional[str]:
    """Return a Markdown string for a message's `content`, or `None` to skip it.

    `None` means "this content type carries no user-visible text" (e.g. a
    hidden reasoning trace) and the caller should drop the message rather
    than emit an empty bubble.
    """
    content_type = content.get("content_type")

    if content_type in _SKIPPED_CONTENT_TYPES:
        return None

    if content_type == "text":
        parts = _extract_text_parts(content.get("parts"))
        return "\n\n".join(part.strip("\n") for part in parts) if parts else None

    if content_type == "code":
        # Legacy plugin/code-interpreter content: re-wrap as a fenced block
        # so the code formatting is preserved when rendered later.
        language = content.get("language")
        lang_tag = language if isinstance(language, str) and language != "unknown" else ""
        text = content.get("text")
        body = text.rstrip("\n") if isinstance(text, str) else ""
        if not body:
            return None
        return f"```{lang_tag}\n{body}\n```"

    if content_type == "execution_output":
        text = content.get("text")
        body = text.strip() if isinstance(text, str) else ""
        if not body:
            return None
        return f"```\n{body}\n```"

    if content_type == "tether_quote":
        text = content.get("text")
        title = content.get("title")
        if not isinstance(text, str) or not text.strip():
            return None
        header = f"> **{title.strip()}**\n" if isinstance(title, str) and title.strip() else ""
        quoted = "\n".join(f"> {line}" for line in text.strip().splitlines())
        return f"{header}{quoted}"

    if content_type == "multimodal_text":
        segments: List[str] = []
        parts = content.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, str):
                    if part.strip():
                        segments.append(part.strip())
                    continue
                if isinstance(part, Mapping):
                    part_type = part.get("content_type") or part.get("type")
                    if part_type == "image_asset_pointer":
                        segments.append(_render_image_part(part))
                    elif part_type == "audio_asset_pointer":
                        # Downloading/transcribing audio is out of scope for
                        # the text parser; leave a clearly-labeled
                        # placeholder rather than silently dropping it.
                        segments.append("*[audio attachment omitted]*")
        return "\n\n".join(segments) if segments else None

    # Unknown/new content type: best-effort fallback rather than silently
    # dropping the message. If it has a `parts` list of strings, treat it
    # like plain text; otherwise skip it and let the caller log that an
    # unrecognized content type was seen (a signal this module needs an
    # update for a new OpenAI content type).
    parts = _extract_text_parts(content.get("parts"))
    if parts:
        return "\n\n".join(parts)

    return None
