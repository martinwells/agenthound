"""Tool function mocking.

Provides the @mock_tool decorator for replacing tool functions
with mock implementations during tests.
"""
from __future__ import annotations

import functools
from typing import Any, Callable, Optional
from unittest.mock import patch

_MISSING = object()


def mock_tool(
    name: str,
    *,
    target: str,
    returns: Any = _MISSING,
    side_effect: Optional[Callable] = None,
) -> Callable:
    """Decorator that mocks a tool function during a test.

    Usage::

        @mock_tool("search", target="myapp.tools.search", returns={"results": []})
        def test_with_mocked_search():
            result = my_agent.run("Search for something")
            ...

    Args:
        name: The tool name (for documentation/identification).
        target: The import path to patch (e.g., "myapp.tools.search_fn").
        returns: The value the mock should return.
        side_effect: A callable to use as the mock's side_effect.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            mock_kwargs: dict = {}
            if returns is not _MISSING:
                mock_kwargs["return_value"] = returns
            if side_effect is not None:
                mock_kwargs["side_effect"] = side_effect

            with patch(target, **mock_kwargs):
                return fn(*args, **kwargs)

        return wrapper

    return decorator
