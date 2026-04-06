from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ExpectedTrigger:
    guardrail: str
    layer: str
    action: str


@dataclass
class Scenario:
    id: str
    category: str
    perspective: str  # malicious_user | benign_edge | compromised_agent
    input: str
    expected_outcome: str  # blocked | allowed | rewritten | escalated
    expected_triggers: list[ExpectedTrigger] = field(default_factory=list)
    description: str = ""
    severity: str = "medium"  # low | medium | high | critical
    tags: list[str] = field(default_factory=list)
    guardrail_overrides: dict[str, Any] = field(default_factory=dict)
    multi_turn: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def load_scenario(path: Path) -> Scenario:
    with open(path) as f:
        data = yaml.safe_load(f)

    triggers = []
    for t in data.get("expected_triggers", []):
        triggers.append(ExpectedTrigger(
            guardrail=t["guardrail"],
            layer=t["layer"],
            action=t["action"],
        ))

    return Scenario(
        id=data["id"],
        category=data.get("category", "general"),
        perspective=data.get("perspective", "malicious_user"),
        input=data["input"],
        expected_outcome=data["expected_outcome"],
        expected_triggers=triggers,
        description=data.get("description", ""),
        severity=data.get("severity", "medium"),
        tags=data.get("tags", []),
        guardrail_overrides=data.get("guardrail_overrides", {}),
        multi_turn=data.get("multi_turn", []),
        metadata=data.get("metadata", {}),
    )


def load_scenarios_from_dir(directory: Path) -> list[Scenario]:
    scenarios = []
    for yaml_file in sorted(directory.rglob("*.yaml")):
        try:
            scenarios.append(load_scenario(yaml_file))
        except Exception as e:
            print(f"Warning: Failed to load scenario {yaml_file}: {e}")
    return scenarios
