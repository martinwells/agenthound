"""Auto-recording and @recorded decorator for agent workflows.

Provides two features:
- auto_record() / stop_auto_record(): global auto-recording with idle-time session splitting
- @recorded(): decorator that records each function invocation as a separate fixture
"""
from __future__ import annotations

import functools
import os
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TypeVar

from agenthound._patching import install_recording, uninstall
from agenthound.models import HttpExchange
from agenthound.recorder import build_fixture, record_session

F = TypeVar("F", bound=Callable[..., Any])

# Idle timeout in seconds — if no API call arrives within this window,
# the current session is considered finished and flushed to disk.
_IDLE_TIMEOUT_SECONDS = 2.0

# ---------------------------------------------------------------------------
# Module-level state for auto_record
# ---------------------------------------------------------------------------
_auto_record_lock = threading.Lock()
_auto_record_active = False
_auto_record_patches: List[object] = []
_auto_record_exchange_log: List[HttpExchange] = []
_auto_record_output_dir: str = ""
_auto_record_tags: Optional[List[str]] = None
_auto_record_metadata: Optional[Dict[str, Any]] = None
_auto_record_sequence: int = 0
_auto_record_timer: Optional[threading.Timer] = None
_auto_record_session_start: Optional[datetime] = None
# Tracks the boundary index in _auto_record_exchange_log — exchanges before
# this index have already been flushed.
_auto_record_flush_index: int = 0


def _generate_filename(output_dir: str, seq: int, ts: Optional[datetime] = None) -> str:
    """Generate a fixture filename from a timestamp and sequence number."""
    if ts is None:
        ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y-%m-%dT%H-%M-%S")
    return os.path.join(output_dir, f"{ts_str}_{seq:03d}.json")


def _flush_session() -> None:
    """Flush the current accumulated exchanges to a fixture file.

    Called either by the idle timer or when stop_auto_record() is invoked.
    Must be called while holding _auto_record_lock.
    """
    global _auto_record_sequence, _auto_record_flush_index, _auto_record_session_start

    exchanges = _auto_record_exchange_log[_auto_record_flush_index:]
    if not exchanges:
        return

    _auto_record_sequence += 1
    path = _generate_filename(
        _auto_record_output_dir,
        _auto_record_sequence,
        _auto_record_session_start,
    )

    fixture = build_fixture(
        list(exchanges),
        tags=list(_auto_record_tags) if _auto_record_tags else None,
        metadata=dict(_auto_record_metadata) if _auto_record_metadata else None,
    )
    fixture.to_file(path)

    _auto_record_flush_index = len(_auto_record_exchange_log)
    _auto_record_session_start = None


def _on_idle_timeout() -> None:
    """Timer callback: flush session when idle timeout fires."""
    with _auto_record_lock:
        if not _auto_record_active:
            return
        _flush_session()


def _schedule_idle_timer() -> None:
    """(Re)schedule the idle-timeout timer. Must be called with lock held."""
    global _auto_record_timer
    if _auto_record_timer is not None:
        _auto_record_timer.cancel()
    _auto_record_timer = threading.Timer(_IDLE_TIMEOUT_SECONDS, _on_idle_timeout)
    _auto_record_timer.daemon = True
    _auto_record_timer.start()


class _AutoRecordExchangeLog(list):
    """A list subclass that detects new exchanges being appended.

    When a new exchange is appended, it resets the idle timer so the session
    boundary is detected after 2 seconds of inactivity.
    """

    def append(self, item: Any) -> None:
        global _auto_record_session_start
        with _auto_record_lock:
            # Check if this is a new session (first exchange after a flush)
            if len(self) == _auto_record_flush_index:
                _auto_record_session_start = datetime.now(timezone.utc)
            super().append(item)
            if _auto_record_active:
                _schedule_idle_timer()


def auto_record(
    output_dir: str,
    *,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Enable global auto-recording of all LLM API calls.

    Sessions are split by idle time: if no API call happens for 2+ seconds,
    the current session is flushed to a fixture file and a new one begins on
    the next call.

    Each session is saved as ``{output_dir}/{timestamp}_{sequence}.json``.

    Call :func:`stop_auto_record` to disable and flush any pending session.
    """
    global _auto_record_active, _auto_record_patches, _auto_record_exchange_log
    global _auto_record_output_dir, _auto_record_tags, _auto_record_metadata
    global _auto_record_sequence, _auto_record_flush_index, _auto_record_session_start

    with _auto_record_lock:
        if _auto_record_active:
            raise RuntimeError("auto_record is already active; call stop_auto_record() first")

        _auto_record_output_dir = output_dir
        _auto_record_tags = list(tags) if tags else None
        _auto_record_metadata = dict(metadata) if metadata else None
        _auto_record_sequence = 0
        _auto_record_flush_index = 0
        _auto_record_session_start = None

        exchange_log = _AutoRecordExchangeLog()
        _auto_record_exchange_log = exchange_log  # type: ignore[assignment]
        _auto_record_patches = install_recording(exchange_log)  # type: ignore[arg-type]
        _auto_record_active = True


def stop_auto_record() -> None:
    """Disable global auto-recording and flush any pending session."""
    global _auto_record_active, _auto_record_timer

    with _auto_record_lock:
        if not _auto_record_active:
            return

        # Cancel any pending timer
        if _auto_record_timer is not None:
            _auto_record_timer.cancel()
            _auto_record_timer = None

        _auto_record_active = False
        uninstall(_auto_record_patches)

        # Flush remaining exchanges
        _flush_session()


# ---------------------------------------------------------------------------
# @recorded decorator
# ---------------------------------------------------------------------------

def recorded(
    output_dir: str,
    *,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """Decorator that records each invocation of a function as a separate session fixture.

    Usage::

        @agenthound.recorded("sessions/", tags=["support"])
        def handle_support_request(user_input):
            return agent.run(user_input)

        # Each call saves a fixture
        handle_support_request("Return order ORD-100")
    """
    _seq_lock = threading.Lock()
    _seq = [0]  # mutable counter inside closure

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with _seq_lock:
                _seq[0] += 1
                seq = _seq[0]
            ts = datetime.now(timezone.utc)
            path = _generate_filename(output_dir, seq, ts)

            merged_metadata: Optional[Dict[str, Any]] = None
            if metadata:
                merged_metadata = dict(metadata)

            with record_session(path, metadata=merged_metadata) as session:
                if tags:
                    session.tag(*tags)
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
