"""Tests for env var resolution in agent runtime."""

import os
from unittest.mock import patch

from guardrail_tester.agent.runtime import _resolve_env


class TestResolveEnv:
    def test_expands_existing_env_var(self):
        with patch.dict(os.environ, {"MY_KEY": "secret123"}):
            assert _resolve_env("${MY_KEY}") == "secret123"

    def test_preserves_literal_when_var_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_env("${NONEXISTENT_VAR}") == "${NONEXISTENT_VAR}"

    def test_mixed_text_and_var(self):
        with patch.dict(os.environ, {"HOST": "example.com"}):
            assert _resolve_env("https://${HOST}/api") == "https://example.com/api"

    def test_multiple_vars(self):
        with patch.dict(os.environ, {"PROTO": "https", "HOST": "api.test.com"}):
            assert _resolve_env("${PROTO}://${HOST}") == "https://api.test.com"

    def test_no_vars_returns_unchanged(self):
        assert _resolve_env("plain-string") == "plain-string"

    def test_non_string_passthrough(self):
        assert _resolve_env(42) == 42
