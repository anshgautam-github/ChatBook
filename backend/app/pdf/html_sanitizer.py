"""Sanitizes HTML fragments derived from untrusted conversation content.

`MarkdownRenderer` converts a ChatGPT message's raw Markdown to HTML, and
Markdown intentionally passes raw inline HTML through unchanged — that's
standard Markdown behavior, not a bug. But a share link's conversation
content is not something this app controls or trusts: anyone can share
any conversation, and a model's own text output can itself contain
HTML-looking snippets (e.g. a coding answer that shows `<script>` or
`<img onerror=...>` as an example, not fenced as code). Without
sanitizing that output before it's marked `| safe` in the PDF template,
such a snippet would be rasterized as *live* markup rather than shown as
the inert example text it's almost always meant to be.

WeasyPrint never executes JavaScript, so this isn't a classic
browser-side XSS risk — but it does fetch remote resources referenced in
`src`/`href`/CSS `url()`/`<link>`, which makes unsanitized HTML a
server-side request-forgery vector: the backend itself would fetch
whatever URL is embedded in someone else's shared conversation.

This uses a blocklist (only the specific tags/attributes that are
actually dangerous — script execution, resource-fetching, event
handlers) rather than an allowlist of every tag Markdown might ever
legitimately emit (tables, definition lists, footnotes, abbreviations,
Pygments' syntax-highlighting spans, ...). An allowlist narrow enough to
be "safe" would also be narrow enough to break some of those normal,
already-shipped rendering features; a blocklist targeting only the
genuinely risky surface leaves everything else untouched.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from bs4 import BeautifulSoup

# Tags with no legitimate purpose in this document — Markdown's own
# output never produces any of these. Removed together with their
# contents (not just unwrapped): there's no reason to surface a script's
# source code or a stylesheet's rules as plain text either.
_DROP_WITH_CONTENTS = {
    "script", "style", "iframe", "object", "embed", "link", "meta",
    "form", "input", "button", "base", "applet", "frame", "frameset",
    "video", "audio", "source", "noscript",
}

# Attributes whose *value* is a URL WeasyPrint might resolve/fetch.
_URL_ATTRS = {"href", "src"}

# `""` covers relative/fragment references (`#fn:1`, internal footnote
# anchors) which carry no scheme to abuse. `data:` is included because
# LatexRenderer's own trusted images use it — but sanitization always
# runs *before* LaTeX placeholders are restored (see html_renderer.py),
# so this only ever matches conversation-supplied `data:` URLs, not ours.
_ALLOWED_URL_SCHEMES = {"", "http", "https", "data"}


def _is_safe_url(value: str) -> bool:
    try:
        scheme = urlsplit(value.strip()).scheme.lower()
    except ValueError:
        return False
    return scheme in _ALLOWED_URL_SCHEMES


def sanitize_html_fragment(html_fragment: str) -> str:
    """Strip script/resource-fetching/event-handler surfaces from `html_fragment`.

    Must run on Markdown's *raw* output, before `LatexRenderer.restore()`
    splices in this app's own trusted `data:` image tags — sanitizing
    afterward would risk stripping our own generated markup instead of
    only the untrusted part.
    """
    if "<" not in html_fragment:
        return html_fragment  # fast path: plain text, nothing to parse

    soup = BeautifulSoup(html_fragment, "html.parser")

    for tag in soup.find_all(_DROP_WITH_CONTENTS):
        tag.decompose()

    for tag in soup.find_all(True):
        for attr_name in list(tag.attrs.keys()):
            lowered = attr_name.lower()
            if lowered.startswith("on") or lowered == "style":
                del tag[attr_name]
                continue
            if lowered in _URL_ATTRS:
                value = tag[attr_name]
                if isinstance(value, list):  # e.g. a malformed multi-value src
                    value = " ".join(value)
                if not _is_safe_url(str(value)):
                    del tag[attr_name]

    return str(soup)
