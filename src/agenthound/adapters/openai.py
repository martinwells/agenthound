"""OpenAI SDK adapter.

Parses OpenAI chat completion HTTP responses into LLMCall objects
and builds synthetic responses for mock testing.
"""
from __future__ import annotations

import json
import uuid
from typing import List, Union

from agenthound.adapters import BaseAdapter, register_adapter
from agenthound.models import HttpExchange, LLMCall, ToolCallRecord, UsageRecord


@register_adapter
class OpenAIAdapter(BaseAdapter):
    provider_name = "openai"

    @classmethod
    def matches_url(cls, url: str) -> bool:
        return "/v1/chat/completions" in url or "/v1/responses" in url

    @classmethod
    def parse_exchange(cls, exchange: HttpExchange, index: int = 0) -> LLMCall:
        body = exchange.response_body or {}
        req_body = exchange.request_body or {}

        model = body.get("model", req_body.get("model", ""))
        messages_in = req_body.get("messages", [])

        # Extract response text and tool calls
        response_text = ""
        tool_calls: List[ToolCallRecord] = []

        choices = body.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            response_text = message.get("content", "") or ""

            for tc in message.get("tool_calls", []):
                func = tc.get("function", {})
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except (json.JSONDecodeError, TypeError):
                    args = {"_raw": args_str}
                tool_calls.append(
                    ToolCallRecord(
                        tool_name=func.get("name", ""),
                        tool_call_id=tc.get("id", ""),
                        arguments=args,
                    )
                )

        # Usage
        usage_data = body.get("usage", {})
        usage = None
        if usage_data:
            usage = UsageRecord(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

        # Error
        error = None
        if exchange.response_status >= 400:
            err_obj = body.get("error", {})
            error = err_obj.get("message", f"HTTP {exchange.response_status}")

        return LLMCall(
            provider="openai",
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
        call_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        if isinstance(spec, str):
            # Plain text response
            return {
                "id": call_id,
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": spec},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            }

        if "tool_call" in spec:
            # Tool call response
            args = spec.get("args", {})
            tc_id = f"call_{uuid.uuid4().hex[:24]}"
            return {
                "id": call_id,
                "object": "chat.completion",
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tc_id,
                                    "type": "function",
                                    "function": {
                                        "name": spec["tool_call"],
                                        "arguments": json.dumps(args),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            }

        # Raw response body passthrough
        return spec

    @classmethod
    def _default_url(cls) -> str:
        return "https://api.openai.com/v1/chat/completions"
