"""Graduated assertion engine for agent tests.

Provides the expect() API with a fluent interface for asserting on
session behavior (tools called, tokens, latency) and result content.

Assertion layers:
  1. Schema   — structure and count checks (free, deterministic)
  2. Constraints — tokens, latency budgets (free, deterministic)
  3. Trace    — tool call order and arguments (free, deterministic)
  4. Content  — text matching on responses/results (free, deterministic)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Union

from agenthound.replayer import ReplaySession

_MISSING = object()


class AgentHoundAssertionError(AssertionError):
    """Raised when an AgentHound assertion fails. Includes detailed context."""


def expect(target: Any) -> Union[SessionExpectation, ResultExpectation]:
    """Create an assertion builder for a session or result.

    Usage::

        expect(session).tools_called(["search", "respond"])
        expect(result).contains("ticket")
    """
    if isinstance(target, ReplaySession):
        return SessionExpectation(target)
    return ResultExpectation(target)


class SessionExpectation:
    """Fluent assertion builder for ReplaySession objects."""

    def __init__(self, session: ReplaySession) -> None:
        self._session = session

    # ── Layer 1: Schema ──────────────────────────────────────────────

    def has_llm_calls(self, n: int) -> SessionExpectation:
        """Assert exactly N LLM calls were made."""
        actual = len(self._session.llm_calls)
        if actual != n:
            raise AgentHoundAssertionError(
                f"Expected {n} LLM call(s), got {actual}.\n"
                f"Models used: {[c.model for c in self._session.llm_calls]}"
            )
        return self

    def has_llm_calls_between(self, min_n: int, max_n: int) -> SessionExpectation:
        """Assert LLM call count is within [min_n, max_n]."""
        actual = len(self._session.llm_calls)
        if not (min_n <= actual <= max_n):
            raise AgentHoundAssertionError(
                f"Expected between {min_n} and {max_n} LLM call(s), got {actual}."
            )
        return self

    def no_errors(self) -> SessionExpectation:
        """Assert no LLM calls resulted in errors."""
        errors = [(i, c.error) for i, c in enumerate(self._session.llm_calls) if c.error]
        if errors:
            details = "\n".join(f"  Call {i}: {e}" for i, e in errors)
            raise AgentHoundAssertionError(f"Expected no errors, but found:\n{details}")
        return self

    def all_calls_have_usage(self) -> SessionExpectation:
        """Assert every LLM call has token usage data."""
        missing = [i for i, c in enumerate(self._session.llm_calls) if c.usage is None]
        if missing:
            raise AgentHoundAssertionError(
                f"Expected all calls to have usage data, but calls at "
                f"indices {missing} are missing usage."
            )
        return self

    # ── Layer 2: Constraints ─────────────────────────────────────────

    def total_tokens_under(self, max_tokens: int) -> SessionExpectation:
        """Assert total token count is under max_tokens."""
        actual = self._session.total_tokens
        if actual >= max_tokens:
            raise AgentHoundAssertionError(
                f"Expected under {max_tokens} tokens, got {actual}."
            )
        return self

    def latency_under(self, max_ms: float) -> SessionExpectation:
        """Assert total session duration is under max_ms milliseconds."""
        actual = self._session.total_duration_ms
        if actual >= max_ms:
            raise AgentHoundAssertionError(
                f"Expected latency under {max_ms}ms, got {actual:.1f}ms."
            )
        return self

    def max_turns(self, n: int) -> SessionExpectation:
        """Assert number of LLM round-trips is at most N."""
        actual = len(self._session.llm_calls)
        if actual > n:
            raise AgentHoundAssertionError(
                f"Expected at most {n} turn(s), got {actual}."
            )
        return self

    # ── Layer 3: Trace ───────────────────────────────────────────────

    def tools_called(self, expected: List[str]) -> SessionExpectation:
        """Assert tools were called in exactly this order."""
        actual = self._session.tools_called
        if actual != expected:
            raise AgentHoundAssertionError(
                f"Expected tools called: {expected}\n"
                f"Actual tools called:   {actual}"
            )
        return self

    def tools_called_unordered(self, expected: Set[str]) -> SessionExpectation:
        """Assert this exact set of tools was called (order doesn't matter)."""
        actual = set(self._session.tools_called)
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            msg = f"Expected tools: {sorted(expected)}\nActual tools:   {sorted(actual)}"
            if missing:
                msg += f"\nMissing: {sorted(missing)}"
            if extra:
                msg += f"\nUnexpected: {sorted(extra)}"
            raise AgentHoundAssertionError(msg)
        return self

    def tool_called(self, name: str, *, times: Optional[int] = None) -> SessionExpectation:
        """Assert a specific tool was called, optionally exactly N times."""
        retries = self._session.tool_retries
        actual_count = retries.get(name, 0)
        if actual_count == 0:
            raise AgentHoundAssertionError(
                f"Expected tool '{name}' to be called, but it was never called.\n"
                f"Tools called: {self._session.tools_called}"
            )
        if times is not None and actual_count != times:
            raise AgentHoundAssertionError(
                f"Expected tool '{name}' to be called {times} time(s), "
                f"got {actual_count}."
            )
        return self

    def tool_called_with(self, name: str, args: Dict[str, Any]) -> SessionExpectation:
        """Assert a tool was called with arguments that are a superset of args."""
        for call in self._session.llm_calls:
            for tc in call.tool_calls:
                if tc.tool_name == name:
                    if all(tc.arguments.get(k) == v for k, v in args.items()):
                        return self
        raise AgentHoundAssertionError(
            f"Expected tool '{name}' to be called with args containing {args}, "
            f"but no matching call was found."
        )

    def no_tool_errors(self) -> SessionExpectation:
        """Assert no tool calls resulted in errors."""
        errors = []
        for call in self._session.llm_calls:
            for tc in call.tool_calls:
                if tc.error:
                    errors.append((tc.tool_name, tc.error))
        if errors:
            details = "\n".join(f"  {name}: {err}" for name, err in errors)
            raise AgentHoundAssertionError(f"Expected no tool errors, but found:\n{details}")
        return self

    def tool_sequence(self, expected: List[str]) -> SessionExpectation:
        """Assert tools were called in this subsequence order."""
        actual = self._session.tools_called
        it = iter(actual)
        for tool in expected:
            if tool not in it:
                raise AgentHoundAssertionError(
                    f"Expected tool sequence {expected} to appear as a "
                    f"subsequence of {actual}"
                )
        return self

    def model_used(self, model: str) -> SessionExpectation:
        """Assert all LLM calls used this model."""
        mismatches = [
            (i, c.model) for i, c in enumerate(self._session.llm_calls) if c.model != model
        ]
        if mismatches:
            details = "\n".join(f"  Call {i}: {m}" for i, m in mismatches)
            raise AgentHoundAssertionError(
                f"Expected all calls to use model '{model}', but found:\n{details}"
            )
        return self

    def completed_successfully(self) -> SessionExpectation:
        """Assert the session completed without errors."""
        return self.no_errors().no_tool_errors()

    # ── Layer 4: Content ─────────────────────────────────────────────

    def final_response_contains(self, text: str) -> SessionExpectation:
        """Assert the last LLM response contains the given text."""
        if not self._session.llm_calls:
            raise AgentHoundAssertionError("No LLM calls in session.")
        last = self._session.llm_calls[-1].response_text
        if text.lower() not in last.lower():
            raise AgentHoundAssertionError(
                f"Expected final response to contain '{text}'.\n"
                f"Final response: {last[:200]}{'...' if len(last) > 200 else ''}"
            )
        return self

    def any_response_contains(self, text: str) -> SessionExpectation:
        """Assert any LLM response in the session contains the given text."""
        for call in self._session.llm_calls:
            if text.lower() in call.response_text.lower():
                return self
        raise AgentHoundAssertionError(
            f"Expected at least one response to contain '{text}', but none did."
        )

    def final_response_matches(self, pattern: str) -> SessionExpectation:
        """Assert the last LLM response matches the given regex pattern."""
        if not self._session.llm_calls:
            raise AgentHoundAssertionError("No LLM calls in session.")
        last = self._session.llm_calls[-1].response_text
        if not re.search(pattern, last, re.IGNORECASE):
            raise AgentHoundAssertionError(
                f"Expected final response to match pattern '{pattern}'.\n"
                f"Final response: {last[:200]}{'...' if len(last) > 200 else ''}"
            )
        return self

class ResultExpectation:
    """Fluent assertion builder for agent result values."""

    def __init__(self, result: Any) -> None:
        self._result = result

    def contains(self, text: str) -> ResultExpectation:
        """Assert the result contains the given text (case-insensitive)."""
        result_str = str(self._result)
        if text.lower() not in result_str.lower():
            raise AgentHoundAssertionError(
                f"Expected result to contain '{text}'.\n"
                f"Result: {result_str[:200]}{'...' if len(result_str) > 200 else ''}"
            )
        return self

    def matches(self, pattern: str) -> ResultExpectation:
        """Assert the result matches the given regex pattern."""
        result_str = str(self._result)
        if not re.search(pattern, result_str):
            raise AgentHoundAssertionError(
                f"Expected result to match pattern '{pattern}'.\n"
                f"Result: {result_str[:200]}{'...' if len(result_str) > 200 else ''}"
            )
        return self

    def equals(self, expected: Any) -> ResultExpectation:
        """Assert the result equals the expected value."""
        if self._result != expected:
            raise AgentHoundAssertionError(
                f"Expected result to equal {expected!r}, got {self._result!r}"
            )
        return self

    def is_type(self, t: type) -> ResultExpectation:
        """Assert the result is an instance of the given type."""
        if not isinstance(self._result, t):
            raise AgentHoundAssertionError(
                f"Expected result to be {t.__name__}, "
                f"got {type(self._result).__name__}"
            )
        return self

    def has_field(self, name: str, value: Any = _MISSING) -> ResultExpectation:
        """Assert the result has an attribute with the given name (and optionally value)."""
        if not hasattr(self._result, name):
            raise AgentHoundAssertionError(
                f"Expected result to have attribute '{name}', but it doesn't.\n"
                f"Available attributes: {[a for a in dir(self._result) if not a.startswith('_')]}"
            )
        if value is not _MISSING:
            actual = getattr(self._result, name)
            if actual != value:
                raise AgentHoundAssertionError(
                    f"Expected result.{name} to equal {value!r}, got {actual!r}"
                )
        return self
