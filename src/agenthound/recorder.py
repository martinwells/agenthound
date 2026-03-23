"""Session recording for agent workflows.

Provides the record_session() context manager that captures all LLM API calls
made during agent execution and saves them as a replayable JSON fixture.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from agenthound._patching import install_recording, uninstall
from agenthound.adapters import detect_adapter
from agenthound.models import HttpExchange, LLMCall, SessionFixture


def build_fixture(
    exchanges: List[HttpExchange],
    *,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    llm_calls: Optional[List[LLMCall]] = None,
) -> SessionFixture:
    """Build a SessionFixture from a list of recorded exchanges.

    This is the shared fixture-building logic used by record_session,
    auto_record, and importers. If *llm_calls* is not provided, exchanges
    are parsed via adapter detection.
    """
    if llm_calls is None:
        llm_calls = []
        for i, exchange in enumerate(exchanges):
            adapter_cls = detect_adapter(exchange.request_url)
            if adapter_cls is not None:
                llm_calls.append(adapter_cls.parse_exchange(exchange, index=i))

    total_duration = 0.0
    for call in llm_calls:
        total_duration += call.duration_ms

    return SessionFixture(
        tags=tags or [],
        metadata=metadata or {},
        exchanges=exchanges,
        llm_calls=llm_calls,
        total_duration_ms=round(total_duration, 2),
    )


class RecordingSession:
    """Accumulates recorded exchanges during a session.

    Yielded by the record_session() context manager.
    """

    def __init__(self, exchange_log: List[HttpExchange]) -> None:
        self._exchange_log = exchange_log
        self._tags: List[str] = []
        self._metadata: Dict[str, Any] = {}

    def tag(self, *tags: str) -> None:
        """Add tags to the session for filtering and organization."""
        self._tags.extend(tags)

    def annotate(self, **kwargs: Any) -> None:
        """Add arbitrary metadata to the session."""
        self._metadata.update(kwargs)

    @property
    def exchanges(self) -> List[HttpExchange]:
        return self._exchange_log

    @property
    def tags(self) -> List[str]:
        return self._tags

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata


@contextmanager
def record_session(
    output_path: str,
    *,
    metadata: Optional[Dict[str, Any]] = None,
) -> Iterator[RecordingSession]:
    """Record all LLM API calls and save them as a fixture.

    Usage::

        with record_session("tests/fixtures/my_test.json") as session:
            result = my_agent.run("Hello")
            session.tag("happy_path")

    The fixture file is written on context exit and can be used with
    the @replay decorator for deterministic test execution.
    """
    exchange_log: List[HttpExchange] = []
    session = RecordingSession(exchange_log)

    if metadata:
        session.annotate(**metadata)

    patches = install_recording(exchange_log)
    exc_occurred = False
    try:
        yield session
    except BaseException:
        exc_occurred = True
        raise
    finally:
        uninstall(patches)

        # Only write fixture if the with-block completed without exception
        if not exc_occurred:
            fixture = build_fixture(
                exchange_log,
                tags=session.tags,
                metadata=session.metadata,
            )
            fixture.to_file(output_path)
