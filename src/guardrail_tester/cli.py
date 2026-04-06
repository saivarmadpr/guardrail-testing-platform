"""CLI entry point for the guardrail testing platform."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from guardrail_tester.logging.structured import init_logger


def _build_registry(guardrails_config_path: str | None = None):
    from guardrail_tester.guardrails.base import GuardrailRegistry
    from guardrail_tester.guardrails.loader import load_guardrails_config, register_all_guardrails

    registry = GuardrailRegistry()
    config = load_guardrails_config(guardrails_config_path)
    register_all_guardrails(registry, config)
    return registry


@click.group()
def main():
    """Guardrail Testing Platform — test and validate LLM guardrails."""
    pass


@main.command()
@click.argument("prompt")
@click.option("--llm-base-url", default=None, help="LLM API base URL (e.g., http://localhost:4000/v1 for LiteLLM proxy)")
@click.option("--config", "config_path", default=None, help="Path to agent config YAML")
@click.option("--guardrails-config", default=None, help="Path to guardrails config YAML")
@click.option("--no-guardrails", is_flag=True, help="Disable all guardrails (baseline mode)")
@click.option("--log-dir", default="logs", help="Directory for log output")
@click.option("--verbose", is_flag=True, help="Enable verbose agent output")
def run(
    prompt: str,
    llm_base_url: str | None,
    config_path: str | None,
    guardrails_config: str | None,
    no_guardrails: bool,
    log_dir: str,
    verbose: bool,
):
    """Run the agent with a single prompt."""
    from guardrail_tester.agent.runtime import run_agent, load_config
    from guardrail_tester.guardrails.base import GuardrailRegistry

    init_logger(log_dir=log_dir)
    config = load_config(config_path)

    if verbose:
        config.setdefault("agent", {})["verbose"] = True

    if no_guardrails:
        registry = GuardrailRegistry()
    else:
        registry = _build_registry(guardrails_config)

    enabled_guards = registry.all()
    active = [g for g in enabled_guards if g.enabled]

    async def _run():
        result = await run_agent(
            user_input=prompt,
            config=config,
            guardrail_registry=registry,
            base_url=llm_base_url,
        )
        print("\n" + "=" * 60)
        print("  AGENT OUTPUT")
        print("=" * 60)
        print(f"\n{result['output']}\n")

        if result.get("blocked"):
            print(f"  [BLOCKED by: {result.get('blocked_by', 'unknown')}]")

        if result.get("guardrail_results"):
            print("  Guardrail Results:")
            for gr in result["guardrail_results"]:
                status = "PASS" if gr["passed"] else "FAIL"
                print(f"    {gr['name']}: {status} ({gr['action']}) - {gr.get('message', '')}")

        if result.get("intermediate_steps"):
            print(f"\n  Tool calls: {len(result['intermediate_steps'])}")
            for step in result["intermediate_steps"]:
                print(f"    -> {step['tool']}({str(step['input'])[:80]})")

        print(f"\n  Guardrails active: {len(active)}/{len(enabled_guards)}")
        print("=" * 60)

    asyncio.run(_run())


@main.command()
@click.option("--scenarios", required=True, help="Path to scenarios directory")
@click.option("--llm-base-url", default=None, help="LLM API base URL")
@click.option("--config", "config_path", default=None, help="Path to agent config YAML")
@click.option("--guardrails-config", default=None, help="Path to guardrails config YAML")
@click.option("--no-guardrails", is_flag=True, help="Disable all guardrails (baseline mode)")
@click.option("--log-dir", default="logs", help="Directory for log output")
@click.option("--report-output", default=None, help="Path to save JSON report")
def eval(
    scenarios: str,
    llm_base_url: str | None,
    config_path: str | None,
    guardrails_config: str | None,
    no_guardrails: bool,
    log_dir: str,
    report_output: str | None,
):
    """Run evaluation scenarios against the agent."""
    from guardrail_tester.agent.runtime import load_config
    from guardrail_tester.eval.runner import run_eval
    from guardrail_tester.eval.reporter import print_report, save_report
    from guardrail_tester.guardrails.base import GuardrailRegistry

    init_logger(log_dir=log_dir)
    config = load_config(config_path)

    if no_guardrails:
        registry = GuardrailRegistry()
    else:
        registry = _build_registry(guardrails_config)

    async def _eval():
        results = await run_eval(
            scenarios_dir=scenarios,
            config=config,
            guardrail_registry=registry,
            base_url=llm_base_url,
        )
        print_report(results)
        if report_output:
            save_report(results, report_output)

    asyncio.run(_eval())


if __name__ == "__main__":
    main()
