from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GuardrailAction(str, Enum):
    BLOCK = "block"
    REWRITE = "rewrite"
    ESCALATE = "escalate"
    LOG = "log"
    DEGRADE = "degrade"


class GuardrailLayer(str, Enum):
    INPUT = "input"
    TOOL = "tool"
    OUTPUT = "output"


@dataclass
class GuardrailContext:
    content: str
    layer: GuardrailLayer
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    conversation_history: list[dict[str, str]] = field(default_factory=list)


@dataclass
class GuardrailResult:
    guardrail_name: str
    passed: bool
    action: GuardrailAction
    message: str = ""
    rewritten_content: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


class Guardrail(ABC):
    """Base class for all guardrails."""

    name: str
    layer: GuardrailLayer
    enabled: bool = True
    default_action: GuardrailAction = GuardrailAction.BLOCK

    def __init__(self, name: str, layer: GuardrailLayer, config: dict[str, Any] | None = None):
        self.name = name
        self.layer = layer
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.default_action = GuardrailAction(self.config.get("action", "block"))

    async def run(self, context: GuardrailContext) -> GuardrailResult:
        if not self.enabled:
            return GuardrailResult(
                guardrail_name=self.name,
                passed=True,
                action=GuardrailAction.LOG,
                message="Guardrail disabled",
            )
        start = time.perf_counter()
        result = await self.check(context)
        result.latency_ms = (time.perf_counter() - start) * 1000
        return result

    @abstractmethod
    async def check(self, context: GuardrailContext) -> GuardrailResult:
        ...


class GuardrailRegistry:
    """Central registry for all guardrails."""

    def __init__(self) -> None:
        self._guardrails: dict[str, Guardrail] = {}

    def register(self, guardrail: Guardrail) -> None:
        self._guardrails[guardrail.name] = guardrail

    def get(self, name: str) -> Guardrail | None:
        return self._guardrails.get(name)

    def get_by_layer(self, layer: GuardrailLayer) -> list[Guardrail]:
        return [g for g in self._guardrails.values() if g.layer == layer and g.enabled]

    def all(self) -> list[Guardrail]:
        return list(self._guardrails.values())

    def enable(self, name: str) -> None:
        if g := self._guardrails.get(name):
            g.enabled = True

    def disable(self, name: str) -> None:
        if g := self._guardrails.get(name):
            g.enabled = False

    def configure_for_scenario(self, overrides: dict[str, dict[str, Any]]) -> None:
        """Apply per-scenario guardrail configuration overrides."""
        for name, config in overrides.items():
            if g := self._guardrails.get(name):
                if "enabled" in config:
                    g.enabled = config["enabled"]
                if "action" in config:
                    g.default_action = GuardrailAction(config["action"])


registry = GuardrailRegistry()
