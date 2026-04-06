from __future__ import annotations

from guardrail_tester.guardrails.base import (
    Guardrail,
    GuardrailAction,
    GuardrailContext,
    GuardrailLayer,
    GuardrailRegistry,
    GuardrailResult,
)
from guardrail_tester.logging.structured import get_logger

logger = get_logger(__name__)


class GuardrailEngine:
    """Executes guardrails for a given layer, short-circuiting on block."""

    def __init__(self, registry: GuardrailRegistry) -> None:
        self.registry = registry

    async def run_layer(
        self, layer: GuardrailLayer, context: GuardrailContext
    ) -> list[GuardrailResult]:
        guards = self.registry.get_by_layer(layer)
        results: list[GuardrailResult] = []

        for guard in guards:
            result = await guard.run(context)
            results.append(result)

            logger.log_guardrail_check(
                guardrail_name=guard.name,
                layer=layer.value,
                passed=result.passed,
                action=result.action.value,
                message=result.message,
                latency_ms=result.latency_ms,
                details=result.details,
            )

            if not result.passed:
                if result.action == GuardrailAction.BLOCK:
                    break
                elif result.action == GuardrailAction.REWRITE and result.rewritten_content:
                    context.content = result.rewritten_content
                elif result.action == GuardrailAction.DEGRADE:
                    context.metadata["degraded_tools"] = result.details.get(
                        "disable_tools", []
                    )

        return results

    def has_block(self, results: list[GuardrailResult]) -> bool:
        return any(
            not r.passed and r.action == GuardrailAction.BLOCK for r in results
        )

    def get_rewritten_content(
        self, results: list[GuardrailResult], original: str
    ) -> str:
        for r in results:
            if r.action == GuardrailAction.REWRITE and r.rewritten_content:
                return r.rewritten_content
        return original

    def get_triggered(self, results: list[GuardrailResult]) -> list[GuardrailResult]:
        return [r for r in results if not r.passed]
