"""Tests for `ExportService` — the Service Layer's single orchestrator
(see app/services/export_service.py). These only check that it wires
`ParserFactory` and `PDFGenerator` together correctly and enforces its
own validation rule. Provider-selection logic itself is covered in
tests/parsers/test_factory.py; each concrete parser's own behavior is
covered in tests/parsers/test_chatgpt_parser.py and
tests/parsers/test_chatgpt_html_parser.py; PDF rendering is covered in
tests/pdf/test_generator.py.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from app.models.conversation import Conversation, Message, MessageRole, QaSection
from app.parsers.conversation_parser import ConversationParser
from app.parsers.factory import ParserFactory
from app.services.export_service import ExportService
from app.utils.exceptions import PdfGenerationError


class _FakeParser(ConversationParser):
    """A minimal `ConversationParser` strategy double — always claims to
    handle whatever URL it's asked about, so wrapping it in a real
    `ParserFactory` is enough to test `ExportService`'s wiring without
    needing an actual provider."""

    def __init__(self, conversation: Optional[Conversation] = None, error: Optional[Exception] = None) -> None:
        self.conversation = conversation
        self.error = error
        self.parsed_urls: List[str] = []

    def can_handle(self, url: str) -> bool:
        return True

    async def parse(self, url: str) -> Conversation:
        self.parsed_urls.append(url)
        if self.error is not None:
            raise self.error
        return self.conversation


class _FakePdfGenerator:
    def __init__(self, pdf_bytes: bytes = b"%PDF-1.4 fake") -> None:
        self.pdf_bytes = pdf_bytes
        self.calls: list[dict] = []

    def generate(self, *, title, sections, source_url=None) -> bytes:
        self.calls.append({"title": title, "sections": sections, "source_url": source_url})
        return self.pdf_bytes


def _message(content: str, role: MessageRole = MessageRole.USER, order: int = 0) -> Message:
    return Message(id=f"msg-{order}", role=role, content=content, order=order)


class TestFetchAndParse:
    def test_delegates_to_the_factory_selected_parser_and_returns_its_result(self) -> None:
        expected_conversation = Conversation(
            title="Fake Conversation", source_url="https://chatgpt.com/share/abc", messages=[], sections=[]
        )
        fake_parser = _FakeParser(conversation=expected_conversation)
        service = ExportService(
            parser_factory=ParserFactory(parsers=[fake_parser]), pdf_generator=_FakePdfGenerator()
        )

        result = asyncio.run(service.fetch_and_parse("https://chatgpt.com/share/abc"))

        assert result is expected_conversation
        assert fake_parser.parsed_urls == ["https://chatgpt.com/share/abc"]

    def test_propagates_parser_errors_unchanged(self) -> None:
        from app.utils.exceptions import ConversationFetchError

        fake_parser = _FakeParser(error=ConversationFetchError("network is down"))
        service = ExportService(parser_factory=ParserFactory(parsers=[fake_parser]))

        with pytest.raises(ConversationFetchError):
            asyncio.run(service.fetch_and_parse("https://chatgpt.com/share/abc"))

    def test_propagates_unsupported_url_error_from_the_factory(self) -> None:
        from app.utils.exceptions import InvalidShareUrlError

        class _NeverHandles(_FakeParser):
            def can_handle(self, url: str) -> bool:
                return False

        service = ExportService(parser_factory=ParserFactory(parsers=[_NeverHandles()]))

        with pytest.raises(InvalidShareUrlError):
            asyncio.run(service.fetch_and_parse("https://not-a-supported-provider.example/x"))


class TestGeneratePdf:
    def test_delegates_to_pdf_generator_with_the_given_arguments(self) -> None:
        section = QaSection(
            id="s1",
            section_index=1,
            question=_message("Q"),
            answer=_message("A", role=MessageRole.ASSISTANT),
        )
        pdf_generator = _FakePdfGenerator(pdf_bytes=b"%PDF-1.4 hello")
        service = ExportService(pdf_generator=pdf_generator)

        result = service.generate_pdf(title="My Notes", sections=[section], source_url="https://chatgpt.com/share/abc")

        assert result == b"%PDF-1.4 hello"
        assert pdf_generator.calls == [
            {"title": "My Notes", "sections": [section], "source_url": "https://chatgpt.com/share/abc"}
        ]

    def test_raises_when_no_sections_are_selected(self) -> None:
        service = ExportService(pdf_generator=_FakePdfGenerator())

        with pytest.raises(PdfGenerationError):
            service.generate_pdf(title="Empty", sections=[])

    def test_pdf_generator_is_never_called_when_selection_is_empty(self) -> None:
        pdf_generator = _FakePdfGenerator()
        service = ExportService(pdf_generator=pdf_generator)

        with pytest.raises(PdfGenerationError):
            service.generate_pdf(title="Empty", sections=[])

        assert pdf_generator.calls == []


class TestConstructorInjectionDefaults:
    def test_omitted_collaborators_default_to_real_implementations(self) -> None:
        from app.pdf.generator import PDFGenerator

        service = ExportService()

        assert isinstance(service._parser_factory, ParserFactory)
        assert isinstance(service._pdf_generator, PDFGenerator)
