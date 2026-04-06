"""Tests for the adversarial prompt generator and regression suite."""

import pytest

from guardrail_tester.eval.adversarial import AdversarialGenerator
from guardrail_tester.eval.regression import get_regression_cases, REGRESSION_CASES


class TestAdversarialGenerator:
    def test_generate_injection_prompts(self):
        gen = AdversarialGenerator(seed=42)
        prompts = gen.generate_injection_prompts(5)
        assert len(prompts) == 5
        assert all(p.category == "injection" for p in prompts)
        assert all(p.expected_outcome == "blocked" for p in prompts)

    def test_generate_pii_exfil_prompts(self):
        gen = AdversarialGenerator(seed=42)
        prompts = gen.generate_pii_exfil_prompts(5)
        assert len(prompts) == 5
        assert all(p.category == "pii_exfiltration" for p in prompts)

    def test_generate_tool_misuse_prompts(self):
        gen = AdversarialGenerator(seed=42)
        prompts = gen.generate_tool_misuse_prompts(5)
        assert len(prompts) == 5
        assert all(p.category == "tool_misuse" for p in prompts)

    def test_generate_encoding_bypass(self):
        gen = AdversarialGenerator(seed=42)
        prompts = gen.generate_encoding_bypass_prompts(3)
        assert len(prompts) == 3
        assert all("encoding_bypass" in p.technique for p in prompts)

    def test_generate_multi_step_attack(self):
        gen = AdversarialGenerator(seed=42)
        steps = gen.generate_multi_step_attack()
        assert len(steps) == 3
        assert steps[0].expected_outcome == "allowed"
        assert steps[-1].expected_outcome == "blocked"

    def test_generate_all(self):
        gen = AdversarialGenerator(seed=42)
        prompts = gen.generate_all(per_category=3)
        assert len(prompts) >= 10
        categories = {p.category for p in prompts}
        assert "injection" in categories
        assert "pii_exfiltration" in categories
        assert "tool_misuse" in categories

    def test_deterministic_with_seed(self):
        gen1 = AdversarialGenerator(seed=123)
        gen2 = AdversarialGenerator(seed=123)
        p1 = gen1.generate_injection_prompts(3)
        p2 = gen2.generate_injection_prompts(3)
        assert [p.prompt for p in p1] == [p.prompt for p in p2]


class TestRegressionCases:
    def test_all_cases_have_required_fields(self):
        for case in REGRESSION_CASES:
            assert case.id
            assert case.prompt
            assert case.description

    def test_filter_by_tags(self):
        benign = get_regression_cases(tags=["benign"])
        assert len(benign) >= 5
        assert all(case.must_allow for case in benign)

    def test_no_filter_returns_all(self):
        cases = get_regression_cases()
        assert len(cases) == len(REGRESSION_CASES)
