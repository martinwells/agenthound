"""Import OpenTelemetry JSON trace exports into AgentHound fixture format.

Reads OTEL JSON files (e.g. from Langfuse, Jaeger, or the OTEL Collector)
and converts LLM-related spans into a SessionFixture with LLMCall entries.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional

from agenthound.models import (
    LLMCall,
    ToolCallRecord,
    UsageRecord,
)
from agenthound.recorder import build_fixture

# Span names (or substrings thereof) that indicate an LLM call
_LLM_SPAN_PATTERNS = re.compile(
    r"(chat[._]completions?|messages|completions?\.create|embeddings)", re.IGNORECASE
)

# Span names that indicate a tool call child span
_TOOL_SPAN_PATTERN = re.compile(r"tool", re.IGNORECASE)


def _get_attr(attrs: List[Dict[str, Any]], key: str) -> Optional[str]:
    """Extract a string attribute value from an OTEL attributes list."""
    for attr in attrs:
        if attr.get("key") == key:
            value = attr.get("value", {})
            # OTEL attribute values are typed: stringValue, intValue, etc.
            if "stringValue" in value:
                return value["stringValue"]
            if "intValue" in value:
                return str(value["intValue"])
            if "doubleValue" in value:
                return str(value["doubleValue"])
            if "boolValue" in value:
                return str(value["boolValue"])
    return None


def _get_int_attr(attrs: List[Dict[str, Any]], key: str) -> int:
    """Extract an integer attribute value, defaulting to 0."""
    val = _get_attr(attrs, key)
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _is_llm_span(span: Dict[str, Any]) -> bool:
    """Determine if a span represents an LLM API call."""
    name = span.get("name", "")
    attrs = span.get("attributes", [])

    # Check for gen_ai.* attributes — definitive signal
    for attr in attrs:
        key = attr.get("key", "")
        if key.startswith("gen_ai."):
            return True

    # Fallback: check span name
    if _LLM_SPAN_PATTERNS.search(name):
        return True

    return False


def _extract_tool_calls_from_children(
    span_id: str, all_spans: List[Dict[str, Any]]
) -> List[ToolCallRecord]:
    """Find child spans that represent tool calls and convert them."""
    tools: List[ToolCallRecord] = []
    for span in all_spans:
        parent_id = span.get("parentSpanId", "")
        if parent_id != span_id:
            continue
        name = span.get("name", "")
        if not _TOOL_SPAN_PATTERN.search(name):
            continue
        attrs = span.get("attributes", [])
        tool_name = _get_attr(attrs, "tool.name") or _get_attr(attrs, "gen_ai.tool.name") or name
        tool_call_id = _get_attr(attrs, "tool.call_id") or ""
        # Try to extract arguments from attributes
        args_raw = _get_attr(attrs, "tool.arguments") or _get_attr(attrs, "tool.parameters")
        arguments: Dict[str, Any] = {}
        if args_raw:
            try:
                arguments = json.loads(args_raw)
            except (json.JSONDecodeError, TypeError):
                arguments = {"raw": args_raw}
        result = _get_attr(attrs, "tool.result") or _get_attr(attrs, "tool.output")
        error = _get_attr(attrs, "tool.error") or _get_attr(attrs, "otel.status_description")
        tools.append(
            ToolCallRecord(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                arguments=arguments,
                result=result,
                error=error,
            )
        )
    return tools


def _span_to_llm_call(
    span: Dict[str, Any], index: int, all_spans: List[Dict[str, Any]]
) -> LLMCall:
    """Convert a single OTEL span into an LLMCall."""
    attrs = span.get("attributes", [])

    provider = _get_attr(attrs, "gen_ai.system") or ""
    model = (
        _get_attr(attrs, "gen_ai.request.model")
        or _get_attr(attrs, "gen_ai.response.model")
        or ""
    )
    input_tokens = _get_int_attr(attrs, "gen_ai.usage.input_tokens")
    output_tokens = _get_int_attr(attrs, "gen_ai.usage.output_tokens")
    total_tokens = _get_int_attr(attrs, "gen_ai.usage.total_tokens")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    # Duration from nanosecond timestamps
    start_ns = int(span.get("startTimeUnixNano", "0"))
    end_ns = int(span.get("endTimeUnixNano", "0"))
    duration_ms = (end_ns - start_ns) / 1_000_000.0 if end_ns > start_ns else 0.0

    # Build usage record
    usage = UsageRecord(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )

    # Extract tool calls from child spans
    span_id = span.get("spanId", "")
    tool_calls = _extract_tool_calls_from_children(span_id, all_spans)

    # Check for error status
    status = span.get("status", {})
    error: Optional[str] = None
    if status.get("code") == 2:  # OTEL StatusCode.ERROR
        error = status.get("message") or _get_attr(attrs, "otel.status_description")

    return LLMCall(
        provider=provider,
        model=model,
        usage=usage,
        duration_ms=round(duration_ms, 2),
        tool_calls=tool_calls,
        error=error,
        exchange_index=index,
    )


def _collect_all_spans(otel_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten all spans from the OTEL JSON structure."""
    spans: List[Dict[str, Any]] = []
    for resource_span in otel_data.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            spans.extend(scope_span.get("spans", []))
    return spans


def import_otel_trace(otel_json_path: str, output_path: str) -> str:
    """Convert an OpenTelemetry JSON trace export into an AgentHound fixture.

    Args:
        otel_json_path: Path to the OTEL JSON file.
        output_path: Path where the AgentHound fixture will be saved.

    Returns:
        The output path (same as the *output_path* argument).
    """
    raw = pathlib.Path(otel_json_path).read_text()
    otel_data = json.loads(raw)

    all_spans = _collect_all_spans(otel_data)

    # Filter to LLM spans and sort by start time
    llm_spans = [s for s in all_spans if _is_llm_span(s)]
    llm_spans.sort(key=lambda s: int(s.get("startTimeUnixNano", "0")))

    # Convert to LLMCall objects
    llm_calls: List[LLMCall] = []
    for i, span in enumerate(llm_spans):
        llm_calls.append(_span_to_llm_call(span, index=i, all_spans=all_spans))

    # Build fixture with pre-computed llm_calls (no exchanges since we don't
    # have raw HTTP data from OTEL traces)
    fixture = build_fixture(
        exchanges=[],
        llm_calls=llm_calls,
        metadata={"source": "otel", "import_file": otel_json_path},
    )
    fixture.to_file(output_path)

    return output_path


def cli_main() -> None:
    """Entry point for the ``agenthound-import`` CLI command."""
    if len(sys.argv) < 2:
        print("Usage: agenthound-import <format> <input> <output>", file=sys.stderr)
        print("Supported formats: otel", file=sys.stderr)
        sys.exit(1)

    fmt = sys.argv[1]

    if fmt == "otel":
        if len(sys.argv) != 4:
            print("Usage: agenthound-import otel <input.json> <output.json>", file=sys.stderr)
            sys.exit(1)
        input_path = sys.argv[2]
        output_path_arg = sys.argv[3]
        result = import_otel_trace(input_path, output_path_arg)
        print(f"Fixture written to {result}")
    else:
        print(f"Unknown format: {fmt}", file=sys.stderr)
        print("Supported formats: otel", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
