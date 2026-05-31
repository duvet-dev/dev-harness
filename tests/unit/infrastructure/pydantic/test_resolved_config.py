"""Tests for infrastructure/pydantic/resolved_config.py."""

from __future__ import annotations

import pytest

from harness.infrastructure.pydantic.resolved_config import ResolvedConfig


class TestResolvedConfig:
    def test_defaults(self):
        rc = ResolvedConfig()
        assert rc.api_key == ""
        assert rc.base_url == ""
        assert rc.model == ""
        assert rc.provider == ""
        assert rc.command == ""
        assert rc.timeout_seconds == 600
        assert rc.api_key_env == ""

    def test_typed_fields(self):
        rc = ResolvedConfig(
            api_key="sk-123",
            base_url="https://api.example.com",
            model="gpt-4o",
            provider="openai",
            command="python3 run.py",
            timeout_seconds=120,
            api_key_env="OPENAI_API_KEY",
        )
        assert rc.api_key == "sk-123"
        assert rc.base_url == "https://api.example.com"
        assert rc.model == "gpt-4o"
        assert rc.provider == "openai"
        assert rc.command == "python3 run.py"
        assert rc.timeout_seconds == 120
        assert rc.api_key_env == "OPENAI_API_KEY"

    def test_extra_fields_allowed(self):
        rc = ResolvedConfig(model="test", custom_field="custom_value")
        assert rc.model_extra == {"custom_field": "custom_value"}

    def test_getitem_returns_attr(self):
        rc = ResolvedConfig(model="deepseek-v4")
        assert rc["model"] == "deepseek-v4"

    def test_getitem_returns_empty_for_missing(self):
        rc = ResolvedConfig()
        assert rc["nonexistent"] == ""

    def test_get_method(self):
        rc = ResolvedConfig(api_key="key-1")
        assert rc.get("api_key") == "key-1"
        assert rc.get("model") == ""
        assert rc.get("nonexistent") is None
        assert rc.get("nope", "fallback") == "fallback"

    def test_contains(self):
        rc = ResolvedConfig(model="gpt-4")
        assert "model" in rc
        assert "api_key" in rc  # has attr with default
        assert "nonexistent_attr" not in rc

    def test_as_dict(self):
        rc = ResolvedConfig(model="gpt-4", provider="openai")
        d = rc.as_dict()
        assert isinstance(d, dict)
        assert d["model"] == "gpt-4"
        assert d["provider"] == "openai"
        assert d["api_key"] == ""

    def test_timeout_default(self):
        rc = ResolvedConfig()
        assert rc.timeout_seconds == 600

    def test_timeout_custom(self):
        rc = ResolvedConfig(timeout_seconds=300)
        assert rc.timeout_seconds == 300
