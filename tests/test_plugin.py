"""Tests for the pytest plugin."""
from __future__ import annotations

import pytest


def test_plugin_loaded(pytestconfig):
    """Verify the agenthound plugin is registered."""
    plugin = pytestconfig.pluginmanager.get_plugin("agenthound")
    assert plugin is not None


def test_markers_registered(pytestconfig):
    """Verify AgentHound markers are registered."""
    marker_names = set()
    for m in pytestconfig.getini("markers"):
        name = m.split("(")[0].split(":")[0].strip()
        marker_names.add(name)
    assert "replay" in marker_names
    assert "mock_llm" in marker_names
    assert "inject_failure" in marker_names


def test_fixtures_dir_option(pytestconfig):
    """Verify the --agenthound-fixtures-dir option has a default."""
    val = pytestconfig.getoption("--agenthound-fixtures-dir")
    assert val == "tests/fixtures"
