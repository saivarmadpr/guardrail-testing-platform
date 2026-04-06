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

BLOCKED_TOPICS = {
    "violence": ["kill", "murder", "bomb", "attack", "weapon", "assault", "shoot", "stab", "terrorism"],
    "illegal_activity": ["hack into", "steal", "fraud", "counterfeit", "launder", "smuggle", "bribe", "blackmail"],
    "self_harm": ["suicide", "self-harm", "end my life", "hurt myself"],
    "explicit": ["pornograph", "sexually explicit", "nude"],
}

ALLOWED_TOPICS = [
    "customer_support", "account", "order", "billing", "subscription",
    "product", "service", "help", "question", "information",
    "email", "report", "schedule", "calendar", "search",
]


class TopicFilter(Guardrail):
    """Blocks requests containing off-topic or dangerous content."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="topic_filter", layer=GuardrailLayer.INPUT, config=config)
        self.blocked_topics = config.get("blocked_topics", BLOCKED_TOPICS) if config else BLOCKED_TOPICS

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        content_lower = context.content.lower()
        triggered_topics: list[str] = []
        triggered_keywords: list[str] = []

        for topic, keywords in self.blocked_topics.items():
            for keyword in keywords:
                if keyword in content_lower:
                    triggered_topics.append(topic)
                    triggered_keywords.append(keyword)
                    break

        if not triggered_topics:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="Content is on-topic",
            )

        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"Blocked topic detected: {', '.join(triggered_topics)}",
            details={"topics": triggered_topics, "keywords": triggered_keywords},
        )
