"""Example tests for a customer support agent.

These tests demonstrate every major AgentHound feature using a realistic
support agent that handles order lookups and refund processing.

Run with:
    pytest examples/test_support_agent.py -v
"""
from __future__ import annotations

import os

import pytest

from agenthound import expect, inject_failure, mock_llm, replay

from support_agent import run_agent

# Resolve fixture paths relative to this file
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
REFUND_FIXTURE = os.path.join(FIXTURES, "refund_happy_path.json")
STATUS_FIXTURE = os.path.join(FIXTURES, "order_status_check.json")


# ─────────────────────────────────────────────────────────────────────────────
# 1. REPLAY TESTS — replay a recorded session, assert on behavior
# ─────────────────────────────────────────────────────────────────────────────


class TestRefundFlow:
    """Tests for the refund happy path using a recorded fixture."""

    @replay(REFUND_FIXTURE)
    def test_calls_correct_tools_in_order(self, session):
        """The agent should look up the order first, then process the refund."""
        run_agent("I want to return order ORD-100")

        expect(session).tools_called(["lookup_order", "process_refund"])

    @replay(REFUND_FIXTURE)
    def test_response_mentions_refund_details(self, session):
        """The final response should include the refund ID and amount."""
        result = run_agent("I want to return order ORD-100")

        expect(result).contains("REF-100")
        expect(result).contains("29.99")

    @replay(REFUND_FIXTURE)
    def test_completes_without_errors(self, session):
        """No errors should occur during a normal refund flow."""
        run_agent("I want to return order ORD-100")

        expect(session).completed_successfully()

    @replay(REFUND_FIXTURE)
    def test_uses_correct_model(self, session):
        """All LLM calls should use gpt-4o-mini."""
        run_agent("I want to return order ORD-100")

        expect(session).model_used("gpt-4o-mini")

    @replay(REFUND_FIXTURE)
    def test_completes_in_three_turns(self, session):
        """Refund flow: lookup → refund → respond = 3 LLM calls."""
        run_agent("I want to return order ORD-100")

        expect(session).has_llm_calls(3)
        expect(session).max_turns(3)

    @replay(REFUND_FIXTURE)
    def test_tool_receives_correct_arguments(self, session):
        """Verify the agent passes the right order ID and amount to tools."""
        run_agent("I want to return order ORD-100")

        expect(session).tool_called_with("lookup_order", {"order_id": "ORD-100"})
        expect(session).tool_called_with("process_refund", {
            "order_id": "ORD-100",
            "amount": 29.99,
        })

    @replay(REFUND_FIXTURE)
    def test_chained_assertions(self, session):
        """All assertions can be chained for a single comprehensive check."""
        result = run_agent("I want to return order ORD-100")

        (
            expect(session)
            .has_llm_calls(3)
            .tools_called(["lookup_order", "process_refund"])
            .total_tokens_under(1000)
            .model_used("gpt-4o-mini")
            .completed_successfully()
            .final_response_contains("REF-100")
            .final_response_matches(r"\$\d+\.\d{2}")
        )

        expect(result).contains("refund").matches(r"REF-\d+")


class TestOrderStatusCheck:
    """Tests for order status inquiries."""

    @replay(STATUS_FIXTURE)
    def test_looks_up_order(self, session):
        """A status check should only call lookup_order, not process_refund."""
        run_agent("Where is my order ORD-200?")

        expect(session).tools_called(["lookup_order"])
        expect(session).tool_called("lookup_order", times=1)

    @replay(STATUS_FIXTURE)
    def test_response_includes_status(self, session):
        """The response should tell the user their order is shipped."""
        result = run_agent("Where is my order ORD-200?")

        expect(result).contains("shipped")
        expect(result).contains("Mechanical Keyboard")

    @replay(STATUS_FIXTURE)
    def test_fewer_turns_than_refund(self, session):
        """Status check should take only 2 turns (lookup → respond)."""
        run_agent("Where is my order ORD-200?")

        expect(session).has_llm_calls(2)


# ─────────────────────────────────────────────────────────────────────────────
# 2. MOCK TESTS — define LLM responses inline, no fixture needed
# ─────────────────────────────────────────────────────────────────────────────


class TestWithMocks:
    """Tests using @mock_llm to define responses programmatically."""

    @mock_llm(responses=[
        {"tool_call": "lookup_order", "args": {"order_id": "ORD-999"}},
        "I'm sorry, I couldn't find order ORD-999 in our system.",
    ])
    def test_agent_calls_lookup_for_unknown_order(self, session):
        """Even for an unknown order, the agent should try to look it up."""
        result = run_agent("What happened to order ORD-999?")

        expect(session).tool_called("lookup_order")
        expect(session).tool_called_with("lookup_order", {"order_id": "ORD-999"})
        expect(result).contains("ORD-999")

    @mock_llm(responses=[
        "I'm sorry, I can only help with order-related questions. "
        "Could you provide your order number?",
    ])
    def test_agent_responds_without_tools_when_appropriate(self, session):
        """When no tool is needed, the agent should respond directly."""
        result = run_agent("Hello, how are you?")

        expect(session).has_llm_calls(1)
        expect(session).tools_called([])  # No tools called
        expect(result).contains("order")

    @mock_llm(
        responses=["I can help with order lookups and refunds."],
        provider="anthropic",
    )
    def test_works_with_anthropic_provider(self, session):
        """mock_llm works with both OpenAI and Anthropic response formats."""
        expect(session).has_llm_calls(1)


# ─────────────────────────────────────────────────────────────────────────────
# 3. FAILURE INJECTION — test how the agent handles errors
# ─────────────────────────────────────────────────────────────────────────────


class TestFailureInjection:
    """Tests using @inject_failure to simulate tool errors."""

    @replay(REFUND_FIXTURE, strict=False)
    @inject_failure(tool="process_refund", error="TimeoutError", at_call=1)
    def test_refund_service_timeout(self, session):
        """When process_refund times out, the exchange returns a 500 error."""
        # The injected failure replaces the refund call's response with an error.
        # In a real test, you'd verify the agent retries or handles gracefully.
        assert session.llm_calls[1].error is not None
        assert "TimeoutError" in session.llm_calls[1].error

    @replay(REFUND_FIXTURE, strict=False)
    @inject_failure(tool="lookup_order", error="ServiceUnavailable", at_call=1)
    def test_order_lookup_failure(self, session):
        """When lookup_order fails, the error is reflected in the session."""
        assert session.llm_calls[0].error is not None
        assert "ServiceUnavailable" in session.llm_calls[0].error


# ─────────────────────────────────────────────────────────────────────────────
# 4. SESSION PROPERTIES — access raw session data for custom assertions
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionProperties:
    """Demonstrates accessing session properties directly."""

    @replay(REFUND_FIXTURE)
    def test_session_metadata(self, session):
        """Session exposes tags and metadata from recording."""
        run_agent("I want to return order ORD-100")

        assert "happy_path" in session.tags
        assert "refund" in session.tags
        assert session.metadata["agent"] == "support"

    @replay(REFUND_FIXTURE)
    def test_token_counts(self, session):
        """Total tokens across all calls are accessible."""
        run_agent("I want to return order ORD-100")

        assert session.total_tokens == 942  # 202 + 308 + 432
        expect(session).total_tokens_under(1000)

    @replay(REFUND_FIXTURE)
    def test_tool_retries_dict(self, session):
        """tool_retries gives a per-tool call count."""
        run_agent("I want to return order ORD-100")

        assert session.tool_retries == {
            "lookup_order": 1,
            "process_refund": 1,
        }

    @replay(REFUND_FIXTURE)
    def test_individual_llm_calls(self, session):
        """Each LLM call is accessible with full detail."""
        run_agent("I want to return order ORD-100")

        # First call: agent decides to look up the order
        call_1 = session.llm_calls[0]
        assert call_1.provider == "openai"
        assert call_1.model == "gpt-4o-mini"
        assert len(call_1.tool_calls) == 1
        assert call_1.tool_calls[0].tool_name == "lookup_order"
        assert call_1.usage is not None
        assert call_1.error is None

        # Third call: agent responds with the refund confirmation
        call_3 = session.llm_calls[2]
        assert len(call_3.tool_calls) == 0
        assert "REF-100" in call_3.response_text
