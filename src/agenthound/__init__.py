"""AgentHound: Tracks down every bug in your agent workflow."""
from __future__ import annotations

from agenthound._version import __version__
from agenthound.assertions import AgentHoundAssertionError, expect
from agenthound.auto_record import auto_record, recorded, stop_auto_record
from agenthound.failures import inject_failure
from agenthound.mock_llm import mock_llm
from agenthound.mock_tool import mock_tool
from agenthound.models import HttpExchange, LLMCall, SessionFixture, ToolCallRecord, UsageRecord
from agenthound.recorder import record_session
from agenthound.replayer import ReplaySession, load_fixture, replay

__all__ = [
    "__version__",
    # Core workflow
    "record_session",
    "replay",
    "load_fixture",
    "expect",
    # Auto-recording
    "auto_record",
    "stop_auto_record",
    "recorded",
    # Mocking
    "mock_llm",
    "mock_tool",
    "inject_failure",
    # Data models
    "SessionFixture",
    "LLMCall",
    "ToolCallRecord",
    "HttpExchange",
    "UsageRecord",
    # Session
    "ReplaySession",
    # Errors
    "AgentHoundAssertionError",
]
