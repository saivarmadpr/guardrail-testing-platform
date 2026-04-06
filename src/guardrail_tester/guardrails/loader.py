"""Loads guardrails from config and registers them in the registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from guardrail_tester.guardrails.base import GuardrailLayer, GuardrailRegistry

from guardrail_tester.guardrails.input.pii_detector import InputPIIDetector
from guardrail_tester.guardrails.input.injection_detector import InjectionDetector
from guardrail_tester.guardrails.input.topic_filter import TopicFilter
from guardrail_tester.guardrails.tool.permission_checker import PermissionChecker
from guardrail_tester.guardrails.tool.param_validator import ParamValidator
from guardrail_tester.guardrails.tool.rate_limiter import RateLimiter
from guardrail_tester.guardrails.tool.scope_enforcer import ScopeEnforcer
from guardrail_tester.guardrails.output.pii_filter import OutputPIIFilter
from guardrail_tester.guardrails.output.toxicity_filter import ToxicityFilter
from guardrail_tester.guardrails.output.hallucination_detector import HallucinationDetector

GUARDRAIL_CLASSES = {
    "input": {
        "pii_detector": InputPIIDetector,
        "injection_detector": InjectionDetector,
        "topic_filter": TopicFilter,
    },
    "tool": {
        "permission_checker": PermissionChecker,
        "param_validator": ParamValidator,
        "rate_limiter": RateLimiter,
        "scope_enforcer": ScopeEnforcer,
    },
    "output": {
        "pii_filter": OutputPIIFilter,
        "toxicity_filter": ToxicityFilter,
        "hallucination_detector": HallucinationDetector,
    },
}


def load_guardrails_config(config_path: str | Path | None = None) -> dict[str, Any]:
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "guardrails.yaml"
    config_path = Path(config_path)
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def register_all_guardrails(
    registry: GuardrailRegistry,
    config: dict[str, Any] | None = None,
) -> GuardrailRegistry:
    """Register all guardrails into the registry based on config."""
    if config is None:
        config = load_guardrails_config()

    guardrails_config = config.get("guardrails", {})

    for layer_name, guard_classes in GUARDRAIL_CLASSES.items():
        layer_config = guardrails_config.get(layer_name, {})
        for guard_key, guard_cls in guard_classes.items():
            guard_config = layer_config.get(guard_key, {})
            guard = guard_cls(config=guard_config)
            registry.register(guard)

    return registry
