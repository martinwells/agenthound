"""Transparent proxy that records LLM API calls as fixture files.

Sits between the app and the real LLM API. Every request is forwarded,
recorded as an HttpExchange + LLMCall, and saved to the fixtures directory.
Calls are grouped into sessions by idle gap (default 5s).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Request, Response

from agenthound.adapters import detect_adapter
from agenthound.models import HttpExchange, LLMCall, SessionFixture

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy")

# ── Target URLs keyed by provider ────────────────────────────────────────
PROVIDER_TARGETS: Dict[str, str] = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
}

# ── Session accumulator ─────────────────────────────────────────────────

# How long (seconds) of silence before a new session starts.
SESSION_GAP_SECONDS = 5.0

_current_exchanges: List[HttpExchange] = []
_current_llm_calls: List[LLMCall] = []
_current_tags: set = set()
_session_start: Optional[float] = None
_last_call_time: Optional[float] = None
_flush_timer: Optional[asyncio.TimerHandle] = None

# Header used by clients to tag proxy sessions.
TAG_HEADER = "x-agenthound-tag"

# Set by server.py at startup — points at the same fixtures_dir.
fixtures_dir: Optional[Path] = None


def _flush_session() -> None:
    """Write the current accumulated calls to a fixture file."""
    global _current_exchanges, _current_llm_calls, _current_tags, _session_start, _last_call_time, _flush_timer

    if _flush_timer is not None:
        _flush_timer.cancel()
        _flush_timer = None

    if not _current_llm_calls:
        return

    total_duration = sum(c.duration_ms for c in _current_llm_calls)

    tags = sorted(_current_tags) if _current_tags else ["proxy"]

    fixture = SessionFixture(
        recorded_at=datetime.now(timezone.utc),
        tags=tags,
        metadata={"source": "agenthound-proxy"},
        exchanges=_current_exchanges,
        llm_calls=_current_llm_calls,
        total_duration_ms=total_duration,
    )

    out_dir = fixtures_dir or Path("tests/fixtures")
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"proxy_{ts}.json"
    fixture.to_file(str(out_dir / name))
    logger.info(f"Saved proxy session: {name} ({len(_current_llm_calls)} calls)")

    _current_exchanges = []
    _current_llm_calls = []
    _current_tags = set()
    _session_start = None
    _last_call_time = None


def _schedule_flush() -> None:
    """Schedule a flush after SESSION_GAP_SECONDS of idle time."""
    global _flush_timer

    if _flush_timer is not None:
        _flush_timer.cancel()

    try:
        loop = asyncio.get_running_loop()
        _flush_timer = loop.call_later(SESSION_GAP_SECONDS, _flush_session)
    except RuntimeError:
        # No running loop — flush synchronously (e.g. during shutdown)
        pass


def _maybe_start_new_session() -> None:
    """Flush the previous session if the idle gap has elapsed."""
    global _session_start, _last_call_time

    now = time.monotonic()
    if _last_call_time is not None and (now - _last_call_time) > SESSION_GAP_SECONDS:
        _flush_session()

    if _session_start is None:
        _session_start = now


def _record_exchange(exchange: HttpExchange, llm_call: Optional[LLMCall]) -> None:
    """Append an exchange to the current session and update timing."""
    global _last_call_time

    _maybe_start_new_session()
    _current_exchanges.append(exchange)
    if llm_call:
        _current_llm_calls.append(llm_call)
    _last_call_time = time.monotonic()

    # Reset the flush timer so we flush after the idle gap
    _schedule_flush()


# ── Proxy route ──────────────────────────────────────────────────────────

@router.api_route("/{path:path}", methods=["POST", "GET", "PUT", "DELETE", "PATCH"])
async def proxy_passthrough(request: Request, path: str) -> Response:
    """Forward any request to the matching LLM provider and record the exchange."""
    # Determine target from the path or fall back to Anthropic
    target_base: Optional[str] = None
    for provider, base_url in PROVIDER_TARGETS.items():
        if path.startswith(provider):
            target_base = base_url
            path = path[len(provider):]  # strip provider prefix
            if path and not path.startswith("/"):
                path = "/" + path
            break

    # Default: treat the whole path as Anthropic
    if target_base is None:
        target_base = PROVIDER_TARGETS["anthropic"]
        if not path.startswith("/"):
            path = "/" + path

    target_url = f"{target_base}{path}"

    # Read the incoming request
    body_bytes = await request.body()
    headers = dict(request.headers)

    # Extract optional tag header before forwarding
    tag = headers.pop(TAG_HEADER, None)
    if tag:
        _current_tags.add(tag)

    # Remove hop-by-hop headers that shouldn't be forwarded
    for h in ("host", "content-length", "transfer-encoding"):
        headers.pop(h, None)

    # Forward to the real API
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=120.0) as client:
        upstream = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body_bytes,
        )
    duration_ms = (time.monotonic() - t0) * 1000

    # Parse bodies for recording
    request_body: Any = None
    if body_bytes:
        try:
            request_body = json.loads(body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            request_body = body_bytes.decode("utf-8", errors="replace")

    response_body: Any = None
    try:
        response_body = upstream.json()
    except (json.JSONDecodeError, ValueError):
        response_body = upstream.text

    exchange = HttpExchange(
        request_url=target_url,
        request_method=request.method,
        request_headers=dict(request.headers),
        request_body=request_body,
        response_status=upstream.status_code,
        response_headers=dict(upstream.headers),
        response_body=response_body,
        timestamp=datetime.now(timezone.utc),
        duration_ms=duration_ms,
    )

    # Try to parse into an LLMCall via the adapter registry
    llm_call: Optional[LLMCall] = None
    adapter = detect_adapter(target_url)
    if adapter:
        try:
            llm_call = adapter.parse_exchange(exchange, index=len(_current_llm_calls))
        except Exception as e:
            logger.warning(f"Adapter parse failed: {e}")

    _record_exchange(exchange, llm_call)

    # Return the upstream response to the caller
    # Filter out hop-by-hop headers from the response
    resp_headers = {
        k: v for k, v in upstream.headers.items()
        if k.lower() not in ("transfer-encoding", "content-encoding", "content-length")
    }

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )


# ── Lifecycle ────────────────────────────────────────────────────────────

def flush() -> None:
    """Flush any pending session (call on shutdown)."""
    _flush_session()
