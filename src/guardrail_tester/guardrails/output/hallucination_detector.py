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

SUSPICIOUS_URL_PATTERNS = [
    re.compile(r"https?://[a-z0-9.-]+\.(?:fake|test|example|invalid|localhost)\b", re.IGNORECASE),
    re.compile(r"https?://(?:www\.)?(?:fake|made-?up|not-?real)[a-z0-9.-]*\.[a-z]{2,}", re.IGNORECASE),
]

FABRICATION_PATTERNS = [
    (re.compile(r"(?:case|docket)\s*(?:no\.?|number|#)\s*\d{2,}-[A-Z]{2,}-\d{4,}", re.IGNORECASE), "fabricated_case_number"),
    (re.compile(r"according\s+to\s+(?:a\s+)?(?:recent\s+)?study\s+(?:by|from|published\s+in)\s+[A-Z]", re.IGNORECASE), "unverifiable_citation"),
    (re.compile(r"ISBN\s*:?\s*\d{3}-\d-\d{3}-\d{5}-\d", re.IGNORECASE), "fabricated_isbn"),
    (re.compile(r"DOI\s*:?\s*10\.\d{4,}/[a-z0-9./-]+", re.IGNORECASE), "fabricated_doi"),
]


class HallucinationDetector(Guardrail):
    """Detects hallucinated URLs, fabricated references, and unverifiable citations."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="hallucination_detector", layer=GuardrailLayer.OUTPUT, config=config)

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        content = context.content
        detections: list[dict[str, str]] = []

        for pattern in SUSPICIOUS_URL_PATTERNS:
            for match in pattern.finditer(content):
                detections.append({
                    "type": "suspicious_url",
                    "value": match.group(),
                })

        for pattern, label in FABRICATION_PATTERNS:
            for match in pattern.finditer(content):
                detections.append({
                    "type": label,
                    "value": match.group()[:100],
                })

        if not detections:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="No hallucination indicators detected",
            )

        types = list({d["type"] for d in detections})
        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"Potential hallucination detected: {', '.join(types)}",
            details={"detections": detections, "types": types},
        )
