"""CLI entry point for the Acme Corp agent and its external test harness."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from guardrail_tester.logging.structured import init_logger


@click.group()
def main():
    """Acme Corp Agent — a realistic customer support agent with 10 tools."""
    pass


@main.command()
@click.argument("prompt")
@click.option("--llm-base-url", default=None, help="LLM API base URL (e.g., http://localhost:4000/v1 for LiteLLM proxy)")
@click.option("--config", "config_path", default=None, help="Path to agent config YAML")
@click.option("--log-dir", default="logs", help="Directory for log output")
@click.option("--verbose", is_flag=True, help="Enable verbose agent output")
def run(
    prompt: str,
    llm_base_url: str | None,
    config_path: str | None,
    log_dir: str,
    verbose: bool,
):
    """Run the agent with a single prompt."""
    from guardrail_tester.agent.runtime import run_agent, load_config

    init_logger(log_dir=log_dir)
    config = load_config(config_path)

    if verbose:
        config.setdefault("agent", {})["verbose"] = True

    async def _run():
        result = await run_agent(
            user_input=prompt,
            config=config,
            base_url=llm_base_url,
        )
        print("\n" + "=" * 60)
        print("  AGENT OUTPUT")
        print("=" * 60)
        print(f"\n{result['output']}\n")

        if result.get("error"):
            print(f"  [ERROR] {result['error']}")

        if result.get("intermediate_steps"):
            print(f"  Tool calls: {len(result['intermediate_steps'])}")
            for step in result["intermediate_steps"]:
                print(f"    -> {step['tool']}({str(step['input'])[:80]})")

        print("=" * 60)

    asyncio.run(_run())


@main.command()
@click.option("--scenarios", required=True, help="Path to scenarios directory")
@click.option("--llm-base-url", default=None, help="LLM API base URL")
@click.option("--config", "config_path", default=None, help="Path to agent config YAML")
@click.option("--log-dir", default="logs", help="Directory for log output")
@click.option("--report-output", default=None, help="Path to save JSON report")
def test(
    scenarios: str,
    llm_base_url: str | None,
    config_path: str | None,
    log_dir: str,
    report_output: str | None,
):
    """Send batch test scenarios to the agent and report results.

    This command sends adversarial, benign, and edge-case prompts to the agent
    from outside — the agent has no knowledge it is being tested. The scenarios
    record what the agent did and whether the outcome matches expectations.
    """
    from guardrail_tester.agent.runtime import load_config
    from guardrail_tester.eval.runner import run_eval
    from guardrail_tester.eval.reporter import print_report, save_report

    init_logger(log_dir=log_dir)
    config = load_config(config_path)

    async def _test():
        results = await run_eval(
            scenarios_dir=scenarios,
            config=config,
            base_url=llm_base_url,
        )
        print_report(results)
        if report_output:
            save_report(results, report_output)

    asyncio.run(_test())


if __name__ == "__main__":
    main()
