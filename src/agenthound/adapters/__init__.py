"""Framework adapter registry.

Adapters parse raw HttpExchange objects into semantic LLMCall objects
and build synthetic HTTP response bodies for mock testing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Type, Union

from agenthound.models import HttpExchange, LLMCall, UsageRecord


class BaseAdapter(ABC):
    """Abstract base for provider adapters."""

    provider_name: str = ""

    @classmethod
    @abstractmethod
    def matches_url(cls, url: str) -> bool:
        """Returns True if this URL belongs to this provider."""
        ...

    @classmethod
    @abstractmethod
    def parse_exchange(cls, exchange: HttpExchange, index: int = 0) -> LLMCall:
        """Parse an HTTP exchange into a semantic LLMCall."""
        ...

    @classmethod
    @abstractmethod
    def build_response_body(cls, spec: Union[dict, str], model: str = "mock-model") -> dict:
        """Build a provider-specific HTTP response body from a mock spec."""
        ...

    @classmethod
    def build_exchange(
        cls,
        spec: Union[dict, str],
        model: str = "mock-model",
    ) -> HttpExchange:
        """Build a complete synthetic HttpExchange from a mock spec."""
        body = cls.build_response_body(spec, model=model)
        return HttpExchange(
            request_url=cls._default_url(),
            request_method="POST",
            request_headers={"content-type": "application/json"},
            request_body={"model": model, "messages": []},
            response_status=200,
            response_headers={"content-type": "application/json"},
            response_body=body,
            timestamp=datetime.now(timezone.utc),
            duration_ms=0.0,
        )

    @classmethod
    def _default_url(cls) -> str:
        return ""


# Global adapter registry — populated by adapter modules on import
ADAPTER_REGISTRY: List[Type[BaseAdapter]] = []


def register_adapter(adapter_cls: Type[BaseAdapter]) -> Type[BaseAdapter]:
    """Register an adapter in the global registry."""
    ADAPTER_REGISTRY.append(adapter_cls)
    return adapter_cls


def detect_adapter(url: str) -> Optional[Type[BaseAdapter]]:
    """Find the adapter that matches a given URL."""
    for adapter_cls in ADAPTER_REGISTRY:
        if adapter_cls.matches_url(url):
            return adapter_cls
    return None


# Import adapter modules to trigger registration
from agenthound.adapters import anthropic as _anthropic_adapter  # noqa: E402, F401
from agenthound.adapters import openai as _openai_adapter  # noqa: E402, F401
