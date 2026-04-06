from __future__ import annotations

from typing import Any

from guardrail_tester.guardrails.base import (
    Guardrail,
    GuardrailAction,
    GuardrailContext,
    GuardrailLayer,
    GuardrailResult,
)

SENSITIVE_PATHS = ["/config/secrets.env", "/etc/passwd", "/etc/shadow", "~/.ssh", "~/.env"]

SENSITIVE_TOOL_PATTERNS = {
    "file_read": {
        "blocked_paths": SENSITIVE_PATHS,
        "reason": "Access to sensitive system files is restricted",
    },
    "email_send": {
        "blocked_domains": ["attacker.com", "evil.com", "tempmail.com", "throwaway.email"],
        "reason": "Sending emails to suspicious domains is blocked",
    },
    "database_query": {
        "blocked_patterns": ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "TRUNCATE "],
        "reason": "Write operations on the database are blocked",
    },
}


class PermissionChecker(Guardrail):
    """Validates tool calls against permission policies."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="permission_checker", layer=GuardrailLayer.TOOL, config=config)

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        tool_name = context.tool_name
        tool_args = context.tool_args or {}

        if tool_name not in SENSITIVE_TOOL_PATTERNS:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message=f"Tool '{tool_name}' has no specific restrictions",
            )

        policy = SENSITIVE_TOOL_PATTERNS[tool_name]

        if tool_name == "file_read":
            path = tool_args.get("path", "")
            for blocked in policy["blocked_paths"]:
                if blocked in path or path.startswith(blocked):
                    return GuardrailResult(
                        guardrail_name=self.name,
                        passed=False,
                        action=self.default_action,
                        message=f"{policy['reason']}: '{path}'",
                        details={"tool": tool_name, "blocked_path": path},
                    )

        elif tool_name == "email_send":
            to_addr = tool_args.get("to", "").lower()
            for domain in policy["blocked_domains"]:
                if domain in to_addr:
                    return GuardrailResult(
                        guardrail_name=self.name,
                        passed=False,
                        action=self.default_action,
                        message=f"{policy['reason']}: '{to_addr}'",
                        details={"tool": tool_name, "blocked_recipient": to_addr},
                    )

        elif tool_name == "database_query":
            query = tool_args.get("query", "").upper()
            for pattern in policy["blocked_patterns"]:
                if pattern in query:
                    return GuardrailResult(
                        guardrail_name=self.name,
                        passed=False,
                        action=self.default_action,
                        message=f"{policy['reason']}: found '{pattern.strip()}'",
                        details={"tool": tool_name, "blocked_pattern": pattern.strip()},
                    )

        return GuardrailResult(
            guardrail_name=self.name,
            passed=True,
            action=GuardrailAction.LOG,
            message=f"Tool '{tool_name}' call permitted",
        )
