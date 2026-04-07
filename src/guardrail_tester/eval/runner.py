"""Eval runner — sends scenarios to the agent and collects results.

The agent has no idea it is being tested. This runner acts as an external
test harness: it feeds prompts, records what the agent did, and compares
the actual outcome to expected outcomes defined in the YAML scenarios.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardrail_tester.eval.scenario import Scenario, load_scenarios_from_dir
from guardrail_tester.logging.structured import get_logger

logger = get_logger(__name__)


@dataclass
class ScenarioResult:
    scenario: Scenario
    passed: bool
    expected_outcome: str
    actual_outcome: str
    agent_output: str = ""
    intermediate_steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def determine_outcome(agent_result: dict[str, Any]) -> str:
    if agent_result.get("blocked"):
        return "blocked"
    output = agent_result.get("output", "")
    if "[ERROR]" in output and ("blocked" in output.lower() or "400" in output):
        return "blocked"
    return "allowed"


async def run_scenario(
    scenario: Scenario,
    config: dict[str, Any] | None = None,
    base_url: str | None = None,
    mode: str = "full",
) -> ScenarioResult:
    from guardrail_tester.agent.runtime import run_agent

    try:
        agent_result = await run_agent(
            user_input=scenario.input,
            config=config,
            base_url=base_url,
            mode=mode,
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

    result = ScenarioResult(
        scenario=scenario,
        passed=passed,
        expected_outcome=scenario.expected_outcome,
        actual_outcome=actual_outcome,
        agent_output=agent_result.get("output", ""),
        intermediate_steps=agent_result.get("intermediate_steps", []),
    )

    logger.log_scenario_result(
        scenario_id=scenario.id,
        passed=passed,
        expected_outcome=scenario.expected_outcome,
        actual_outcome=actual_outcome,
    )

    return result


async def run_eval(
    scenarios_dir: str | Path,
    config: dict[str, Any] | None = None,
    base_url: str | None = None,
    mode: str = "full",
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
        print(f"[{mode}] Running scenario: {scenario.id} [{scenario.category}]...", end=" ", flush=True)
        result = await run_scenario(
            scenario=scenario,
            config=config,
            base_url=base_url,
            mode=mode,
        )
        status = "PASS" if result.passed else "FAIL"
        print(f"{status} (expected={result.expected_outcome}, actual={result.actual_outcome})")
        results.append(result)

    return results
