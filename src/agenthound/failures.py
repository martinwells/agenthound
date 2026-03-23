"""Failure injection for chaos testing agents.

Provides the @inject_failure decorator that injects errors at specific
points in a replayed session, testing agent resilience and recovery.
"""
from __future__ import annotations

from typing import Callable


def inject_failure(
    *,
    tool: str,
    error: str,
    at_call: int = 1,
) -> Callable:
    """Decorator that injects a failure at a specific tool call during replay.

    Must be composed with @replay. The @replay decorator reads the failure
    metadata and applies mutations to the fixture before replay begins.

    Usage::

        @replay("fixtures/refund.json")
        @inject_failure(tool="process_refund", error="TimeoutError", at_call=1)
        def test_refund_timeout(session):
            result = my_agent.run("Return order ORD-123")
            assert session.tool_retries["process_refund"] >= 1

    Args:
        tool: Name of the tool to inject failure on.
        error: Error type string (e.g., "TimeoutError", "RateLimitError").
        at_call: Which occurrence of the tool call to fail (1-based, default 1).
    """

    def decorator(fn: Callable) -> Callable:
        # Attach failure metadata to the function for @replay to pick up
        if not hasattr(fn, "_agenthound_failures"):
            fn._agenthound_failures = []  # type: ignore[attr-defined]
        fn._agenthound_failures.append(  # type: ignore[attr-defined]
            {"tool": tool, "error": error, "at_call": at_call}
        )
        return fn

    return decorator
