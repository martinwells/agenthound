"""Manual LLM response mocking.

Provides the @mock_llm decorator for defining LLM responses programmatically
without recording a real session first.
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable, List, Union

from agenthound._patching import install_replay, uninstall
from agenthound.adapters import ADAPTER_REGISTRY
from agenthound.models import HttpExchange, LLMCall, SessionFixture
from agenthound.replayer import ReplaySession


def mock_llm(
    responses: List[Union[dict, str]],
    *,
    provider: str = "openai",
    model: str = "mock-model",
) -> Callable:
    """Decorator that mocks LLM responses with a predefined sequence.

    Usage::

        @mock_llm(responses=[
            {"tool_call": "search", "args": {"q": "weather"}},
            "The weather is sunny today.",
        ])
        def test_weather_agent(session):
            result = my_agent.run("What's the weather?")
            expect(session).tools_called(["search"])

    Each element in ``responses`` is either:
    - A string: treated as a plain text response
    - A dict with ``tool_call`` key: treated as a tool call response
    - A raw dict: passed through as the response body
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the right adapter
            adapter_cls = None
            for cls in ADAPTER_REGISTRY:
                if cls.provider_name == provider:
                    adapter_cls = cls
                    break
            if adapter_cls is None:
                raise ValueError(
                    f"No adapter found for provider '{provider}'. "
                    f"Available: {[c.provider_name for c in ADAPTER_REGISTRY]}"
                )

            # Build synthetic exchanges
            exchanges: List[HttpExchange] = []
            llm_calls: List[LLMCall] = []
            for i, spec in enumerate(responses):
                exchange = adapter_cls.build_exchange(spec, model=model)
                exchanges.append(exchange)
                llm_calls.append(adapter_cls.parse_exchange(exchange, index=i))

            fixture = SessionFixture(
                exchanges=exchanges,
                llm_calls=llm_calls,
            )
            session = ReplaySession(fixture)

            patches = install_replay(exchanges, strict=False)
            try:
                sig = inspect.signature(fn)
                if "session" in sig.parameters:
                    kwargs["session"] = session
                return fn(*args, **kwargs)
            finally:
                uninstall(patches)

        # Remove 'session' from the wrapper's visible signature so pytest
        # doesn't try to inject it as a fixture — @mock_llm provides it.
        sig = inspect.signature(fn)
        params = [p for name, p in sig.parameters.items() if name != "session"]
        wrapper.__signature__ = sig.replace(parameters=params)

        return wrapper

    return decorator
