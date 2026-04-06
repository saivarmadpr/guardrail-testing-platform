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

SQL_INJECTION_PATTERNS = [
    re.compile(r"('\s*(OR|AND)\s+['\"0-9])", re.IGNORECASE),
    re.compile(r"(;\s*(DROP|DELETE|UPDATE|INSERT|ALTER|EXEC|EXECUTE))", re.IGNORECASE),
    re.compile(r"(UNION\s+(ALL\s+)?SELECT)", re.IGNORECASE),
    re.compile(r"(';\s*--)", re.IGNORECASE),
    re.compile(r"(1\s*=\s*1)"),
    re.compile(r"('\s*OR\s+''=')", re.IGNORECASE),
]

PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\./"),
    re.compile(r"\.\.\\"),
    re.compile(r"%2e%2e[/\\]", re.IGNORECASE),
    re.compile(r"~[/\\]"),
    re.compile(r"/etc/(passwd|shadow|hosts)"),
    re.compile(r"/(root|home)/.*\.(ssh|env|bash)"),
]

COMMAND_INJECTION_PATTERNS = [
    re.compile(r"[;&|`$]\s*\w+"),
    re.compile(r"\$\(.*\)"),
    re.compile(r"`.*`"),
]


class ParamValidator(Guardrail):
    """Validates tool parameters against injection attack patterns."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="param_validator", layer=GuardrailLayer.TOOL, config=config)

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        tool_name = context.tool_name
        tool_args = context.tool_args or {}
        detections: list[dict[str, str]] = []

        all_values = " ".join(str(v) for v in tool_args.values())

        if tool_name == "database_query":
            query = tool_args.get("query", "")
            for pattern in SQL_INJECTION_PATTERNS:
                match = pattern.search(query)
                if match:
                    detections.append({
                        "type": "sql_injection",
                        "matched": match.group()[:100],
                        "param": "query",
                    })

        if tool_name == "file_read":
            path = tool_args.get("path", "")
            for pattern in PATH_TRAVERSAL_PATTERNS:
                match = pattern.search(path)
                if match:
                    detections.append({
                        "type": "path_traversal",
                        "matched": match.group()[:100],
                        "param": "path",
                    })

        for pattern in COMMAND_INJECTION_PATTERNS:
            match = pattern.search(all_values)
            if match:
                detections.append({
                    "type": "command_injection",
                    "matched": match.group()[:100],
                    "param": "general",
                })

        if not detections:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="Parameters validated successfully",
            )

        types = list({d["type"] for d in detections})
        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message=f"Dangerous parameter pattern detected: {', '.join(types)}",
            details={"detections": detections, "types": types, "tool": tool_name},
        )
