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
    "ssn": (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***-**-****"),
    "credit_card": (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "****-****-****-****"),
    "phone": (re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"), "(***) ***-****"),
    "email_address": (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL REDACTED]"),
}


class InputPIIDetector(Guardrail):
    """Detects PII patterns in user input and optionally redacts them."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="input_pii_detector", layer=GuardrailLayer.INPUT, config=config)

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
                message="No PII detected in input",
            )

        if self.default_action == GuardrailAction.REWRITE:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=False,
                action=GuardrailAction.REWRITE,
                message=f"PII detected and redacted in input: {', '.join(detected)}",
                rewritten_content=redacted,
                details={"detected_types": detected},
            )

        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"PII detected in input: {', '.join(detected)}",
            details={"detected_types": detected},
        )
