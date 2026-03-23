"""Core data models for AgentHound fixture files.

The fixture schema has two layers:
- exchanges: raw HTTP request/response pairs (used by replay transport)
- llm_calls: semantic LLM call data (used by assertion engine)
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Headers that are redacted by default when writing fixtures
_REDACT_HEADERS = {"authorization", "x-api-key", "api-key"}


class HttpExchange(BaseModel):
    """A single HTTP request-response pair captured at the httpx transport level."""

    request_url: str
    request_method: str = "POST"
    request_headers: Dict[str, str] = Field(default_factory=dict)
    request_body: Optional[Any] = None
    response_status: int = 200
    response_headers: Dict[str, str] = Field(default_factory=dict)
    response_body: Optional[Any] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0

    def redacted(self) -> HttpExchange:
        """Return a copy with sensitive headers replaced by [REDACTED]."""
        redacted_headers = {
            k: "[REDACTED]" if k.lower() in _REDACT_HEADERS else v
            for k, v in self.request_headers.items()
        }
        return self.model_copy(update={"request_headers": redacted_headers})


class ToolCallRecord(BaseModel):
    """A tool call extracted from an LLM response."""

    tool_name: str
    tool_call_id: str = ""
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None


class UsageRecord(BaseModel):
    """Token usage for a single LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class LLMCall(BaseModel):
    """Semantic view of a single LLM API call, parsed from an HttpExchange."""

    provider: str  # "openai" | "anthropic"
    model: str = ""
    messages_in: List[Dict[str, Any]] = Field(default_factory=list)
    response: Dict[str, Any] = Field(default_factory=dict)
    response_text: str = ""
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    usage: Optional[UsageRecord] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    exchange_index: int = 0


class SessionFixture(BaseModel):
    """Root model for a recorded agent session. Serialized to/from JSON fixture files."""

    version: str = "1.0"
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    exchanges: List[HttpExchange] = Field(default_factory=list)
    llm_calls: List[LLMCall] = Field(default_factory=list)
    total_duration_ms: float = 0.0

    def to_file(self, path: str) -> None:
        """Write this fixture to a JSON file."""
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Redact auth headers before writing
        redacted_exchanges = [e.redacted() for e in self.exchanges]
        data = self.model_copy(update={"exchanges": redacted_exchanges}).model_dump(mode="json")
        p.write_text(json.dumps(data, indent=2, default=str) + "\n")

    @classmethod
    def from_file(cls, path: str) -> SessionFixture:
        """Load a fixture from a JSON file."""
        text = pathlib.Path(path).read_text()
        data = json.loads(text)
        # Check schema version
        version = data.get("version", "1.0")
        if not version.startswith("1."):
            raise ValueError(
                f"Unsupported fixture schema version: {version}. "
                f"This version of agenthound supports 1.x."
            )
        return cls.model_validate(data)
