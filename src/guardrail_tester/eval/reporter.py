"""Eval reporter — aggregates scenario results and displays a summary."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from guardrail_tester.eval.runner import ScenarioResult


def generate_summary(results: list[ScenarioResult]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        cat = r.scenario.category
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0, "failed": 0}
        by_category[cat]["total"] += 1
        if r.passed:
            by_category[cat]["passed"] += 1
        else:
            by_category[cat]["failed"] += 1

    by_outcome = Counter(r.actual_outcome for r in results)
    by_expected = Counter(r.expected_outcome for r in results)

    failures = []
    for r in results:
        if not r.passed:
            failures.append({
                "scenario_id": r.scenario.id,
                "category": r.scenario.category,
                "expected": r.expected_outcome,
                "actual": r.actual_outcome,
                "output_preview": r.agent_output[:200],
                "error": r.error,
            })

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
        "by_category": by_category,
        "by_actual_outcome": dict(by_outcome),
        "by_expected_outcome": dict(by_expected),
        "failures": failures,
    }


def print_report(results: list[ScenarioResult]) -> None:
    summary = generate_summary(results)

    print("\n" + "=" * 60)
    print("  TEST REPORT")
    print("=" * 60)

    print(f"\n  Total scenarios: {summary['total']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Pass rate: {summary['pass_rate']}%")

    print("\n  By Category:")
    print("  " + "-" * 50)
    for cat, counts in summary["by_category"].items():
        rate = round(counts["passed"] / counts["total"] * 100, 1) if counts["total"] > 0 else 0
        print(f"    {cat:<25} {counts['passed']}/{counts['total']} ({rate}%)")

    print("\n  Actual Outcomes:")
    print("  " + "-" * 50)
    for outcome, count in summary["by_actual_outcome"].items():
        print(f"    {outcome:<25} {count}")

    if summary["failures"]:
        print(f"\n  Failures ({len(summary['failures'])}):")
        print("  " + "-" * 50)
        for f in summary["failures"]:
            print(f"    [{f['category']}] {f['scenario_id']}")
            print(f"      Expected: {f['expected']}, Got: {f['actual']}")
            if f["error"]:
                print(f"      Error: {f['error'][:100]}")

    print("\n" + "=" * 60)


def save_report(results: list[ScenarioResult], output_path: str | Path) -> None:
    summary = generate_summary(results)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Report saved to {output_path}")
