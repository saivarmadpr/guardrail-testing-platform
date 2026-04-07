"""Tests for resolve_mode() and the three guardrail modes."""

import os
from unittest.mock import patch

import pytest

from guardrail_tester.agent.runtime import resolve_mode, VALID_MODES


SAMPLE_CONFIG = {
    "llm": {
        "base_url": "http://localhost:4000/v1",
        "api_key": "sk-1234",
    },
    "shield": {"enabled": True},
}


class TestResolveModeBare:
    def test_uses_openai_direct(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key"}):
            result = resolve_mode("bare", SAMPLE_CONFIG)
        assert result["base_url"] == "https://api.openai.com/v1"
        assert result["api_key"] == "sk-real-key"
        assert result["shield_enabled"] is False

    def test_missing_openai_key_returns_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            result = resolve_mode("bare", SAMPLE_CONFIG)
        assert result["api_key"] == ""
        assert result["shield_enabled"] is False


class TestResolveModeProxyOnly:
    def test_uses_proxy_url(self):
        result = resolve_mode("proxy-only", SAMPLE_CONFIG)
        assert result["base_url"] == "http://localhost:4000/v1"
        assert result["api_key"] == "sk-1234"
        assert result["shield_enabled"] is False

    def test_defaults_when_no_llm_config(self):
        result = resolve_mode("proxy-only", {})
        assert result["base_url"] == "http://localhost:4000/v1"
        assert result["api_key"] == "sk-1234"


class TestResolveModeFull:
    def test_uses_proxy_url_with_shield(self):
        result = resolve_mode("full", SAMPLE_CONFIG)
        assert result["base_url"] == "http://localhost:4000/v1"
        assert result["api_key"] == "sk-1234"
        assert result["shield_enabled"] is True

    def test_defaults_when_no_llm_config(self):
        result = resolve_mode("full", {})
        assert result["shield_enabled"] is True


class TestInvalidMode:
    def test_raises_on_unknown_mode(self):
        with pytest.raises(ValueError, match="Invalid mode"):
            resolve_mode("turbo", SAMPLE_CONFIG)


class TestValidModes:
    def test_all_valid_modes_accepted(self):
        for mode in VALID_MODES:
            result = resolve_mode(mode, SAMPLE_CONFIG)
            assert "base_url" in result
            assert "api_key" in result
            assert "shield_enabled" in result
