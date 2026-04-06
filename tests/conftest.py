"""Shared fixtures for guardrail testing platform tests."""

import pytest

from guardrail_tester.guardrails.base import (
    Guardrail,
    GuardrailAction,
    GuardrailContext,
    GuardrailLayer,
    GuardrailRegistry,
    GuardrailResult,
)
from guardrail_tester.guardrails.engine import GuardrailEngine
from guardrail_tester.logging.structured import init_logger


@pytest.fixture
def registry():
    return GuardrailRegistry()


@pytest.fixture
def engine(registry):
    return GuardrailEngine(registry)


@pytest.fixture
def logger(tmp_path):
    return init_logger(log_dir=tmp_path, run_id="test_run")


class AlwaysPassGuardrail(Guardrail):
    async def check(self, context: GuardrailContext) -> GuardrailResult:
        return GuardrailResult(
            guardrail_name=self.name,
            passed=True,
            action=GuardrailAction.LOG,
            message="Passed",
        )


class AlwaysBlockGuardrail(Guardrail):
    async def check(self, context: GuardrailContext) -> GuardrailResult:
        return GuardrailResult(
            guardrail_name=self.name,
            passed=False,
            action=self.default_action,
            message="Blocked by test guardrail",
        )


class PIIDetectorGuardrail(Guardrail):
    """Detects SSN patterns in content."""

    async def check(self, context: GuardrailContext) -> GuardrailResult:
        import re
        ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        if ssn_pattern.search(context.content):
            return GuardrailResult(
                guardrail_name=self.name,
                passed=False,
                action=self.default_action,
                message="SSN detected in content",
                details={"pattern": "ssn"},
            )
        return GuardrailResult(
            guardrail_name=self.name,
            passed=True,
            action=GuardrailAction.LOG,
            message="No PII detected",
        )
