from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from guardrail_tester.guardrails.base import (
    Guardrail,
    GuardrailAction,
    GuardrailContext,
    GuardrailLayer,
    GuardrailResult,
)


class RateLimiter(Guardrail):
    """Rate limits tool calls per tool and globally within a time window."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(name="rate_limiter", layer=GuardrailLayer.TOOL, config=config)
        self.max_calls_per_minute: int = (config or {}).get("max_calls_per_minute", 30)
        self.max_calls_per_tool: int = (config or {}).get("max_calls_per_tool", 10)
        self.window_seconds: float = (config or {}).get("window_seconds", 60.0)
        self._global_calls: list[float] = []
        self._tool_calls: dict[str, list[float]] = defaultdict(list)

    def _prune_old(self, timestamps: list[float], now: float) -> list[float]:
        cutoff = now - self.window_seconds
        return [t for t in timestamps if t > cutoff]

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        now = time.monotonic()
        tool_name = context.tool_name or "unknown"

        self._global_calls = self._prune_old(self._global_calls, now)
        self._tool_calls[tool_name] = self._prune_old(self._tool_calls[tool_name], now)

        global_count = len(self._global_calls)
        tool_count = len(self._tool_calls[tool_name])

        if global_count >= self.max_calls_per_minute:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=False,
                action=self.default_action,
                message=f"Global rate limit exceeded: {global_count}/{self.max_calls_per_minute} calls in window",
                details={
                    "global_count": global_count,
                    "limit": self.max_calls_per_minute,
                    "tool": tool_name,
                    "disable_tools": [tool_name],
                },
            )

        if tool_count >= self.max_calls_per_tool:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=False,
                action=self.default_action,
                message=f"Tool rate limit exceeded for '{tool_name}': {tool_count}/{self.max_calls_per_tool} calls in window",
                details={
                    "tool_count": tool_count,
                    "limit": self.max_calls_per_tool,
                    "tool": tool_name,
                    "disable_tools": [tool_name],
                },
            )

        self._global_calls.append(now)
        self._tool_calls[tool_name].append(now)

        return GuardrailResult(
            guardrail_name=self.name,
            passed=True,
            action=GuardrailAction.LOG,
            message=f"Rate OK: global {global_count + 1}/{self.max_calls_per_minute}, {tool_name} {tool_count + 1}/{self.max_calls_per_tool}",
        )

    def reset(self) -> None:
        self._global_calls.clear()
        self._tool_calls.clear()
