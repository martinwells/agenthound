"""Tests for the @mock_llm decorator."""
from __future__ import annotations

import httpx
import pytest

from agenthound.assertions import expect
from agenthound.mock_llm import mock_llm


class TestMockLLM:
    def test_text_response(self):
        @mock_llm(responses=["Hello, world!"])
        def my_test(session):
            client = httpx.Client()
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
            )
            client.close()

            body = r.json()
            assert body["choices"][0]["message"]["content"] == "Hello, world!"
            assert session.llm_calls[0].response_text == "Hello, world!"

        my_test()

    def test_tool_call_response(self):
        @mock_llm(responses=[
            {"tool_call": "search", "args": {"q": "weather"}},
            "The weather is sunny.",
        ])
        def my_test(session):
            client = httpx.Client()
            r1 = client.post("https://api.openai.com/v1/chat/completions", json={})
            r2 = client.post("https://api.openai.com/v1/chat/completions", json={})
            client.close()

            # First response is a tool call
            body1 = r1.json()
            tc = body1["choices"][0]["message"]["tool_calls"][0]
            assert tc["function"]["name"] == "search"

            # Second is text
            body2 = r2.json()
            assert body2["choices"][0]["message"]["content"] == "The weather is sunny."

            # Session-level assertions
            expect(session).tools_called(["search"])
            expect(session).has_llm_calls(2)

        my_test()

    def test_anthropic_provider(self):
        @mock_llm(
            responses=["Hello from Claude!"],
            provider="anthropic",
        )
        def my_test(session):
            client = httpx.Client()
            r = client.post("https://api.anthropic.com/v1/messages", json={})
            client.close()

            body = r.json()
            assert body["content"][0]["text"] == "Hello from Claude!"
            assert body["type"] == "message"

        my_test()

    def test_no_session_param(self):
        @mock_llm(responses=["OK"])
        def my_test():
            client = httpx.Client()
            r = client.post("https://api.openai.com/v1/chat/completions", json={})
            client.close()
            assert r.json()["choices"][0]["message"]["content"] == "OK"

        my_test()

    def test_invalid_provider(self):
        with pytest.raises(ValueError, match="No adapter found"):
            @mock_llm(responses=["x"], provider="nonexistent")
            def my_test():
                pass
            my_test()
