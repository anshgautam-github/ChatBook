from app.pdf.html_sanitizer import sanitize_html_fragment


class TestDangerousTagsRemoved:
    def test_script_tag_and_its_contents_are_removed(self) -> None:
        result = sanitize_html_fragment("<p>hello <script>alert(1)</script> world</p>")
        assert "<script" not in result
        assert "alert(1)" not in result
        assert "hello" in result and "world" in result

    def test_iframe_and_its_contents_are_removed(self) -> None:
        result = sanitize_html_fragment('<iframe src="http://evil.example/"></iframe>after')
        assert "<iframe" not in result
        assert "evil.example" not in result
        assert "after" in result

    def test_style_and_link_tags_are_removed(self) -> None:
        result = sanitize_html_fragment(
            '<style>body{background:url(http://evil.example/x)}</style>'
            '<link rel="stylesheet" href="http://evil.example/x.css">visible'
        )
        assert "<style" not in result
        assert "<link" not in result
        assert "evil.example" not in result
        assert "visible" in result


class TestEventHandlerAndStyleAttributesStripped:
    def test_onclick_and_similar_attributes_are_stripped(self) -> None:
        result = sanitize_html_fragment('<a href="https://example.com" onclick="steal()">link</a>')
        assert "onclick" not in result
        assert 'href="https://example.com"' in result
        assert "link" in result

    def test_inline_style_attribute_is_stripped(self) -> None:
        result = sanitize_html_fragment('<div style="background:url(http://evil.example/x.png)">text</div>')
        assert "style=" not in result
        assert "evil.example" not in result
        assert "text" in result


class TestUrlSchemeValidation:
    def test_javascript_scheme_in_href_is_stripped(self) -> None:
        result = sanitize_html_fragment('<a href="javascript:alert(1)">click me</a>')
        assert "javascript:" not in result
        assert "click me" in result

    def test_https_and_data_schemes_are_kept(self) -> None:
        assert 'src="https://example.com/a.png"' in sanitize_html_fragment(
            '<img src="https://example.com/a.png" alt="ok">'
        )
        assert 'src="data:image/svg+xml;base64,AAAA"' in sanitize_html_fragment(
            '<img src="data:image/svg+xml;base64,AAAA" alt="latex">'
        )

    def test_fragment_only_href_is_kept(self) -> None:
        # Footnote references (`python-markdown`'s "extra" bundle) link via
        # bare `#fn:1`-style fragments with no scheme at all.
        result = sanitize_html_fragment('<sup><a href="#fn:1">1</a></sup>')
        assert 'href="#fn:1"' in result


class TestLegitimateMarkdownOutputIsUnaffected:
    def test_pygments_syntax_highlighting_spans_survive(self) -> None:
        result = sanitize_html_fragment(
            '<div class="codehilite"><pre><span class="k">def</span> '
            '<span class="nf">foo</span>():</pre></div>'
        )
        assert 'class="codehilite"' in result
        assert 'class="k">def<' in result
        assert 'class="nf">foo<' in result

    def test_tables_survive(self) -> None:
        result = sanitize_html_fragment("<table><tr><th>Input</th></tr></table>")
        assert "<table>" in result
        assert "<th>Input</th>" in result

    def test_definition_lists_survive(self) -> None:
        result = sanitize_html_fragment("<dl><dt>Term</dt><dd>Definition</dd></dl>")
        assert "<dt>Term</dt>" in result
        assert "<dd>Definition</dd>" in result

    def test_abbr_title_attribute_survives(self) -> None:
        result = sanitize_html_fragment('<abbr title="HyperText Markup Language">HTML</abbr>')
        assert 'title="HyperText Markup Language"' in result

    def test_plain_text_with_no_tags_is_returned_unchanged(self) -> None:
        assert sanitize_html_fragment("just plain text, no markup") == "just plain text, no markup"
