"""Tests for the eval reporter."""

from guardrail_tester.eval.runner import ScenarioResult
from guardrail_tester.eval.scenario import Scenario
from guardrail_tester.eval.reporter import generate_summary


def _make_result(scenario_id: str, category: str, passed: bool, expected: str = "blocked", actual: str = "blocked") -> ScenarioResult:
    return ScenarioResult(
        scenario=Scenario(
            id=scenario_id,
            category=category,
            perspective="malicious_user",
            input="test",
            expected_outcome=expected,
        ),
        passed=passed,
        expected_outcome=expected,
        actual_outcome=actual,
        agent_output="test output",
    )


def test_summary_all_pass():
    results = [
        _make_result("s1", "pii", True),
        _make_result("s2", "injection", True),
    ]
    summary = generate_summary(results)
    assert summary["total"] == 2
    assert summary["passed"] == 2
    assert summary["failed"] == 0
    assert summary["pass_rate"] == 100.0


def test_summary_mixed():
    results = [
        _make_result("s1", "pii", True, "blocked", "blocked"),
        _make_result("s2", "pii", False, "blocked", "allowed"),
        _make_result("s3", "injection", True, "blocked", "blocked"),
    ]
    summary = generate_summary(results)
    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert len(summary["failures"]) == 1
    assert summary["failures"][0]["scenario_id"] == "s2"


def test_summary_by_category():
    results = [
        _make_result("s1", "pii", True),
        _make_result("s2", "pii", False, "blocked", "allowed"),
        _make_result("s3", "injection", True),
    ]
    summary = generate_summary(results)
    assert summary["by_category"]["pii"]["total"] == 2
    assert summary["by_category"]["pii"]["passed"] == 1
    assert summary["by_category"]["injection"]["total"] == 1
