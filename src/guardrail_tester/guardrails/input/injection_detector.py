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

INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?previous\s+instructions", "instruction_override"),
    (r"disregard\s+(your|all|any)\s+(instructions|rules|guidelines)", "instruction_override"),
    (r"forget\s+(your|all|any)\s+(rules|instructions|guidelines)", "instruction_override"),
    (r"you\s+are\s+now\s+(?:a|an|in)\s+", "role_hijack"),
    (r"act\s+as\s+if\s+you", "role_hijack"),
    (r"pretend\s+(you\s+are|to\s+be)", "role_hijack"),
    (r"(reveal|show|display|output|print)\s+(your\s+)?(system\s+prompt|instructions|rules)", "system_prompt_extraction"),
    (r"what\s+are\s+your\s+(instructions|rules|system\s+prompt)", "system_prompt_extraction"),
    (r"\bDAN\s+mode\b", "jailbreak"),
    (r"\bjailbreak\b", "jailbreak"),
    (r"(bypass|override|circumvent)\s+(your|the|any)\s+(rules|restrictions|guardrails|safety)", "bypass_attempt"),
    (r"do\s+not\s+follow\s+(your|any)\s+(rules|instructions)", "instruction_override"),
    (r"\bdev(eloper)?\s+mode\b", "jailbreak"),
    (r"maintenance\s+mode", "jailbreak"),
    (r"admin(istrator)?\s+override", "bypass_attempt"),
]

ENCODING_PATTERNS = [
    (re.compile(r"[A-Za-z0-9+/]{20,}={0,2}"), "base64_suspicious"),
    (re.compile(r"(\\x[0-9a-fA-F]{2}){4,}"), "hex_encoding"),
    (re.compile(r"(&#\d{2,3};){4,}"), "html_entity_encoding"),
]


class InjectionDetector(Guardrail):
    """Detects prompt injection, jailbreak attempts, and encoding-based bypasses."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="injection_detector", layer=GuardrailLayer.INPUT, config=config)
        self._compiled = [(re.compile(p, re.IGNORECASE), cat) for p, cat in INJECTION_PATTERNS]

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        content = context.content
        detections: list[dict[str, str]] = []

        for pattern, category in self._compiled:
            match = pattern.search(content)
            if match:
                detections.append({
                    "category": category,
                    "matched_text": match.group()[:100],
                })

        for pattern, category in ENCODING_PATTERNS:
            if pattern.search(content):
                detections.append({
                    "category": category,
                    "matched_text": "(encoded content)",
                })

        if not detections:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="No injection patterns detected",
            )

        categories = list({d["category"] for d in detections})
        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"Prompt injection detected: {', '.join(categories)}",
            details={"detections": detections, "categories": categories},
        )
