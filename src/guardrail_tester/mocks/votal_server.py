"""Mock Votal classification server for offline testing."""

from __future__ import annotations

import re
from typing import Any


PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
}

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "disregard your instructions",
    "forget your rules",
    "you are now",
    "act as if you",
    "system prompt",
    "reveal your instructions",
    "what are your instructions",
    "DAN mode",
    "jailbreak",
    "bypass your",
    "override your",
]

BLOCKED_KEYWORDS = [
    "kill", "bomb", "attack", "weapon", "illegal",
    "hack into", "steal", "fraud",
]


class MockVotalServer:
    """Simulates the Votal /classify and /classify_output endpoints."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.call_log: list[dict[str, Any]] = []

    def classify_input(self, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        results = []
        action = "allow"

        for pattern_name, pattern in PII_PATTERNS.items():
            if pattern.search(message):
                results.append({
                    "guardrail": "pii-detection",
                    "passed": False,
                    "message": f"PII detected in input: {pattern_name}",
                })

        msg_lower = message.lower()
        for injection in INJECTION_PATTERNS:
            if injection in msg_lower:
                results.append({
                    "guardrail": "adversarial-prompt-detection",
                    "passed": False,
                    "message": f"Potential prompt injection detected: '{injection}'",
                })
                action = "block"
                break

        for keyword in BLOCKED_KEYWORDS:
            if keyword in msg_lower:
                results.append({
                    "guardrail": "keyword-blocklist",
                    "passed": False,
                    "message": f"Blocked keyword detected: '{keyword}'",
                })
                action = "block"
                break

        if all(r["passed"] for r in results) if results else True:
            action = "allow"
        elif action != "block":
            action = "flag"

        response = {
            "action": action,
            "guardrail_results": results,
        }
        self.call_log.append({"endpoint": "classify", "message": message[:200], "response": response})
        return response

    def classify_output(self, output: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        results = []
        action = "allow"

        for pattern_name, pattern in PII_PATTERNS.items():
            if pattern.search(output):
                results.append({
                    "guardrail": "pii-leakage",
                    "passed": False,
                    "message": f"PII leakage detected in output: {pattern_name}",
                })
                action = "block"

        hallucinated_url = re.compile(r"https?://[a-z0-9.-]+\.(?:fake|test|example)\.[a-z]{2,}")
        if hallucinated_url.search(output):
            results.append({
                "guardrail": "hallucinated-links",
                "passed": False,
                "message": "Potentially hallucinated URL detected in output",
            })

        if not results:
            results.append({
                "guardrail": "all",
                "passed": True,
                "message": "Output passed all checks",
            })

        response = {
            "action": action,
            "guardrail_results": results,
        }
        self.call_log.append({"endpoint": "classify_output", "output": output[:200], "response": response})
        return response
