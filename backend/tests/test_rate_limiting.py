"""Tests for per-endpoint rate limiting (see app/utils/rate_limiter.py).

Uses a small, test-only limit (well below the real default of 15/minute)
so these tests run fast and deterministically rather than needing 15+
requests to trip the real configured limit. The limit is lowered the same
way a real deployment would configure it — via the `RATE_LIMIT_PER_MINUTE`
env var — rather than monkeypatching slowapi internals directly, since
`rate_limit_value()` re-reads `Settings` on every request (see that
function's docstring for why). `Settings` is cached via `lru_cache`, so
the cache has to be cleared after changing the env var for the new value
to actually take effect.

Every test gets a fresh rate-limit "bucket": `TestClient` requests are all
seen as coming from the same pseudo-client address (Starlette's test
transport doesn't simulate different real IPs), so without resetting the
limiter's storage between tests, an earlier test tripping the limit would
leak into every test that runs after it in the same process.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_export_facade
from app.config.settings import get_settings
from app.main import app
from app.models.conversation import Conversation, QaSection
from app.utils.rate_limiter import limiter

TEST_LIMIT_PER_MINUTE = 3

_SECTION_PAYLOAD = {
    "selected_sections": [
        {
            "id": "s1",
            "section_index": 1,
            "question": {"id": "m1", "role": "user", "content": "hi", "order": 0},
            "answer": {"id": "m2", "role": "assistant", "content": "hello", "order": 1},
        }
    ]
}


@pytest.fixture(autouse=True)
def _low_rate_limit(monkeypatch):
    """Lower the configured limit for every test in this module and reset
    the limiter's counters before and after each one, so tests are
    isolated both from the real default and from each other."""
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", str(TEST_LIMIT_PER_MINUTE))
    get_settings.cache_clear()
    limiter.reset()
    yield
    limiter.reset()
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


class _FakeExportFacade:
    """Stands in for the real `ExportFacade` (see app/api/deps.py) so
    these tests never make a real network call or run actual PDF
    rendering — only the rate limiter itself is under test here. Tracks
    a call count per method so a test can confirm the route body never
    actually runs once the limit is hit."""

    def __init__(self) -> None:
        self.parse_call_count = 0
        self.generate_call_count = 0

    async def fetch_and_parse(self, url: str) -> Conversation:
        self.parse_call_count += 1
        return Conversation(title="Fake Conversation", source_url=url, messages=[], sections=[])

    def generate_pdf(self, *, title: str, sections: list[QaSection], source_url=None) -> bytes:
        self.generate_call_count += 1
        return b"%PDF-1.4 fake pdf bytes"


@pytest.fixture
def fake_export_facade():
    fake = _FakeExportFacade()
    app.dependency_overrides[get_export_facade] = lambda: fake
    yield fake
    del app.dependency_overrides[get_export_facade]


class TestParseEndpointRateLimit:
    def test_requests_up_to_the_limit_are_allowed(self, client, fake_export_facade):
        for _ in range(TEST_LIMIT_PER_MINUTE):
            response = client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})
            assert response.status_code == 200

    def test_request_beyond_the_limit_returns_429(self, client, fake_export_facade):
        for _ in range(TEST_LIMIT_PER_MINUTE):
            client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})

        response = client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})

        assert response.status_code == 429

    def test_429_response_has_a_clear_human_readable_message(self, client, fake_export_facade):
        for _ in range(TEST_LIMIT_PER_MINUTE):
            client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})

        response = client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})
        body = response.json()

        # Matches the shape every other error path in this API uses
        # (see app/utils/exceptions.py + the route layer's HTTPException
        # usage) so client-side error handling doesn't need a special
        # case just for rate-limit errors.
        assert "detail" in body
        assert isinstance(body["detail"], str) and body["detail"].strip()
        assert "too many requests" in body["detail"].lower()

    def test_underlying_service_is_never_called_once_the_limit_is_hit(
        self, client, fake_export_facade
    ):
        for _ in range(TEST_LIMIT_PER_MINUTE):
            client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})
        call_count_at_limit = fake_export_facade.parse_call_count

        client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})

        # The 429 is returned before the route body ever runs — the rate
        # limiter should shed load, not just fail after doing the work.
        assert fake_export_facade.parse_call_count == call_count_at_limit


class TestGeneratePdfEndpointRateLimit:
    def test_requests_up_to_the_limit_are_allowed(self, client, fake_export_facade):
        for _ in range(TEST_LIMIT_PER_MINUTE):
            response = client.post("/api/generate-pdf", json=_SECTION_PAYLOAD)
            assert response.status_code == 200

    def test_request_beyond_the_limit_returns_429_with_clear_message(self, client, fake_export_facade):
        for _ in range(TEST_LIMIT_PER_MINUTE):
            client.post("/api/generate-pdf", json=_SECTION_PAYLOAD)

        response = client.post("/api/generate-pdf", json=_SECTION_PAYLOAD)

        assert response.status_code == 429
        body = response.json()
        assert "detail" in body
        assert "too many requests" in body["detail"].lower()


class TestRateLimitsAreIndependentPerEndpoint:
    def test_exhausting_parse_does_not_block_generate_pdf(self, client, fake_export_facade):
        for _ in range(TEST_LIMIT_PER_MINUTE + 1):
            client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})

        response = client.post("/api/generate-pdf", json=_SECTION_PAYLOAD)

        assert response.status_code == 200

    def test_exhausting_generate_pdf_does_not_block_parse(self, client, fake_export_facade):
        for _ in range(TEST_LIMIT_PER_MINUTE + 1):
            client.post("/api/generate-pdf", json=_SECTION_PAYLOAD)

        response = client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})

        assert response.status_code == 200


class TestUnrelatedEndpointsAreNeverRateLimited:
    def test_health_check_is_unaffected_even_after_exhausting_other_limits(
        self, client, fake_export_facade
    ):
        for _ in range(TEST_LIMIT_PER_MINUTE + 5):
            client.post("/api/parse", json={"url": "https://chatgpt.com/share/abc"})

        # /health carries no @limiter.limit(...) decorator and no
        # `default_limits` were configured on the Limiter, so it should
        # never be affected by any other endpoint's limit.
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200
