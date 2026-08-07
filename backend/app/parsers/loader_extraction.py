"""Low-level extraction of embedded conversation JSON from a ChatGPT share page.

ChatGPT's frontend has shipped (at least) two different ways of embedding
page data into the initial server-rendered HTML:

1. **Modern (`chatgpt.com`, React Router / "Remix" style streaming SSR).**
   The page ships a `<script>` tag that calls
   ``window.__reactRouterContext.streamController.enqueue(...)`` one or more
   times. The argument is either a JSON-encoded string containing a JSON
   array, or (less commonly observed) the array literal directly. That array
   is a flattened, deduplicated object graph: string/number/bool values are
   inline, but any bare integer found as a value is a *reference* — "resolve
   this by looking up `loader[value]` and decoding that instead". This is
   the same reference-graph trick used by React Flight/RSC payloads and by
   React Router's "turbo-stream" loader data format.

2. **Legacy (`chat.openai.com`, Next.js).** A single
   `<script id="__NEXT_DATA__" type="application/json">` tag contains a
   plain JSON document under `props.pageProps`.

This module ONLY knows how to pull raw, decoded JSON *values* out of HTML —
it has no opinion about what a "conversation" looks like. That knowledge
lives in `payload_locator.py` and `conversation_builder.py`. Keeping the
"where does OpenAI hide the data" logic isolated here (and the "what shape
is a conversation" logic isolated elsewhere) is what lets a future HTML
change be fixed by editing this one file.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Optional

from bs4 import BeautifulSoup

from app.utils.logger import get_logger

logger = get_logger(__name__)

_ENQUEUE_CALL = "streamController.enqueue("
_NEXT_DATA_SCRIPT_ID = "__NEXT_DATA__"


def _iter_script_contents(html: str) -> List[str]:
    """Return the text content of every `<script>` tag in `html`."""
    soup = BeautifulSoup(html, "lxml")
    return [script.string or script.get_text() for script in soup.find_all("script")]


def _iter_next_data_scripts(html: str) -> List[str]:
    """Return the text content of every `<script id="__NEXT_DATA__">` tag."""
    soup = BeautifulSoup(html, "lxml")
    return [
        script.string or script.get_text()
        for script in soup.find_all("script", id=_NEXT_DATA_SCRIPT_ID)
    ]


def _extract_enqueue_argument(text: str, call_start: int) -> Optional[Any]:
    """Decode the single argument passed to one `streamController.enqueue(...)` call.

    `call_start` is the index right after the opening `(`. The argument is
    either a JSON string literal (whose decoded *text* is itself JSON we
    need to parse again) or a bare JSON array/object literal.
    """
    # Skip a leading "(" some bundlers add around the argument, e.g. `enqueue((...))`.
    cursor = call_start
    while cursor < len(text) and text[cursor] in " \t\n(":
        cursor += 1

    if cursor >= len(text):
        return None

    decoder = json.JSONDecoder()
    try:
        value, _end = decoder.raw_decode(text, cursor)
    except json.JSONDecodeError:
        return None

    # If the argument was itself a JSON string, its *contents* are usually a
    # second layer of JSON (the actual payload). Try to decode that too; if
    # it doesn't parse, fall back to the raw string (matches bare-array
    # calls where `value` is already the payload).
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    return value


def extract_react_router_loader(html: str) -> Optional[List[Any]]:
    """Find and decode the first React Router streaming loader payload.

    Returns the flattened reference array (still needs
    `resolve_loader_references`) or `None` if no script contained a
    recognizable `streamController.enqueue([...])` call.
    """
    for script_text in _iter_script_contents(html):
        if not script_text or _ENQUEUE_CALL not in script_text:
            continue

        search_from = 0
        while True:
            anchor = script_text.find(_ENQUEUE_CALL, search_from)
            if anchor == -1:
                break

            call_start = anchor + len(_ENQUEUE_CALL)
            payload = _extract_enqueue_argument(script_text, call_start)
            search_from = call_start + 1

            if isinstance(payload, list):
                return payload
            # Not a list (e.g. a status string chunk) — keep scanning for
            # another `enqueue(` call in the same script.

    return None


def resolve_loader_references(loader: List[Any]) -> dict:
    """Resolve a flattened React Router loader array into nested dict/list data.

    The array is `[reserved, key_1, value_1, key_2, value_2, ...]`. Each
    `value` may itself be:
      - an `int` — a reference to `loader[int]`, resolved recursively
      - a `dict` — whose own values may contain further references, and
        whose keys of the form `"_<N>"` mean "the real key name is the
        string stored at `loader[N]`" (another dedup trick)
      - a `list` — whose items may contain further references
      - anything else — a literal, returned as-is

    A small cache prevents re-resolving (or infinitely recursing through)
    the same index twice.
    """
    cache: dict = {}

    def decode_key(raw_key: Any) -> str:
        if isinstance(raw_key, str) and raw_key.startswith("_") and raw_key[1:].isdigit():
            index = int(raw_key[1:])
            if 0 <= index < len(loader) and isinstance(loader[index], str):
                return loader[index]
        return str(raw_key)

    def resolve(value: Any) -> Any:
        if isinstance(value, bool):
            return value  # bool is a subclass of int — never treat it as an index
        if isinstance(value, int):
            if value in cache:
                return cache[value]
            if not (0 <= value < len(loader)):
                return value
            cache[value] = None  # break potential reference cycles
            resolved = resolve(loader[value])
            cache[value] = resolved
            return resolved
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            return {decode_key(k): resolve(v) for k, v in value.items()}
        return value

    resolved: dict = {}
    pairs = iter(loader[1:])
    for key in pairs:
        try:
            value = next(pairs)
        except StopIteration:
            break
        if isinstance(key, str) and key not in resolved:
            resolved[key] = resolve(value)
    return resolved


_JSON_LOOKS_LIKE_OBJECT = re.compile(r"^\s*[\{\[]")


def extract_next_data(html: str) -> Optional[dict]:
    """Find and parse a legacy Next.js `__NEXT_DATA__` script tag, if present."""
    for script_text in _iter_next_data_scripts(html):
        if not script_text or not _JSON_LOOKS_LIKE_OBJECT.match(script_text):
            continue
        try:
            parsed = json.loads(script_text)
        except json.JSONDecodeError as exc:
            logger.warning("Found __NEXT_DATA__ script but it was not valid JSON: %s", exc)
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
