"""Tests for the assertion engine."""
from __future__ import annotations

import os

import pytest

from agenthound.assertions import (
    AgentHoundAssertionError,
    ResultExpectation,
    SessionExpectation,
    expect,
)
from agenthound.models import LLMCall, SessionFixture, ToolCallRecord, UsageRecord
from agenthound.replayer import ReplaySession

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample_session.json")


@pytest.fixture
def session():
    fixture = SessionFixture.from_file(FIXTURE_PATH)
    return ReplaySession(fixture)


class TestExpectDispatch:
    def test_session_returns_session_expectation(self, session):
        result = expect(session)
        assert isinstance(result, SessionExpectation)

    def test_string_returns_result_expectation(self):
        result = expect("hello")
        assert isinstance(result, ResultExpectation)

    def test_int_returns_result_expectation(self):
        result = expect(42)
        assert isinstance(result, ResultExpectation)


class TestSessionExpectationSchema:
    def test_has_llm_calls(self, session):
        expect(session).has_llm_calls(3)

    def test_has_llm_calls_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="Expected 5"):
            expect(session).has_llm_calls(5)

    def test_has_llm_calls_between(self, session):
        expect(session).has_llm_calls_between(1, 5)

    def test_has_llm_calls_between_fails(self, session):
        with pytest.raises(AgentHoundAssertionError):
            expect(session).has_llm_calls_between(10, 20)

    def test_no_errors(self, session):
        expect(session).no_errors()

    def test_all_calls_have_usage(self, session):
        expect(session).all_calls_have_usage()


class TestSessionExpectationConstraints:
    def test_total_tokens_under(self, session):
        expect(session).total_tokens_under(10000)

    def test_total_tokens_under_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="Expected under"):
            expect(session).total_tokens_under(1)

    def test_latency_under(self, session):
        expect(session).latency_under(5000.0)

    def test_latency_under_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="Expected latency under"):
            expect(session).latency_under(1.0)

    def test_max_turns(self, session):
        expect(session).max_turns(5)

    def test_max_turns_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="Expected at most"):
            expect(session).max_turns(1)


class TestSessionExpectationTrace:
    def test_tools_called(self, session):
        expect(session).tools_called(["lookup_order", "process_refund"])

    def test_tools_called_fails_wrong_order(self, session):
        with pytest.raises(AgentHoundAssertionError, match="Expected tools called"):
            expect(session).tools_called(["process_refund", "lookup_order"])

    def test_tools_called_unordered(self, session):
        expect(session).tools_called_unordered({"lookup_order", "process_refund"})

    def test_tool_called(self, session):
        expect(session).tool_called("lookup_order")

    def test_tool_called_times(self, session):
        expect(session).tool_called("lookup_order", times=1)

    def test_tool_called_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="never called"):
            expect(session).tool_called("nonexistent_tool")

    def test_tool_called_with(self, session):
        expect(session).tool_called_with("lookup_order", {"order_id": "ORD-123"})

    def test_tool_called_with_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="no matching call"):
            expect(session).tool_called_with("lookup_order", {"order_id": "WRONG"})

    def test_no_tool_errors(self, session):
        expect(session).no_tool_errors()

    def test_tool_sequence(self, session):
        expect(session).tool_sequence(["lookup_order", "process_refund"])

    def test_model_used(self, session):
        expect(session).model_used("gpt-4o-mini")

    def test_model_used_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="Expected all calls to use model"):
            expect(session).model_used("gpt-4o")

    def test_completed_successfully(self, session):
        expect(session).completed_successfully()


class TestSessionExpectationContent:
    def test_final_response_contains(self, session):
        expect(session).final_response_contains("refund")

    def test_final_response_contains_fails(self, session):
        with pytest.raises(AgentHoundAssertionError, match="Expected final response to contain"):
            expect(session).final_response_contains("error_xyz")

    def test_any_response_contains(self, session):
        expect(session).any_response_contains("refund")

    def test_final_response_matches(self, session):
        expect(session).final_response_matches(r"REF-\d+")


class TestSessionExpectationChaining:
    def test_fluent_chaining(self, session):
        """All assertions can be chained."""
        (
            expect(session)
            .has_llm_calls(3)
            .tools_called(["lookup_order", "process_refund"])
            .no_errors()
            .final_response_contains("refund")
        )


class TestResultExpectation:
    def test_contains(self):
        expect("Your refund has been processed").contains("refund")

    def test_contains_fails(self):
        with pytest.raises(AgentHoundAssertionError, match="Expected result to contain"):
            expect("Hello world").contains("goodbye")

    def test_matches(self):
        expect("Order ORD-123 processed").matches(r"ORD-\d+")

    def test_equals(self):
        expect(42).equals(42)

    def test_equals_fails(self):
        with pytest.raises(AgentHoundAssertionError):
            expect(42).equals(43)

    def test_is_type(self):
        expect("hello").is_type(str)

    def test_is_type_fails(self):
        with pytest.raises(AgentHoundAssertionError, match="Expected result to be int"):
            expect("hello").is_type(int)

    def test_chaining(self):
        expect("Your refund for order ORD-123").contains("refund").matches(r"ORD-\d+")
