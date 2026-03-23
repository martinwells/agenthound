"""Tests for the replay decorator and ReplaySession."""
from __future__ import annotations

import os

import httpx
import pytest

from agenthound.replayer import ReplaySession, load_fixture, replay

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_session.json")


class TestLoadFixture:
    def test_load_sample(self):
        fixture = load_fixture(FIXTURE_PATH)
        assert fixture.version == "1.0"
        assert len(fixture.exchanges) == 3

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_fixture("/nonexistent/path.json")


class TestReplaySession:
    def test_properties(self):
        fixture = load_fixture(FIXTURE_PATH)
        session = ReplaySession(fixture)

        assert session.tags == ["happy_path", "refund"]
        assert session.total_duration_ms == 1350.0
        assert session.tools_called == ["lookup_order", "process_refund"]
        assert session.tool_retries == {"lookup_order": 1, "process_refund": 1}
        assert session.total_tokens == 850  # 175 + 280 + 395


class TestReplayDecorator:
    def test_basic_replay(self):
        """The @replay decorator injects a session and replays HTTP calls."""

        @replay(FIXTURE_PATH)
        def my_test(session):
            # Make the same HTTP calls the agent would make
            client = httpx.Client()
            r1 = client.post(
                "https://api.openai.com/v1/chat/completions",
                json={"model": "gpt-4o-mini", "messages": []},
            )
            r2 = client.post(
                "https://api.openai.com/v1/chat/completions",
                json={"model": "gpt-4o-mini", "messages": []},
            )
            r3 = client.post(
                "https://api.openai.com/v1/chat/completions",
                json={"model": "gpt-4o-mini", "messages": []},
            )
            client.close()

            # Verify we got the recorded responses
            assert r1.status_code == 200
            body1 = r1.json()
            assert body1["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "lookup_order"

            # Session assertions
            assert session.tools_called == ["lookup_order", "process_refund"]

        my_test()

    def test_replay_without_session_param(self):
        """@replay works even if the function doesn't have a session param."""

        @replay(FIXTURE_PATH, strict=False)
        def my_test():
            client = httpx.Client()
            r = client.post("https://api.openai.com/v1/chat/completions", json={})
            assert r.status_code == 200
            client.close()

        my_test()
