from app.pdf.syntax_highlighting import get_pygments_css


class TestGetPygmentsCss:
    def test_returns_non_empty_css(self) -> None:
        css = get_pygments_css()
        assert isinstance(css, str)
        assert len(css) > 0

    def test_default_css_class_is_codehilite(self) -> None:
        css = get_pygments_css()
        assert ".codehilite" in css

    def test_custom_css_class_is_used(self) -> None:
        css = get_pygments_css(css_class="my-code")
        assert ".my-code" in css
        assert ".codehilite" not in css

    def test_different_styles_produce_different_css(self) -> None:
        friendly = get_pygments_css(style="friendly")
        default = get_pygments_css(style="default")
        assert friendly != default
