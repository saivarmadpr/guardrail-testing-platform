"""Tests for VotalGuardedMemory."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from guardrail_tester.shield.client import VotalShield, ShieldResult
from guardrail_tester.shield.memory import VotalGuardedMemory


@pytest.fixture
def mock_shield():
    s = MagicMock(spec=VotalShield)
    s.check_memory = AsyncMock()
    return s


class TestSaveContext:
    def test_clean_write_passes_through(self, mock_shield):
        mock_shield.check_memory.return_value = ShieldResult(allowed=True, action="pass")

        memory = VotalGuardedMemory(
            shield=mock_shield,
            agent_key="test-agent",
            session_id="test-session",
        )
        memory.save_context(
            {"input": "What is my order status?"},
            {"output": "Your order is shipped."},
        )

        history = memory.load_memory_variables({})
        assert "shipped" in history["history"]

    def test_pii_scrubbed_on_write(self, mock_shield):
        async def check_memory_side_effect(**kwargs):
            value = kwargs.get("value", "")
            if "123-45-6789" in value:
                return ShieldResult(
                    allowed=False,
                    action="rewrite",
                    sanitized_output="SSN: [REDACTED]",
                )
            return ShieldResult(allowed=True, action="pass")

        mock_shield.check_memory.side_effect = check_memory_side_effect

        memory = VotalGuardedMemory(
            shield=mock_shield,
            agent_key="test-agent",
            session_id="test-session",
        )
        memory.save_context(
            {"input": "Look up John Smith"},
            {"output": "John Smith, SSN: 123-45-6789"},
        )

        history = memory.load_memory_variables({})
        assert "123-45-6789" not in history["history"]
        assert "[REDACTED]" in history["history"]


class TestLoadMemoryVariables:
    def test_injection_blocked_on_read(self, mock_shield):
        memory = VotalGuardedMemory(
            shield=mock_shield,
            agent_key="test-agent",
            session_id="test-session",
        )

        mock_shield.check_memory.return_value = ShieldResult(allowed=True, action="pass")
        memory.save_context(
            {"input": "normal question"},
            {"output": "normal answer"},
        )

        mock_shield.check_memory.return_value = ShieldResult(
            allowed=False,
            action="block",
            guardrail_results=[{"message": "Injection detected in memory"}],
        )

        result = memory.load_memory_variables({})
        assert "[MEMORY BLOCKED" in result["history"]

    def test_clean_read_passes_through(self, mock_shield):
        mock_shield.check_memory.return_value = ShieldResult(allowed=True, action="pass")

        memory = VotalGuardedMemory(
            shield=mock_shield,
            agent_key="test-agent",
            session_id="test-session",
        )
        memory.save_context(
            {"input": "Hello"},
            {"output": "Hi there!"},
        )

        result = memory.load_memory_variables({})
        assert "Hi there!" in result["history"]


class TestNoShield:
    def test_works_without_shield(self):
        memory = VotalGuardedMemory()
        memory.save_context(
            {"input": "test"},
            {"output": "response"},
        )
        result = memory.load_memory_variables({})
        assert "response" in result["history"]
