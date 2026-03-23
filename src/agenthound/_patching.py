"""Low-level httpx monkey-patching for transport interception.

Patches httpx.Client._transport_for_url (and async equivalent) so that
any httpx client in the process routes through our recording or replay transport.
"""
from __future__ import annotations

from typing import List
from unittest.mock import patch

import httpx

from agenthound.models import HttpExchange
from agenthound.transport import (
    AsyncRecordingTransport,
    AsyncReplayTransport,
    RecordingTransport,
    ReplayTransport,
)


def _make_recording_wrapper(original_method, exchange_log):
    """Create a wrapper for _transport_for_url that records exchanges."""

    def wrapper(self, url):
        transport = original_method(self, url)
        # Avoid double-wrapping
        if isinstance(transport, (RecordingTransport, AsyncRecordingTransport)):
            return transport
        return RecordingTransport(transport, exchange_log)

    return wrapper


def _make_async_recording_wrapper(original_method, exchange_log):
    """Create a wrapper for async _transport_for_url that records exchanges."""

    def wrapper(self, url):
        transport = original_method(self, url)
        if isinstance(transport, (RecordingTransport, AsyncRecordingTransport)):
            return transport
        return AsyncRecordingTransport(transport, exchange_log)

    return wrapper


def _make_replay_wrapper(replay_transport):
    """Create a wrapper for _transport_for_url that returns the replay transport."""

    def wrapper(self, url):
        return replay_transport

    return wrapper


def install_recording(exchange_log: List[HttpExchange]) -> List[object]:
    """Install recording transports on all httpx clients.

    Returns a list of patch objects that must be stopped to uninstall.
    """
    orig_sync = httpx.Client._transport_for_url
    orig_async = httpx.AsyncClient._transport_for_url

    sync_patch = patch.object(
        httpx.Client,
        "_transport_for_url",
        _make_recording_wrapper(orig_sync, exchange_log),
    )
    async_patch = patch.object(
        httpx.AsyncClient,
        "_transport_for_url",
        _make_async_recording_wrapper(orig_async, exchange_log),
    )

    sync_patch.start()
    async_patch.start()

    return [sync_patch, async_patch]


def install_replay(
    exchanges: List[HttpExchange], *, strict: bool = True
) -> List[object]:
    """Install replay transports on all httpx clients.

    Returns a list of patch objects that must be stopped to uninstall.
    """
    sync_transport = ReplayTransport(exchanges, strict=strict)
    async_transport = AsyncReplayTransport(exchanges, strict=strict)

    sync_patch = patch.object(
        httpx.Client,
        "_transport_for_url",
        _make_replay_wrapper(sync_transport),
    )
    async_patch = patch.object(
        httpx.AsyncClient,
        "_transport_for_url",
        _make_replay_wrapper(async_transport),
    )

    sync_patch.start()
    async_patch.start()

    return [sync_patch, async_patch]


def uninstall(patches: List[object]) -> None:
    """Stop all installed patches, restoring original transports."""
    for p in patches:
        try:
            p.stop()  # type: ignore[union-attr]
        except RuntimeError:
            pass  # Already stopped
