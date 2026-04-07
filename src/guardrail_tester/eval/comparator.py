"""Side-by-side comparison of guardrail test results across three modes.

Modes:
  bare        -- no guardrails (direct to OpenAI)
  proxy-only  -- LiteLLM proxy (input/output guardrails via Votal pre_call/post_call)
  full        -- LiteLLM proxy + Shield middleware (all 5 checkpoints)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardrail_tester.eval.runner import ScenarioResult


MODES = ("bare", "proxy-only", "full")

MODE_LABELS = {
    "bare": "Bare",
    "proxy-only": "Proxy",
    "full": "Full",
}


@dataclass
class ComparisonRow:
    scenario_id: str
    category: str
    expected: str
    results: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str | None] = field(default_factory=dict)

    @property
    def all_pass(self) -> bool:
        return all(self.results.get(m) == self.expected for m in MODES)

    def mode_passed(self, mode: str) -> bool:
        return self.results.get(mode) == self.expected


@dataclass
class ComparisonSummary:
    rows: list[ComparisonRow]
    per_mode_pass: dict[str, int] = field(default_factory=dict)
    per_mode_total: dict[str, int] = field(default_factory=dict)
    total_scenarios: int = 0

    @property
    def per_mode_rate(self) -> dict[str, float]:
        return {
            m: round(self.per_mode_pass.get(m, 0) / self.per_mode_total.get(m, 1) * 100, 1)
            for m in MODES
        }


def build_comparison(
    results_by_mode: dict[str, list[ScenarioResult]],
) -> ComparisonSummary:
    scenario_index: dict[str, ComparisonRow] = {}

    for mode in MODES:
        for sr in results_by_mode.get(mode, []):
            sid = sr.scenario.id
            if sid not in scenario_index:
                scenario_index[sid] = ComparisonRow(
                    scenario_id=sid,
                    category=sr.scenario.category,
                    expected=sr.expected_outcome,
                )
            row = scenario_index[sid]
            row.results[mode] = sr.actual_outcome
            row.outputs[mode] = sr.agent_output[:200]
            row.errors[mode] = sr.error

    rows = sorted(scenario_index.values(), key=lambda r: (r.category, r.scenario_id))

    per_mode_pass: dict[str, int] = {m: 0 for m in MODES}
    per_mode_total: dict[str, int] = {m: 0 for m in MODES}

    for row in rows:
        for m in MODES:
            if m in row.results:
                per_mode_total[m] += 1
                if row.mode_passed(m):
                    per_mode_pass[m] += 1

    return ComparisonSummary(
        rows=rows,
        per_mode_pass=per_mode_pass,
        per_mode_total=per_mode_total,
        total_scenarios=len(rows),
    )


def _outcome_symbol(actual: str, expected: str) -> str:
    if actual == expected:
        return "PASS"
    return "FAIL"


def print_comparison(summary: ComparisonSummary) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()

    table = Table(title="Guardrail Comparison: bare vs proxy-only vs full", show_lines=True)
    table.add_column("Scenario", style="bold", min_width=30)
    table.add_column("Category", min_width=10)
    table.add_column("Expected", min_width=9)
    table.add_column("Bare", min_width=12)
    table.add_column("Proxy", min_width=12)
    table.add_column("Full", min_width=12)

    for row in summary.rows:
        cells = []
        for mode in MODES:
            actual = row.results.get(mode, "n/a")
            verdict = _outcome_symbol(actual, row.expected)
            if verdict == "PASS":
                cells.append(f"[green]{actual} PASS[/green]")
            else:
                cells.append(f"[red]{actual} FAIL[/red]")

        table.add_row(
            row.scenario_id,
            row.category,
            row.expected,
            *cells,
        )

    console.print(table)

    # Summary line
    rates = summary.per_mode_rate
    console.print()
    console.print("[bold]Pass rates:[/bold]")
    for mode in MODES:
        p = summary.per_mode_pass.get(mode, 0)
        t = summary.per_mode_total.get(mode, 0)
        r = rates.get(mode, 0)
        label = MODE_LABELS[mode]
        color = "green" if r >= 80 else "yellow" if r >= 50 else "red"
        console.print(f"  {label:<12} [{color}]{p}/{t} ({r}%)[/{color}]")

    # Highlight what the proxy/shield caught that bare missed
    proxy_catches = []
    shield_catches = []
    for row in summary.rows:
        bare = row.results.get("bare", "")
        proxy = row.results.get("proxy-only", "")
        full = row.results.get("full", "")

        if bare != row.expected and proxy == row.expected:
            proxy_catches.append(row.scenario_id)
        if proxy != row.expected and full == row.expected:
            shield_catches.append(row.scenario_id)

    if proxy_catches:
        console.print(f"\n[bold cyan]Proxy caught (bare missed):[/bold cyan] {len(proxy_catches)} scenarios")
        for sid in proxy_catches:
            console.print(f"  - {sid}")

    if shield_catches:
        console.print(f"\n[bold magenta]Shield caught (proxy missed):[/bold magenta] {len(shield_catches)} scenarios")
        for sid in shield_catches:
            console.print(f"  - {sid}")


def save_comparison(summary: ComparisonSummary, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "total_scenarios": summary.total_scenarios,
        "per_mode_pass": summary.per_mode_pass,
        "per_mode_total": summary.per_mode_total,
        "per_mode_rate": summary.per_mode_rate,
        "rows": [],
    }

    for row in summary.rows:
        data["rows"].append({
            "scenario_id": row.scenario_id,
            "category": row.category,
            "expected": row.expected,
            "results": row.results,
            "outputs": row.outputs,
            "errors": row.errors,
        })

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Comparison report saved to {output_path}")
