"""Anthropic SDK adapter.

Parses Anthropic Messages API HTTP responses into LLMCall objects
and builds synthetic responses for mock testing.
"""
from __future__ import annotations

import uuid
from typing import List, Union

from agenthound.adapters import BaseAdapter, register_adapter
from agenthound.models import HttpExchange, LLMCall, ToolCallRecord, UsageRecord


@register_adapter
class AnthropicAdapter(BaseAdapter):
    provider_name = "anthropic"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return "/v1/messages" in url

    @classmethod
    def parse_exchange(cls, exchange: HttpExchange, index: int = 0) -> LLMCall:
        body = exchange.response_body or {}
        req_body = exchange.request_body or {}

        model = body.get("model", req_body.get("model", ""))
        messages_in = req_body.get("messages", [])

        # Extract response text and tool calls from content blocks
        response_text = ""
        tool_calls: List[ToolCallRecord] = []

        for block in body.get("content", []):
            if block.get("type") == "text":
                response_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCallRecord(
                        tool_name=block.get("name", ""),
                        tool_call_id=block.get("id", ""),
                        arguments=block.get("input", {}),
                    )
                )

        # Usage
        usage_data = body.get("usage", {})
        usage = None
        if usage_data:
            input_tokens = usage_data.get("input_tokens", 0)
            output_tokens = usage_data.get("output_tokens", 0)
            usage = UsageRecord(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            )

        # Error
        error = None
        if exchange.response_status >= 400:
            err_obj = body.get("error", {})
            error = err_obj.get("message", f"HTTP {exchange.response_status}")

        return LLMCall(
            provider="anthropic",
            model=model,
            messages_in=messages_in,
            response=body,
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            duration_ms=exchange.duration_ms,
            error=error,
            exchange_index=index,
        )

    @classmethod
    def build_response_body(cls, spec: Union[dict, str], model: str = "mock-model") -> dict:
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        if isinstance(spec, str):
            return {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [{"type": "text", "text": spec}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 10},
            }

        if "tool_call" in spec:
            args = spec.get("args", {})
            tc_id = f"toolu_{uuid.uuid4().hex[:24]}"
            return {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [
                    {
                        "type": "tool_use",
                        "id": tc_id,
                        "name": spec["tool_call"],
                        "input": args,
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 10},
            }

        return spec

    @classmethod
    def _default_url(cls) -> str:
        return "https://api.anthropic.com/v1/messages"
