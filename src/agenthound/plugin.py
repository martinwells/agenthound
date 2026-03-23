"""pytest plugin for AgentHound.

Registers markers, fixtures, and CLI options so AgentHound integrates
seamlessly with the pytest ecosystem.
"""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register AgentHound markers."""
    config.addinivalue_line("markers", "replay(path): replay a recorded session fixture")
    config.addinivalue_line("markers", "mock_llm(responses): mock LLM responses")
    config.addinivalue_line("markers", "inject_failure(tool, error): inject a failure")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add AgentHound CLI options."""
    group = parser.getgroup("agenthound", "AgentHound options")
    group.addoption(
        "--agenthound-record",
        action="store_true",
        default=False,
        help="Run tests in recording mode (real API calls, save fixtures).",
    )
    group.addoption(
        "--agenthound-update",
        action="store_true",
        default=False,
        help="Re-record fixtures that already exist.",
    )
    group.addoption(
        "--agenthound-fixtures-dir",
        default="tests/fixtures",
        help="Default directory for fixture files (default: tests/fixtures).",
    )


@pytest.fixture
def agenthound_fixtures_dir(request: pytest.FixtureRequest) -> str:
    """The configured fixtures directory."""
    return request.config.getoption("--agenthound-fixtures-dir")  # type: ignore[return-value]


@pytest.fixture
def agenthound_recording(request: pytest.FixtureRequest) -> bool:
    """Whether recording mode is active."""
    return request.config.getoption("--agenthound-record")  # type: ignore[return-value]
