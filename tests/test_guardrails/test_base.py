"""Tests for guardrail base classes and registry."""

import pytest

from guardrail_tester.guardrails.base import (
    GuardrailAction,
    GuardrailContext,
    GuardrailLayer,
    GuardrailRegistry,
)
from tests.conftest import AlwaysBlockGuardrail, AlwaysPassGuardrail


@pytest.mark.asyncio
async def test_guardrail_pass():
    guard = AlwaysPassGuardrail(name="test_pass", layer=GuardrailLayer.INPUT)
    ctx = GuardrailContext(content="hello", layer=GuardrailLayer.INPUT)
    result = await guard.run(ctx)
    assert result.passed is True
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_guardrail_block():
    guard = AlwaysBlockGuardrail(name="test_block", layer=GuardrailLayer.INPUT)
    ctx = GuardrailContext(content="bad input", layer=GuardrailLayer.INPUT)
    result = await guard.run(ctx)
    assert result.passed is False
    assert result.action == GuardrailAction.BLOCK


@pytest.mark.asyncio
async def test_disabled_guardrail_always_passes():
    guard = AlwaysBlockGuardrail(
        name="disabled_block",
        layer=GuardrailLayer.INPUT,
        config={"enabled": False},
    )
    ctx = GuardrailContext(content="bad input", layer=GuardrailLayer.INPUT)
    result = await guard.run(ctx)
    assert result.passed is True


def test_registry_register_and_get():
    registry = GuardrailRegistry()
    guard = AlwaysPassGuardrail(name="test", layer=GuardrailLayer.INPUT)
    registry.register(guard)
    assert registry.get("test") is guard


def test_registry_get_by_layer():
    registry = GuardrailRegistry()
    input_guard = AlwaysPassGuardrail(name="input1", layer=GuardrailLayer.INPUT)
    tool_guard = AlwaysPassGuardrail(name="tool1", layer=GuardrailLayer.TOOL)
    registry.register(input_guard)
    registry.register(tool_guard)
    assert len(registry.get_by_layer(GuardrailLayer.INPUT)) == 1
    assert len(registry.get_by_layer(GuardrailLayer.TOOL)) == 1
    assert len(registry.get_by_layer(GuardrailLayer.OUTPUT)) == 0


def test_registry_configure_for_scenario():
    registry = GuardrailRegistry()
    guard = AlwaysBlockGuardrail(name="test", layer=GuardrailLayer.INPUT)
    registry.register(guard)
    assert guard.enabled is True

    registry.configure_for_scenario({"test": {"enabled": False}})
    assert guard.enabled is False

    registry.configure_for_scenario({"test": {"enabled": True, "action": "rewrite"}})
    assert guard.enabled is True
    assert guard.default_action == GuardrailAction.REWRITE
