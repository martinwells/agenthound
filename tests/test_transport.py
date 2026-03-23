"""Tests for recording and replay transports."""
from __future__ import annotations

import json
from typing import List

import httpx
import pytest

from agenthound.models import HttpExchange
from agenthound.transport import (
    AgentHoundTransportError,
    NoMoreRecordedExchanges,
    RecordingTransport,
    ReplayTransport,
)


class TestRecordingTransport:
    def test_records_exchange(self):
        """RecordingTransport captures the request and response."""
        # Create a mock transport that returns a canned response
        mock = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"result": "ok"})
        )
        exchange_log: List[HttpExchange] = []
        transport = RecordingTransport(mock, exchange_log)

        client = httpx.Client(transport=transport)
        response = client.post(
            "https://api.openai.com/v1/chat/completions",
            json={"model": "gpt-4o", "messages": []},
        )

        assert response.status_code == 200
        assert response.json() == {"result": "ok"}

        # Verify the exchange was recorded
        assert len(exchange_log) == 1
        ex = exchange_log[0]
        assert "chat/completions" in ex.request_url
        assert ex.request_method == "POST"
        assert ex.response_status == 200
        assert ex.response_body == {"result": "ok"}
        assert ex.duration_ms >= 0

        client.close()

    def test_records_multiple_exchanges(self):
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json={"call": call_count})

        mock = httpx.MockTransport(handler)
        exchange_log: List[HttpExchange] = []
        transport = RecordingTransport(mock, exchange_log)

        client = httpx.Client(transport=transport)
        client.post("https://api.openai.com/v1/chat/completions", json={})
        client.post("https://api.openai.com/v1/chat/completions", json={})

        assert len(exchange_log) == 2
        assert exchange_log[0].response_body == {"call": 1}
        assert exchange_log[1].response_body == {"call": 2}

        client.close()


class TestReplayTransport:
    def test_replays_recorded_response(self):
        exchanges = [
            HttpExchange(
                request_url="https://api.openai.com/v1/chat/completions",
                response_status=200,
                response_headers={"content-type": "application/json"},
                response_body={"choices": [{"message": {"content": "Hello!"}}]},
            )
        ]
        transport = ReplayTransport(exchanges)
        client = httpx.Client(transport=transport)

        response = client.post(
            "https://api.openai.com/v1/chat/completions",
            json={"model": "gpt-4o", "messages": []},
        )

        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "Hello!"

        client.close()

    def test_replays_sequence(self):
        exchanges = [
            HttpExchange(
                request_url="https://api.openai.com/v1/chat/completions",
                response_body={"n": 1},
            ),
            HttpExchange(
                request_url="https://api.openai.com/v1/chat/completions",
                response_body={"n": 2},
            ),
        ]
        transport = ReplayTransport(exchanges, strict=False)
        client = httpx.Client(transport=transport)

        r1 = client.post("https://api.openai.com/v1/chat/completions", json={})
        r2 = client.post("https://api.openai.com/v1/chat/completions", json={})

        assert r1.json() == {"n": 1}
        assert r2.json() == {"n": 2}

        client.close()

    def test_raises_when_exhausted(self):
        exchanges = [
            HttpExchange(
                request_url="https://api.openai.com/v1/chat/completions",
                response_body={"n": 1},
            ),
        ]
        transport = ReplayTransport(exchanges, strict=False)
        client = httpx.Client(transport=transport)

        client.post("https://api.openai.com/v1/chat/completions", json={})

        with pytest.raises(NoMoreRecordedExchanges):
            client.post("https://api.openai.com/v1/chat/completions", json={})

        client.close()

    def test_strict_mode_validates_path(self):
        exchanges = [
            HttpExchange(
                request_url="https://api.openai.com/v1/chat/completions",
                response_body={"n": 1},
            ),
        ]
        transport = ReplayTransport(exchanges, strict=True)
        client = httpx.Client(transport=transport)

        # Different path should raise
        with pytest.raises(AgentHoundTransportError, match="Replay mismatch"):
            client.post("https://api.openai.com/v1/different/endpoint", json={})

        client.close()

    def test_non_strict_mode_ignores_path(self):
        exchanges = [
            HttpExchange(
                request_url="https://api.openai.com/v1/chat/completions",
                response_body={"n": 1},
            ),
        ]
        transport = ReplayTransport(exchanges, strict=False)
        client = httpx.Client(transport=transport)

        response = client.post("https://different.host.com/any/path", json={})
        assert response.json() == {"n": 1}

        client.close()
