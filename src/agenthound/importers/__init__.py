"""Importers for converting external trace formats into AgentHound fixtures.

Currently supported:
- OTEL (OpenTelemetry) JSON trace exports
"""
from __future__ import annotations

from agenthound.importers.otel import import_otel_trace

__all__ = ["import_otel_trace"]
