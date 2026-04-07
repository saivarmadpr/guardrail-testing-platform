"""Tests for the comparison reporter."""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from guardrail_tester.eval.comparator import (
    ComparisonRow,
    ComparisonSummary,
    build_comparison,
    print_comparison,
    save_comparison,
    MODES,
)
from guardrail_tester.eval.runner import ScenarioResult


def _make_scenario(sid: str, category: str = "injection", expected: str = "blocked"):
    s = MagicMock()
    s.id = sid
    s.category = category
    s.expected_outcome = expected
    s.input = f"test input for {sid}"
    return s


def _make_result(sid: str, category: str, expected: str, actual: str, output: str = "") -> ScenarioResult:
    scenario = _make_scenario(sid, category, expected)
    return ScenarioResult(
        scenario=scenario,
        passed=actual == expected,
        expected_outcome=expected,
        actual_outcome=actual,
        agent_output=output or f"output for {sid}",
    )


class TestComparisonRow:
    def test_all_pass(self):
        row = ComparisonRow(
            scenario_id="test_1",
            category="benign",
            expected="allowed",
            results={"bare": "allowed", "proxy-only": "allowed", "full": "allowed"},
        )
        assert row.all_pass is True

    def test_partial_fail(self):
        row = ComparisonRow(
            scenario_id="test_2",
            category="injection",
            expected="blocked",
            results={"bare": "allowed", "proxy-only": "blocked", "full": "blocked"},
        )
        assert row.all_pass is False
        assert row.mode_passed("bare") is False
        assert row.mode_passed("proxy-only") is True
        assert row.mode_passed("full") is True


class TestBuildComparison:
    def test_builds_from_three_modes(self):
        results_by_mode = {
            "bare": [
                _make_result("s1", "benign", "allowed", "allowed"),
                _make_result("s2", "injection", "blocked", "allowed"),
            ],
            "proxy-only": [
                _make_result("s1", "benign", "allowed", "allowed"),
                _make_result("s2", "injection", "blocked", "blocked"),
            ],
            "full": [
                _make_result("s1", "benign", "allowed", "allowed"),
                _make_result("s2", "injection", "blocked", "blocked"),
            ],
        }

        summary = build_comparison(results_by_mode)

        assert summary.total_scenarios == 2
        assert summary.per_mode_pass["bare"] == 1
        assert summary.per_mode_pass["proxy-only"] == 2
        assert summary.per_mode_pass["full"] == 2

    def test_rates(self):
        results_by_mode = {
            "bare": [_make_result("s1", "benign", "allowed", "allowed")],
            "proxy-only": [_make_result("s1", "benign", "allowed", "allowed")],
            "full": [_make_result("s1", "benign", "allowed", "allowed")],
        }

        summary = build_comparison(results_by_mode)
        rates = summary.per_mode_rate
        assert rates["bare"] == 100.0
        assert rates["full"] == 100.0

    def test_empty_results(self):
        summary = build_comparison({})
        assert summary.total_scenarios == 0


class TestPrintComparison:
    def test_does_not_crash(self, capsys):
        rows = [
            ComparisonRow(
                scenario_id="s1", category="benign", expected="allowed",
                results={"bare": "allowed", "proxy-only": "allowed", "full": "allowed"},
            ),
            ComparisonRow(
                scenario_id="s2", category="injection", expected="blocked",
                results={"bare": "allowed", "proxy-only": "blocked", "full": "blocked"},
            ),
        ]
        summary = ComparisonSummary(
            rows=rows,
            per_mode_pass={"bare": 1, "proxy-only": 2, "full": 2},
            per_mode_total={"bare": 2, "proxy-only": 2, "full": 2},
            total_scenarios=2,
        )
        print_comparison(summary)


class TestSaveComparison:
    def test_saves_json(self):
        rows = [
            ComparisonRow(
                scenario_id="s1", category="benign", expected="allowed",
                results={"bare": "allowed", "proxy-only": "allowed", "full": "allowed"},
            ),
        ]
        summary = ComparisonSummary(
            rows=rows,
            per_mode_pass={"bare": 1, "proxy-only": 1, "full": 1},
            per_mode_total={"bare": 1, "proxy-only": 1, "full": 1},
            total_scenarios=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            save_comparison(summary, path)

            assert path.exists()
            data = json.loads(path.read_text())
            assert data["total_scenarios"] == 1
            assert len(data["rows"]) == 1
            assert data["rows"][0]["scenario_id"] == "s1"
            assert data["per_mode_rate"]["bare"] == 100.0
