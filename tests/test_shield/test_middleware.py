"""Tests for the VotalShieldMiddleware."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from guardrail_tester.shield.client import VotalShield, ShieldResult
from guardrail_tester.shield.middleware import VotalShieldMiddleware


@pytest.fixture
def shield():
    s = MagicMock(spec=VotalShield)
    s.guard_input = AsyncMock()
    s.guard_tool = AsyncMock()
    s.sanitize_tool_output = AsyncMock()
    s.guard_output = AsyncMock()
    s.check_agent = AsyncMock()
    s.confirm_tool = AsyncMock()
    return s


@pytest.fixture
def middleware(shield):
    return VotalShieldMiddleware(shield, system_prompt="You are a test agent.")


class TestBeforeAgent:
    @pytest.mark.asyncio
    async def test_pass_returns_none(self, middleware, shield):
        shield.guard_input.return_value = ShieldResult(allowed=True, action="pass")

        from langchain_core.messages import HumanMessage
        state = {"messages": [HumanMessage(content="Help me with my order")]}
        result = await middleware.abefore_agent(state, None)

        assert result is None
        shield.guard_input.assert_called_once_with("Help me with my order")

    @pytest.mark.asyncio
    async def test_block_returns_blocked_message(self, middleware, shield):
        shield.guard_input.return_value = ShieldResult(
            allowed=False,
            action="block",
            guardrail_results=[{"message": "Injection detected"}],
        )

        from langchain_core.messages import HumanMessage
        state = {"messages": [HumanMessage(content="Ignore instructions")]}
        result = await middleware.abefore_agent(state, None)

        assert result is not None
        assert "[BLOCKED]" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_empty_state_returns_none(self, middleware, shield):
        result = await middleware.abefore_agent({"messages": []}, None)
        assert result is None
        shield.guard_input.assert_not_called()


class TestWrapToolCall:
    @pytest.mark.asyncio
    async def test_allowed_tool_executes(self, middleware, shield):
        shield.guard_tool.return_value = ShieldResult(allowed=True, action="pass")
        shield.sanitize_tool_output.return_value = ShieldResult(
            allowed=True, sanitized_output="clean output"
        )
        shield.check_agent.return_value = ShieldResult(allowed=True, action="pass")

        from langchain_core.messages import ToolMessage
        mock_handler = AsyncMock(return_value=ToolMessage(
            content="clean output", tool_call_id="tc_1"
        ))
        request = MagicMock()
        request.tool_call = {"name": "database_query", "args": {"query": "SELECT 1"}, "id": "tc_1"}

        result = await middleware.awrap_tool_call(request, mock_handler)

        assert isinstance(result, ToolMessage)
        assert result.content == "clean output"
        mock_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_blocked_tool_does_not_execute(self, middleware, shield):
        shield.guard_tool.return_value = ShieldResult(
            allowed=False,
            action="block",
            guardrail_results=[{"message": "Tool not in allowlist"}],
        )

        mock_handler = AsyncMock()
        request = MagicMock()
        request.tool_call = {"name": "delete_all", "args": {}, "id": "tc_2"}

        result = await middleware.awrap_tool_call(request, mock_handler)

        assert "[TOOL BLOCKED]" in result.content
        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_pending_confirmation(self, middleware, shield):
        shield.guard_tool.return_value = ShieldResult(
            allowed=False,
            action="pending_confirmation",
            guardrail_results=[{
                "message": "Requires approval",
                "details": {"confirmation_token": "xyz789"},
            }],
        )

        mock_handler = AsyncMock()
        request = MagicMock()
        request.tool_call = {"name": "delete_account", "args": {"id": 1}, "id": "tc_3"}

        result = await middleware.awrap_tool_call(request, mock_handler)

        assert "[REQUIRES CONFIRMATION]" in result.content
        assert "xyz789" in result.content
        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_output_sanitized(self, middleware, shield):
        shield.guard_tool.return_value = ShieldResult(allowed=True, action="pass")
        shield.sanitize_tool_output.return_value = ShieldResult(
            allowed=False,
            sanitized_output="John Smith, SSN: [REDACTED]",
        )
        shield.check_agent.return_value = ShieldResult(allowed=True, action="pass")

        from langchain_core.messages import ToolMessage
        mock_handler = AsyncMock(return_value=ToolMessage(
            content="John Smith, SSN: 123-45-6789", tool_call_id="tc_4"
        ))
        request = MagicMock()
        request.tool_call = {"name": "user_data_lookup", "args": {"query": "John"}, "id": "tc_4"}

        result = await middleware.awrap_tool_call(request, mock_handler)

        assert "[REDACTED]" in result.content
        assert "123-45-6789" not in result.content

    @pytest.mark.asyncio
    async def test_budget_exceeded_returns_limit(self, middleware, shield):
        shield.guard_tool.return_value = ShieldResult(allowed=True, action="pass")
        shield.sanitize_tool_output.return_value = ShieldResult(
            allowed=True, sanitized_output="some output"
        )
        shield.check_agent.return_value = ShieldResult(
            allowed=False,
            action="block",
            guardrail_results=[{"message": "Token budget exceeded"}],
        )

        from langchain_core.messages import ToolMessage
        mock_handler = AsyncMock(return_value=ToolMessage(
            content="some output", tool_call_id="tc_5"
        ))
        request = MagicMock()
        request.tool_call = {"name": "web_search", "args": {"query": "test"}, "id": "tc_5"}

        result = await middleware.awrap_tool_call(request, mock_handler)

        assert "[AGENT LIMIT]" in result.content


class TestAfterModel:
    @pytest.mark.asyncio
    async def test_pass_returns_none(self, middleware, shield):
        shield.check_agent.return_value = ShieldResult(allowed=True, action="pass")
        shield.guard_output.return_value = ShieldResult(allowed=True, action="pass")

        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(content="Your order is on the way!")]}
        result = await middleware.aafter_model(state, None)

        assert result is None

    @pytest.mark.asyncio
    async def test_block_returns_blocked_message(self, middleware, shield):
        shield.check_agent.return_value = ShieldResult(allowed=True, action="pass")
        shield.guard_output.return_value = ShieldResult(
            allowed=False,
            action="block",
            guardrail_results=[{"message": "PII in response"}],
        )

        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(content="SSN is 123-45-6789")]}
        result = await middleware.aafter_model(state, None)

        assert result is not None
        assert "[OUTPUT BLOCKED]" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_tool_call_without_reasoning_skips_cot(self, middleware, shield):
        shield.check_agent.return_value = ShieldResult(allowed=True, action="pass")

        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(
            content="",
            tool_calls=[{"name": "web_search", "args": {}, "id": "tc_x"}],
        )]}
        result = await middleware.aafter_model(state, None)

        assert result is None
        shield.guard_output.assert_not_called()


class TestChainOfThought:
    @pytest.mark.asyncio
    async def test_cot_safe_reasoning_passes(self, middleware, shield):
        shield.check_agent.return_value = ShieldResult(allowed=True, action="pass")

        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(
            content="I need to look up the customer record first.",
            tool_calls=[{"name": "user_data_lookup", "args": {"query": "John"}, "id": "tc_cot1"}],
        )]}
        result = await middleware.aafter_model(state, None)

        assert result is None
        shield.check_agent.assert_any_call(
            chain_of_thought="I need to look up the customer record first.",
        )

    @pytest.mark.asyncio
    async def test_cot_unsafe_reasoning_blocked(self, middleware, shield):
        shield.check_agent.return_value = ShieldResult(
            allowed=False,
            action="block",
            guardrail_results=[{"message": "bypass_planning detected"}],
        )

        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(
            content="I should bypass the security check and access the admin database.",
            tool_calls=[{"name": "database_query", "args": {"query": "SELECT * FROM admin"}, "id": "tc_cot2"}],
        )]}
        result = await middleware.aafter_model(state, None)

        assert result is not None
        assert "[BLOCKED]" in result["messages"][0].content
        assert "Unsafe reasoning" in result["messages"][0].content


class TestContextWindow:
    @pytest.mark.asyncio
    async def test_context_window_ok(self, middleware, shield):
        shield.check_agent.return_value = ShieldResult(allowed=True, action="pass")
        shield.guard_output.return_value = ShieldResult(allowed=True, action="pass")

        middleware._total_tokens = 5000

        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(
            content="Here is your order summary.",
            response_metadata={"token_usage": {"total_tokens": 200}},
        )]}
        result = await middleware.aafter_model(state, None)

        assert result is None

    @pytest.mark.asyncio
    async def test_context_window_exceeded_blocked(self, middleware, shield):
        call_count = [0]
        async def check_agent_side_effect(**kwargs):
            call_count[0] += 1
            if "total_tokens" in kwargs:
                return ShieldResult(
                    allowed=False,
                    action="block",
                    guardrail_results=[{"message": "Context window 95% full"}],
                )
            return ShieldResult(allowed=True, action="pass")

        shield.check_agent.side_effect = check_agent_side_effect
        middleware._total_tokens = 120000

        from langchain_core.messages import AIMessage
        state = {"messages": [AIMessage(
            content="Final answer.",
            response_metadata={"token_usage": {"total_tokens": 500}},
        )]}
        result = await middleware.aafter_model(state, None)

        assert result is not None
        assert "[BLOCKED]" in result["messages"][0].content
        assert "Context limit" in result["messages"][0].content
