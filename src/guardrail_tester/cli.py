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
@click.option("--mode", type=click.Choice(["bare", "proxy-only", "full"]), default="full",
              help="Guardrail mode: bare (no guardrails), proxy-only (LiteLLM only), full (proxy + shield)")
@click.option("--llm-base-url", default=None, help="Override LLM API base URL")
@click.option("--config", "config_path", default=None, help="Path to agent config YAML")
@click.option("--log-dir", default="logs", help="Directory for log output")
@click.option("--verbose", is_flag=True, help="Enable verbose agent output")
def run(
    prompt: str,
    mode: str,
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
            mode=mode,
        )
        mode_label = {"bare": "BARE (no guardrails)", "proxy-only": "PROXY-ONLY", "full": "FULL (proxy + shield)"}
        print(f"\n{'=' * 60}")
        print(f"  AGENT OUTPUT  [mode: {mode_label.get(mode, mode)}]")
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
@click.option("--mode", type=click.Choice(["bare", "proxy-only", "full"]), default="full",
              help="Guardrail mode: bare (no guardrails), proxy-only (LiteLLM only), full (proxy + shield)")
@click.option("--llm-base-url", default=None, help="Override LLM API base URL")
@click.option("--config", "config_path", default=None, help="Path to agent config YAML")
@click.option("--log-dir", default="logs", help="Directory for log output")
@click.option("--report-output", default=None, help="Path to save JSON report")
def test(
    scenarios: str,
    mode: str,
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
            mode=mode,
        )
        print_report(results)
        if report_output:
            save_report(results, report_output)

    asyncio.run(_test())


@main.command()
@click.option("--scenarios", required=True, help="Path to scenarios directory")
@click.option("--modes", default="bare,proxy-only,full",
              help="Comma-separated modes to compare (default: bare,proxy-only,full)")
@click.option("--config", "config_path", default=None, help="Path to agent config YAML")
@click.option("--log-dir", default="logs", help="Directory for log output")
@click.option("--report-output", default=None, help="Path to save JSON comparison report")
def compare(
    scenarios: str,
    modes: str,
    config_path: str | None,
    log_dir: str,
    report_output: str | None,
):
    """Run all scenarios across multiple guardrail modes and compare results.

    Produces a side-by-side table showing how each scenario behaves under
    bare (no guardrails), proxy-only (LiteLLM), and full (proxy + shield) modes.
    """
    from guardrail_tester.agent.runtime import load_config
    from guardrail_tester.eval.runner import run_eval
    from guardrail_tester.eval.comparator import (
        build_comparison, print_comparison, save_comparison, MODES,
    )

    init_logger(log_dir=log_dir)
    config = load_config(config_path)

    mode_list = [m.strip() for m in modes.split(",")]
    for m in mode_list:
        if m not in MODES:
            raise click.BadParameter(f"Invalid mode {m!r}. Choose from: {', '.join(MODES)}")

    async def _compare():
        results_by_mode: dict[str, list] = {}

        for mode in mode_list:
            print(f"\n{'=' * 60}")
            print(f"  Running scenarios in [{mode.upper()}] mode")
            print(f"{'=' * 60}\n")
            results_by_mode[mode] = await run_eval(
                scenarios_dir=scenarios,
                config=config,
                mode=mode,
            )

        summary = build_comparison(results_by_mode)
        print(f"\n{'=' * 60}")
        print("  COMPARISON RESULTS")
        print(f"{'=' * 60}\n")
        print_comparison(summary)

        if report_output:
            save_comparison(summary, report_output)

    asyncio.run(_compare())


if __name__ == "__main__":
    main()
