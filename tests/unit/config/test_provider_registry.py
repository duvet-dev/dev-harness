"""Tests for harness.config.provider_registry."""

import os
from pathlib import Path

import pytest
import yaml

from harness.config.provider_registry import (
    _extract_providers,
    _load_user_config,
    _load_yaml_config,
    _resolve_config_values,
    load_providers,
    merge_providers,
    resolve_env_refs_in_config,
)
from harness.config.provider_models import ProviderError


@pytest.fixture
def project_dir(tmp_path) -> Path:
    """Set up a project directory with a .harness/providers.yaml."""
    harness_dir = tmp_path / ".harness"
    harness_dir.mkdir(parents=True)
    providers_file = harness_dir / "providers.yaml"
    with open(providers_file, "w") as f:
        yaml.dump({
            "providers": {
                "deepseek": {
                    "type": "openai-compatible",
                    "api_key": "${DEEPSEEK_API_KEY}",
                    "base_url": "https://api.deepseek.com",
                    "models": {"default": "deepseek-v4-flash"},
                },
            },
        }, f)
    return tmp_path


class TestLoadYamlConfig:
    def test_load_existing(self, tmp_path):
        path = tmp_path / "test.yaml"
        with open(path, "w") as f:
            yaml.dump({"providers": {"a": {"type": "openai"}}}, f)
        result = _load_yaml_config(path)
        assert result == {"a": {"type": "openai"}}

    def test_load_missing(self, tmp_path):
        result = _load_yaml_config(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_malformed(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text(": broken yaml [")
        with pytest.raises(ProviderError, match="Failed to parse"):
            _load_yaml_config(path)

    def test_load_providers_not_a_dict(self, tmp_path):
        path = tmp_path / "bad.yaml"
        with open(path, "w") as f:
            yaml.dump({"providers": "not a dict"}, f)
        with pytest.raises(ProviderError, match="must be a mapping"):
            _load_yaml_config(path)


class TestMergeProviders:
    def test_base_only(self):
        base = {"a": {"type": "openai"}}
        merged = merge_providers(base, {})
        assert merged == base

    def test_override_only(self):
        merged = merge_providers({}, {"a": {"type": "cli"}})
        assert merged == {"a": {"type": "cli"}}

    def test_merge_override_wins(self):
        base = {"a": {"type": "openai", "base_url": "https://old.com"}}
        override = {"a": {"base_url": "https://new.com"}}
        merged = merge_providers(base, override)
        assert merged["a"]["type"] == "openai"
        assert merged["a"]["base_url"] == "https://new.com"

    def test_merge_new_providers(self):
        base = {"a": {"type": "openai"}}
        override = {"b": {"type": "cli"}}
        merged = merge_providers(base, override)
        assert "a" in merged
        assert "b" in merged

    def test_merge_does_not_mutate_base(self):
        base = {"a": {"type": "openai"}}
        original = dict(base)
        merge_providers(base, {"a": {"type": "cli"}})
        assert base == original


class TestResolveEnvRefsInConfig:
    def test_resolve_strings(self):
        os.environ["MY_VAR"] = "resolved"
        try:
            data = {"a": {"api_key": "${MY_VAR}"}}
            resolved = resolve_env_refs_in_config(data)
            assert resolved["a"]["api_key"] == "resolved"
        finally:
            del os.environ["MY_VAR"]

    def test_resolve_nested_dicts(self):
        os.environ["NESTED_VAR"] = "nested-val"
        try:
            data = {"a": {"nested": {"key": "${NESTED_VAR}"}}}
            resolved = resolve_env_refs_in_config(data)
            assert resolved["a"]["nested"]["key"] == "nested-val"
        finally:
            del os.environ["NESTED_VAR"]

    def test_resolve_lists(self):
        os.environ["ITEM"] = "list-item"
        try:
            data = {"a": {"items": ["${ITEM}", "plain"]}}
            resolved = resolve_env_refs_in_config(data)
            assert resolved["a"]["items"] == ["list-item", "plain"]
        finally:
            del os.environ["ITEM"]

    def test_resolve_non_string(self):
        data = {"a": {"count": 42, "enabled": True}}
        resolved = resolve_env_refs_in_config(data)
        assert resolved["a"]["count"] == 42
        assert resolved["a"]["enabled"] is True


class TestLoadProviders:
    def test_load_success(self, project_dir):
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        try:
            result = load_providers(project_dir)
            assert result.has("deepseek") is True
            provider = result.get("deepseek")
            assert provider is not None
            assert provider.type == "openai-compatible"
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_load_missing_env_var_raises(self, project_dir):
        with pytest.raises(ProviderError, match="not set"):
            load_providers(project_dir)

    def test_load_no_providers_file(self, tmp_path):
        result = load_providers(tmp_path)
        assert result.has("anything") is False
        assert result.validate() == []

    def test_load_with_user_config(self, project_dir):
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        try:
            # Create a user config with an override
            user_file = project_dir / "user-providers.yaml"
            with open(user_file, "w") as f:
                yaml.dump({
                    "providers": {
                        "deepseek": {
                            "base_url": "https://override.deepseek.com",
                        },
                    },
                }, f)

            result = load_providers(project_dir, user_config_path=user_file)
            provider = result.get("deepseek")
            assert provider is not None
            assert provider.base_url == "https://override.deepseek.com"
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_load_with_env_override_path(self, project_dir):
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        os.environ["HARNESS_PROVIDERS_PATH"] = str(
            project_dir / "custom-path.yaml"
        )
        try:
            # Create the custom path
            with open(project_dir / "custom-path.yaml", "w") as f:
                yaml.dump({
                    "providers": {
                        "custom": {"type": "cli", "command": "tool"},
                    },
                }, f)

            result = load_providers(project_dir)
            assert result.has("custom") is True
        finally:
            del os.environ["DEEPSEEK_API_KEY"]
            del os.environ["HARNESS_PROVIDERS_PATH"]

    def test_load_skips_invalid_providers(self, project_dir):
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        try:
            # Add an invalid provider entry (non-dict)
            providers_file = project_dir / ".harness" / "providers.yaml"
            with open(providers_file) as f:
                data = yaml.safe_load(f)
            data["providers"]["invalid"] = "not a dict"
            with open(providers_file, "w") as f:
                yaml.dump(data, f)

            result = load_providers(project_dir)
            # Should skip the invalid provider
            assert result.has("invalid") is False
            assert result.has("deepseek") is True
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_load_validates_merged_config(self, project_dir):
        """Invalid merged config should raise ProviderError."""
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        try:
            providers_file = project_dir / ".harness" / "providers.yaml"
            with open(providers_file) as f:
                data = yaml.safe_load(f)
            # Add an invalid provider type
            data["providers"]["bad"] = {"type": "invalid_type"}
            with open(providers_file, "w") as f:
                yaml.dump(data, f)

            with pytest.raises(ProviderError, match="invalid"):
                load_providers(project_dir)
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_load_resolve_env_true_checks_missing_vars(self, project_dir):
        """When resolve_env=True, missing env vars should raise eagerly."""
        with pytest.raises(ProviderError):
            load_providers(project_dir, resolve_env=True)


class TestLoadUserConfig:
    def test_user_config_via_param(self, tmp_path):
        path = tmp_path / "user.yaml"
        with open(path, "w") as f:
            yaml.dump({"providers": {"a": {"type": "openai"}}}, f)
        result = _load_user_config(path)
        assert "a" in result

    def test_user_config_via_env_var(self, tmp_path):
        path = tmp_path / "env-path.yaml"
        with open(path, "w") as f:
            yaml.dump({"providers": {"b": {"type": "cli"}}}, f)
        os.environ["HARNESS_PROVIDERS_PATH"] = str(path)
        try:
            result = _load_user_config(None)
            assert "b" in result
        finally:
            del os.environ["HARNESS_PROVIDERS_PATH"]

    def test_user_config_default_missing(self, tmp_path):
        result = _load_user_config(None)
        assert result == {}


class TestExtractProviders:
    def test_valid(self):
        result = _extract_providers({"a": {"type": "openai"}})
        assert result == {"a": {"type": "openai"}}

    def test_skips_non_dict(self):
        result = _extract_providers({
            "a": {"type": "openai"},
            "b": "not a dict",
        })
        assert "a" in result
        assert "b" not in result
