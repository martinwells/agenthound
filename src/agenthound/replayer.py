"""Session replay for deterministic agent testing.

Provides the @replay decorator that loads a recorded fixture and serves
pre-recorded responses, enabling fully deterministic tests.
"""
from __future__ import annotations

import functools
import inspect
from collections import Counter
from typing import Any, Callable, Dict, List

from agenthound._patching import install_replay, uninstall
from agenthound.models import LLMCall, SessionFixture


class ReplaySession:
    """Provides access to fixture data during a replayed test.

    Passed as the ``session`` argument to test functions decorated with @replay.
    """

    def __init__(self, fixture: SessionFixture) -> None:
        self._fixture = fixture

    @property
    def fixture(self) -> SessionFixture:
        return self._fixture

    @property
    def llm_calls(self) -> List[LLMCall]:
        return self._fixture.llm_calls

    @property
    def tags(self) -> List[str]:
        return self._fixture.tags

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._fixture.metadata

    @property
    def total_duration_ms(self) -> float:
        return self._fixture.total_duration_ms

    @property
    def tools_called(self) -> List[str]:
        """Ordered list of all tool names called across all LLM responses."""
        names: List[str] = []
        for call in self._fixture.llm_calls:
            for tc in call.tool_calls:
                names.append(tc.tool_name)
        return names

    @property
    def tool_retries(self) -> Dict[str, int]:
        """Count of how many times each tool was called."""
        return dict(Counter(self.tools_called))

    @property
    def total_tokens(self) -> int:
        total = 0
        for call in self._fixture.llm_calls:
            if call.usage:
                total += call.usage.total_tokens
        return total


def load_fixture(path: str) -> SessionFixture:
    """Load a session fixture from a JSON file."""
    return SessionFixture.from_file(path)


def replay(
    fixture_path: str,
    *,
    strict: bool = True,
) -> Callable:
    """Decorator that replays a recorded session fixture during a test.

    Usage::

        @replay("fixtures/my_session.json")
        def test_my_agent(session):
            result = my_agent.run("Hello")
            expect(session).tools_called(["greet"])

    The decorator:
    1. Loads the fixture file
    2. Applies any failure injections (from @inject_failure)
    3. Installs a replay transport so all httpx calls return recorded responses
    4. Injects a ReplaySession as the ``session`` parameter
    5. Tears down after the test
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            fixture = load_fixture(fixture_path)

            # Apply failure injections if any were registered by @inject_failure
            failures = getattr(fn, "_agenthound_failures", [])
            if failures:
                fixture = _apply_failures(fixture, failures)

            session = ReplaySession(fixture)

            patches = install_replay(fixture.exchanges, strict=strict)
            try:
                sig = inspect.signature(fn)
                if "session" in sig.parameters:
                    kwargs["session"] = session
                return fn(*args, **kwargs)
            finally:
                uninstall(patches)

        # Remove 'session' from the wrapper's visible signature so pytest
        # doesn't try to inject it as a fixture — @replay provides it.
        sig = inspect.signature(fn)
        params = [p for name, p in sig.parameters.items() if name != "session"]
        wrapper.__signature__ = sig.replace(parameters=params)

        return wrapper

    return decorator


def _apply_failures(fixture: SessionFixture, failures: list) -> SessionFixture:
    """Apply failure injection mutations to a fixture's exchanges."""
    from agenthound.adapters import detect_adapter

    exchanges = [e.model_copy() for e in fixture.exchanges]
    llm_calls = list(fixture.llm_calls)

    for failure in failures:
        tool_name = failure["tool"]
        error_type = failure["error"]
        at_call = failure.get("at_call", 1)

        # Find the Nth exchange that contains a response with the target tool call
        tool_occurrence = 0
        for i, call in enumerate(llm_calls):
            for tc in call.tool_calls:
                if tc.tool_name == tool_name:
                    tool_occurrence += 1
                    if tool_occurrence == at_call:
                        # Replace this exchange with an error response
                        exc_idx = call.exchange_index
                        adapter_cls = detect_adapter(exchanges[exc_idx].request_url)
                        if adapter_cls is not None:
                            exchanges[exc_idx] = exchanges[exc_idx].model_copy(
                                update={
                                    "response_status": 500,
                                    "response_body": {
                                        "error": {
                                            "type": error_type,
                                            "message": (
                                                f"Injected {error_type} on "
                                                f"{tool_name} (call {at_call})"
                                            ),
                                        }
                                    },
                                }
                            )
                            # Update the LLM call to reflect the error
                            llm_calls[i] = call.model_copy(
                                update={
                                    "error": f"Injected {error_type}",
                                    "tool_calls": [],
                                    "response_text": "",
                                }
                            )
                        break
            else:
                continue
            break

    return fixture.model_copy(update={"exchanges": exchanges, "llm_calls": llm_calls})
