"""Eval runner — executes scenarios and collects results."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardrail_tester.eval.scenario import Scenario, load_scenarios_from_dir
from guardrail_tester.guardrails.base import GuardrailRegistry
from guardrail_tester.logging.structured import get_logger

logger = get_logger(__name__)


@dataclass
class ScenarioResult:
    scenario: Scenario
    passed: bool
    expected_outcome: str
    actual_outcome: str
    agent_output: str = ""
    triggered_guardrails: list[dict[str, Any]] = field(default_factory=list)
    intermediate_steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def determine_outcome(agent_result: dict[str, Any]) -> str:
    if agent_result.get("blocked"):
        return "blocked"
    output = agent_result.get("output", "")
    if output.startswith("[OUTPUT BLOCKED]"):
        return "blocked"
    guardrail_results = agent_result.get("guardrail_results", [])
    for gr in guardrail_results:
        if not gr.get("passed"):
            action = gr.get("action", "")
            if action == "rewrite":
                return "rewritten"
            if action == "escalate":
                return "escalated"
    return "allowed"


async def run_scenario(
    scenario: Scenario,
    config: dict[str, Any] | None = None,
    guardrail_registry: GuardrailRegistry | None = None,
    base_url: str | None = None,
) -> ScenarioResult:
    if guardrail_registry and scenario.guardrail_overrides:
        guardrail_registry.configure_for_scenario(scenario.guardrail_overrides)

    from guardrail_tester.agent.runtime import run_agent

    try:
        agent_result = await run_agent(
            user_input=scenario.input,
            config=config,
            guardrail_registry=guardrail_registry,
            base_url=base_url,
        )
    except Exception as e:
        return ScenarioResult(
            scenario=scenario,
            passed=False,
            expected_outcome=scenario.expected_outcome,
            actual_outcome="error",
            error=str(e),
        )

    actual_outcome = determine_outcome(agent_result)
    passed = actual_outcome == scenario.expected_outcome

    triggered = [
        gr for gr in agent_result.get("guardrail_results", [])
        if not gr.get("passed")
    ]

    result = ScenarioResult(
        scenario=scenario,
        passed=passed,
        expected_outcome=scenario.expected_outcome,
        actual_outcome=actual_outcome,
        agent_output=agent_result.get("output", ""),
        triggered_guardrails=triggered,
        intermediate_steps=agent_result.get("intermediate_steps", []),
    )

    logger.log_scenario_result(
        scenario_id=scenario.id,
        passed=passed,
        expected_outcome=scenario.expected_outcome,
        actual_outcome=actual_outcome,
        triggered_guardrails=triggered,
    )

    return result


async def run_eval(
    scenarios_dir: str | Path,
    config: dict[str, Any] | None = None,
    guardrail_registry: GuardrailRegistry | None = None,
    base_url: str | None = None,
) -> list[ScenarioResult]:
    scenarios_path = Path(scenarios_dir)
    scenarios = load_scenarios_from_dir(scenarios_path)

    if not scenarios:
        print(f"No scenarios found in {scenarios_path}")
        return []

    from guardrail_tester.agent.runtime import load_config as _load_config

    config = config or _load_config()
    results = []

    for scenario in scenarios:
        print(f"Running scenario: {scenario.id} [{scenario.category}]...", end=" ", flush=True)
        result = await run_scenario(
            scenario=scenario,
            config=config,
            guardrail_registry=guardrail_registry,
            base_url=base_url,
        )
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} (expected={result.expected_outcome}, actual={result.actual_outcome})")
        results.append(result)

    return results
