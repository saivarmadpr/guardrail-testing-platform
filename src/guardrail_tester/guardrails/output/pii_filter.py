from __future__ import annotations

import re
from typing import Any

from guardrail_tester.guardrails.base import (
    Guardrail,
    GuardrailAction,
    GuardrailContext,
    GuardrailLayer,
    GuardrailResult,
)

PII_PATTERNS = {
    "ssn": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN REDACTED]"),
    "credit_card": (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CC REDACTED]"),
    "phone": (re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), "[PHONE REDACTED]"),
}


class OutputPIIFilter(Guardrail):
    """Detects PII leakage in agent output and optionally redacts it."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="output_pii_filter", layer=GuardrailLayer.OUTPUT, config=config)

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        detected: list[str] = []
        redacted = context.content

        for pii_type, (pattern, replacement) in PII_PATTERNS.items():
            if pattern.search(context.content):
                detected.append(pii_type)
                redacted = pattern.sub(replacement, redacted)

        if not detected:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="No PII detected in output",
            )

        if self.default_action == GuardrailAction.REWRITE:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=False,
                action=GuardrailAction.REWRITE,
                message=f"PII redacted in output: {', '.join(detected)}",
                rewritten_content=redacted,
                details={"detected_types": detected},
            )

        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"PII leakage detected in output: {', '.join(detected)}",
            details={"detected_types": detected},
        )
