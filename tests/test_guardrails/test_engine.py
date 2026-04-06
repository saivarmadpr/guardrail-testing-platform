"""Tests for the guardrail engine."""

import pytest

from guardrail_tester.guardrails.base import (
    GuardrailAction,
    GuardrailContext,
    GuardrailLayer,
    GuardrailRegistry,
    GuardrailResult,
    Guardrail,
)
from guardrail_tester.guardrails.engine import GuardrailEngine
from tests.conftest import AlwaysBlockGuardrail, AlwaysPassGuardrail, PIIDetectorGuardrail


@pytest.mark.asyncio
async def test_engine_empty_layer():
    registry = GuardrailRegistry()
    engine = GuardrailEngine(registry)
    ctx = GuardrailContext(content="hello", layer=GuardrailLayer.INPUT)
    results = await engine.run_layer(GuardrailLayer.INPUT, ctx)
    assert results == []


@pytest.mark.asyncio
async def test_engine_pass_through():
    registry = GuardrailRegistry()
    registry.register(AlwaysPassGuardrail(name="pass1", layer=GuardrailLayer.INPUT))
    registry.register(AlwaysPassGuardrail(name="pass2", layer=GuardrailLayer.INPUT))
    engine = GuardrailEngine(registry)

    ctx = GuardrailContext(content="hello", layer=GuardrailLayer.INPUT)
    results = await engine.run_layer(GuardrailLayer.INPUT, ctx)
    assert len(results) == 2
    assert all(r.passed for r in results)
    assert not engine.has_block(results)


@pytest.mark.asyncio
async def test_engine_block_short_circuits():
    registry = GuardrailRegistry()
    registry.register(AlwaysBlockGuardrail(name="blocker", layer=GuardrailLayer.INPUT))
    registry.register(AlwaysPassGuardrail(name="never_reached", layer=GuardrailLayer.INPUT))
    engine = GuardrailEngine(registry)

    ctx = GuardrailContext(content="bad", layer=GuardrailLayer.INPUT)
    results = await engine.run_layer(GuardrailLayer.INPUT, ctx)
    assert len(results) == 1
    assert engine.has_block(results)


@pytest.mark.asyncio
async def test_engine_pii_detection():
    registry = GuardrailRegistry()
    registry.register(PIIDetectorGuardrail(
        name="pii", layer=GuardrailLayer.OUTPUT, config={"action": "block"}
    ))
    engine = GuardrailEngine(registry)

    safe_ctx = GuardrailContext(content="Hello, how can I help?", layer=GuardrailLayer.OUTPUT)
    safe_results = await engine.run_layer(GuardrailLayer.OUTPUT, safe_ctx)
    assert all(r.passed for r in safe_results)

    pii_ctx = GuardrailContext(content="The SSN is 123-45-6789", layer=GuardrailLayer.OUTPUT)
    pii_results = await engine.run_layer(GuardrailLayer.OUTPUT, pii_ctx)
    assert engine.has_block(pii_results)


@pytest.mark.asyncio
async def test_engine_rewrite():
    class RewriteGuardrail(Guardrail):
        async def check(self, context: GuardrailContext) -> GuardrailResult:
            if "secret" in context.content.lower():
                return GuardrailResult(
                    guardrail_name=self.name,
                    passed=False,
                    action=GuardrailAction.REWRITE,
                    message="Rewrote content",
                    rewritten_content=context.content.replace("secret", "[REDACTED]"),
                )
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
            )

    registry = GuardrailRegistry()
    registry.register(RewriteGuardrail(
        name="rewriter", layer=GuardrailLayer.OUTPUT, config={"action": "rewrite"}
    ))
    engine = GuardrailEngine(registry)

    ctx = GuardrailContext(content="The secret code is 42", layer=GuardrailLayer.OUTPUT)
    results = await engine.run_layer(GuardrailLayer.OUTPUT, ctx)
    rewritten = engine.get_rewritten_content(results, "The secret code is 42")
    assert "[REDACTED]" in rewritten
    assert "secret" not in rewritten
