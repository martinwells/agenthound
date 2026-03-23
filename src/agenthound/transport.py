"""Recording and replay transports for httpx.

These custom transports intercept HTTP calls at the httpx level, enabling
framework-agnostic recording and deterministic replay of LLM API calls.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, List
from urllib.parse import urlparse

import httpx

from agenthound.models import HttpExchange


class AgentHoundTransportError(Exception):
    """Base error for transport issues."""


class NoMoreRecordedExchanges(AgentHoundTransportError):
    """Raised when replay runs out of recorded exchanges."""


def _parse_body(raw: bytes) -> Any:
    """Try to parse response/request body as JSON, fall back to string."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def _serialize_body(body: Any) -> bytes:
    """Convert a body value back to bytes for httpx.Response."""
    if body is None:
        return b""
    if isinstance(body, bytes):
        return body
    if isinstance(body, str):
        return body.encode("utf-8")
    return json.dumps(body).encode("utf-8")


class RecordingTransport(httpx.BaseTransport):
    """Wraps a real transport, recording every exchange."""

    def __init__(self, wrapped: httpx.BaseTransport, exchange_log: List[HttpExchange]) -> None:
        self._wrapped = wrapped
        self._exchange_log = exchange_log

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        # Capture request
        request_headers = dict(request.headers)
        request_body = _parse_body(request.content)

        start = time.monotonic()
        response = self._wrapped.handle_request(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Read the full response body so we can capture it
        response.read()

        response_headers = dict(response.headers)
        response_body = _parse_body(response.content)

        exchange = HttpExchange(
            request_url=str(request.url),
            request_method=request.method,
            request_headers=request_headers,
            request_body=request_body,
            response_status=response.status_code,
            response_headers=response_headers,
            response_body=response_body,
            timestamp=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        )
        self._exchange_log.append(exchange)
        return response

    def close(self) -> None:
        self._wrapped.close()


class AsyncRecordingTransport(httpx.AsyncBaseTransport):
    """Async version of RecordingTransport."""

    def __init__(
        self, wrapped: httpx.AsyncBaseTransport, exchange_log: List[HttpExchange]
    ) -> None:
        self._wrapped = wrapped
        self._exchange_log = exchange_log

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request_headers = dict(request.headers)
        request_body = _parse_body(request.content)

        start = time.monotonic()
        response = await self._wrapped.handle_async_request(request)
        duration_ms = (time.monotonic() - start) * 1000

        await response.aread()

        response_headers = dict(response.headers)
        response_body = _parse_body(response.content)

        exchange = HttpExchange(
            request_url=str(request.url),
            request_method=request.method,
            request_headers=request_headers,
            request_body=request_body,
            response_status=response.status_code,
            response_headers=response_headers,
            response_body=response_body,
            timestamp=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        )
        self._exchange_log.append(exchange)
        return response

    async def aclose(self) -> None:
        await self._wrapped.aclose()


class ReplayTransport(httpx.BaseTransport):
    """Serves pre-recorded responses instead of making real HTTP calls."""

    def __init__(self, exchanges: List[HttpExchange], *, strict: bool = True) -> None:
        self._exchanges = exchanges
        self._call_index = 0
        self._strict = strict

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self._call_index >= len(self._exchanges):
            raise NoMoreRecordedExchanges(
                f"Replay exhausted: {self._call_index} calls made but only "
                f"{len(self._exchanges)} exchanges recorded. "
                f"The agent may be making more API calls than expected."
            )

        expected = self._exchanges[self._call_index]
        self._call_index += 1

        if self._strict:
            # Validate URL path matches (ignore host — may differ between record/replay)
            expected_path = urlparse(expected.request_url).path
            actual_path = urlparse(str(request.url)).path
            if expected_path != actual_path:
                raise AgentHoundTransportError(
                    f"Replay mismatch at call {self._call_index}: "
                    f"expected path '{expected_path}' but got '{actual_path}'"
                )

        body = _serialize_body(expected.response_body)
        headers = dict(expected.response_headers)
        # Ensure content-length is correct for the serialized body
        headers["content-length"] = str(len(body))

        return httpx.Response(
            status_code=expected.response_status,
            headers=headers,
            content=body,
        )

    def close(self) -> None:
        pass


class AsyncReplayTransport(httpx.AsyncBaseTransport):
    """Async version of ReplayTransport."""

    def __init__(self, exchanges: List[HttpExchange], *, strict: bool = True) -> None:
        self._exchanges = exchanges
        self._call_index = 0
        self._strict = strict

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self._call_index >= len(self._exchanges):
            raise NoMoreRecordedExchanges(
                f"Replay exhausted: {self._call_index} calls made but only "
                f"{len(self._exchanges)} exchanges recorded."
            )

        expected = self._exchanges[self._call_index]
        self._call_index += 1

        if self._strict:
            expected_path = urlparse(expected.request_url).path
            actual_path = urlparse(str(request.url)).path
            if expected_path != actual_path:
                raise AgentHoundTransportError(
                    f"Replay mismatch at call {self._call_index}: "
                    f"expected path '{expected_path}' but got '{actual_path}'"
                )

        body = _serialize_body(expected.response_body)
        headers = dict(expected.response_headers)
        headers["content-length"] = str(len(body))

        return httpx.Response(
            status_code=expected.response_status,
            headers=headers,
            content=body,
        )

    async def aclose(self) -> None:
        pass
