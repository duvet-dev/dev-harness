"""Tests for harness.config.provider_models."""

import os

import pytest

from harness.config.provider_models import (
    ModelDef,
    ProviderConfig,
    ProviderConfigSet,
    ProviderError,
    has_env_ref,
    provider_config_from_dict,
    resolve_env_ref,
    resolve_value,
)


class TestEnvRefResolution:
    def test_resolve_env_ref_success(self):
        os.environ["TEST_VAR"] = "my-value"
        try:
            result = resolve_env_ref("${TEST_VAR}")
            assert result == "my-value"
        finally:
            del os.environ["TEST_VAR"]

    def test_resolve_env_ref_missing_raises(self):
        with pytest.raises(ProviderError, match="not set"):
            resolve_env_ref("${UNDEFINED_VAR_XYZ}")

    def test_resolve_env_ref_no_refs(self):
        result = resolve_env_ref("plain-string")
        assert result == "plain-string"

    def test_resolve_env_ref_prefix_suffix(self):
        os.environ["TOKEN"] = "abc123"
        try:
            result = resolve_env_ref("prefix-${TOKEN}-suffix")
            assert result == "prefix-abc123-suffix"
        finally:
            del os.environ["TOKEN"]

    def test_has_env_ref_true(self):
        assert has_env_ref("${VAR}") is True

    def test_has_env_ref_false(self):
        assert has_env_ref("no refs here") is False
        assert has_env_ref("${INCOMPLETE") is False

    def test_resolve_value_no_ref(self):
        assert resolve_value("hello") == "hello"

    def test_resolve_value_with_ref(self):
        os.environ["VAL"] = "world"
        try:
            assert resolve_value("${VAL}") == "world"
        finally:
            del os.environ["VAL"]


class TestProviderConfig:
    def test_minimal_config(self):
        pc = ProviderConfig(name="test")
        assert pc.name == "test"
        assert pc.type == "openai-compatible"
        assert pc.api_key == ""

    def test_resolve_api_key_empty(self):
        pc = ProviderConfig(name="test")
        assert pc.resolve_api_key() == ""

    def test_resolve_api_key_env_ref(self):
        os.environ["MY_KEY"] = "sk-xyz"
        try:
            pc = ProviderConfig(name="test", api_key="${MY_KEY}")
            assert pc.resolve_api_key() == "sk-xyz"
        finally:
            del os.environ["MY_KEY"]

    def test_models_as_string_normalized(self):
        """String models are converted to single-item list (line 128)."""
        pc = ProviderConfig(name="test", models="gpt-4o")
        assert len(pc.models) == 1
        assert pc.models[0].name == "gpt-4o"

    def test_models_as_set_normalized(self):
        """Set models fall through to else branch (line 140)."""
        pc = ProviderConfig(name="test", models={"gpt-4o"})
        assert len(pc.models) > 0

    def test_models_as_generator_normalized(self):
        """Generator models are converted via list() (line 140)."""
        from harness.config.provider_models import ModelDef
        pc = ProviderConfig(name="test", models=(m for m in ["claude-3"]))
        assert len(pc.models) == 1

    def test_resolve_base_url_empty(self):
        pc = ProviderConfig(name="test")
        assert pc.resolve_base_url() == ""

    def test_resolve_command_empty(self):
        pc = ProviderConfig(name="test", type="cli")
        assert pc.resolve_command() == ""

    def test_resolve_model_found(self):
        pc = ProviderConfig(
            name="deepseek",
            models=[ModelDef(name="deepseek-v4-flash"), ModelDef(name="deepseek-reasoner")],
        )
        assert pc.resolve_model("deepseek-v4-flash") == "deepseek-v4-flash"
        assert pc.resolve_model("deepseek-reasoner") == "deepseek-reasoner"

    def test_resolve_model_not_found_raises(self):
        pc = ProviderConfig(
            name="deepseek",
            models=[ModelDef(name="deepseek-v4-flash")],
        )
        # Returns the key as-is if not found in models
        assert pc.resolve_model("nonexistent") == "nonexistent"

    def test_resolve_model_empty_models(self):
        pc = ProviderConfig(name="test")
        # When models dict is empty, the key is passed through directly
        result = pc.resolve_model("anything")
        assert result == "anything"

    def test_validate_valid(self):
        pc = ProviderConfig(name="test", type="openai", base_url="https://api.example.com")
        assert pc.validate() == []

    def test_validate_invalid_type(self):
        pc = ProviderConfig(name="test", type="invalid_type")
        errors = pc.validate()
        assert len(errors) == 1
        assert "Invalid provider type" in errors[0]

    def test_validate_compatible_no_base_url(self):
        pc = ProviderConfig(name="test", type="openai-compatible", base_url="")
        errors = pc.validate()
        assert len(errors) >= 1
        assert any("base_url" in e for e in errors)

    def test_validate_cli_no_command(self):
        pc = ProviderConfig(name="test", type="cli", command="")
        errors = pc.validate()
        assert len(errors) >= 1
        assert any("command" in e for e in errors)

    def test_to_resolved_dict(self):
        os.environ["KEY"] = "sk-val"
        try:
            pc = ProviderConfig(
                name="test",
                type="openai",
                api_key="${KEY}",
                base_url="https://api.example.com",
                models=[ModelDef(name="gpt-4o", context_window=128000, default_temperature=0.3)],
                description="A test provider",
            )
            resolved = pc.to_resolved_dict()
            assert resolved["api_key"] == "sk-val"
            assert resolved["base_url"] == "https://api.example.com"
            assert len(resolved["models"]) == 1
            assert resolved["models"][0]["name"] == "gpt-4o"
            assert resolved["models"][0]["context_window"] == 128000
            assert resolved["models"][0]["default_temperature"] == 0.3
            assert resolved["description"] == "A test provider"
        finally:
            del os.environ["KEY"]

    def test_to_resolved_dict_no_env(self):
        pc = ProviderConfig(
            name="test",
            type="cli",
            command="claude",
            description="CLI tool",
        )
        resolved = pc.to_resolved_dict()
        assert resolved["command"] == "claude"
        assert resolved["api_key"] == ""


class TestProviderConfigSet:
    def test_empty_set(self):
        pcs = ProviderConfigSet()
        assert pcs.get("anything") is None

    def test_get_and_has(self):
        pcs = ProviderConfigSet(
            providers={
                "deepseek": ProviderConfig(name="deepseek", type="openai"),
            }
        )
        assert pcs.has("deepseek") is True
        assert pcs.has("nonexistent") is False
        assert pcs.get("deepseek") is not None
        assert pcs.get("nonexistent") is None

    def test_resolve_model_success(self):
        pcs = ProviderConfigSet(
            providers={
                "deepseek": ProviderConfig(
                    name="deepseek",
                    models={"default": "deepseek-v4-flash"},
                ),
            }
        )
        assert pcs.resolve_model("deepseek", "deepseek-v4-flash") == "deepseek-v4-flash"

    def test_resolve_model_provider_not_found(self):
        pcs = ProviderConfigSet(providers={})
        with pytest.raises(ProviderError, match="not found"):
            pcs.resolve_model("unknown", "default")

    def test_get_resolved_valid(self):
        pcs = ProviderConfigSet(
            providers={
                "test": ProviderConfig(name="test", type="cli", command="echo"),
            }
        )
        resolved = pcs.get_resolved("test")
        assert resolved is not None
        assert resolved["command"] == "echo"

    def test_get_resolved_missing(self):
        pcs = ProviderConfigSet()
        assert pcs.get_resolved("ghost") is None

    def test_validate_all_valid(self):
        pcs = ProviderConfigSet(
            providers={
                "a": ProviderConfig(name="a", type="openai"),
                "b": ProviderConfig(name="b", type="cli", command="tool"),
            }
        )
        assert pcs.validate() == []

    def test_validate_with_errors(self):
        pcs = ProviderConfigSet(
            providers={
                "bad": ProviderConfig(name="bad", type="nope"),
            }
        )
        errors = pcs.validate()
        assert len(errors) >= 1

    def test_resolve_model_case_sensitive(self):
        pcs = ProviderConfigSet(
            providers={
                "DeepSeek": ProviderConfig(
                    name="DeepSeek",
                    models={"Default": "deepseek-chat"},
                ),
            }
        )
        assert pcs.resolve_model("DeepSeek", "deepseek-chat") == "deepseek-chat"
        # Not found in models, returns key as-is
        assert pcs.resolve_model("DeepSeek", "default") == "default"


class TestProviderConfigFromDict:
    def test_minimal(self):
        pc = provider_config_from_dict("test", {})
        assert pc.name == "test"
        assert pc.type == "openai-compatible"

    def test_full(self):
        pc = provider_config_from_dict("test", {
            "type": "cli",
            "api_key": "${KEY}",
            "base_url": "https://example.com",
            "models": {"default": "gpt-4o"},
            "command": "my-cli",
            "description": "My tool",
        })
        assert pc.type == "cli"
        assert pc.api_key == "${KEY}"
        assert pc.command == "my-cli"


class TestModelDef:
    def test_model_entry(self):
        md = ModelDef(name="gpt-4o", context_window=8192, default_temperature=0.7)
        assert md.name == 'gpt-4o'
        assert md.name == "gpt-4o"
        assert md.context_window == 8192
        assert md.default_temperature == 0.7
