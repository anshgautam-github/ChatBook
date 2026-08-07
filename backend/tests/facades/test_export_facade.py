"""Tests for `ExportFacade` — the single entry point API routes call into
(see app/facades/export_facade.py). Because the Facade is pure
delegation by design, these tests only assert that: (1) each method
forwards its arguments to `ExportService` unchanged and returns its
result unchanged, and (2) errors raised by `ExportService` propagate
through untouched. `ExportService`'s own orchestration logic is already
covered by tests/services/test_export_service.py — it is not re-tested
here.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from app.facades.export_facade import ExportFacade
from app.models.conversation import Conversation, Message, MessageRole, QaSection
from app.services.export_service import ExportService
from app.utils.exceptions import ConversationFetchError, PdfGenerationError


class _FakeExportService:
    def __init__(
        self,
        conversation: Optional[Conversation] = None,
        pdf_bytes: bytes = b"%PDF-1.4 fake",
        fetch_error: Optional[Exception] = None,
        pdf_error: Optional[Exception] = None,
    ) -> None:
        self.conversation = conversation
        self.pdf_bytes = pdf_bytes
        self.fetch_error = fetch_error
        self.pdf_error = pdf_error
        self.fetch_calls: List[str] = []
        self.pdf_calls: List[dict] = []

    async def fetch_and_parse(self, url: str) -> Conversation:
        self.fetch_calls.append(url)
        if self.fetch_error is not None:
            raise self.fetch_error
        return self.conversation

    def generate_pdf(self, *, title: str, sections: List[QaSection], source_url=None) -> bytes:
        self.pdf_calls.append({"title": title, "sections": sections, "source_url": source_url})
        if self.pdf_error is not None:
            raise self.pdf_error
        return self.pdf_bytes


def _message(content: str, role: MessageRole = MessageRole.USER, order: int = 0) -> Message:
    return Message(id=f"msg-{order}", role=role, content=content, order=order)


class TestFetchAndParse:
    def test_forwards_the_url_and_returns_the_service_result_unchanged(self) -> None:
        expected = Conversation(title="Fake", source_url="https://chatgpt.com/share/abc", messages=[], sections=[])
        fake_service = _FakeExportService(conversation=expected)
        facade = ExportFacade(export_service=fake_service)

        result = asyncio.run(facade.fetch_and_parse("https://chatgpt.com/share/abc"))

        assert result is expected
        assert fake_service.fetch_calls == ["https://chatgpt.com/share/abc"]

    def test_propagates_service_errors_unchanged(self) -> None:
        fake_service = _FakeExportService(fetch_error=ConversationFetchError("network is down"))
        facade = ExportFacade(export_service=fake_service)

        with pytest.raises(ConversationFetchError):
            asyncio.run(facade.fetch_and_parse("https://chatgpt.com/share/abc"))

    def test_adds_no_logic_of_its_own(self) -> None:
        """A regression guard for requirement #3 (no business logic in the
        Facade): calling with the same URL twice must hit the service
        exactly twice, with no caching, retrying, or short-circuiting."""
        fake_service = _FakeExportService(
            conversation=Conversation(title="x", source_url="u", messages=[], sections=[])
        )
        facade = ExportFacade(export_service=fake_service)

        asyncio.run(facade.fetch_and_parse("https://chatgpt.com/share/abc"))
        asyncio.run(facade.fetch_and_parse("https://chatgpt.com/share/abc"))

        assert fake_service.fetch_calls == [
            "https://chatgpt.com/share/abc",
            "https://chatgpt.com/share/abc",
        ]


class TestGeneratePdf:
    def test_forwards_arguments_and_returns_the_service_result_unchanged(self) -> None:
        section = QaSection(
            id="s1", section_index=1, question=_message("Q"), answer=_message("A", role=MessageRole.ASSISTANT)
        )
        fake_service = _FakeExportService(pdf_bytes=b"%PDF-1.4 hello")
        facade = ExportFacade(export_service=fake_service)

        result = facade.generate_pdf(title="My Notes", sections=[section], source_url="https://chatgpt.com/share/abc")

        assert result == b"%PDF-1.4 hello"
        assert fake_service.pdf_calls == [
            {"title": "My Notes", "sections": [section], "source_url": "https://chatgpt.com/share/abc"}
        ]

    def test_propagates_service_errors_unchanged(self) -> None:
        fake_service = _FakeExportService(pdf_error=PdfGenerationError("no sections selected"))
        facade = ExportFacade(export_service=fake_service)

        with pytest.raises(PdfGenerationError):
            facade.generate_pdf(title="Empty", sections=[])

    def test_source_url_defaults_to_none_when_omitted(self) -> None:
        fake_service = _FakeExportService()
        facade = ExportFacade(export_service=fake_service)

        facade.generate_pdf(title="No Source", sections=[])

        assert fake_service.pdf_calls == [{"title": "No Source", "sections": [], "source_url": None}]


class TestConstructorInjectionDefaults:
    def test_omitted_export_service_defaults_to_the_real_implementation(self) -> None:
        facade = ExportFacade()

        assert isinstance(facade._export_service, ExportService)
