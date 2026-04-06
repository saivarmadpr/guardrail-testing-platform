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

TOXICITY_PATTERNS = {
    "threat": [
        r"\b(i\s+will|i\'m\s+going\s+to|gonna)\s+(kill|hurt|destroy|attack)\b",
        r"\byou\s+(will|should)\s+(die|suffer|pay)\b",
    ],
    "slur": [
        r"\b(idiot|stupid|moron|dumb|loser|pathetic)\b",
    ],
    "profanity": [
        r"\b(fuck|shit|damn|ass|bitch|crap|hell)\b",
    ],
    "harassment": [
        r"\b(shut\s+up|go\s+away|leave\s+me\s+alone|nobody\s+(asked|cares))\b",
    ],
}


class ToxicityFilter(Guardrail):
    """Detects toxic, threatening, or abusive content in agent output."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="toxicity_filter", layer=GuardrailLayer.OUTPUT, config=config)
        self._compiled: dict[str, list[re.Pattern]] = {}
        for category, patterns in TOXICITY_PATTERNS.items():
            self._compiled[category] = [re.compile(p, re.IGNORECASE) for p in patterns]

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        content = context.content
        detections: dict[str, list[str]] = {}

        for category, patterns in self._compiled.items():
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    detections.setdefault(category, []).append(match.group())

        if not detections:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="No toxic content detected",
            )

        categories = list(detections.keys())
        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"Toxic content detected: {', '.join(categories)}",
            details={"categories": categories, "matches": detections},
        )
