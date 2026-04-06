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

SCOPE_VIOLATIONS = {
    "bulk_export": {
        "tools": ["database_query"],
        "patterns": [
            re.compile(r"SELECT\s+\*\s+FROM\s+\w+\s*$", re.IGNORECASE),
            re.compile(r"SELECT\s+\*\s+FROM\s+\w+\s+WHERE\s+1\s*=\s*1", re.IGNORECASE),
            re.compile(r"LIMIT\s+(\d+)", re.IGNORECASE),
        ],
        "max_limit": 50,
        "message": "Bulk data export exceeding scope limits",
    },
    "cross_customer_access": {
        "tools": ["user_data_lookup"],
        "patterns": [
            re.compile(r"^\*$"),
            re.compile(r"^all$", re.IGNORECASE),
        ],
        "message": "Attempting to access all customer records",
    },
    "sensitive_file_access": {
        "tools": ["file_read"],
        "patterns": [
            re.compile(r"secret|password|credential|\.env|\.key|\.pem", re.IGNORECASE),
        ],
        "message": "Attempting to access sensitive configuration files",
    },
}


class ScopeEnforcer(Guardrail):
    """Prevents agents from exceeding their authority boundaries."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="scope_enforcer", layer=GuardrailLayer.TOOL, config=config)

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        tool_name = context.tool_name or ""
        tool_args = context.tool_args or {}
        violations: list[str] = []

        for violation_type, rule in SCOPE_VIOLATIONS.items():
            if tool_name not in rule["tools"]:
                continue

            all_values = " ".join(str(v) for v in tool_args.values())

            for pattern in rule["patterns"]:
                match = pattern.search(all_values)
                if match:
                    if violation_type == "bulk_export" and "LIMIT" in pattern.pattern.upper():
                        try:
                            limit_val = int(match.group(1))
                            if limit_val <= rule["max_limit"]:
                                continue
                        except (IndexError, ValueError):
                            pass

                    violations.append(f"{violation_type}: {rule['message']}")
                    break

        if not violations:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="Tool call within authorized scope",
            )

        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"Scope violation: {'; '.join(violations)}",
            details={"violations": violations, "tool": tool_name},
        )
