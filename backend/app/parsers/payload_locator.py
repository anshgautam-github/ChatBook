"""Locates the raw ChatGPT conversation payload inside a share page.

This is the layer between `loader_extraction.py` (generic "get me the JSON
that's embedded in this HTML") and `conversation_builder.py` (generic "turn
this conversation JSON into our domain model"). It knows the *specific*
nesting ChatGPT currently uses (which route key holds the conversation,
which legacy key holds it, etc.) but falls back to a structural search so a
route rename alone doesn't break the whole pipeline.

A "conversation payload" is a dict that looks like OpenAI's internal
`ApiConversation` shape: at minimum a `mapping` dict of node-id -> node.
"""
from __future__ import annotations

from typing import Any, Optional

from app.parsers.loader_extraction import (
    extract_next_data,
    extract_react_router_loader,
    resolve_loader_references,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# The current React Router route name for a share page. If OpenAI renames
# this route, `_search_for_conversation_payload` below still finds the data
# structurally, so nothing breaks — this constant is just a fast path.
_MODERN_SHARE_ROUTE_KEY = "routes/share.$shareId.($action)"


def _looks_like_conversation_payload(value: Any) -> bool:
    """Heuristic: does this dict look like OpenAI's conversation JSON?

    Used both as a fast-path shape check and as the predicate for the
    structural fallback search, so it's the single place that encodes
    "what does a conversation dict look like".
    """
    if not isinstance(value, dict):
        return False
    mapping = value.get("mapping")
    return isinstance(mapping, dict) and len(mapping) > 0


def _search_for_conversation_payload(node: Any, _depth: int = 0) -> Optional[dict]:
    """Recursively scan decoded JSON for the first dict that looks like a conversation.

    This is the resilience net: if OpenAI renames the route key or nests
    `serverResponse.data` differently, this still finds the payload as long
    as the conversation's own shape (a `mapping` dict of nodes) is
    unchanged. Depth is capped to avoid runaway recursion on pathological
    input.
    """
    if _depth > 12:
        return None

    if _looks_like_conversation_payload(node):
        return node

    if isinstance(node, dict):
        for value in node.values():
            found = _search_for_conversation_payload(value, _depth + 1)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _search_for_conversation_payload(item, _depth + 1)
            if found is not None:
                return found

    return None


def _from_modern_share(html: str) -> Optional[dict]:
    loader = extract_react_router_loader(html)
    if loader is None:
        return None

    try:
        decoded = resolve_loader_references(loader)
    except (RecursionError, ValueError) as exc:
        logger.warning("Failed to resolve React Router loader references: %s", exc)
        return None

    loader_data = decoded.get("loaderData")
    if isinstance(loader_data, dict):
        route = loader_data.get(_MODERN_SHARE_ROUTE_KEY)
        if isinstance(route, dict):
            server_response = route.get("serverResponse")
            if isinstance(server_response, dict):
                data = server_response.get("data")
                if _looks_like_conversation_payload(data):
                    return data

    # Route key changed or nesting shifted — fall back to a structural search
    # over the whole decoded loader payload.
    return _search_for_conversation_payload(decoded)


def _from_legacy_share(html: str) -> Optional[dict]:
    next_data = extract_next_data(html)
    if next_data is None:
        return None

    props = next_data.get("props")
    if isinstance(props, dict):
        page_props = props.get("pageProps")
        if isinstance(page_props, dict):
            server_response = page_props.get("serverResponse")
            if isinstance(server_response, dict):
                data = server_response.get("data")
                if _looks_like_conversation_payload(data):
                    return data

    return _search_for_conversation_payload(next_data)


def find_conversation_payload(html: str) -> Optional[dict]:
    """Best-effort extraction of the raw conversation dict from a share page.

    Tries, in order: the modern React Router streaming format, then the
    legacy Next.js `__NEXT_DATA__` format. Returns `None` if neither yields
    a recognizable conversation payload (the caller should treat this as
    "the page structure isn't recognized" — most likely OpenAI shipped a
    change that this module needs to learn about).
    """
    payload = _from_modern_share(html)
    if payload is not None:
        return payload

    payload = _from_legacy_share(html)
    if payload is not None:
        return payload

    logger.warning("Could not locate a conversation payload in the share page HTML")
    return None
