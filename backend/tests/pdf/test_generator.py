"""Tests for PDFGenerator.

WeasyPrint (and its native Pango/Cairo dependencies) may not be installed
in every environment this test suite runs in, so the `weasyprint` module
itself is faked via `monkeypatch.setitem(sys.modules, ...)` rather than
requiring the real package. This still exercises the real import-and-call
path inside `render_html_to_pdf` (`from weasyprint import HTML`), just
against a stand-in implementation.
"""
import sys
import types

import pytest

from app.pdf.generator import PDFGenerator
from app.utils.exceptions import PdfGenerationError


class _StubHtmlBuilder:
    """A minimal stand-in for HtmlDocumentBuilder so these tests exercise
    only PDFGenerator's own wiring, not the real HTML-building logic."""

    def __init__(self, html_to_return: str = "<html><body>hi</body></html>") -> None:
        self.html_to_return = html_to_return
        self.last_call = None

    def build(self, title, sections, source_url=None):
        self.last_call = {"title": title, "sections": sections, "source_url": source_url}
        return self.html_to_return


def _install_fake_weasyprint(monkeypatch, write_pdf_impl):
    fake_module = types.ModuleType("weasyprint")

    class FakeHTML:
        def __init__(self, string):
            self.string = string

        def write_pdf(self):
            return write_pdf_impl(self.string)

    fake_module.HTML = FakeHTML
    monkeypatch.setitem(sys.modules, "weasyprint", fake_module)


class TestGenerateDelegatesToHtmlBuilder:
    def test_generate_passes_title_sections_and_source_url_to_builder(self, monkeypatch) -> None:
        _install_fake_weasyprint(monkeypatch, lambda html: b"%PDF-FAKE")
        stub_builder = _StubHtmlBuilder()
        generator = PDFGenerator(html_builder=stub_builder)

        result = generator.generate(title="T", sections=[], source_url="https://x")

        assert result == b"%PDF-FAKE"
        assert stub_builder.last_call == {"title": "T", "sections": [], "source_url": "https://x"}

    def test_generate_converts_the_html_the_builder_returned(self, monkeypatch) -> None:
        seen_html = {}

        def write_pdf_impl(html):
            seen_html["value"] = html
            return b"%PDF-BYTES"

        _install_fake_weasyprint(monkeypatch, write_pdf_impl)
        stub_builder = _StubHtmlBuilder(html_to_return="<html><body>specific marker</body></html>")
        generator = PDFGenerator(html_builder=stub_builder)

        generator.generate(title="T", sections=[])

        assert "specific marker" in seen_html["value"]

    def test_default_html_builder_is_used_when_none_is_injected(self) -> None:
        generator = PDFGenerator()
        assert generator._html_builder is not None


class TestRenderHtmlToPdf:
    def test_returns_bytes_from_weasyprint_on_success(self, monkeypatch) -> None:
        _install_fake_weasyprint(monkeypatch, lambda html: b"%PDF-OK")
        result = PDFGenerator.render_html_to_pdf("<html></html>")
        assert result == b"%PDF-OK"

    def test_wraps_weasyprint_rendering_failures_in_pdf_generation_error(self, monkeypatch) -> None:
        def failing_write_pdf(html):
            raise RuntimeError("boom")

        _install_fake_weasyprint(monkeypatch, failing_write_pdf)

        with pytest.raises(PdfGenerationError):
            PDFGenerator.render_html_to_pdf("<html></html>")

    def test_raises_pdf_generation_error_when_weasyprint_is_unavailable(self, monkeypatch) -> None:
        monkeypatch.delitem(sys.modules, "weasyprint", raising=False)
        monkeypatch.setitem(sys.modules, "weasyprint", None)

        with pytest.raises(PdfGenerationError):
            PDFGenerator.render_html_to_pdf("<html></html>")
