"""A minimal customer support agent for demonstrating AgentHound.

This agent handles order lookups and refund processing using the OpenAI SDK.
In a real application, the tool functions would call your backend services.
"""
from __future__ import annotations

import json

import httpx

# ---------------------------------------------------------------------------
# Tools — in a real app these would call your database / payment API
# ---------------------------------------------------------------------------

ORDERS = {
    "ORD-100": {"status": "delivered", "total": 29.99, "item": "Wireless Mouse"},
    "ORD-200": {"status": "shipped", "total": 149.00, "item": "Mechanical Keyboard"},
    "ORD-300": {"status": "delivered", "total": 59.99, "item": "USB-C Hub"},
}


def lookup_order(order_id: str) -> dict:
    """Look up an order by ID."""
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": f"Order {order_id} not found"}
    return {"order_id": order_id, **order}


def process_refund(order_id: str, amount: float) -> dict:
    """Process a refund for an order."""
    order = ORDERS.get(order_id)
    if order is None:
        return {"error": f"Order {order_id} not found"}
    if order["status"] != "delivered":
        return {"error": f"Cannot refund order with status '{order['status']}'"}
    return {"success": True, "refund_id": f"REF-{order_id[4:]}", "amount": amount}


# ---------------------------------------------------------------------------
# Tool definitions for the OpenAI API
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up an order by its ID to get status and details.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "process_refund",
            "description": "Process a refund for a delivered order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["order_id", "amount"],
            },
        },
    },
]

TOOL_MAP = {
    "lookup_order": lookup_order,
    "process_refund": process_refund,
}

SYSTEM_PROMPT = (
    "You are a helpful customer support agent. "
    "Use the available tools to look up orders and process refunds. "
    "Be concise and professional."
)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


def run_agent(user_message: str, api_key: str = "test-key") -> str:
    """Run the support agent with a user message and return the final response.

    This is a standard OpenAI tool-use loop:
    1. Send messages to the API
    2. If the response contains tool calls, execute them and send results back
    3. Repeat until the model returns a text response
    """
    client = httpx.Client()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = "https://api.openai.com/v1/chat/completions"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for _ in range(10):  # Max iterations to prevent infinite loops
        response = client.post(
            url,
            headers=headers,
            json={"model": "gpt-4o-mini", "messages": messages, "tools": TOOLS},
        )
        body = response.json()
        choice = body["choices"][0]
        message = choice["message"]

        # If the model returned text, we're done
        if message.get("content") and choice["finish_reason"] == "stop":
            client.close()
            return message["content"]

        # If the model wants to call tools, execute them
        if message.get("tool_calls"):
            messages.append(message)
            for tc in message["tool_calls"]:
                func_name = tc["function"]["name"]
                func_args = json.loads(tc["function"]["arguments"])
                tool_fn = TOOL_MAP.get(func_name)
                if tool_fn:
                    result = tool_fn(**func_args)
                else:
                    result = {"error": f"Unknown tool: {func_name}"}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })
            continue

        # Unexpected response — return whatever we got
        client.close()
        return message.get("content", "")

    client.close()
    return "Error: agent loop exceeded maximum iterations"
