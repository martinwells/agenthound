"""Tests for failure injection."""
from __future__ import annotations

import os

import httpx
import pytest

from agenthound.failures import inject_failure
from agenthound.replayer import replay

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_session.json")


class TestInjectFailure:
    def test_injects_error_on_tool_call(self):
        @replay(FIXTURE_PATH, strict=False)
        @inject_failure(tool="lookup_order", error="TimeoutError", at_call=1)
        def my_test(session):
            # The first exchange (which has lookup_order) should now return 500
            client = httpx.Client()
            r = client.post("https://api.openai.com/v1/chat/completions", json={})
            client.close()

            assert r.status_code == 500
            body = r.json()
            assert "TimeoutError" in body["error"]["type"]

            # Session should show the error
            assert session.llm_calls[0].error is not None
            assert "TimeoutError" in session.llm_calls[0].error

        my_test()

    def test_failure_metadata_attached(self):
        @inject_failure(tool="search", error="RateLimitError")
        def my_test():
            pass

        assert hasattr(my_test, "_agenthound_failures")
        assert len(my_test._agenthound_failures) == 1
        assert my_test._agenthound_failures[0]["tool"] == "search"
        assert my_test._agenthound_failures[0]["error"] == "RateLimitError"
        assert my_test._agenthound_failures[0]["at_call"] == 1

    def test_multiple_failures(self):
        @inject_failure(tool="search", error="TimeoutError", at_call=1)
        @inject_failure(tool="search", error="RateLimitError", at_call=2)
        def my_test():
            pass

        assert len(my_test._agenthound_failures) == 2
