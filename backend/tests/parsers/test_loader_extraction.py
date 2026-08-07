import json

from app.parsers.loader_extraction import (
    extract_next_data,
    extract_react_router_loader,
    resolve_loader_references,
)


class TestExtractReactRouterLoader:
    def test_quoted_string_argument(self) -> None:
        """Matches the real wire format: enqueue("<json-escaped array>")."""
        loader = ["reserved", "loaderData", {"title": "hi"}]
        inner = json.dumps(loader)
        html = (
            "<html><script>"
            f"window.__reactRouterContext.streamController.enqueue({json.dumps(inner)});"
            "</script></html>"
        )
        assert extract_react_router_loader(html) == loader

    def test_bare_array_argument(self) -> None:
        """Also supports enqueue([...]) without the extra string-quoting layer."""
        loader = ["reserved", "loaderData", {"title": "hi"}]
        html = (
            "<html><script>"
            f"window.__reactRouterContext.streamController.enqueue({json.dumps(loader)});"
            "</script></html>"
        )
        assert extract_react_router_loader(html) == loader

    def test_returns_none_when_no_script_present(self) -> None:
        assert extract_react_router_loader("<html><body>hello</body></html>") is None

    def test_returns_none_when_no_enqueue_call(self) -> None:
        html = "<html><script>console.log('nothing to see here');</script></html>"
        assert extract_react_router_loader(html) is None

    def test_skips_non_list_chunk_and_finds_later_list(self) -> None:
        """A status-string chunk followed by the real array (dual enqueue calls)."""
        loader = ["reserved", "loaderData", {"title": "hi"}]
        html = (
            "<html><script>"
            'window.__reactRouterContext.streamController.enqueue("pending");'
            f"window.__reactRouterContext.streamController.enqueue({json.dumps(loader)});"
            "</script></html>"
        )
        assert extract_react_router_loader(html) == loader

    def test_malformed_json_argument_is_skipped(self) -> None:
        html = (
            "<html><script>"
            'window.__reactRouterContext.streamController.enqueue("{not valid json");'
            "</script></html>"
        )
        assert extract_react_router_loader(html) is None

    def test_empty_html(self) -> None:
        assert extract_react_router_loader("") is None


class TestResolveLoaderReferences:
    def test_resolves_plain_values_without_references(self) -> None:
        loader = ["reserved", "loaderData", {"title": "Hello"}]
        resolved = resolve_loader_references(loader)
        assert resolved["loaderData"] == {"title": "Hello"}

    def test_resolves_integer_index_references(self) -> None:
        # loader[4] holds the real value; loader[2]'s "value" of 4 is a
        # reference to it, and key "_3" means "look up the key name at
        # loader[3]" — this mirrors the dedup encoding seen in a real
        # captured chatgpt.com share page.
        loader = [
            "reserved",
            "loaderData",
            {"_3": 4},
            "title",
            "Hello World",
        ]
        resolved = resolve_loader_references(loader)
        assert resolved["loaderData"] == {"title": "Hello World"}

    def test_out_of_range_reference_is_left_as_literal_int(self) -> None:
        loader = ["reserved", "loaderData", 999]
        resolved = resolve_loader_references(loader)
        assert resolved["loaderData"] == 999

    def test_odd_length_loader_ignores_trailing_key(self) -> None:
        # 42 is used instead of a small int like 1 because any int that's a
        # valid index into `loader` is treated as a reference — 42 is safely
        # out of range here, so it resolves as a plain literal.
        loader = ["reserved", "loaderData", {"a": 42}, "dangling"]
        resolved = resolve_loader_references(loader)
        assert resolved == {"loaderData": {"a": 42}}

    def test_resolves_nested_lists(self) -> None:
        # Same reasoning as above: 100/200/300 are out of range for this
        # 3-element loader, so they resolve as literals rather than indices.
        loader = ["reserved", "items", [100, 200, 300]]
        resolved = resolve_loader_references(loader)
        assert resolved["items"] == [100, 200, 300]


class TestExtractNextData:
    def test_finds_and_parses_next_data_script(self) -> None:
        payload = {"props": {"pageProps": {"hello": "world"}}}
        html = (
            '<html><script id="__NEXT_DATA__" type="application/json">'
            f"{json.dumps(payload)}"
            "</script></html>"
        )
        assert extract_next_data(html) == payload

    def test_returns_none_when_absent(self) -> None:
        assert extract_next_data("<html><body>no next data here</body></html>") is None

    def test_returns_none_for_invalid_json(self) -> None:
        html = '<html><script id="__NEXT_DATA__">{not valid json</script></html>'
        assert extract_next_data(html) is None
