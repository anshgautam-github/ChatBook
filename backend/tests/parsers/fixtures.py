"""Shared test helpers: build synthetic ChatGPT conversation payloads and
wrap them in HTML matching the two known share-page formats.

These are deliberately simplified compared to a real captured page (no
index-reference deduplication in the modern-format wrapper) — the
reference-resolution mechanism itself is tested in isolation in
`test_loader_extraction.py`. What matters here is that `find_conversation_payload`
and `ChatGptHtmlParser` can locate and unwrap the conversation dict
regardless of which wire format it arrived in.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

MODERN_ROUTE_KEY = "routes/share.$shareId.($action)"


def user_message(node_id: str, text: str) -> Dict[str, Any]:
    return {
        "id": f"msg-{node_id}",
        "author": {"role": "user"},
        "content": {"content_type": "text", "parts": [text]},
        "recipient": "all",
    }


def assistant_message(node_id: str, text: str) -> Dict[str, Any]:
    return {
        "id": f"msg-{node_id}",
        "author": {"role": "assistant"},
        "content": {"content_type": "text", "parts": [text]},
        "recipient": "all",
    }


def system_message(node_id: str, text: str = "") -> Dict[str, Any]:
    return {
        "id": f"msg-{node_id}",
        "author": {"role": "system"},
        "content": {"content_type": "text", "parts": [text]},
        "recipient": "all",
    }


def tool_message(node_id: str, text: str) -> Dict[str, Any]:
    return {
        "id": f"msg-{node_id}",
        "author": {"role": "tool"},
        "content": {"content_type": "text", "parts": [text]},
        "recipient": "all",
    }


def tool_addressed_assistant_message(node_id: str, text: str) -> Dict[str, Any]:
    """An assistant message addressed to a tool, not the user (recipient != "all")."""
    return {
        "id": f"msg-{node_id}",
        "author": {"role": "assistant"},
        "content": {"content_type": "text", "parts": [text]},
        "recipient": "python",
    }


def hidden_message(node_id: str, text: str) -> Dict[str, Any]:
    return {
        "id": f"msg-{node_id}",
        "author": {"role": "assistant"},
        "content": {"content_type": "text", "parts": [text]},
        "recipient": "all",
        "metadata": {"is_visually_hidden_from_conversation": True},
    }


def thoughts_message(node_id: str) -> Dict[str, Any]:
    return {
        "id": f"msg-{node_id}",
        "author": {"role": "assistant"},
        "content": {
            "content_type": "thoughts",
            "thoughts": [{"summary": "Planning", "content": "Internal reasoning."}],
        },
        "recipient": "all",
    }


def build_mapping(
    entries: List[Tuple[str, Optional[Dict[str, Any]]]]
) -> Tuple[Dict[str, Any], List[Dict[str, str]], Optional[str]]:
    """Wire up a linear chain of (node_id, message) pairs into a mapping tree.

    Returns `(mapping, linear_conversation, current_node)` ready to drop
    into a conversation payload's `data` dict.
    """
    mapping: Dict[str, Any] = {}
    parent: Optional[str] = None
    for node_id, message in entries:
        mapping[node_id] = {"id": node_id, "parent": parent, "children": [], "message": message}
        if parent is not None:
            mapping[parent]["children"].append(node_id)
        parent = node_id

    linear = [{"id": node_id} for node_id, _ in entries]
    current_node = entries[-1][0] if entries else None
    return mapping, linear, current_node


def build_conversation_data(
    title: str,
    entries: List[Tuple[str, Optional[Dict[str, Any]]]],
    include_linear_conversation: bool = True,
) -> Dict[str, Any]:
    mapping, linear, current_node = build_mapping(entries)
    data: Dict[str, Any] = {
        "title": title,
        "mapping": mapping,
        "current_node": current_node,
        "model": {"slug": "gpt-4o"},
        "update_time": 1700000000.0,
    }
    if include_linear_conversation:
        data["linear_conversation"] = linear
    return data


def build_modern_share_html(
    data: Dict[str, Any],
    share_id: str = "test-share-id",
    route_key: str = MODERN_ROUTE_KEY,
    quoted: bool = True,
) -> str:
    """Wrap `data` in the modern React-Router streaming HTML format.

    `quoted=True` mirrors the real wire format observed on live share pages
    (`enqueue("...")` with a JSON-string argument); `quoted=False` covers
    the simpler bare-array-argument form defensively supported as a
    fallback.
    """
    loader = [
        "ignored-reserved-slot",
        "loaderData",
        {
            route_key: {
                "sharedConversationId": share_id,
                "serverResponse": {"type": "data", "data": data},
            }
        },
    ]
    payload_json = json.dumps(loader)
    argument = json.dumps(payload_json) if quoted else payload_json
    return (
        "<html><body><script>"
        f"window.__reactRouterContext.streamController.enqueue({argument});"
        "</script></body></html>"
    )


def build_legacy_share_html(data: Dict[str, Any]) -> str:
    """Wrap `data` in the legacy Next.js `__NEXT_DATA__` HTML format."""
    next_data = {"props": {"pageProps": {"serverResponse": {"type": "data", "data": data}}}}
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(next_data)}"
        "</script></body></html>"
    )
