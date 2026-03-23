"""Tests for core data models."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from agenthound.models import (
    HttpExchange,
    LLMCall,
    SessionFixture,
    ToolCallRecord,
    UsageRecord,
)


class TestHttpExchange:
    def test_create_minimal(self):
        ex = HttpExchange(request_url="https://api.openai.com/v1/chat/completions")
        assert ex.request_method == "POST"
        assert ex.response_status == 200

    def test_redact_headers(self):
        ex = HttpExchange(
            request_url="https://api.openai.com/v1/chat/completions",
            request_headers={
                "Authorization": "Bearer sk-secret",
                "x-api-key": "key-123",
                "content-type": "application/json",
            },
        )
        redacted = ex.redacted()
        assert redacted.request_headers["Authorization"] == "[REDACTED]"
        assert redacted.request_headers["x-api-key"] == "[REDACTED]"
        assert redacted.request_headers["content-type"] == "application/json"
        # Original unchanged
        assert ex.request_headers["Authorization"] == "Bearer sk-secret"

    def test_json_round_trip(self):
        ex = HttpExchange(
            request_url="https://api.openai.com/v1/chat/completions",
            request_body={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
            response_body={"choices": [{"message": {"content": "Hello!"}}]},
        )
        data = ex.model_dump(mode="json")
        restored = HttpExchange.model_validate(data)
        assert restored.request_url == ex.request_url
        assert restored.request_body == ex.request_body
        assert restored.response_body == ex.response_body


class TestToolCallRecord:
    def test_create(self):
        tc = ToolCallRecord(
            tool_name="search",
            tool_call_id="call_001",
            arguments={"q": "weather"},
        )
        assert tc.tool_name == "search"
        assert tc.arguments == {"q": "weather"}
        assert tc.error is None


class TestUsageRecord:
    def test_create(self):
        usage = UsageRecord(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.total_tokens == 150


class TestLLMCall:
    def test_create(self):
        call = LLMCall(
            provider="openai",
            model="gpt-4o",
            tool_calls=[
                ToolCallRecord(tool_name="search", arguments={"q": "test"}),
            ],
            usage=UsageRecord(input_tokens=100, output_tokens=50, total_tokens=150),
        )
        assert call.provider == "openai"
        assert len(call.tool_calls) == 1
        assert call.tool_calls[0].tool_name == "search"


class TestSessionFixture:
    def test_to_file_and_from_file(self):
        fixture = SessionFixture(
            tags=["test"],
            metadata={"env": "test"},
            exchanges=[
                HttpExchange(
                    request_url="https://api.openai.com/v1/chat/completions",
                    request_headers={"Authorization": "Bearer sk-secret"},
                    response_body={"choices": [{"message": {"content": "Hi"}}]},
                )
            ],
            llm_calls=[
                LLMCall(provider="openai", model="gpt-4o", response_text="Hi"),
            ],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_fixture.json")
            fixture.to_file(path)

            # Verify file was written
            assert os.path.exists(path)

            # Verify auth was redacted in file
            with open(path) as f:
                data = json.load(f)
            assert data["exchanges"][0]["request_headers"]["Authorization"] == "[REDACTED]"

            # Load it back
            loaded = SessionFixture.from_file(path)
            assert loaded.tags == ["test"]
            assert loaded.metadata == {"env": "test"}
            assert len(loaded.exchanges) == 1
            assert len(loaded.llm_calls) == 1

    def test_from_file_sample(self):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_session.json")
        fixture = SessionFixture.from_file(fixture_path)
        assert fixture.version == "1.0"
        assert fixture.tags == ["happy_path", "refund"]
        assert len(fixture.exchanges) == 3
        assert len(fixture.llm_calls) == 3
        assert fixture.total_duration_ms == 1350.0

    def test_unsupported_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bad.json")
            with open(path, "w") as f:
                json.dump({"version": "99.0", "exchanges": [], "llm_calls": []}, f)
            with pytest.raises(ValueError, match="Unsupported fixture schema version"):
                SessionFixture.from_file(path)
